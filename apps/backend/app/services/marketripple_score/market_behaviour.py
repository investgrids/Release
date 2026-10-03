"""
Market Behaviour pillar — S2-B. Real data confirmed live in S1 (251 real
daily rows/1yr for a reference bank); deliberately does NOT read Warehouse's
price_bars table (confirmed live in S1: 8 rows/symbol in production, far
too thin for a 200-DMA) and does NOT reuse the existing /chart endpoint
(get_stock_chart only fetches weekly resolution beyond 1 month) — this is
its own dedicated daily fetch, exactly as S1 recommended.

Purpose per the owner's own framing: "Is the market currently confirming
the fundamental/intelligence case?" — not prediction. Four real, simple
inputs, combined with explicitly candidate (unvalidated) weights:
  - 200-DMA position       35%
  - medium-term relative return vs NIFTY 50   30%
  - sector-relative return vs the real sector ETF   20%
  - RSI(14)                15%
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.services.marketripple_score.contracts import PillarScore, PillarStatus

_NIFTY_TICKER = "^NSEI"
_NSE_TIMEZONE = ZoneInfo("Asia/Kolkata")
_SESSION_FINALIZED_AT = time(16, 0)  # 30 minutes after the 15:30 IST close

# Candidate completeness bar only. It is not enforced by score_market_behaviour
# or the publication gate pending review of the measured 1/422-score impact.
MIN_MARKET_BEHAVIOUR_COVERAGE_PCT = 50.0
MIN_MARKET_BEHAVIOUR_OWN_OBSERVATIONS = 64


def market_behaviour_snapshot_is_sufficient(snapshot, *, allow_legacy_inference: bool = True) -> bool:
    """Check the publication candidate against stored or scorer provenance.

    Legacy snapshots have no `market_behaviour_inputs`; under the current
    four-component formula, 75% or 100% proves at least one relative return
    was computed, and a 63-session return proves at least 64 own closes.
    Lower legacy coverage is not enough evidence and fails closed.
    """
    coverage_pct = getattr(snapshot, "market_behaviour_coverage_pct", None)
    provenance = getattr(snapshot, "market_behaviour_inputs", None)
    if not isinstance(provenance, dict):
        return bool(allow_legacy_inference and coverage_pct is not None and coverage_pct >= 75.0)

    symbol = str(getattr(snapshot, "symbol", "")).upper()
    own_series = provenance.get("series", {}).get(f"{symbol}.NS", {})
    own_observation_count = own_series.get("observation_count", 0)
    inputs = provenance.get("inputs", {})
    metrics_used = []
    if inputs.get("relative_return_vs_nifty50_pct", {}).get("value") is not None:
        metrics_used.append("relative_return_vs_nifty50")
    if inputs.get("relative_return_vs_sector_etf_pct", {}).get("value") is not None:
        metrics_used.append("relative_return_vs_sector_etf (recorded benchmark)")
    return market_behaviour_coverage_meets_minimum(
        coverage_pct, own_observation_count, metrics_used,
    )


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _pct_return(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    return round((closes[-1] - closes[-1 - lookback]) / closes[-1 - lookback] * 100, 2)


def completed_session_cutoff_date(now: datetime | None = None) -> date:
    """Return the latest NSE session date safe to include in daily indicators.

    The current day's daily candle is excluded until 16:00 IST, allowing a
    30-minute vendor-finalization buffer after the 15:30 close.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    nse_now = now.astimezone(_NSE_TIMEZONE)
    if nse_now.time() < _SESSION_FINALIZED_AT:
        return nse_now.date() - timedelta(days=1)
    return nse_now.date()


def market_behaviour_coverage_meets_minimum(
    coverage_pct: float | None, own_observation_count: int, metrics_used: list[str],
) -> bool:
    """Candidate floor; informational until the publication impact is approved.

    Requires at least two components, enough completed closes for the
    63-session return window, and a real market/sector-relative comparison.
    """
    has_relative_comparison = any(
        metric.startswith("relative_return_vs_nifty50")
        or metric.startswith("relative_return_vs_sector_etf")
        for metric in metrics_used
    )
    return (
        coverage_pct is not None
        and coverage_pct >= MIN_MARKET_BEHAVIOUR_COVERAGE_PCT
        and own_observation_count >= MIN_MARKET_BEHAVIOUR_OWN_OBSERVATIONS
        and has_relative_comparison
    )


def pillar_has_sufficient_market_history(pillar: PillarScore | None) -> bool:
    """The floor, checked on a freshly computed pillar."""
    if pillar is None or pillar.score is None or pillar.coverage_pct is None:
        return False
    has_relative = any(m.startswith("relative_return_vs_") for m in pillar.metrics_used)
    return pillar.coverage_pct >= MIN_MARKET_BEHAVIOUR_COVERAGE_PCT and has_relative


