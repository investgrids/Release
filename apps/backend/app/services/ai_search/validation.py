"""
Deterministic post-response validation layer — no LLM calls, ever. Runs
after every specialist response, before it's returned to the pipeline.

Each check has a defined repair-or-omit behavior (never a hard failure of
the whole response — a bad sub-field degrades gracefully, matching the
"every section must degrade gracefully if evidence is unavailable" rule).
See the plan's §5 table for the full checklist this implements.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.ai_search.schema import VERDICT_SCALE
from app.services.ai_search.timeline_checks import (
    check_near_duplicate_entries,
    check_numeric_range_contradiction,
    check_verdict_tense_contradiction,
    tone as _tone,
)

# Nominal (lo_days, hi_days) window for each of V3's 5 fixed
# timeline_intelligence keys — used by check_numeric_range_contradiction to
# catch e.g. a "one_week" entry whose own text says "3-6 months".
_HORIZON_DAYS = {
    "immediate": (0, 1),
    "one_week": (1, 7),
    "one_to_three_months": (30, 90),
    "six_to_twelve_months": (180, 365),
    "one_to_three_years": (365, 1095),
}
_HORIZON_ORDER = list(_HORIZON_DAYS.keys())


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


def _narrative_company_mentions(text: str) -> dict[str, str]:
    """Real, listed NSE companies whose name/alias appears as a whole word
    in `text` — reuses the same known-universe list _verify_companies_exist
    already trusts, rather than any new NLP. Returns {symbol: matched_name}.
    Whole-word matching only (not substring) to avoid the obvious false
    positive class — a short alias like "it" or "hal" (as a word, not the
    company) appearing inside unrelated text."""
    from app.api.companies import _NSE_UNIVERSE
    t = (text or "").lower()
    if not t:
        return {}
    found: dict[str, str] = {}
    for c in _NSE_UNIVERSE:
        candidates = [c["name"].lower()] + [a.lower() for a in c.get("aliases", [])]
        for cand in candidates:
            if len(cand) < 3:
                continue  # too short to whole-word-match reliably (e.g. "it", "lt")
            if re.search(rf"\b{re.escape(cand)}\b", t):
                found[c["symbol"]] = c["name"]
                break
    return found


def _check_companies_narrative_consistency(out: dict, report: ValidationReport) -> None:
    """The same 'two things computed independently, never cross-checked'
    pattern as the confidence bug, applied to companies — verified live on
    a defense-budget report: the summary named HAL, BEL, AND L&T, but the
    structured companies[] list only had HAL and BEL. Detection only (never
    silently fabricates a full company entry with a guessed impact score/
    reason for a name the model didn't structurally analyze, and never
    edits the narrative text) — flagged so it's visible to the benchmark
    runner/transparency panel rather than silently shipped inconsistent."""
    companies = out.get("companies")
    if not isinstance(companies, list):
        return
    listed_symbols = {(c.get("symbol") or "").upper() for c in companies if isinstance(c, dict)}
    narrative = f"{out.get('summary', '')} {out.get('bottom_line', '')}"
    mentioned = _narrative_company_mentions(narrative)
    missing = {sym: name for sym, name in mentioned.items() if sym not in listed_symbols}
    if missing:
        names = ", ".join(f"{name} ({sym})" for sym, name in missing.items())
        report.omissions.append(
            f"companies: narrative names {names} but the structured companies list omits {'it' if len(missing) == 1 else 'them'}"
        )


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
    try:
        _check_companies_narrative_consistency(out, report)
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
    """Cheap heuristics, deliberately conservative — only flag the clearest
    cases to avoid false positives on genuinely nuanced theses (e.g.
    near-term-pain/long-term-gain). Four checks, in order:
    1. immediate-term and 1-3yr framing shouldn't flatly contradict each
       other in sentiment word choice with no bridging medium-term text.
    2. no single entry's tone should flatly contradict the OVERALL verdict
       direction either — (1) alone missed this: a negative "immediate"
       entry under a bullish/Strong Positive verdict, with nothing
       upstream or downstream ever comparing the two (verified live, the
       RBI banking-stocks report).
    3. no entry should state a timeframe inside its own text that falls
       outside its own horizon label (verified live, defense-budget
       report: a "one_to_three_months"-labeled entry's own sentence said
       "next 3-6 months").
    4. no two entries should be near-verbatim restatements of each other
       (verified live, same report: 'immediate' and 'one_week' nearly
       word-for-word identical)."""
    ti = out.get("timeline_intelligence")
    if not isinstance(ti, dict) or not ti:
        return

    immediate = _tone(ti.get("immediate", ""))
    long_term = _tone(ti.get("one_to_three_years", ""))
    if immediate and long_term and immediate != long_term and not ti.get("one_to_three_months") and not ti.get("six_to_twelve_months"):
        # Flatly opposite immediate vs long-term tone with no bridging
        # medium-term text to explain the transition — likely inconsistent.
        out["timeline_intelligence"] = {}
        report.omissions.append("timeline_intelligence: immediate/long-term tone contradicted with no bridging medium-term explanation")
        return  # already wiped everything — nothing left for the checks below to examine

    entries = [(k, ti.get(k, "")) for k in _HORIZON_ORDER if ti.get(k)]

    verdict = out.get("investment_verdict") or {}
    tense_flags = check_verdict_tense_contradiction(entries, verdict.get("direction", "neutral"))
    for label in tense_flags:
        ti[label] = ""
    if tense_flags:
        report.omissions.append(
            f"timeline_intelligence: {', '.join(tense_flags)} tone contradicted the overall verdict direction — omitted"
        )

    numeric_flags = check_numeric_range_contradiction(entries, _HORIZON_DAYS)
    for label in numeric_flags:
        ti[label] = ""
    if numeric_flags:
        report.omissions.append(
            f"timeline_intelligence: {', '.join(numeric_flags)} stated a timeframe outside its own horizon — omitted"
        )

    dup_pairs = check_near_duplicate_entries(entries)
    if dup_pairs:
        collapsed = set()
        for label_a, label_b in dup_pairs:
            if label_b not in collapsed:
                ti[label_b] = ""
                collapsed.add(label_b)
        report.repairs.append(
            f"timeline_intelligence: near-duplicate entries collapsed ({', '.join(f'{a}~{b}' for a, b in dup_pairs)})"
        )


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
    from app.services.ai_search.regexes import _OUTLOOK_LABELS

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
