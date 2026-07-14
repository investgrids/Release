"""
Opening Prediction Service — Tomorrow's NSE Nifty 50 opening prediction.

Four-layer pipeline:
  1. Signal Layer   — live data: Gift Nifty, VIX, FII, Crude, USD/INR, US/Asian futures
  2. Event Layer    — calendar events today + tomorrow + MIE breaking signals
  3. Historical Layer — similar past setups from historical_memory DB
  4. AI Reasoning   — LLM synthesises all layers → structured probability prediction
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_CACHE: dict[str, tuple[float, Any]] = {}
_TTL = 1800  # 30 minutes


def _cget(key: str) -> Any | None:
    e = _CACHE.get(key)
    return e[1] if e and time.time() - e[0] < _TTL else None


def _cset(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)


def _ist_today() -> str:
    ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    return ist.strftime("%Y-%m-%d")


def _ist_tomorrow() -> str:
    ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30, days=1)
    return ist.strftime("%Y-%m-%d")


async def build_opening_prediction(db) -> dict:
    cached = _cget("opening_prediction")
    if cached:
        return cached

    signals    = await _gather_signals()
    events     = await _gather_events(db)
    historical = await _gather_historical(signals, events)
    prediction = await _run_ai(signals, events, historical)

    result = {
        "signals":         signals,
        "events":          events,
        "historical":      historical,
        "prediction":      prediction,
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "cache_ttl_seconds": _TTL,
    }
    _cset("opening_prediction", result)
    return result


def _fetch_signals_sync() -> dict:
    """Sync yfinance calls — run in executor so we don't block the event loop."""
    import math
    try:
        import yfinance as yf
    except ImportError:
        return {}

    def _quote(ticker: str) -> dict | None:
        try:
            fi    = yf.Ticker(ticker).fast_info
            price = float(fi.last_price or 0)
            prev  = float(fi.previous_close or 0)
            if not price or not prev:
                return None
            change = price - prev
            pct    = (change / prev) * 100
            return {"price": price, "change": change, "pct_float": pct,
                    "pct": f"{'+' if pct >= 0 else ''}{pct:.2f}%",
                    "positive": change >= 0}
        except Exception:
            return None

    def _fmt(q: dict | None, name: str) -> dict:
        if not q:
            return {"name": name, "value": "—", "pct": "—", "positive": None}
        return {
            "name":     name,
            "value":    f"{q['price']:,.0f}" if q["price"] > 1000 else f"{q['price']:.2f}",
            "pct":      q["pct"],
            "positive": q["positive"],
        }

    MARKETS = [
        ("^NSEI", "Nifty 50"), ("^BSESN", "Sensex"),
        ("^NSEBANK", "Bank Nifty"), ("^INDIAVIX", "India VIX"),
        ("ES=F", "S&P 500 Fut."), ("NQ=F", "Nasdaq Fut."),
        ("YM=F", "Dow Fut."),
        ("^N225", "Nikkei"), ("^HSI", "Hang Seng"),
        ("FTSE=F", "FTSE"), ("^GDAXI", "DAX"),
        ("BZ=F", "Brent"), ("GC=F", "Gold"),
        ("USDINR=X", "USD/INR"),
        ("^NSEBANK", "BNF"),
    ]
    quotes: dict[str, dict | None] = {}
    for ticker, name in MARKETS:
        if ticker not in quotes:
            quotes[ticker] = _quote(ticker)

    nifty_q  = quotes.get("^NSEI")
    bnf_q    = quotes.get("^NSEBANK")
    vix_q    = quotes.get("^INDIAVIX")
    sp_q     = quotes.get("ES=F")
    nq_q     = quotes.get("NQ=F")
    ym_q     = quotes.get("YM=F")
    nikkei_q = quotes.get("^N225")
    hsi_q    = quotes.get("^HSI")
    brent_q  = quotes.get("BZ=F")
    usd_q    = quotes.get("USDINR=X")

    us_futures = [_fmt(sp_q, "S&P 500 Fut."), _fmt(nq_q, "Nasdaq Fut."), _fmt(ym_q, "Dow Fut.")]
    asian      = [_fmt(nikkei_q, "Nikkei"), _fmt(hsi_q, "Hang Seng")]
    all_mkts   = us_futures + asian

    pos_count  = sum(1 for m in all_mkts if m.get("positive"))
    total      = len([m for m in all_mkts if m.get("positive") is not None]) or 1
    global_pct = int(pos_count / total * 100)

    vix_float = round(vix_q["price"], 2) if vix_q else 15.0
    vix_level = "LOW" if vix_float < 14 else "ELEVATED" if vix_float > 20 else "MODERATE"
    vix_interp = ("Calm open, low volatility" if vix_float < 14
                  else "High volatility, wide swings possible" if vix_float > 20
                  else "Moderate volatility")

    crude_dir = ("falling" if brent_q and not brent_q["positive"]
                 else "rising" if brent_q and brent_q["positive"]
                 else "stable")

    gift_value = "—"
    gift_pct   = "—"
    gift_pos   = True
    if nifty_q:
        # Use Nifty spot as proxy when futures ticker unavailable
        gift_value = f"{nifty_q['price']:,.0f}"
        gift_pct   = nifty_q["pct"]
        gift_pos   = nifty_q["positive"]

    return {
        "gift_nifty": {
            "value":    gift_value,
            "change":   gift_pct,
            "positive": gift_pos,
            "premium_pct": None,
            "opening_range": {},
        },
        "india_vix": {
            "value":          f"{vix_float}" if vix_q else "—",
            "float":          vix_float,
            "level":          vix_level,
            "interpretation": vix_interp,
        },
        "bank_nifty": {
            "value":    _fmt(bnf_q, "Bank Nifty")["value"],
            "change":   _fmt(bnf_q, "Bank Nifty")["pct"],
            "positive": bnf_q["positive"] if bnf_q else None,
        },
        "usd_inr": {
            "value":    _fmt(usd_q, "USD/INR")["value"],
            "positive": (not usd_q["positive"]) if usd_q else None,  # rupee weakens when USD/INR rises
        },
        "brent_crude": {
            "value":     _fmt(brent_q, "Brent")["value"],
            "change":    _fmt(brent_q, "Brent")["pct"],
            "positive":  brent_q["positive"] if brent_q else None,
            "direction": crude_dir,
        },
        "fii": {"net": None, "available": False, "buying": None},
        "us_futures":       us_futures,
        "asian_markets":    asian,
        "european_markets": [],
        "global_sentiment": {
            "positive_count": pos_count,
            "total":          total,
            "pct_positive":   global_pct,
            "label": "Bullish" if global_pct >= 60 else "Mixed" if global_pct >= 40 else "Bearish",
        },
        "crude_trend": crude_dir,
    }


