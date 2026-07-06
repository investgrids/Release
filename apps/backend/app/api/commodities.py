"""Commodities & Energy prices — yfinance + AI insights."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import structlog
from fastapi import APIRouter

from app.cache import get as cache_get, set as cache_set

log = structlog.get_logger(__name__)
router = APIRouter()

_PRICES_TTL   = 120   # 2 min
_INSIGHTS_TTL = 1800  # 30 min

_METALS_DEF = [
    {"id": "gold",     "name": "Gold",     "ticker": "GC=F", "unit": "USD / oz"},
    {"id": "silver",   "name": "Silver",   "ticker": "SI=F", "unit": "USD / oz"},
    {"id": "copper",   "name": "Copper",   "ticker": "HG=F", "unit": "USD / lb"},
    {"id": "platinum", "name": "Platinum", "ticker": "PL=F", "unit": "USD / oz"},
]

_ENERGY_DEF = [
    {"id": "brent",  "name": "Crude Oil (Brent)",     "ticker": "BZ=F", "unit": "USD / bbl"},
    {"id": "wti",    "name": "Crude Oil (WTI)",        "ticker": "CL=F", "unit": "USD / bbl"},
    {"id": "natgas", "name": "Natural Gas",            "ticker": "NG=F", "unit": "USD / MMBtu"},
    {"id": "petrol", "name": "India Petrol (Retail)", "ticker": None,   "unit": "INR / Litre"},
]

_FB_METALS = [
    {"id": "gold",     "name": "Gold",     "unit": "USD / oz",  "price": "2,427.50", "change": "+28.40", "pct": 1.18,  "positive": True,  "high": "2,438.70", "low": "2,392.10", "chart": []},
    {"id": "silver",   "name": "Silver",   "unit": "USD / oz",  "price": "28.65",    "change": "+0.42",  "pct": 1.49,  "positive": True,  "high": "28.74",    "low": "28.10",    "chart": []},
    {"id": "copper",   "name": "Copper",   "unit": "USD / lb",  "price": "4.68",     "change": "+0.07",  "pct": 1.52,  "positive": True,  "high": "4.71",     "low": "4.59",     "chart": []},
    {"id": "platinum", "name": "Platinum", "unit": "USD / oz",  "price": "1,045.30", "change": "+9.10",  "pct": 0.88,  "positive": True,  "high": "1,051.80", "low": "1,028.40", "chart": []},
]

_FB_ENERGY = [
    {"id": "brent",  "name": "Crude Oil (Brent)",     "unit": "USD / bbl",   "price": "83.47",  "change": "+2.34", "pct": 2.89,  "positive": True,  "high": "83.92",  "low": "80.95",  "chart": []},
    {"id": "wti",    "name": "Crude Oil (WTI)",        "unit": "USD / bbl",   "price": "79.68",  "change": "+2.11", "pct": 2.72,  "positive": True,  "high": "80.12",  "low": "77.32",  "chart": []},
    {"id": "natgas", "name": "Natural Gas",            "unit": "USD / MMBtu", "price": "2.56",   "change": "+0.05", "pct": 2.00,  "positive": True,  "high": "2.58",   "low": "2.47",   "chart": []},
    {"id": "petrol", "name": "India Petrol (Retail)", "unit": "INR / Litre", "price": "103.19", "change": "-0.28", "pct": -0.27, "positive": False, "high": "103.45", "low": "102.85", "chart": []},
]

_FB_INSIGHTS = {
    "metals": {
        "impact": "High Impact",
        "items": [
            {"text": "Gold is up due to safe-haven demand amid escalating geopolitical tensions.", "impact": "Bullish"},
            {"text": "Silver and Platinum are gaining as industrial demand remains strong despite global uncertainties.", "impact": "Moderately Bullish"},
            {"text": "Copper prices rising due to supply concerns and strong demand from China.", "impact": "Bullish"},
        ],
    },
    "energy": {
        "impact": "Very High Impact",
        "items": [
            {"text": "Crude oil prices are up sharply due to supply risks from geopolitical tensions in the Middle East.", "impact": "Very Bullish"},
            {"text": "Petrol and diesel prices likely to remain elevated in the short term. Monitor OPEC+ decisions.", "impact": "Bullish"},
            {"text": "Natural gas prices inch higher as US inventory falls and summer demand expectations rise.", "impact": "Moderately Bullish"},
        ],
    },
    "key_drivers_metals": [
        {"label": "Middle East Tensions", "level": "High"},
        {"label": "US Dollar Index",      "level": "Moderate"},
        {"label": "China Manufacturing",  "level": "Moderate"},
        {"label": "Interest Rate Outlook","level": "Low"},
    ],
    "key_drivers_energy": [
        {"label": "OPEC+ Decisions",      "level": "High"},
        {"label": "Geopolitical Risk",    "level": "High"},
        {"label": "US Crude Inventory",   "level": "Moderate"},
        {"label": "Summer Demand",        "level": "Moderate"},
    ],
    "daily_summary": (
        "War-related tensions continue to support safe-haven assets like gold. "
        "Crude oil remains volatile with upside risk. Monitor geopolitical news, "
        "OPEC+ updates, and USD movement for near-term price direction."
    ),
}


def _fetch_one_sync(defn: dict, brent_price: float | None = None) -> dict:
    """Fetch price + 7-day sparkline for one commodity (blocking, runs in executor)."""
    import math
    import yfinance as yf
    from app.services.market_data import _fmt_price, _fetch_history

    item: dict = {"id": defn["id"], "name": defn["name"], "unit": defn["unit"], "chart": []}

    if defn["ticker"] is None:
        # India Petrol: estimate from live Brent crude price
        if brent_price:
            inr_usd   = 84.0
            petrol    = round(brent_price * inr_usd / 159 * 2.4, 2)
            item.update({
                "price": _fmt_price(petrol), "change": "Live",
                "pct": 0.0, "positive": True,
                "high": _fmt_price(petrol * 1.002), "low": _fmt_price(petrol * 0.998),
            })
        else:
            item.update({"price": "103.19", "change": "—", "pct": 0.0,
                         "positive": True, "high": "103.45", "low": "102.85"})
        return item

    try:
        t    = yf.Ticker(defn["ticker"])
        info = t.fast_info
        price      = float(info.last_price)
        prev_close = float(info.previous_close)
        change     = price - prev_close
        pct        = (change / prev_close) * 100 if prev_close else 0.0
        try:
            high = float(info.day_high)
            low  = float(info.day_low)
        except Exception:
            high = price * 1.003
            low  = price * 0.997

        item.update({
            "price":    _fmt_price(price),
            "change":   f"{'+' if change >= 0 else ''}{change:,.2f}",
            "pct":      round(pct, 2),
            "positive": change >= 0,
            "high":     _fmt_price(high),
            "low":      _fmt_price(low),
        })
        hist = _fetch_history(defn["ticker"], "7d", "1d")
        item["chart"] = [{"label": h["label"], "value": h["value"]} for h in hist]

    except Exception:
        item.update({"price": "—", "change": "—", "pct": 0.0,
                     "positive": True, "high": "—", "low": "—"})
    return item


async def _fetch_group(defs: list[dict]) -> list[dict]:
    loop    = asyncio.get_running_loop()
    results: list[dict] = []
    brent_price: float | None = None

    for defn in defs:
        data = await loop.run_in_executor(None, _fetch_one_sync, defn, brent_price)
        if defn["id"] == "brent" and data.get("price") not in ("—", None):
            try:
                brent_price = float(data["price"].replace(",", ""))
            except Exception:
                pass
        results.append(data)
    return results


async def _get_insights(metals: list[dict], energy: list[dict]) -> dict:
    from app.services.ai_service import _call_with_fallback

    cached = await cache_get("commodities:insights:v3")
    if cached:
        return cached

    def line(c: dict) -> str:
        sign = "+" if c.get("positive") else ""
        return f"  {c['name']}: {c['price']} {c['unit']} ({sign}{c.get('pct', 0):.2f}%)"

    m_lines = "\n".join(line(c) for c in metals if c.get("price") != "—")
    e_lines = "\n".join(line(c) for c in energy if c.get("price") != "—")

    prompt = (
        f"Global commodity prices:\nMetals:\n{m_lines}\nEnergy:\n{e_lines}\n\n"
        "Generate AI insights for Indian investors. Return ONLY this JSON:\n"
        '{"metals":{"impact":"High Impact",'
        '"items":[{"text":"...","impact":"Bullish"},{"text":"...","impact":"Moderately Bullish"},{"text":"...","impact":"Neutral"}]},'
        '"energy":{"impact":"Very High Impact",'
        '"items":[{"text":"...","impact":"Very Bullish"},{"text":"...","impact":"Bullish"},{"text":"...","impact":"Moderately Bullish"}]},'
        '"key_drivers_metals":[{"label":"...","level":"High"},{"label":"...","level":"Moderate"},{"label":"...","level":"Moderate"},{"label":"...","level":"Low"}],'
        '"key_drivers_energy":[{"label":"...","level":"High"},{"label":"...","level":"High"},{"label":"...","level":"Moderate"},{"label":"...","level":"Low"}],'
        '"daily_summary":"2-sentence summary for Indian investors."}'
    )

    raw = await _call_with_fallback(prompt, max_tokens=700)
    if raw:
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = re.sub(r"^```(?:json)?\s*", "", clean)
                clean = re.sub(r"\s*```$", "", clean).strip()
            insights = json.loads(clean)
            await cache_set("commodities:insights:v3", insights, _INSIGHTS_TTL)
            return insights
        except Exception:
            pass

    await cache_set("commodities:insights:v3", _FB_INSIGHTS, _INSIGHTS_TTL)
    return _FB_INSIGHTS


@router.get("/")
async def get_commodities():
    cached = await cache_get("commodities:prices:v2")
    if cached:
        return cached

    metals_raw, energy_raw = await asyncio.gather(
        _fetch_group(_METALS_DEF),
        _fetch_group(_ENERGY_DEF),
    )

    metals = metals_raw if any(m["price"] != "—" for m in metals_raw) else _FB_METALS
    energy = energy_raw if any(e["price"] != "—" for e in energy_raw) else _FB_ENERGY

    insights = await _get_insights(metals, energy)
    result   = {"metals": metals, "energy": energy, "insights": insights, "updated": "Live"}

    await cache_set("commodities:prices:v2", result, _PRICES_TTL)
    return result
