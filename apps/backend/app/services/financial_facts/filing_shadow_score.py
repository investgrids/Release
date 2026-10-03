"""
Local shadow scoring for the filing-backed method. Not wired into the live scorer or any scheduler.

SCORING_VERSION = "NSE_FILING_SCORE_V2" (metrics contract: NSE_FILING_METRICS_V1)
Two methodology changes versus the first shadow runs, both of which can move scores:
  1. TIE-SAFE PERCENTILES. Equal values get the same percentile (mid-rank: the average of the ranks they occupy), independent of
     peer order. With no ties the result equals the live scorer's formula (n-1-rank)/(n-1)*100. The live function ranks equal values
     by sort order, so they received different percentiles.
  2. PEER-ONLY VALUATION. Valuation = mean of the peer P/E and P/B percentiles (cheaper is better; BOTH required). The own-history
     component is removed: it compared filing-based current earnings with Yahoo diluted-EPS history and changed 123 rating bands.
Pillars and headline: financial strength = mean of the available metric percentiles (>= 4 of 6); valuation as above; market behaviour is the
stored snapshot pillar; headline = 8/15 FS + 4/15 valuation + 3/15 MB (exact fractions); overall coverage must be >= 65.
"""
from __future__ import annotations

from fractions import Fraction

SCORING_VERSION = "NSE_FILING_SCORE_V2"
HIGHER_IS_BETTER = {"revenue_growth": True, "profit_growth": True, "roe": True, "roce": True, "debt_to_equity": False, "interest_coverage": True}
MIN_METRICS = 4
MIN_COVERAGE = 65.0
# Only companies whose filing passed every gate set the peer benchmark: an earnings-quality review (exceptional gain, regulatory deferral,
# non-core profit) means that company's ratios are not acceptable score inputs, so they must not rank other companies either.
USABLE_STATUS = ("ok",)


def band(score: float) -> str:
    return "Strong" if score >= 75 else "Positive" if score >= 60 else "Neutral" if score >= 45 else "Cautious"


def percentile_rank(values: dict, symbol: str, cheaper_is_better: bool = False) -> float | None:
    """0-100, 100 = best. Mid-rank for ties; None when the symbol has no value or fewer than two peers have one."""
    vals = {k: v for k, v in values.items() if isinstance(v, (int, float)) and v == v and abs(v) != float("inf")}
    if symbol not in vals or len(vals) < 2:
        return None
    mine = vals[symbol]
    better = sum(1 for v in vals.values() if (v < mine if cheaper_is_better else v > mine))
    tied = sum(1 for v in vals.values() if v == mine)  # includes the symbol itself
    avg_rank = better + (tied - 1) / 2
    n = len(vals)
    return round((n - 1 - avg_rank) / (n - 1) * 100, 1)


def score_group(members: list[str], fm: dict, mb: dict, pool_statuses: tuple = USABLE_STATUS) -> dict:
    """fm: symbol -> FilingMetrics dict (status, metrics, valuation); mb: symbol -> stored market-behaviour pillar (or None).
    Returns symbol -> result with state 'scored' or 'withheld' and the exact reason."""
    usable = {s: f for s, f in fm.items() if s in members and f and f["status"] in pool_statuses}
    pct: dict[str, dict] = {}
    for m, hib in HIGHER_IS_BETTER.items():
        vals = {s: f["metrics"].get(m) for s, f in usable.items() if f["metrics"].get(m) is not None}
        pct[m] = {s: percentile_rank(vals, s, cheaper_is_better=not hib) for s in vals}
    pes = {s: f["valuation"].get("pe") for s, f in usable.items() if f["valuation"].get("pe") is not None}
    pbs = {s: f["valuation"].get("pb") for s, f in usable.items() if f["valuation"].get("pb") is not None}
    out = {}
    for s in members:
        f = fm.get(s)
        if f is None:
            out[s] = {"state": "withheld", "reason": "NO_FILING_RECORD"}; continue
        if f["status"] != "ok":
            out[s] = {"state": "withheld", "reason": f["status"]}; continue
        used = [m for m in HIGHER_IS_BETTER if pct[m].get(s) is not None]
        fs = round(sum(pct[m][s] for m in used) / len(used), 1) if used else None
        pe_p = percentile_rank(pes, s, True) if s in pes else None
        pb_p = percentile_rank(pbs, s, True) if s in pbs else None
        val = round((pe_p + pb_p) / 2, 1) if pe_p is not None and pb_p is not None else None
        r = {"fs": fs, "fs_n": len(used), "val": val, "val_parts": [k for k, v in (("pe", pe_p), ("pb", pb_p)) if v is not None], "mb": mb.get(s)}
        if len(used) < MIN_METRICS:
            r.update(state="withheld", reason="INSUFFICIENT_FINANCIAL_METRICS")
        elif val is None:
            only = "PE_ONLY" if pe_p is not None else "PB_ONLY" if pb_p is not None else "NONE"
            r.update(state="withheld", reason=f"VALUATION_NEEDS_TWO_COMPONENTS ({only})")
        elif mb.get(s) is None:
            r.update(state="withheld", reason="MARKET_BEHAVIOUR_MISSING")
        else:
            cov = (len(used) / 6 * 100) * 8 / 15 + 100 * 4 / 15 + 100 * 3 / 15
            if cov < MIN_COVERAGE:
                r.update(state="withheld", reason="INSUFFICIENT_OVERALL_COVERAGE")
            else:
                score = round(float(Fraction(fs).limit_denominator(10**6) * Fraction(8, 15) + Fraction(val).limit_denominator(10**6) * Fraction(4, 15)
                                    + Fraction(mb[s]).limit_denominator(10**6) * Fraction(3, 15)), 1)
                r.update(state="scored", score=score, rating=band(score), coverage=round(cov, 1))
        out[s] = r
    return out
