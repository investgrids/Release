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

from app.services.marketripple_score.contracts import PillarScore, PillarStatus

_NIFTY_TICKER = "^NSEI"

# Reused verbatim from market_data.py — the same real, already-fixed
# sector ETF map (Warehouse sector-metrics work, 2026-08-25), not a
# second, competing sector-benchmark list.
from app.services.market_data import _SECTOR_ETFS  # noqa: E402


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


def _fetch_daily_closes_sync(ticker: str) -> list[float]:
    import math
    import yfinance as yf

    try:
        hist = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True, timeout=10)
    except Exception:
        return []
    if hist is None or hist.empty:
        return []
    closes = []
    for _, row in hist.iterrows():
        try:
            c = row["Close"]
            if hasattr(c, "iloc"):
                c = c.iloc[0]
            v = float(c)
            if not math.isnan(v) and not math.isinf(v):
                closes.append(v)
        except Exception:
            continue
    return closes


async def score_market_behaviour(symbol: str, sector: str | None) -> PillarScore:
    loop = asyncio.get_event_loop()
    sector_ticker = _SECTOR_ETFS.get(sector) if sector else None

    tickers = [f"{symbol.upper()}.NS", _NIFTY_TICKER] + ([sector_ticker] if sector_ticker else [])
    fetched = await asyncio.gather(*[loop.run_in_executor(None, _fetch_daily_closes_sync, t) for t in tickers])
    own_closes, nifty_closes = fetched[0], fetched[1]
    sector_closes = fetched[2] if sector_ticker else []

    if len(own_closes) < 30:
        return PillarScore(
            name="market_behaviour", score=None, coverage_pct=0.0,
            status=PillarStatus.INSUFFICIENT,
            metrics_used=[], metrics_missing=["daily_price_history"],
            sources=[f"yfinance live daily ({symbol}.NS)"],
            detail={"real_daily_rows": len(own_closes)},
        )

    sub_scores: dict[str, float] = {}
    metrics_used, metrics_missing = [], []
    detail: dict = {"real_daily_rows": len(own_closes)}

    # 200-DMA position
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
