"""
ThemeScoringWorker — scores 12 active market themes every 10 min.
Two signals: price change (60%) + news activity (40%).
"""
from __future__ import annotations

import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from uuid import uuid4

log = structlog.get_logger(__name__)

THEMES: dict[str, list[str]] = {
    "Banking":            ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "INDUSINDBK"],
    "IT & Technology":    ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM"],
    "Power & Energy":     ["NTPC", "POWERGRID", "TATAPOWER", "ADANIGREEN", "SJVN", "CESC"],
    "Defence":            ["HAL", "BEL", "BHEL", "COCHINSHIP", "BEML", "MIDHANI"],
    "Auto & EV":          ["TATAMOTORS", "MARUTI", "M&M", "BAJAJ-AUTO", "EICHERMOT", "TVSMOTOR"],
    "Pharma & Healthcare":["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP", "MAXHEALTH"],
    "Infrastructure":     ["LT", "RVNL", "IRCON", "ADANIPORTS", "GMRINFRA", "NCC"],
    "FMCG":               ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO"],
    "Metals & Mining":    ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "COALINDIA", "NMDC"],
    "Real Estate":        ["DLF", "GODREJPROP", "OBEROIRLTY", "PHOENIXLTD", "PRESTIGE"],
    "Financial Services": ["BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "CHOLAFIN"],
    "Chemicals":          ["PIDILITIND", "SRF", "DEEPAKNTR", "NAVINFLUOR", "AARTI"],
}


def _fetch_prices_sync(tickers: list[str]) -> dict[str, float]:
    """Fetch last prices via yfinance — runs in executor."""
    try:
        import yfinance as yf
        results: dict[str, float] = {}
        for sym in tickers[:4]:
            try:
                t = yf.Ticker(f"{sym}.NS")
                info = t.fast_info
                prev = float(info.previous_close or 1)
                curr = float(info.last_price or prev)
                results[sym] = ((curr - prev) / prev) * 100 if prev else 0.0
            except Exception:
                results[sym] = 0.0
        return results
    except Exception:
        return {}


async def _score_theme(theme: str, tickers: list[str]) -> dict:
    loop = asyncio.get_event_loop()
    try:
        changes = await loop.run_in_executor(None, _fetch_prices_sync, tickers)
    except Exception:
        changes = {}

    vals = [v for v in changes.values() if v != 0.0]
    price_signal = sum(vals) / len(vals) if vals else 0.0
    price_score = min(100.0, max(0.0, 50.0 + price_signal * 16.67))

    # News signal from triage DB
    news_count = 0
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import EventTriage
        from sqlalchemy import select, desc

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(EventTriage).where(EventTriage.triaged_at >= since).limit(200)
            )).scalars().all()

        for r in rows:
            if theme in (r.themes or []) or any(s in (r.tickers or []) for s in tickers):
                news_count += 1
    except Exception:
        pass

    news_score = min(100.0, news_count * 10.0)
    composite = price_score * 0.6 + news_score * 0.4

    top_stocks = sorted(
        [{"sym": sym, "change_pct": round(chg, 2)} for sym, chg in changes.items()],
        key=lambda x: abs(x["change_pct"]), reverse=True
    )[:3]

    return {
        "score": round(composite, 1),
        "price_signal": round(price_signal, 2),
        "news_signal": round(news_score, 1),
        "news_count_24h": news_count,
        "top_stocks": top_stocks,
        "momentum": "rising" if price_signal > 0.5 else ("falling" if price_signal < -0.5 else "stable"),
    }


async def run_theme_scoring() -> None:
    """Score all themes and upsert into theme_state. Called by APScheduler every 10 min."""
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence import ThemeState
    from sqlalchemy import select

    log.info("theme_worker.start")
    results: list[tuple[str, dict]] = []

    for theme, tickers in THEMES.items():
        scores = await _score_theme(theme, tickers)
        results.append((theme, scores))
        await asyncio.sleep(0.1)

    try:
        async with AsyncSessionLocal() as db:
            for theme, s in results:
                existing = (await db.execute(
                    select(ThemeState).where(ThemeState.theme == theme)
                )).scalar_one_or_none()

                if existing:
                    existing.score = s["score"]
                    existing.momentum = s["momentum"]
                    existing.top_stocks = s["top_stocks"]
                    existing.price_signal = s["price_signal"]
                    existing.news_signal = s["news_signal"]
                    existing.news_count_24h = s["news_count_24h"]
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    db.add(ThemeState(
                        id=str(uuid4()),
                        theme=theme,
                        score=s["score"],
                        momentum=s["momentum"],
                        top_stocks=s["top_stocks"],
                        price_signal=s["price_signal"],
                        news_signal=s["news_signal"],
                        news_count_24h=s["news_count_24h"],
                    ))
            await db.commit()
        log.info("theme_worker.done", themes=len(results))
    except Exception as exc:
        log.error("theme_worker.save_error", error=str(exc))

    try:
        from app.core.redis import cache_set
        ranked = sorted(results, key=lambda x: x[1]["score"], reverse=True)
        await cache_set("market:themes:ranked", [
            {"theme": t, **s} for t, s in ranked
        ], 700)
    except Exception:
        pass
