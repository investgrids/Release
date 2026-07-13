"""
PriceThresholdMonitor — polls key instruments every 2 min.
Generates a RawEvent on the EventIngestionBus when a threshold is breached.
"""
from __future__ import annotations

import asyncio
import structlog
from datetime import datetime, timezone
from uuid import uuid4

log = structlog.get_logger(__name__)

_INSTRUMENTS = {
    "NIFTY":     {"ticker": "^NSEI",     "name": "Nifty 50",    "threshold_pct": 0.75},
    "BANKNIFTY": {"ticker": "^NSEBANK",  "name": "Bank Nifty",  "threshold_pct": 1.0},
    "USDINR":    {"ticker": "USDINR=X",  "name": "USD/INR",     "threshold_pct": 0.3},
    "BRENT":     {"ticker": "BZ=F",      "name": "Brent Crude", "threshold_pct": 1.5},
    "VIX":       {"ticker": "^INDIAVIX", "name": "India VIX",   "threshold_pct": 5.0},
}

_last_prices: dict[str, float] = {}


def _fetch_price_sync(ticker: str) -> float | None:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        return float(info.last_price or 0) or None
    except Exception:
        return None


async def run_price_monitor_cycle() -> None:
    """Called by APScheduler every 2 minutes."""
    from app.services.intelligence.event_bus import get_event_bus, RawEvent

    bus = get_event_bus()
    loop = asyncio.get_event_loop()

    for key, cfg in _INSTRUMENTS.items():
        try:
            price = await loop.run_in_executor(None, _fetch_price_sync, cfg["ticker"])
            if price is None:
                continue

            if key in _last_prices and _last_prices[key] > 0:
                last = _last_prices[key]
                change_pct = ((price - last) / last) * 100

                if abs(change_pct) >= cfg["threshold_pct"]:
                    verb = "surged" if change_pct > 0 else "fell"
                    headline = (
                        f"{cfg['name']} {verb} {abs(change_pct):.1f}% "
                        f"to {price:,.1f}"
                    )
                    await bus.push(RawEvent(
                        id=str(uuid4()),
                        headline=headline,
                        summary=(
                            f"{cfg['name']} moved {change_pct:+.2f}% from "
                            f"{last:,.1f} to {price:,.1f}. "
                            "Automated price threshold alert."
                        ),
                        source="price",
                        raw_impact=min(10.0, abs(change_pct) * 2),
                        meta={"instrument": key, "change_pct": change_pct, "price": price},
                    ))
                    log.info(
                        "price_monitor.breach",
                        instrument=key, change_pct=round(change_pct, 2),
                    )

            _last_prices[key] = price

        except Exception as exc:
            log.warning("price_monitor.error", instrument=key, error=str(exc))

        await asyncio.sleep(0.3)
