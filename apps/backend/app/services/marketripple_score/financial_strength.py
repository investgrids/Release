"""
Financial Strength pillar — S2-C, Banking reference sector. Explicitly
PARTIAL by design, not a bug to fix here: S1 found 7 of 12 proposed
banking metrics (both asset-quality metrics, both capital metrics, CASA,
deposit growth, advances) completely absent from every real data source
this app has. Scored from only the 4 real, usable metrics — ROE, ROA,
NII growth, Profit growth — ranked against the same real Banking peer
group Valuation uses.

NIM is deliberately computed and reported in `detail` for visibility but
NEVER included in metrics_used or the score itself, per explicit owner
instruction: `Net Interest Income / Total Assets` is a real, live number
but not actual bank NIM (the real denominator is average interest-earning
assets, a line item that doesn't exist in this data source) — reporting
it as NIM would misrepresent a proxy as the real thing.

status is unconditionally PARTIAL for every real Banking symbol this
scores today (never COMPLETE) — that's not a threshold miscalibration,
it's the accurate reflection of a 12-metric pillar with 8 structurally
unavailable inputs (7 blocked + NIM downgraded to a non-scored proxy).
"""
from __future__ import annotations

import asyncio

from app.services.marketripple_score.contracts import PillarScore, PillarStatus
from app.services.marketripple_score.valuation import _BANKING_PEER_GROUP, _percentile_rank

_PROPOSED_BANKING_METRICS = 12  # asset quality x3, capital x2, profitability x3 (incl. NIM), funding x2, growth x2


def _fetch_financial_strength_inputs_sync(symbol: str) -> dict:
    """Real, confirmed live: fetching 5 real peer tickers' `.info` at once
    (5 concurrent calls per pillar, x4 pillars per bank) intermittently
    returns an empty/partial dict from yfinance under that concurrent
    load — reproduced twice, a different bank failing each run, never the
    same real underlying data actually missing (re-checked in isolation:
    real values exist every time). One retry after a short pause is the
    standard fix for this class of live-API flakiness, not a data gap."""
    import time
    import yfinance as yf

    t = yf.Ticker(f"{symbol.upper()}.NS")
    info = {}
    for attempt in range(2):
        try:
            info = t.info or {}
        except Exception:
            info = {}
        if info.get("returnOnEquity") is not None or info.get("returnOnAssets") is not None:
            break
        if attempt == 0:
            time.sleep(1.5)
    roe = info.get("returnOnEquity")
    roa = info.get("returnOnAssets")

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

    return {"roe": roe, "roa": roa, "nii_growth": nii_growth, "profit_growth": profit_growth, "nim_proxy_not_scored": nim_proxy}


