"""
Financial Strength pillar — S3-D revision, Banking reference sector.
Now scores 7 real metrics instead of S2-C's 4, using the real FinancialFact
store (S3-B/C) for the 4 metrics that were BLOCKED at S1/S2 time and are
now confirmed real and reliably available: Gross NPA %, Net NPA %, CET1
Ratio, ROA (replacing the old yfinance-sourced ROA with the real,
primary-source regulatory figure). ROE, NII growth, and Profit growth stay
yfinance-sourced, unchanged from S2-C — real, already validated, no reason
to re-source them.

Owner's explicit S3-D scoping decision (2026-08-25) — deliberately NOT
scoring the other 5 originally-proposed metrics, kept as explicit known
gaps so coverage stays honest against the full 12-metric ambition, not a
quietly-narrowed one:
  - CASA, Provision Coverage Ratio, total CAR: confirmed structurally
    absent from NSE's real XBRL taxonomy (S3-A/S3-B).
  - Deposit growth, Advances growth: the underlying real values exist
    (FinancialFact has real Deposits/Advances) but only 1 real year deep
    per bank — not enough history for a real growth rate yet (S3-C).

NIM stays a computed-but-never-scored diagnostic (unchanged from S2-C):
`NII / Total Assets` is real but not actual bank NIM (real denominator is
average interest-earning assets, still unavailable).

Anomaly handling (owner's explicit rule): a FinancialFact row with
quality_status=ANOMALY must never enter scoring, and is never silently
replaced with an estimate — _latest_valid_fact_value() walks back to the
symbol's own latest real POPULATED+non-ANOMALY observation for that
metric instead. Confirmed live: ICICIBANK's real FY25 Q1 Gross NPA/ROA are
flagged ANOMALY (see S3-B/C) — this pillar falls back to ICICIBANK's real
FY25 Q2 or Q3 value, never FY25 Q1's own anomalous figure, and never a
computed/interpolated substitute.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
from app.services.marketripple_score.contracts import PillarScore, PillarStatus
from app.services.marketripple_score.valuation import _percentile_rank

_PROPOSED_BANKING_METRICS = 12  # asset quality x3, capital x2, profitability x3 (incl. NIM), funding x2, growth x2

# metric_code -> (real FinancialFact tag, higher_is_better)
_FACT_METRICS: list[tuple[str, bool]] = [
    ("gross_npa_pct", False),  # lower NPA is better
    ("net_npa_pct", False),
    ("cet1_ratio", True),
    ("roa", True),
]

# S5-B (owner decision, 2026-08-29): the real, currently-scoreable Banking
# V1 metric set — the 4 FinancialFact-sourced metrics above plus the 3
# yfinance-sourced ones (roe, nii_growth, profit_growth) below. This is
# the authoritative denominator for publication eligibility going
# forward — NOT _PROPOSED_BANKING_METRICS (12), which is the original,
# larger ambition kept only for the honest coverage_pct disclosure and is
# now explicitly "historical implementation baggage" for any publication
# decision (owner's own words).
REAL_BANKING_METRICS_TOTAL = len(_FACT_METRICS) + 3

_KNOWN_UNAVAILABLE = [
    "casa_ratio (SOURCE_UNAVAILABLE — confirmed absent from NSE's real XBRL taxonomy, S3-A)",
    "provision_coverage_ratio (SOURCE_UNAVAILABLE — same)",
    "car_total (SOURCE_UNAVAILABLE — same; never derived as CET1+AdditionalTier1, would omit Tier 2)",
    "deposit_growth (real Deposits value exists but only 1 real year deep — not enough history for growth yet, S3-C)",
    "advances_growth (same — only 1 real year deep)",
]


async def _latest_valid_fact_value(db: AsyncSession, symbol: str, metric_code: str) -> float | None:
    """The real, current, non-anomalous, plausible, non-quarantined
    observation for this symbol+metric — walks back past any ANOMALY,
    IMPLAUSIBLE_SCALE, or SOURCE_DOCUMENT_QUARANTINED (S4.5-B) flagged
    period rather than using it or fabricating a replacement. Applies
    identically whether `symbol` is the scored bank or a peer being pulled
    into another bank's percentile ranking — a filer whose values are
    excluded from its own score is excluded from every other bank's peer
    pool too. Non-Consolidated only (load-bearing, see FinancialFact's own
    module docstring)."""
    from app.db.models.financial_fact import (
        EXTRACTION_POPULATED, FinancialFact, QUALITY_ANOMALY,
        QUALITY_IMPLAUSIBLE_SCALE, QUALITY_SOURCE_DOCUMENT_QUARANTINED,
    )

    rows = (await db.execute(
        select(FinancialFact.value, FinancialFact.fiscal_year, FinancialFact.fiscal_quarter, FinancialFact.quality_status)
        .where(
            FinancialFact.symbol == symbol, FinancialFact.metric_code == metric_code,
            FinancialFact.consolidation_scope == "Non-Consolidated", FinancialFact.extraction_status == EXTRACTION_POPULATED,
        )
    )).all()
    _excluded = (QUALITY_ANOMALY, QUALITY_IMPLAUSIBLE_SCALE, QUALITY_SOURCE_DOCUMENT_QUARANTINED)
    valid = [(v, fy, fq or 0) for v, fy, fq, qs in rows if qs not in _excluded and v is not None]
    if not valid:
        return None
    valid.sort(key=lambda r: (r[1], r[2]), reverse=True)
    return valid[0][0]


def _fetch_financial_strength_inputs_sync(symbol: str) -> dict:
    """Real, confirmed live: fetching 5 real peer tickers' `.info` at once
    intermittently returns an empty/partial dict from yfinance under
    concurrent load. One retry after a short pause is the standard fix for
    this class of live-API flakiness, not a data gap — see the identical,
    already-validated comment on valuation.py's own peer fetch."""
    import time
    import yfinance as yf

    t = yf.Ticker(f"{symbol.upper()}.NS")
    info = {}
    for attempt in range(2):
        try:
            info = t.info or {}
        except Exception:
            info = {}
        if info.get("returnOnEquity") is not None:
            break
        if attempt == 0:
            time.sleep(1.5)
    roe = info.get("returnOnEquity")

    nii_growth = None
    profit_growth = None
    nim_proxy = None
    try:
        fin = t.financials
        bs = t.balance_sheet
        if fin is not None and not fin.empty:
            if "Net Interest Income" in fin.index and len(fin.columns) >= 2:
                nii = fin.loc["Net Interest Income"]
                cur, prev = nii.iloc[0], nii.iloc[1]
                if cur == cur and prev == prev and prev != 0:  # not NaN
                    nii_growth = round(float((cur - prev) / abs(prev) * 100), 1)
                if bs is not None and not bs.empty and "Total Assets" in bs.index and cur == cur:
                    total_assets = bs.loc["Total Assets"].iloc[0]
                    if total_assets == total_assets and total_assets != 0:
                        nim_proxy = round(float(cur) / float(total_assets) * 100, 2)
            if "Net Income" in fin.index and len(fin.columns) >= 2:
                ni = fin.loc["Net Income"]
                cur, prev = ni.iloc[0], ni.iloc[1]
                if cur == cur and prev == prev and prev != 0:
                    profit_growth = round(float((cur - prev) / abs(prev) * 100), 1)
    except Exception:
        pass

    return {"roe": roe, "nii_growth": nii_growth, "profit_growth": profit_growth, "nim_proxy_not_scored": nim_proxy}


