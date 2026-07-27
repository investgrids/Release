"""
Deterministic post-response validation layer — no LLM calls, ever. Runs
after every specialist response, before it's returned to the pipeline.

Each check has a defined repair-or-omit behavior (never a hard failure of
the whole response — a bad sub-field degrades gracefully, matching the
"every section must degrade gracefully if evidence is unavailable" rule).
See the plan's §5 table for the full checklist this implements.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.ai_search.schema import VERDICT_SCALE


@dataclass
class ValidationReport:
    """What the validator actually did — surfaced to the benchmark runner
    (contradiction_flag, repairs_applied) and optionally to the UI/transparency
    panel, never hidden."""
    repairs: list[str] = field(default_factory=list)
    omissions: list[str] = field(default_factory=list)
    contradiction_flagged: bool = False

    @property
    def clean(self) -> bool:
        return not self.repairs and not self.omissions


def _direction_to_verdict_scale(direction: str, confidence: float | None) -> str:
    conf = confidence if confidence is not None else 50
    direction = (direction or "neutral").lower()
    if direction == "bullish":
        return "Strong Positive" if conf >= 80 else "Positive"
    if direction == "bearish":
        return "Strong Negative" if conf >= 80 else "Negative"
    return "Cautious" if conf < 40 else "Neutral"


def _known_symbols() -> set[str]:
    from app.api.companies import _NSE_UNIVERSE
    return {c["symbol"] for c in _NSE_UNIVERSE}


def validate_and_repair(parsed: dict) -> tuple[dict, ValidationReport]:
    """Mutates a shallow-copied version of `parsed` in place per the repair
    rules and returns (repaired_dict, report). Never raises — a bug in this
    function must not take down the whole response; anything unexpected is
    left alone rather than crashing the pipeline."""
    report = ValidationReport()
    out = dict(parsed)

    try:
        _check_verdict_consistency(out, report)
    except Exception:
        pass
    try:
        _check_scenario_probabilities(out, report)
    except Exception:
        pass
    try:
        _dedupe_companies(out, report)
    except Exception:
        pass
    try:
        _clamp_confidence_values(out, report)
    except Exception:
        pass
    try:
        _check_timeline_consistency(out, report)
    except Exception:
        pass
    try:
        _verify_companies_exist(out, report)
    except Exception:
        pass
    try:
        _check_contradictions(out, report)
    except Exception:
        pass

    return out, report


def _check_verdict_consistency(out: dict, report: ValidationReport) -> None:
    """decision_engine_v2.verdict_scale must be one of the real 6 values AND
    must agree in direction with investment_verdict.direction — the model
    demonstrably confuses this with investment_verdict.rating's own 8-value
    enum in practice (verified live), so this repair is load-bearing, not
    a theoretical edge case."""
    dev2 = out.get("decision_engine_v2")
    verdict = out.get("investment_verdict") or {}
    if not isinstance(dev2, dict):
        return
    scale = dev2.get("verdict_scale")
    direction = verdict.get("direction", "neutral")
    confidence = verdict.get("confidence")
    if scale not in VERDICT_SCALE:
        dev2["verdict_scale"] = _direction_to_verdict_scale(direction, confidence)
        report.repairs.append(f"decision_engine_v2.verdict_scale: '{scale}' is not a valid value — recomputed from investment_verdict.direction/confidence")
        return
    # Even a validly-worded scale can point the wrong direction relative to
    # investment_verdict — e.g. "Positive" alongside direction=bearish.
    positive = {"Strong Positive", "Positive"}
    negative = {"Strong Negative", "Negative"}
    mismatched = (
        (scale in positive and direction == "bearish")
        or (scale in negative and direction == "bullish")
    )
    if mismatched:
        dev2["verdict_scale"] = _direction_to_verdict_scale(direction, confidence)
        report.repairs.append(f"decision_engine_v2.verdict_scale ('{scale}') disagreed with investment_verdict.direction ('{direction}') — recomputed")


def _check_scenario_probabilities(out: dict, report: ValidationReport) -> None:
    scenarios = out.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        return
    keys = [k for k in ("bull", "base", "bear") if isinstance(scenarios.get(k), dict)]
    if len(keys) < 3:
        # Incomplete scenario set — not worth trying to renormalize a
        # partial structure; omit rather than present a misleading 2-case split.
        out["scenarios"] = {}
        report.omissions.append("scenarios: fewer than 3 of bull/base/bear present")
        return
    total = sum(float(scenarios[k].get("probability", 0) or 0) for k in keys)
    if total <= 0:
        out["scenarios"] = {}
        report.omissions.append("scenarios: all probabilities were zero/missing")
        return
    if total != 100:
        # Round the first two independently, then force the last one to
        # make up the exact remainder — three independent `round()` calls
        # can under/overshoot 100 by a point or two (e.g. 40/40/40 -> 33+33+33
        # = 99), which would just recreate the exact bug this repair exists
        # to fix.
        running = 0
        for k in keys[:-1]:
            raw = float(scenarios[k].get("probability", 0) or 0)
            scenarios[k]["probability"] = round(raw / total * 100)
            running += scenarios[k]["probability"]
        scenarios[keys[-1]]["probability"] = 100 - running
        report.repairs.append(f"scenarios probabilities summed to {total:.0f}, renormalized to 100")


def _dedupe_companies(out: dict, report: ValidationReport) -> None:
    companies = out.get("companies")
    if not isinstance(companies, list) or not companies:
        return
    best_by_symbol: dict[str, dict] = {}
    order: list[str] = []
    for c in companies:
        if not isinstance(c, dict):
            continue
        sym = (c.get("symbol") or "").upper()
        if not sym:
            continue
        if sym not in best_by_symbol:
            order.append(sym)
            best_by_symbol[sym] = c
        elif float(c.get("impact_score", 0) or 0) > float(best_by_symbol[sym].get("impact_score", 0) or 0):
            best_by_symbol[sym] = c
    if len(order) < len(companies):
        out["companies"] = [best_by_symbol[s] for s in order]
        report.repairs.append(f"companies: deduped {len(companies)} -> {len(order)} entries")


def _clamp_confidence_values(out: dict, report: ValidationReport) -> None:
    clamped = 0

    def _clamp(d: dict, key: str) -> None:
        nonlocal clamped
        v = d.get(key)
        if isinstance(v, (int, float)) and not (0 <= v <= 100):
            d[key] = max(0, min(100, v))
            clamped += 1

    _clamp(out, "confidence")
    verdict = out.get("investment_verdict")
    if isinstance(verdict, dict):
        _clamp(verdict, "confidence")
        _clamp(verdict, "opportunity_score")
    for c in out.get("companies") or []:
        if isinstance(c, dict):
            _clamp(c, "confidence")
            _clamp(c, "impact_score")
    for s in out.get("sectors") or []:
        if isinstance(s, dict):
            _clamp(s, "confidence")
            _clamp(s, "score")
    scenarios = out.get("scenarios") or {}
    for k in ("bull", "base", "bear"):
        if isinstance(scenarios.get(k), dict):
            _clamp(scenarios[k], "confidence")
    if clamped:
        report.repairs.append(f"clamped {clamped} out-of-range confidence/score value(s) to [0,100]")


def _check_timeline_consistency(out: dict, report: ValidationReport) -> None:
    """Cheap heuristic: immediate-term and 1-3yr framing shouldn't flatly
    contradict each other in sentiment word choice (e.g. immediate says
    "sharp decline" while long-term says "strong rally" with no bridging
    explanation). Not a deep semantic check — deliberately conservative,
    only flags the clearest cases to avoid false positives on genuinely
    nuanced near-term-pain/long-term-gain theses."""
    ti = out.get("timeline_intelligence")
    if not isinstance(ti, dict) or not ti:
        return
    _NEGATIVE_WORDS = {"decline", "crash", "fall", "drop", "weak", "bearish", "sell-off", "selloff"}
    _POSITIVE_WORDS = {"rally", "surge", "strong growth", "bullish", "outperform", "breakout"}

    def _tone(text: str) -> str | None:
        t = (text or "").lower()
        neg = any(w in t for w in _NEGATIVE_WORDS)
        pos = any(w in t for w in _POSITIVE_WORDS)
        if neg and not pos:
            return "negative"
        if pos and not neg:
            return "positive"
        return None

    immediate = _tone(ti.get("immediate", ""))
    long_term = _tone(ti.get("one_to_three_years", ""))
    if immediate and long_term and immediate != long_term and not ti.get("one_to_three_months") and not ti.get("six_to_twelve_months"):
        # Flatly opposite immediate vs long-term tone with no bridging
        # medium-term text to explain the transition — likely inconsistent.
        out["timeline_intelligence"] = {}
        report.omissions.append("timeline_intelligence: immediate/long-term tone contradicted with no bridging medium-term explanation")


def _verify_companies_exist(out: dict, report: ValidationReport) -> None:
    """Never let a fabricated ticker through — companies[] and
    investment_verdict.top_picks must both be real, listed NSE symbols."""
    known = _known_symbols()
    companies = out.get("companies")
    if isinstance(companies, list):
        real = [c for c in companies if isinstance(c, dict) and (c.get("symbol") or "").upper() in known]
        if len(real) < len(companies):
            dropped = len(companies) - len(real)
            out["companies"] = real
            report.repairs.append(f"companies: dropped {dropped} entr{'y' if dropped == 1 else 'ies'} with a symbol not in the real NSE universe")

    verdict = out.get("investment_verdict")
    if isinstance(verdict, dict) and isinstance(verdict.get("top_picks"), list):
        real_picks = [p for p in verdict["top_picks"] if str(p).upper() in known]
        if len(real_picks) < len(verdict["top_picks"]):
            verdict["top_picks"] = real_picks
            report.repairs.append("investment_verdict.top_picks: dropped fabricated/unrecognized ticker(s)")


def _check_contradictions(out: dict, report: ValidationReport) -> None:
    """The named failure mode: bullish sentiment + a heavily bearish scenario
    + a top-tier positive rating all coexisting. Downgrades toward neutral
    and adds a caveat rather than silently picking a side."""
    from app.services.ai_search_service import _OUTLOOK_LABELS

    verdict = out.get("investment_verdict") or {}
    sentiment = (out.get("sentiment") or "neutral").lower()
    scenarios = out.get("scenarios") or {}
    bear_prob = float((scenarios.get("bear") or {}).get("probability", 0) or 0)
    top_tier_positive = {"Strongly Constructive", "Constructive", "Positive Outlook"}
    rating = verdict.get("rating", "")

    contradiction = sentiment == "bullish" and bear_prob > 50 and rating in top_tier_positive
    if contradiction:
        report.contradiction_flagged = True
        # Downgrade one tier rather than flipping fully bearish — a >50%
        # bear scenario alongside genuine bullish evidence is a real
        # "elevated uncertainty" case, not proof the bull case is wrong.
        try:
            idx = _OUTLOOK_LABELS.index(rating)
            new_idx = min(idx + 2, len(_OUTLOOK_LABELS) - 1)
            verdict["rating"] = _OUTLOOK_LABELS[new_idx]
        except ValueError:
            verdict["rating"] = "Selectively Constructive"
        report.repairs.append(
            f"investment_verdict.rating downgraded from '{rating}' to '{verdict['rating']}' — "
            f"bullish sentiment coexisted with a {bear_prob:.0f}% bear scenario probability"
        )
        ai_conclusion = out.get("ai_conclusion")
        if isinstance(ai_conclusion, dict) and ai_conclusion.get("investor_action_note"):
            ai_conclusion["investor_action_note"] = None
            report.omissions.append("ai_conclusion.investor_action_note omitted due to unresolved contradiction")