def snapshot_lacks_market_history(snap) -> bool:
    """The floor, checked on a stored snapshot (the public projection).

    Snapshots computed after this rule carry INSUFFICIENT_MARKET_HISTORY in
    their block reasons when they fail it. Older snapshots store only the
    pillar's coverage: below 50% fails outright. (At exactly 50% an old
    snapshot can't prove a relative comparison; none was published in
    production when this shipped, and the weekly refresh re-judges every
    company with the full rule.)"""
    from app.services.marketripple_score.eligibility import REASON_INSUFFICIENT_MARKET_HISTORY

    if REASON_INSUFFICIENT_MARKET_HISTORY in (snap.publication_block_reasons or []):
        return True
    coverage = getattr(snap, "market_behaviour_coverage_pct", None)
    return coverage is None or coverage < MIN_MARKET_BEHAVIOUR_COVERAGE_PCT

# Reused verbatim from market_data.py — the same real, already-fixed
# sector ETF map (Warehouse sector-metrics work, 2026-08-25), not a
# second, competing sector-benchmark list.
from app.services.market_data import _SECTOR_ETFS  # noqa: E402

# Real, found-live bug (2026-09-27, while extending this pillar to non-
# bank sectors): _SECTOR_ETFS's own keys are abbreviated display labels
# ("IT", "Pharma", "Auto", "Metal", "Infra", "Realty") used by several
# OTHER, unrelated features (market_retriever.py, price_monitor.py,
# market_data.py's own sector-performance widget) — they do NOT match
# _NSE_UNIVERSE's real sector strings ("Technology", "Pharmaceuticals",
# "Automotive", "Metals", "Infrastructure", "Real Estate"), which is what
# this pillar is actually called with. Before this fix, sector_ticker was
# silently None for every non-Banking, non-FMCG, non-Energy sector this
# pillar could ever be asked to score — a real coverage gap, not a
# fabricated "no sector ETF exists" fact. Fixed with a LOCAL alias map
# here rather than renaming the shared dict's keys, which would change
# what those other, unrelated features display.
_SECTOR_LABEL_TO_ETF_KEY: dict[str, str] = {
    "Technology": "IT", "Pharmaceuticals": "Pharma", "Automotive": "Auto",
    "Metals": "Metal", "Infrastructure": "Infra", "Real Estate": "Realty",
}


def _fetch_daily_close_observations_sync(ticker: str) -> list[tuple[str, float]]:
    import math
    import yfinance as yf

    try:
        hist = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True, timeout=10)
    except Exception:
        return []
    if hist is None or hist.empty:
        return []
    observations = []
    for index, row in hist.iterrows():
        try:
            close = row["Close"]
            if hasattr(close, "iloc"):
                close = close.iloc[0]
            value = float(close)
            if math.isfinite(value):
                observed = index.to_pydatetime() if hasattr(index, "to_pydatetime") else index
                observations.append((observed.date().isoformat(), value))
        except Exception:
            continue
    return observations


def _fetch_daily_closes_sync(ticker: str) -> list[float]:
    return [close for _, close in _fetch_daily_close_observations_sync(ticker)]


def _dated_observations(rows: list, cutoff_date: date) -> list[tuple[str, float]]:
    observations = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 2:
            continue
        observed, close = row
        try:
            observed_date = observed.date() if isinstance(observed, datetime) else observed
            observed_date = observed_date if isinstance(observed_date, date) else date.fromisoformat(str(observed)[:10])
            value = float(close)
        except (TypeError, ValueError):
            continue
        if observed_date <= cutoff_date and value == value and abs(value) != float("inf"):
            observations.append((observed_date.isoformat(), value))
    return observations


def _window(observations: list[tuple[str, float]], size: int) -> dict:
    values = observations[-size:]
    return {
        "observation_start": values[0][0] if values else None,
        "observation_end": values[-1][0] if values else None,
        "observation_count": len(values),
        "requested_observations": size,
    }


