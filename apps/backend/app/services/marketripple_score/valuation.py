"""
Valuation pillar — S2-B. Reuses the real peer group already shipped for
Peer Comparison (2026-08-25 fix, app/api/stocks.py::_PEER_GROUPS) rather
than a second, independently-curated peer list — for Banking, that group
IS the 5 S1 reference companies. Two real components, combined:

  - Peer-relative valuation (PE, PB percentile among real peers) with a
    real ROE-based quality adjustment, per the owner's explicit ask that
    a premium-quality bank not be penalized for a higher P/B than a
    weaker peer's.
  - Own historical range: S1 found real annual EPS depth is only ~5
    years — a coarse annual P/E series, not a dense rolling percentile.
    Computed here from real annual EPS + the real daily close nearest
    each fiscal year end (yfinance has no historical-PE API directly).

Candidate weights (peer 70% / historical 30% when both available) are
explicitly unvalidated — see engine.py's 5-bank comparison.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
from app.services.marketripple_score.contracts import PillarScore, PillarStatus


def _fetch_valuation_snapshot_sync(symbol: str) -> dict:
    """See financial_strength.py::_fetch_financial_strength_inputs_sync's
    docstring — same real, confirmed-live retry rationale (concurrent
    peer-info fetches intermittently return partial data from yfinance;
    the underlying data itself is real and present on retry)."""
    import time
    import yfinance as yf

    t = yf.Ticker(f"{symbol.upper()}.NS")
    info = {}
    for attempt in range(2):
        try:
            info = t.info or {}
        except Exception:
            info = {}
        if info.get("trailingPE") is not None or info.get("priceToBook") is not None:
            break
        if attempt == 0:
            time.sleep(1.5)
    return {
        "pe": info.get("trailingPE"),
        "pb": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
    }


def _fetch_annual_eps_and_dates_sync(symbol: str) -> list[tuple[datetime, float]]:
    """Real (fiscal_year_end_date, diluted_eps) pairs, most-recent first,
    dropping any period with no real EPS value."""
    import yfinance as yf

    try:
        fin = yf.Ticker(f"{symbol.upper()}.NS").financials
    except Exception:
        return []
    if fin is None or fin.empty or "Diluted EPS" not in fin.index:
        return []
    out = []
    for col in fin.columns:
        val = fin.loc["Diluted EPS", col]
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if v != v:  # NaN
            continue
        dt = col.to_pydatetime() if hasattr(col, "to_pydatetime") else None
        if dt:
            out.append((dt.replace(tzinfo=timezone.utc), v))
    return out


def _fetch_price_history_sync(symbol: str) -> list[tuple[datetime, float]]:
    import math
    import yfinance as yf

    try:
        hist = yf.download(f"{symbol.upper()}.NS", period="5y", interval="1wk", progress=False, auto_adjust=True, timeout=15)
    except Exception:
        return []
    if hist is None or hist.empty:
        return []
    out = []
    for idx, row in hist.iterrows():
        try:
            c = row["Close"]
            if hasattr(c, "iloc"):
                c = c.iloc[0]
            v = float(c)
            if math.isnan(v) or math.isinf(v):
                continue
            dt = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else None
            if dt:
                out.append((dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt, v))
        except Exception:
            continue
    return out


def _nearest_price(price_series: list[tuple[datetime, float]], target: datetime) -> float | None:
    if not price_series:
        return None
    return min(price_series, key=lambda p: abs((p[0] - target).total_seconds()))[1]


def _percentile_rank(values: dict[str, float], symbol: str, cheaper_is_better: bool = True) -> float | None:
    """0-100, 100 = best (cheapest when cheaper_is_better). Real rank among
    real values only — a peer with no real value for this metric is
    excluded from the ranking, not treated as a data point."""
    if symbol not in values or len(values) < 2:
        return None
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=not cheaper_is_better)
    rank = next(i for i, (s, _) in enumerate(ordered) if s == symbol)  # 0 = best
    n = len(ordered)
    return round((n - 1 - rank) / (n - 1) * 100, 1)


async def score_valuation(symbol: str, sector: str | None, peer_group: list[str] | None = None) -> PillarScore:
    """peer_group: overrides the default peer group — S4.5 (owner decision,
    2026-08-29) made ALL_ELIGIBLE_NSE_BANKS the canonical Banking V1 peer
    universe, replacing the earlier 5-bank default; this parameter still
    exists for callers that genuinely need a different, explicit
    population (e.g. a future narrower "Large Private Bank Rank" analytic),
    never as a silent way to get a different score for the same bank."""
    loop = asyncio.get_event_loop()
    symbol = symbol.upper()

    if sector != "Banking":
        return PillarScore(
            name="valuation", score=None, coverage_pct=0.0, status=PillarStatus.INSUFFICIENT,
            metrics_used=[], metrics_missing=["banking_reference_implementation_only"],
            sources=[], detail={"note": "S2 Valuation is Banking-only in this phase, matching S1's reference scope"},
        )

    active_peer_group = peer_group if peer_group is not None else ALL_ELIGIBLE_NSE_BANKS
    peer_symbols = list(dict.fromkeys([symbol] + [s for s in active_peer_group if s != symbol]))
    # Sequential, not asyncio.gather — see financial_strength.py's own
    # identical comment; same real, confirmed-live reason.
    snapshots = []
    for s in peer_symbols:
        snapshots.append(await loop.run_in_executor(None, _fetch_valuation_snapshot_sync, s))
        await asyncio.sleep(0.4)
    by_symbol = dict(zip(peer_symbols, snapshots))

    metrics_used, metrics_missing = [], []
    detail: dict = {"peer_group": peer_symbols}
    sub_scores: dict[str, float] = {}

    pe_values = {s: d["pe"] for s, d in by_symbol.items() if d.get("pe")}
    pb_values = {s: d["pb"] for s, d in by_symbol.items() if d.get("pb")}
    roe_values = {s: d["roe"] for s, d in by_symbol.items() if d.get("roe") is not None}

    pe_pctile = _percentile_rank(pe_values, symbol, cheaper_is_better=True)
    pb_pctile = _percentile_rank(pb_values, symbol, cheaper_is_better=True)
    roe_pctile = _percentile_rank(roe_values, symbol, cheaper_is_better=False)

    if pe_pctile is not None:
        metrics_used.append("pe_peer_percentile")
        detail["pe"] = by_symbol[symbol].get("pe")
        detail["pe_peer_percentile"] = pe_pctile
    else:
        metrics_missing.append("pe_peer_percentile")
    if pb_pctile is not None:
        metrics_used.append("pb_peer_percentile")
        detail["pb"] = by_symbol[symbol].get("pb")
        detail["pb_peer_percentile"] = pb_pctile
    else:
        metrics_missing.append("pb_peer_percentile")

    if pe_pctile is not None or pb_pctile is not None:
        raw_valuation_pctile = sum(v for v in [pe_pctile, pb_pctile] if v is not None) / sum(1 for v in [pe_pctile, pb_pctile] if v is not None)
        if roe_pctile is not None:
            metrics_used.append("roe_quality_adjustment")
            detail["roe_peer_percentile"] = roe_pctile
            sub_scores["peer"] = round(raw_valuation_pctile * 0.75 + roe_pctile * 0.25, 1)
        else:
            metrics_missing.append("roe_quality_adjustment")
            sub_scores["peer"] = round(raw_valuation_pctile, 1)

    # Own historical range — coarse, real, annual-only (S1 finding)
    eps_history, price_history = await asyncio.gather(
        loop.run_in_executor(None, _fetch_annual_eps_and_dates_sync, symbol),
        loop.run_in_executor(None, _fetch_price_history_sync, symbol),
    )
    historical_pes: dict[str, float] = {}
    for dt, eps in eps_history:
        if eps <= 0:
            continue
        price = _nearest_price(price_history, dt)
        if price is not None:
            historical_pes[dt.strftime("%Y-%m-%d")] = round(price / eps, 1)
    current_pe = by_symbol[symbol].get("pe")
    if len(historical_pes) >= 3 and current_pe:
        all_pes = dict(historical_pes)
        all_pes["current"] = current_pe
        own_range_pctile = _percentile_rank(all_pes, "current", cheaper_is_better=True)
        if own_range_pctile is not None:
            sub_scores["own_history"] = own_range_pctile
            metrics_used.append("own_historical_pe_range (%d annual points)" % len(historical_pes))
            detail["historical_annual_pe"] = historical_pes
    else:
        metrics_missing.append("own_historical_pe_range (only %d usable annual points, need >=3)" % len(historical_pes))

    if not sub_scores:
        return PillarScore(
            name="valuation", score=None, coverage_pct=0.0, status=PillarStatus.INSUFFICIENT,
            metrics_used=metrics_used, metrics_missing=metrics_missing,
            sources=[f"yfinance live ({symbol}.NS + {len(peer_symbols)-1} real peers)"], detail=detail,
        )

    weights = {"peer": 0.70, "own_history": 0.30}
    used_weight = sum(weights[k] for k in sub_scores)
    score = round(sum(sub_scores[k] * weights[k] for k in sub_scores) / used_weight, 1)

    total_proposed = 3  # peer PE+PB (counted as one component), quality adjustment, own history
    coverage_pct = round(len(sub_scores) / 2 * 100, 1)  # peer + own_history are the 2 real sub-components
    status = (
        PillarStatus.COMPLETE if len(sub_scores) == 2 and roe_pctile is not None
        else PillarStatus.PARTIAL
    )

    return PillarScore(
        name="valuation", score=score, coverage_pct=coverage_pct, status=status,
        metrics_used=metrics_used, metrics_missing=metrics_missing,
        sources=[f"yfinance live ({symbol}.NS + {len(peer_symbols)-1} real peers: {', '.join(s for s in peer_symbols if s != symbol)})"],
        detail=detail,
    )