async def score_financial_strength(symbol: str, sector: str | None) -> PillarScore:
    loop = asyncio.get_event_loop()
    symbol = symbol.upper()

    if sector != "Banking":
        return PillarScore(
            name="financial_strength", score=None, coverage_pct=0.0, status=PillarStatus.INSUFFICIENT,
            metrics_used=[], metrics_missing=["banking_reference_implementation_only"],
            sources=[], detail={"note": "S2 Financial Strength is Banking-only in this phase"},
        )

    peer_symbols = list(dict.fromkeys([symbol] + [s for s in _BANKING_PEER_GROUP if s != symbol]))
    # Sequential, not asyncio.gather — confirmed live: firing all 5 real
    # peer .info fetches at once, on top of Valuation's own simultaneous
    # 5-peer fetch for the same bank, reproducibly starves ROE/ROA out of
    # yfinance's response for 4 of 5 real reference banks (retried with a
    # 1.5s pause, still starved — this is sustained concurrent pressure
    # across pillars, not a one-off network blip). A small stagger trades
    # latency for the real data actually being there.
    fetched = []
    for s in peer_symbols:
        fetched.append(await loop.run_in_executor(None, _fetch_financial_strength_inputs_sync, s))
        await asyncio.sleep(0.4)
    by_symbol = dict(zip(peer_symbols, fetched))
    own = by_symbol[symbol]

    metrics_used, metrics_missing = [], []
    sub_scores: dict[str, float] = {}
    detail: dict = {
        "peer_group": peer_symbols,
        "nim_proxy_pct": own.get("nim_proxy_not_scored"),
        "nim_proxy_disclaimer": "NII / Total Assets — NOT real NIM (needs average interest-earning assets, unavailable); computed for visibility only, never scored",
    }

    roe_values = {s: d["roe"] for s, d in by_symbol.items() if d.get("roe") is not None}
    roa_values = {s: d["roa"] for s, d in by_symbol.items() if d.get("roa") is not None}

    roe_pctile = _percentile_rank(roe_values, symbol, cheaper_is_better=False)
    roa_pctile = _percentile_rank(roa_values, symbol, cheaper_is_better=False)

    if roe_pctile is not None:
        sub_scores["roe"] = roe_pctile
        metrics_used.append("roe_peer_percentile")
        detail["roe"] = own.get("roe")
    else:
        metrics_missing.append("roe_peer_percentile")

    if roa_pctile is not None:
        sub_scores["roa"] = roa_pctile
        metrics_used.append("roa_peer_percentile")
        detail["roa"] = own.get("roa")
    else:
        metrics_missing.append("roa_peer_percentile")

    if own.get("nii_growth") is not None:
        # Simple, transparent mapping: growth of 0% -> 50, +10%/-10% moves
        # the score by 25 points either way, capped 0-100 — candidate,
        # unvalidated, same as every other threshold in this phase.
        sub_scores["nii_growth"] = max(0.0, min(100.0, 50 + own["nii_growth"] * 2.5))
        metrics_used.append("nii_growth_yoy")
        detail["nii_growth_pct"] = own["nii_growth"]
    else:
        metrics_missing.append("nii_growth_yoy")

    if own.get("profit_growth") is not None:
        sub_scores["profit_growth"] = max(0.0, min(100.0, 50 + own["profit_growth"] * 2.5))
        metrics_used.append("profit_growth_yoy")
        detail["profit_growth_pct"] = own["profit_growth"]
    else:
        metrics_missing.append("profit_growth_yoy")

    # The 7 structurally blocked metrics — always missing, always listed,
    # never silently absent from the pillar's own self-report.
    metrics_missing += [
        "net_npa (BLOCKED — no source anywhere, see S1 audit)",
        "gross_npa (BLOCKED)",
        "provision_coverage (BLOCKED)",
        "cet1 (BLOCKED)",
        "car (BLOCKED)",
        "casa (BLOCKED)",
        "deposit_growth (BLOCKED)",
        "advances_growth (BLOCKED)",
        "nim (real value known but excluded from score — see nim_proxy_disclaimer)",
    ]

    if not sub_scores:
        return PillarScore(
            name="financial_strength", score=None, coverage_pct=0.0, status=PillarStatus.INSUFFICIENT,
            metrics_used=metrics_used, metrics_missing=metrics_missing,
            sources=[f"yfinance live ({symbol}.NS + {len(peer_symbols)-1} real peers)"], detail=detail,
        )

    # Equal weight across whichever of the 4 real metrics are available —
    # candidate, unvalidated.
    score = round(sum(sub_scores.values()) / len(sub_scores), 1)
    coverage_pct = round(len(metrics_used) / _PROPOSED_BANKING_METRICS * 100, 1)

    return PillarScore(
        name="financial_strength", score=score, coverage_pct=coverage_pct,
        status=PillarStatus.PARTIAL,  # never COMPLETE for Banking today — see module docstring
        metrics_used=metrics_used, metrics_missing=metrics_missing,
        sources=[f"yfinance live ({symbol}.NS + {len(peer_symbols)-1} real peers: {', '.join(s for s in peer_symbols if s != symbol)})"],
        detail=detail,
    )