def _input_provenance(
    *, symbol_ticker: str, own: list[tuple[str, float]], nifty: list[tuple[str, float]],
    sector_ticker: str | None, sector: list[tuple[str, float]], cutoff_date: date,
    own_fetched_at: str, benchmark_fetched_at: str | None,
    inputs: dict[str, tuple[float | None, str, dict[str, int]]],
) -> dict:
    observations_by_ticker = {symbol_ticker: own, _NIFTY_TICKER: nifty}
    if sector_ticker:
        observations_by_ticker[sector_ticker] = sector
    fetch_times = {symbol_ticker: own_fetched_at, _NIFTY_TICKER: benchmark_fetched_at or own_fetched_at}
    if sector_ticker:
        fetch_times[sector_ticker] = benchmark_fetched_at or own_fetched_at

    series = {}
    for ticker, observations in observations_by_ticker.items():
        limit = 200 if ticker == symbol_ticker else 64
        captured = observations[-limit:]
        series[ticker] = {
            "source": "Yahoo Finance via yfinance",
            "interval": "1d",
            "auto_adjust": True,
            "fetched_at": fetch_times[ticker],
            **_window(observations, limit),
            "observations": [{"date": day, "close": close} for day, close in captured],
        }

    input_values = {}
    for name, (value, unit, windows) in inputs.items():
        input_values[name] = {
            "value": value,
            "unit": unit,
            "source": "Yahoo Finance via yfinance",
            "observation_windows": {
                ticker: _window(observations_by_ticker.get(ticker, []), size)
                for ticker, size in windows.items()
            },
        }
    return {
        "version": 1,
        "provider": "Yahoo Finance via yfinance",
        "interval": "1d",
        "auto_adjust": True,
        "cutoff_date": cutoff_date.isoformat(),
        "collected_at": own_fetched_at,
        "series": series,
        "inputs": input_values,
    }