async def score_financial_strength(
    db: AsyncSession, symbol: str, sector: str | None, peer_group: list[str] | None = None,
) -> PillarScore:
    """peer_group: overrides the default peer group — see
    valuation.py::score_valuation's identical parameter for why. The
    scoring formula itself (percentile ranking, anomaly/plausibility
    exclusion, equal-weight average) is completely unchanged by this — S4's
    own frozen-algorithm requirement stays intact; only the population
    being percentile-ranked against becomes configurable. Default is
    ALL_ELIGIBLE_NSE_BANKS (S4.5 owner decision, 2026-08-29) — the
    canonical Banking V1 peer universe, not a narrower hand-picked group."""
    loop = asyncio.get_event_loop()
    symbol = symbol.upper()

    if sector != "Banking":
        return PillarScore(
            name="financial_strength", score=None, coverage_pct=0.0, status=PillarStatus.INSUFFICIENT,
            metrics_used=[], metrics_missing=["banking_reference_implementation_only"],
            sources=[], detail={"note": "S3-D Financial Strength is Banking-only in this phase"},
        )

    active_peer_group = peer_group if peer_group is not None else ALL_ELIGIBLE_NSE_BANKS
    peer_symbols = list(dict.fromkeys([symbol] + [s for s in active_peer_group if s != symbol]))

    # yfinance-sourced (ROE, NII growth, Profit growth) — sequential, not
    # asyncio.gather, per the real, confirmed-live concurrent-load finding
    # already documented in valuation.py's own peer fetch.
    yf_fetched = []
    for s in peer_symbols:
        yf_fetched.append(await loop.run_in_executor(None, _fetch_financial_strength_inputs_sync, s))
        await asyncio.sleep(0.4)
    by_symbol_yf = dict(zip(peer_symbols, yf_fetched))
    own_yf = by_symbol_yf[symbol]

    # FinancialFact-sourced (Gross NPA%, Net NPA%, CET1, ROA) — real
    # primary-source values, anomaly-excluded per _latest_valid_fact_value.
    fact_values: dict[str, dict[str, float]] = {code: {} for code, _ in _FACT_METRICS}
    for s in peer_symbols:
        for code, _ in _FACT_METRICS:
            v = await _latest_valid_fact_value(db, s, code)
            if v is not None:
                fact_values[code][s] = v

    metrics_used, metrics_missing = [], list(_KNOWN_UNAVAILABLE)
    sub_scores: dict[str, float] = {}
    detail: dict = {
        "peer_group": peer_symbols,
        "nim_proxy_pct": own_yf.get("nim_proxy_not_scored"),
        "nim_proxy_disclaimer": "NII / Total Assets — NOT real NIM (needs average interest-earning assets, unavailable); computed for visibility only, never scored",
    }

    for code, higher_is_better in _FACT_METRICS:
        pctile = _percentile_rank(fact_values[code], symbol, cheaper_is_better=not higher_is_better)
        if pctile is not None:
            sub_scores[code] = pctile
            metrics_used.append(f"{code}_peer_percentile (real, NSE XBRL, Non-Consolidated)")
            detail[code] = fact_values[code].get(symbol)
        else:
            metrics_missing.append(f"{code} (no valid — non-anomalous — real observation for this symbol yet)")

    roe_values = {s: d["roe"] for s, d in by_symbol_yf.items() if d.get("roe") is not None}
    roe_pctile = _percentile_rank(roe_values, symbol, cheaper_is_better=False)
    if roe_pctile is not None:
        sub_scores["roe"] = roe_pctile
        metrics_used.append("roe_peer_percentile (yfinance)")
        detail["roe"] = own_yf.get("roe")
    else:
        metrics_missing.append("roe_peer_percentile")

    nii_growth_values = {s: d["nii_growth"] for s, d in by_symbol_yf.items() if d.get("nii_growth") is not None}
    nii_growth_pctile = _percentile_rank(nii_growth_values, symbol, cheaper_is_better=False)
    if nii_growth_pctile is not None:
        sub_scores["nii_growth"] = nii_growth_pctile
        metrics_used.append("nii_growth_peer_percentile (yfinance)")
        detail["nii_growth_pct"] = own_yf.get("nii_growth")
    else:
        metrics_missing.append("nii_growth_peer_percentile")

    profit_growth_values = {s: d["profit_growth"] for s, d in by_symbol_yf.items() if d.get("profit_growth") is not None}
    profit_growth_pctile = _percentile_rank(profit_growth_values, symbol, cheaper_is_better=False)
    if profit_growth_pctile is not None:
        sub_scores["profit_growth"] = profit_growth_pctile
        metrics_used.append("profit_growth_peer_percentile (yfinance)")
        detail["profit_growth_pct"] = own_yf.get("profit_growth")
    else:
        metrics_missing.append("profit_growth_peer_percentile")

    if not sub_scores:
        return PillarScore(
            name="financial_strength", score=None, coverage_pct=0.0, status=PillarStatus.INSUFFICIENT,
            metrics_used=metrics_used, metrics_missing=metrics_missing,
            sources=[f"NSE real XBRL + yfinance ({symbol}.NS + {len(peer_symbols)-1} real peers)"], detail=detail,
        )

    # Equal weight across whichever of the 7 real metrics are available —
    # candidate, unvalidated, per owner's explicit instruction not to tune
    # this on the S3-D run.
    score = round(sum(sub_scores.values()) / len(sub_scores), 1)
    coverage_pct = round(len(sub_scores) / _PROPOSED_BANKING_METRICS * 100, 1)

    return PillarScore(
        name="financial_strength", score=score, coverage_pct=coverage_pct,
        status=PillarStatus.PARTIAL,  # never COMPLETE for Banking today — see module docstring
        metrics_used=metrics_used, metrics_missing=metrics_missing,
        sources=[f"NSE real XBRL (Non-Consolidated) + yfinance ({symbol}.NS + {len(peer_symbols)-1} real peers: {', '.join(s for s in peer_symbols if s != symbol)})"],
        detail=detail,
    )