async def _gather_signals() -> dict:
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        # Try using the cached enhanced premarket data from the market API
        from app.api.market import _cached_sync, _fetch_enhanced_premarket, _fetch_fii_dii
        enhanced = await loop.run_in_executor(
            None, lambda: _cached_sync("pm_enh", 900, _fetch_enhanced_premarket)
        )
        fii_dii = await loop.run_in_executor(
            None, lambda: _cached_sync("fii_dii", 21600, _fetch_fii_dii)
        )
        from app.services.market_data import get_premarket_data
        base = await get_premarket_data()
    except Exception as exc:
        log.warning("opening_prediction.signals_premarket_error", error=str(exc))
        try:
            raw = await loop.run_in_executor(None, _fetch_signals_sync)
            return raw
        except Exception as exc2:
            log.warning("opening_prediction.signals_direct_error", error=str(exc2))
            return {
                "gift_nifty": {"value": "—", "change": "—", "positive": True, "premium_pct": None, "opening_range": {}},
                "india_vix": {"value": "—", "float": 15.0, "level": "MODERATE", "interpretation": ""},
                "bank_nifty": {"value": "—", "change": "—", "positive": None},
                "usd_inr": {"value": "—", "positive": None},
                "brent_crude": {"value": "—", "change": "—", "positive": None, "direction": "stable"},
                "fii": {"net": None, "available": False, "buying": None},
                "us_futures": [], "asian_markets": [], "european_markets": [],
                "global_sentiment": {"positive_count": 0, "total": 1, "pct_positive": 50, "label": "Mixed"},
                "crude_trend": "stable",
            }

    gift       = enhanced.get("gift_nifty", {})
    vix        = enhanced.get("india_vix", {})
    banknifty  = enhanced.get("banknifty", {})
    currencies = enhanced.get("currencies", [])
    us_futures = enhanced.get("us_futures", [])
    european   = enhanced.get("european", [])
    asian      = base.get("asian", [])
    comms      = base.get("commodities", [])
    fii_net    = fii_dii.get("fii_net") if fii_dii.get("available") else None

    usd_inr = next((c for c in currencies if "USD" in c.get("name", "")), None)
    crude   = next((c for c in comms if "Brent" in c.get("name", "")), None)

    try:
        vix_float = float(str(vix.get("value", "15")).replace(",", ""))
    except (ValueError, TypeError):
        vix_float = 15.0

    vix_level = "LOW" if vix_float < 14 else "ELEVATED" if vix_float > 20 else "MODERATE"

    all_markets = asian + us_futures + european
    pos_count   = sum(1 for m in all_markets if m.get("positive"))
    total       = len(all_markets) or 1
    global_pct  = int(pos_count / total * 100)

    crude_dir = "rising" if crude and crude.get("positive") else "falling" if crude else "stable"

    return {
        "gift_nifty": {
            "value":        gift.get("value", "—"),
            "change":       gift.get("pct", "—"),
            "positive":     bool(gift.get("positive", True)),
            "premium_pct":  gift.get("premium_pct"),
            "opening_range": gift.get("opening_range", {}),
        },
        "india_vix": {
            "value":          vix.get("value", "—"),
            "float":          vix_float,
            "level":          vix_level,
            "interpretation": vix.get("interpretation", ""),
        },
        "bank_nifty": {
            "value":    banknifty.get("value", "—"),
            "change":   banknifty.get("pct", "—"),
            "positive": bool(banknifty.get("positive", True)),
        },
        "usd_inr": {
            "value":    usd_inr["value"] if usd_inr else "—",
            "positive": usd_inr.get("positive") if usd_inr else None,
        },
        "brent_crude": {
            "value":     crude["value"] if crude else "—",
            "change":    crude.get("change_str", "—") if crude else "—",
            "positive":  crude.get("positive") if crude else None,
            "direction": crude_dir,
        },
        "fii": {
            "net":       fii_net,
            "available": bool(fii_dii.get("available", False)),
            "buying":    (fii_net >= 0) if fii_net is not None else None,
        },
        "us_futures":       us_futures[:3],
        "asian_markets":    asian[:4],
        "european_markets": european[:3],
        "global_sentiment": {
            "positive_count": pos_count,
            "total":          total,
            "pct_positive":   global_pct,
            "label": "Bullish" if global_pct >= 60 else "Mixed" if global_pct >= 40 else "Bearish",
        },
        "crude_trend": crude_dir,
    }