async def score_market_behaviour(
    symbol: str, sector: str | None,
    prefetched_benchmarks: dict[str, list[tuple[str, float]]] | None = None,
    cutoff_date: date | str | None = None,
    benchmark_fetched_at: str | None = None,
) -> PillarScore:
    """`prefetched_benchmarks`: an already-fetched {ticker: dated closes} map for
    _NIFTY_TICKER and/or the real sector ETF ticker (NS1 round 2, 2026-09-27)
    — NIFTY and a given sector's ETF are the SAME real benchmark for every
    company in that sector, so a batch computing many companies in one
    sector should fetch each benchmark once and share it, rather than every
    company independently re-fetching the identical NIFTY/sector-ETF series.
    None (default, every existing caller) fetches fresh, unchanged from
    before this parameter existed. The company's OWN daily closes are
    always fetched fresh — that part was never redundant across companies."""
    loop = asyncio.get_event_loop()
    if cutoff_date is None:
        cutoff_date = completed_session_cutoff_date()
    elif isinstance(cutoff_date, str):
        cutoff_date = date.fromisoformat(cutoff_date)
    sector_ticker = _SECTOR_ETFS.get(_SECTOR_LABEL_TO_ETF_KEY.get(sector, sector)) if sector else None
    prefetched_benchmarks = prefetched_benchmarks or {}
    symbol_ticker = f"{symbol.upper()}.NS"

    to_fetch = [symbol_ticker]
    if not prefetched_benchmarks.get(_NIFTY_TICKER):
        to_fetch.append(_NIFTY_TICKER)
    if sector_ticker and not prefetched_benchmarks.get(sector_ticker):
        to_fetch.append(sector_ticker)

    fetched = await asyncio.gather(*[loop.run_in_executor(None, _fetch_daily_close_observations_sync, t) for t in to_fetch])
    fetched_by_ticker = dict(zip(to_fetch, fetched))

    own_fetched_at = datetime.now(timezone.utc).isoformat()
    own_observations = _dated_observations(fetched_by_ticker[symbol_ticker], cutoff_date)
    nifty_observations = _dated_observations(
        prefetched_benchmarks.get(_NIFTY_TICKER) or fetched_by_ticker.get(_NIFTY_TICKER, []), cutoff_date,
    )
    sector_observations = _dated_observations(
        prefetched_benchmarks.get(sector_ticker) or fetched_by_ticker.get(sector_ticker, []), cutoff_date,
    ) if sector_ticker else []
    own_closes = [close for _, close in own_observations]
    nifty_closes = [close for _, close in nifty_observations]
    sector_closes = [close for _, close in sector_observations]

    if len(own_closes) < 30:
        provenance = _input_provenance(
            symbol_ticker=symbol_ticker, own=own_observations, nifty=nifty_observations,
            sector_ticker=sector_ticker, sector=sector_observations, cutoff_date=cutoff_date,
            own_fetched_at=own_fetched_at, benchmark_fetched_at=benchmark_fetched_at, inputs={},
        )
        return PillarScore(
            name="market_behaviour", score=None, coverage_pct=0.0,
            status=PillarStatus.INSUFFICIENT,
            metrics_used=[], metrics_missing=["daily_price_history"],
            sources=[f"yfinance live daily ({symbol}.NS)"],
            detail={"real_daily_rows": len(own_closes), "input_provenance": provenance},
        )

    sub_scores: dict[str, float] = {}
    metrics_used, metrics_missing = [], []
    detail: dict = {"real_daily_rows": len(own_closes)}

    # 200-DMA position
    position_pct = None
    if len(own_closes) >= 200:
        sma200 = sum(own_closes[-200:]) / 200
        position_pct = round((own_closes[-1] - sma200) / sma200 * 100, 2)
        sub_scores["dma200"] = max(0.0, min(100.0, 50 + position_pct * 5))
        metrics_used.append("200_dma_position")
        detail["price_vs_200dma_pct"] = position_pct
    else:
        metrics_missing.append("200_dma_position (needs 200 real daily rows, has %d)" % len(own_closes))

    # Medium-term relative return vs NIFTY 50 (63 trading days ~ 3 months)
    own_3m = _pct_return(own_closes, 63)
    nifty_3m = _pct_return(nifty_closes, 63) if nifty_closes else None
    if own_3m is not None and nifty_3m is not None:
        rel = round(own_3m - nifty_3m, 2)
        sub_scores["relative_market"] = max(0.0, min(100.0, 50 + rel * 3))
        metrics_used.append("relative_return_vs_nifty50")
        detail["own_3m_return_pct"] = own_3m
        detail["nifty_3m_return_pct"] = nifty_3m
    else:
        metrics_missing.append("relative_return_vs_nifty50")

    # Sector-relative return
    if sector_ticker:
        sector_3m = _pct_return(sector_closes, 63) if sector_closes else None
        if own_3m is not None and sector_3m is not None:
            rel_sector = round(own_3m - sector_3m, 2)
            sub_scores["relative_sector"] = max(0.0, min(100.0, 50 + rel_sector * 3))
            metrics_used.append(f"relative_return_vs_sector_etf ({sector_ticker})")
            detail["sector_3m_return_pct"] = sector_3m
        else:
            metrics_missing.append(f"relative_return_vs_sector_etf ({sector_ticker})")
    else:
        metrics_missing.append("relative_return_vs_sector_etf (no real sector ETF mapped for sector=%r)" % sector)

    # RSI(14)
    rsi = _rsi(own_closes)
    if rsi is not None:
        sub_scores["rsi"] = rsi
        metrics_used.append("rsi_14")
        detail["rsi_14"] = rsi
    else:
        metrics_missing.append("rsi_14")

    input_windows: dict[str, tuple[float | None, str, dict[str, int]]] = {
        "price_vs_200dma_pct": (position_pct, "percent", {symbol_ticker: 200}),
        "own_3m_return_pct": (own_3m, "percent", {symbol_ticker: 64}),
        "nifty_3m_return_pct": (nifty_3m, "percent", {_NIFTY_TICKER: 64}),
        "relative_return_vs_nifty50_pct": (
            round(own_3m - nifty_3m, 2) if own_3m is not None and nifty_3m is not None else None,
            "percentage_points", {symbol_ticker: 64, _NIFTY_TICKER: 64},
        ),
        "rsi_14": (rsi, "index_points", {symbol_ticker: 15}),
    }
    if sector_ticker:
        input_windows["sector_3m_return_pct"] = (sector_3m, "percent", {sector_ticker: 64})
        input_windows["relative_return_vs_sector_etf_pct"] = (
            round(own_3m - sector_3m, 2) if own_3m is not None and sector_3m is not None else None,
            "percentage_points", {symbol_ticker: 64, sector_ticker: 64},
        )
    detail["input_provenance"] = _input_provenance(
        symbol_ticker=symbol_ticker, own=own_observations, nifty=nifty_observations,
        sector_ticker=sector_ticker, sector=sector_observations, cutoff_date=cutoff_date,
        own_fetched_at=own_fetched_at, benchmark_fetched_at=benchmark_fetched_at,
        inputs=input_windows,
    )

    if not sub_scores:
        return PillarScore(
            name="market_behaviour", score=None, coverage_pct=0.0,
            status=PillarStatus.INSUFFICIENT, metrics_used=[], metrics_missing=metrics_missing,
            sources=[f"yfinance live daily ({symbol}.NS, {_NIFTY_TICKER}" + (f", {sector_ticker}" if sector_ticker else "") + ")"],
            detail=detail,
        )

    # Candidate weights — explicitly unvalidated, see module docstring.
    weights = {"dma200": 0.35, "relative_market": 0.30, "relative_sector": 0.20, "rsi": 0.15}
    used_weight_sum = sum(weights[k] for k in sub_scores)
    score = round(sum(sub_scores[k] * weights[k] for k in sub_scores) / used_weight_sum, 1)

    total_proposed = 4
    coverage_pct = round(len(metrics_used) / total_proposed * 100, 1)
    status = (
        PillarStatus.COMPLETE if len(metrics_used) == total_proposed
        else PillarStatus.PARTIAL if metrics_used
        else PillarStatus.INSUFFICIENT
    )

    return PillarScore(
        name="market_behaviour", score=score, coverage_pct=coverage_pct, status=status,
        metrics_used=metrics_used, metrics_missing=metrics_missing,
        sources=[f"yfinance live daily ({symbol}.NS, {_NIFTY_TICKER}" + (f", {sector_ticker}" if sector_ticker else "") + ")"],
        detail=detail,
    )