async def _gather_events(db) -> dict:
    from sqlalchemy import select
    from app.db.models_legacy import CalendarEvent

    today_str    = _ist_today()
    tomorrow_str = _ist_tomorrow()

    try:
        rows = (await db.execute(select(CalendarEvent))).scalars().all()
    except Exception:
        rows = []

    today_events:    list[dict] = []
    tomorrow_events: list[dict] = []

    for row in rows:
        try:
            d   = datetime.strptime(row.date.strip(), "%b %d, %Y").date()
            ev  = {"title": row.title, "category": row.category, "description": row.description}
            ds  = d.strftime("%Y-%m-%d")
            if ds == today_str:
                today_events.append(ev)
            elif ds == tomorrow_str:
                tomorrow_events.append(ev)
        except Exception:
            pass

    mie_signals: list[dict] = []
    try:
        from app.services.intelligence.engine import get_mie_state
        mie = await get_mie_state()
        for ev in (mie.get("top_events") or [])[:3]:
            mie_signals.append({
                "title":   ev.get("event", ev.get("title", "")),
                "urgency": ev.get("urgency", 50),
            })
    except Exception:
        pass

    return {
        "today":       today_events[:5],
        "tomorrow":    tomorrow_events[:5],
        "mie_signals": mie_signals[:3],
    }


async def _gather_historical(signals: dict, events: dict) -> dict:
    from app.services.historical_memory_service import find_similar_events

    global_lbl = signals["global_sentiment"]["label"]
    crude_dir  = signals["crude_trend"]

    sentiment    = "bullish" if global_lbl == "Bullish" else "bearish" if global_lbl == "Bearish" else "neutral"
    market_regime = "bull" if global_lbl == "Bullish" else "bear" if global_lbl == "Bearish" else "recovery"

    # Detect event category from calendar
    category = None
    for ev in (events.get("today", []) + events.get("tomorrow", [])):
        t = ev.get("title", "").lower()
        c = ev.get("category", "").lower()
        if "rbi" in t or "monetary" in t or "repo" in t:
            category = "Monetary Policy"; break
        if "earning" in t or "result" in t or "q1" in t or "q2" in t or "q3" in t or "q4" in t:
            category = "Corporate Results"; break
        if "budget" in t or c == "government":
            category = "Union Budget"; break
        if c == "global":
            category = "Global Market Shock"; break

    query: dict = {
        "sentiment":          sentiment,
        "market_regime":      market_regime,
        "crude_trend":        crude_dir,
        "interest_rate_trend": "stable",
    }
    if category:
        query["category"] = category

    similar = await find_similar_events(query, limit=5, min_similarity=20.0)

    nifty_1d_vals = [e["nifty_1d"] for e in similar if e.get("nifty_1d") is not None]
    avg_1d        = round(sum(nifty_1d_vals) / len(nifty_1d_vals), 2) if nifty_1d_vals else None
    bullish_count = sum(1 for v in nifty_1d_vals if v > 0)

    return {
        "similar_events":          similar[:3],
        "count":                   len(similar),
        "avg_nifty_1d":            avg_1d,
        "bullish_sessions":        bullish_count,
        "total_sessions":          len(nifty_1d_vals),
        "historical_accuracy_hint": (
            f"{bullish_count} of {len(nifty_1d_vals)} similar setups had positive next-day moves"
            if nifty_1d_vals else None
        ),
    }


async def _run_ai(signals: dict, events: dict, historical: dict) -> dict:
    from app.services.ai_service import _call_with_fallback

    gift  = signals["gift_nifty"]
    vix   = signals["india_vix"]
    bnf   = signals["bank_nifty"]
    usd   = signals["usd_inr"]
    crude = signals["brent_crude"]
    fii   = signals["fii"]
    glo   = signals["global_sentiment"]

    signal_lines = [
        f"Gift Nifty: {gift['value']} ({gift['change']}) — {'Premium' if gift['positive'] else 'Discount'} to spot",
        f"India VIX: {vix['value']} — {vix['level']} volatility, {vix['interpretation']}",
        f"Bank Nifty Futures: {bnf['value']} ({bnf['change']})",
        f"USD/INR: {usd['value']} ({'Rupee weakening' if usd.get('positive') else 'Rupee holding firm'})",
        f"Brent Crude: {crude['value']} ({crude['change']}) — trend {crude['direction']}",
    ]
    if fii["available"] and fii["net"] is not None:
        sign = "+" if fii["net"] >= 0 else ""
        signal_lines.append(
            f"FII previous session: {sign}₹{fii['net']:,.0f}Cr — {'Buying' if fii['buying'] else 'Selling'}"
        )
    for m in signals["us_futures"][:3]:
        signal_lines.append(f"{m['name']}: {m.get('value','—')} ({m.get('pct','—')}) {'↑' if m.get('positive') else '↓'}")
    for m in signals["asian_markets"][:3]:
        signal_lines.append(f"{m.get('name','Asia')}: {m.get('value','—')} ({m.get('pct','—')}) {'↑' if m.get('positive') else '↓'}")
    signal_lines.append(
        f"Global sentiment: {glo['positive_count']}/{glo['total']} markets positive → {glo['label']}"
    )

    event_lines = []
    if events["today"]:
        event_lines.append("Today: " + ", ".join(e["title"] for e in events["today"][:3]))
    if events["tomorrow"]:
        event_lines.append("Tomorrow: " + ", ".join(e["title"] for e in events["tomorrow"][:3]))
    if events["mie_signals"]:
        event_lines.append("Breaking signals: " + ", ".join(e["title"] for e in events["mie_signals"][:2]))
    if not event_lines:
        event_lines.append("No major events in the next 24 hours.")

    hist_lines = []
    if historical.get("similar_events"):
        hist_lines.append(f"Found {historical['count']} similar historical setups.")
        if historical["avg_nifty_1d"] is not None:
            hist_lines.append(f"Average Nifty next-day move: {historical['avg_nifty_1d']:+.2f}%")
        if historical["historical_accuracy_hint"]:
            hist_lines.append(historical["historical_accuracy_hint"])
        for ev in historical["similar_events"][:2]:
            nd = ev.get("nifty_1d")
            nd_str = f"{nd:+.1f}%" if nd is not None else "N/A"
            hist_lines.append(
                f"  • {ev['event_title']} ({ev.get('event_date','')}): 1d {nd_str}"
            )
    else:
        hist_lines.append("No closely matching historical setups found.")

    prompt = (
        "Predict tomorrow's NSE Nifty 50 market opening based on the following data.\n\n"
        "SIGNAL LAYER:\n" + "\n".join(f"  • {l}" for l in signal_lines) + "\n\n"
        "EVENT LAYER:\n" + "\n".join(f"  • {l}" for l in event_lines) + "\n\n"
        "HISTORICAL CONTEXT:\n" + "\n".join(f"  {l}" for l in hist_lines) + "\n\n"
        "Nifty 50 previous close: ~24,300 points.\n\n"
        "Task:\n"
        "  1. Identify dominant direction (Positive / Negative / Neutral)\n"
        "  2. Note any CONFLICTING signals between layers\n"
        "  3. Set confidence 45-90% based on signal agreement and event risk\n"
        "  4. Give expected opening range in Nifty POINTS (e.g., +25 to +60, or -50 to -15)\n"
        "  5. List exactly 3 primary_drivers (specific data points from above)\n"
        "  6. List exactly 2 risks\n"
        "  7. Write 2-sentence reasoning explaining the prediction\n\n"
        "Respond ONLY with this JSON (no markdown, no extra text):\n"
        '{\n'
        '  "direction": "Positive",\n'
        '  "confidence": 68,\n'
        '  "range_low": 20,\n'
        '  "range_high": 55,\n'
        '  "primary_drivers": ["...", "...", "..."],\n'
        '  "risks": ["...", "..."],\n'
        '  "conflicting_signals": ["..."],\n'
        '  "reasoning": "Two sentences here.",\n'
        '  "historical_note": "One sentence or null",\n'
        '  "uncertainty_note": "One sentence or null"\n'
        '}'
    )

    system = (
        "You are a senior NSE equity strategist. You give probability-based Nifty opening predictions. "
        "Respond ONLY with valid JSON — no markdown fences, no extra text."
    )

    raw = await _call_with_fallback(prompt, system, max_tokens=700)

    if not raw:
        return _fallback_prediction(signals)

    try:
        cleaned = re.sub(r"```[a-z]*\n?|```", "", raw).strip()
        # Find first { ... }
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        data = json.loads(m.group(0) if m else cleaned)
        return {
            "direction":           data.get("direction", "Neutral"),
            "confidence":          max(45, min(92, int(data.get("confidence", 60)))),
            "range_low":           int(data.get("range_low", -20)),
            "range_high":          int(data.get("range_high", 30)),
            "primary_drivers":     (data.get("primary_drivers") or [])[:3],
            "risks":               (data.get("risks") or [])[:3],
            "conflicting_signals": (data.get("conflicting_signals") or [])[:3],
            "reasoning":           data.get("reasoning", ""),
            "historical_note":     data.get("historical_note"),
            "uncertainty_note":    data.get("uncertainty_note"),
            "ai_generated":        True,
        }
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        log.warning("opening_prediction.parse_error", raw=raw[:200])
        return _fallback_prediction(signals)


def _fallback_prediction(signals: dict) -> dict:
    glo  = signals["global_sentiment"]
    gift = signals["gift_nifty"]
    vix  = signals["india_vix"]

    bull      = glo["pct_positive"]
    direction = "Positive" if bull >= 60 and gift["positive"] else "Negative" if bull < 40 else "Neutral"
    confidence = max(50, min(78, int(bull * 0.6 + 32)))

    base = 25 if direction == "Positive" else -45 if direction == "Negative" else -10
    return {
        "direction":  direction,
        "confidence": confidence,
        "range_low":  base,
        "range_high": base + 40,
        "primary_drivers": [
            f"Gift Nifty {'positive' if gift['positive'] else 'negative'} at {gift['value']}",
            f"India VIX {vix['value']} ({vix['level'].lower()} volatility)",
            f"{glo['positive_count']} of {glo['total']} global markets positive",
        ],
        "risks":               ["AI reasoning unavailable — signal-only estimate", "Monitor pre-open session carefully"],
        "conflicting_signals": [],
        "reasoning":           (
            f"{glo['positive_count']} of {glo['total']} global markets are currently positive. "
            f"Gift Nifty is {'trading positive' if gift['positive'] else 'under pressure'}, "
            f"suggesting a {'positive' if direction == 'Positive' else 'cautious'} opening."
        ),
        "historical_note":  None,
        "uncertainty_note": "Prediction based on signal formula only — AI layer unavailable.",
        "ai_generated":     False,
    }
