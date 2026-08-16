"""
Opening Prediction Service — Tomorrow's NSE Nifty 50 opening prediction.

Four-layer pipeline:
  1. Signal Layer   — live data: Gift Nifty, VIX, FII, Crude, USD/INR, US/Asian futures
  2. Event Layer    — calendar events today + tomorrow + MIE breaking signals
  3. Historical Layer — similar past setups from historical_memory DB
  4. AI Reasoning   — LLM synthesises all layers → structured probability prediction

Phase 1C addition: an OPTIONAL fifth input, `weekend_context`
(app.services.weekend_intelligence.context.WeekendContext) — additive
only (brief §3/§13). When None (every caller that doesn't pass one,
and every call on a day with no valid target-session snapshot), this
module's behavior is byte-for-byte identical to before Phase 1C. When
present, it contributes in two independent, deliberately different ways:

  1. AI PATH (_run_ai): weekend context becomes one more labeled section
     in the SAME existing prompt/LLM call (no second generation call —
     brief §44) — the AI freely decides how much weight to give it,
     same as every other signal in the prompt today. Its influence on
     the AI's own output is therefore NOT separately decomposable; this
     is an inherent property of folding it into a free-form LLM call,
     not a Phase 1C shortcut.

  2. DETERMINISTIC SHADOW SCORE (_weekend_adjusted_score): the existing
     _fallback_prediction() arithmetic, extended by one small bounded
     term derived from weekend_context. Computed on EVERY call
     regardless of whether the AI path succeeds — cheap (no LLM, no
     network), and gives a clean, always-available
     base_score -> weekend_adjustment -> final_score triple. This is
     what `result["weekend_adjustment"]` reports; it is a diagnostic/
     explanatory lens, not a second competing prediction engine (brief
     §3: "must NOT create a second Monday prediction engine" — this
     triple never overrides `result["prediction"]`, it explains one
     input to it).
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.services.weekend_intelligence.context import WeekendContext

log = structlog.get_logger(__name__)

_CACHE: dict[str, tuple[float, Any]] = {}
_TTL = 1800  # 30 minutes

# Brief §17: "do not invent a large arbitrary weight... use a
# conservative contribution." 0.15 means a maximally-confident,
# maximally-directional weekend context (production_confidence=100)
# can move the deterministic signed score by at most 15 points out of
# its ~50-92 range — enough to be visible, never enough to flip a
# strongly-held Monday-fresh signal on its own (see
# _weekend_adjusted_score's docstring for the exact arithmetic).
_WEEKEND_BOUNDED_WEIGHT = 0.15

# Below this weekend production_confidence, the contribution is treated
# as statistically indistinguishable from noise and zeroed rather than
# applying a token adjustment that implies more precision than the
# underlying evidence supports.
_WEEKEND_MIN_CONFIDENCE_TO_APPLY = 15.0

_BIAS_TO_SIGN = {
    "strong_positive": 1.0, "positive": 1.0,
    "strong_negative": -1.0, "negative": -1.0,
    "mixed": 0.0, "neutral": 0.0,
}


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


async def build_opening_prediction(db, weekend_context: "WeekendContext | None" = None) -> dict:
    """weekend_context: optional (default None — every pre-existing
    caller gets byte-for-byte pre-Phase-1C behavior, see module
    docstring). Callers that want weekend-informed predictions must load
    one themselves via
    app.services.weekend_intelligence.context.get_weekend_context_for_session
    and pass it in — this function does not reach into Weekend
    Intelligence persistence itself (mirrors the same separation brief
    §10 requires of the context loader, applied symmetrically here)."""
    # Cache key MUST vary with weekend_context identity — the old
    # single-slot key "opening_prediction" would otherwise let a
    # weekend-informed result leak into a caller that passed no context
    # (or vice versa) for up to 30 minutes. A real bug caught before it
    # shipped: this module's cache is a single process-local dict shared
    # across ALL 3 existing callers (market.py, daily_brief_intelligence.py,
    # fact_registry.py), most of which will NOT be updated to pass
    # weekend_context in this phase (see final report §D) — they must
    # keep getting the no-context result, not whatever the last caller
    # who DID pass context happened to produce.
    cache_key = "opening_prediction"
    if weekend_context is not None:
        cache_key = f"opening_prediction:wi:{weekend_context.snapshot_id}:{weekend_context.snapshot_version}"

    cached = _cget(cache_key)
    if cached:
        return cached

    signals    = await _gather_signals()
    events     = await _gather_events(db)
    historical = await _gather_historical(signals, events)

    # Deterministic shadow triple — always computed, zero extra cost
    # (pure arithmetic over `signals`, no LLM/network call). This is
    # what answers "existing Monday score -> weekend contribution ->
    # final Monday score" regardless of whether the AI path below
    # succeeds. See _weekend_adjusted_score's docstring for the exact
    # formula and app.services.opening_prediction_service module
    # docstring for why this is a diagnostic lens, not a second engine.
    weekend_adjustment = _weekend_adjusted_score(signals, weekend_context)

    prediction = await _run_ai(signals, events, historical, weekend_context, weekend_adjustment)

    result = {
        "signals":         signals,
        "events":          events,
        "historical":      historical,
        "prediction":      prediction,
        "weekend_adjustment": weekend_adjustment,
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "cache_ttl_seconds": _TTL,
    }
    if weekend_context is not None:
        # Brief §21/§22, minimal honest version: this engine has NO
        # existing per-company or per-sector Monday-fresh data source to
        # blend against (its own signals are index/macro-level only —
        # Gift Nifty, VIX, Bank Nifty, USD/INR, Brent, FII, futures — see
        # module docstring). Building a real "weekend candidate + Monday
        # fresh data = ranked watchlist" would mean inventing a new
        # per-company data pipeline, which brief §21 itself says not to
        # do ("do not build a separate stock-ranking engine unless
        # necessary"). So these are exposed plainly as weekend-derived
        # context, clearly separate from `prediction`, not silently
        # presented as if already cross-checked against fresh Monday
        # per-company data. The one place a genuine overlap exists —
        # Banking sector vs. the already-gathered Bank Nifty signal — is
        # noted inline rather than blended into a score, since Bank
        # Nifty's direction is already visible in `signals["bank_nifty"]`
        # for a reader to combine themselves.
        result["weekend_watchlist"] = {
            "companies": [
                {"symbol": s.id, "state": s.direction, "confidence": s.confidence}
                for s in weekend_context.top_company_signals[:12]
            ],
            "sectors": [
                {"sector": s.id, "direction": s.direction, "confidence": s.confidence}
                for s in weekend_context.top_sector_signals[:5]
            ],
            "note": (
                "Weekend-derived candidates, not yet cross-checked against Monday fresh per-company data "
                "(this engine has no per-company Monday data source). Banking sector overlaps with "
                f"signals.bank_nifty (positive={signals['bank_nifty'].get('positive')}) — compare manually."
            ),
        }
    _cset(cache_key, result)

    if weekend_context is not None:
        log.info(
            "weekend_context.applied" if weekend_adjustment["applied"] else "weekend_context.not_applied",
            target_trading_date=weekend_context.target_trading_date,
            snapshot_id=weekend_context.snapshot_id, snapshot_version=weekend_context.snapshot_version,
            status=weekend_context.status, production_confidence=weekend_context.production_confidence,
            base_score=weekend_adjustment["base_score"], adjustment=weekend_adjustment["adjustment"],
            final_score=weekend_adjustment["final_score"], reason=weekend_adjustment["reason"],
        )
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
    today_str    = _ist_today()
    tomorrow_str = _ist_tomorrow()

    try:
        # Phase 5A.9 — migrated off the dead legacy CalendarEvent table
        # (same reasoning as db/crud.py::get_calendar) onto the real,
        # live-ingested EconomicCalendarEvent table. legacy_adapter
        # returns rows shaped identically to the old ORM object, so the
        # strptime parsing immediately below is unchanged.
        from app.services.economic_calendar.legacy_adapter import get_legacy_shaped_calendar
        rows = await get_legacy_shaped_calendar(db)
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
        # Phase 1E integration-test finding: this imported a function
        # named get_mie_state, which has never existed in engine.py (the
        # real name is get_intelligence_state — refresh_mie_state is the
        # cache-writer, get_intelligence_state is the cache-or-compute
        # reader every other real caller, e.g. app/api/mie.py, actually
        # uses). The bare `except Exception: pass` below silently
        # swallowed the resulting ImportError on every single call since
        # this code was written, so mie_signals has always been empty in
        # practice — never caught because failing open (empty list) looks
        # identical to "no breaking signals right now." Discovered only
        # by actually calling _gather_events() end-to-end (Phase 1E's
        # integrated double-count test), not by any prior unit test,
        # which always exercised _weekend_prompt_lines with a hand-built
        # events dict instead of a real one from this function.
        from app.services.intelligence.engine import get_intelligence_state
        mie = await get_intelligence_state()
        for ev in (mie.get("top_events") or [])[:3]:
            mie_signals.append({
                # read_top_events()'s real key is "headline" — "event"/
                # "title" never existed on these rows either, a second,
                # compounding instance of the same root cause.
                "title":   ev.get("headline", ev.get("event", ev.get("title", ""))),
                "urgency": ev.get("urgency", 50),
                # Phase 1C: id was already present on read_top_events()'s
                # rows (engine.py) but not previously propagated here —
                # needed for the weekend double-count guard (see
                # _weekend_prompt_lines) to detect when the same Event
                # already surfaced through this MIE layer.
                "id":      ev.get("id"),
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


def _weekend_adjusted_score(signals: dict, weekend_context: "WeekendContext | None") -> dict:
    """The always-computed base_score -> adjustment -> final_score triple
    (brief §28's baseline comparison, and the single thing explicitly
    prioritized in review: 'Existing Monday score -> X, Weekend
    contribution -> +Y/-Y, Final Monday score -> Z').

    base_score is the EXISTING deterministic formula (_base_fallback_score
    below — byte-for-byte the pre-Phase-1C _fallback_prediction logic),
    expressed as one signed number: +confidence for Positive, -confidence
    for Negative, 0 for Neutral. This is the "existing Monday score" the
    review asked to see, computed from Monday-fresh signals only, weekend
    context never touches it.

    adjustment = weekend_sign * production_confidence * _WEEKEND_BOUNDED_WEIGHT
    (brief §17's example formula, using this module's real fallback
    formula as "existing engine mechanics" rather than inventing new
    scoring). With weight=0.15 and production_confidence in [0,100], the
    adjustment is bounded to [-15, +15] — small relative to base_score's
    ~50-92 range, which is WHY Monday-fresh data structurally wins (brief
    §15): a maximally-confident weekend context can nudge the score, it
    cannot flip a strongly-held Monday-fresh base_score on its own. This
    is precedence by construction (the weight ratio), not a special-cased
    override branch.

    Zeroed (adjustment=0, applied=False) when: no weekend_context: brief
    §13's "no valid context -> existing engine behavior"; status ==
    insufficient_evidence or overall_bias == neutral: brief §19 - no
    directional signal to contribute; production_confidence below
    _WEEKEND_MIN_CONFIDENCE_TO_APPLY: too weak to be more than noise.
    Never zeroed merely for status == degraded (brief §18) — a degraded
    snapshot's already-lower production_confidence naturally scales its
    own contribution down; no separate degraded-specific multiplier
    exists (or is needed) here.
    """
    base = _base_fallback_score(signals)
    base_sign = 1.0 if base["direction"] == "Positive" else -1.0 if base["direction"] == "Negative" else 0.0
    base_score = round(base_sign * base["confidence"], 1)

    result = {
        "applied": False, "base_direction": base["direction"], "base_score": base_score,
        "weekend_direction": None, "weekend_confidence": None,
        "adjustment": 0.0, "final_direction": base["direction"], "final_score": base_score,
        "reason": "no_weekend_context",
    }
    if weekend_context is None:
        return result

    if not weekend_context.has_directional_signal:
        result["reason"] = f"weekend status={weekend_context.status} bias={weekend_context.overall_bias} — no directional signal"
        return result

    if weekend_context.production_confidence < _WEEKEND_MIN_CONFIDENCE_TO_APPLY:
        result["reason"] = f"weekend production_confidence {weekend_context.production_confidence:.1f}% below floor {_WEEKEND_MIN_CONFIDENCE_TO_APPLY:.0f}%"
        return result

    weekend_sign = _BIAS_TO_SIGN.get(weekend_context.overall_bias, 0.0)
    adjustment = round(weekend_sign * weekend_context.production_confidence * _WEEKEND_BOUNDED_WEIGHT, 1)
    final_score = base_score + adjustment
    final_score = max(-92.0, min(92.0, final_score))

    if final_score >= 15:
        final_direction = "Positive"
    elif final_score <= -15:
        final_direction = "Negative"
    else:
        final_direction = "Neutral"

    return {
        "applied": True, "base_direction": base["direction"], "base_score": base_score,
        "weekend_direction": weekend_context.overall_bias,
        "weekend_confidence": round(weekend_context.production_confidence, 1),
        "adjustment": adjustment, "final_direction": final_direction, "final_score": round(final_score, 1),
        "reason": (
            f"weekend bias={weekend_context.overall_bias} "
            f"confidence={weekend_context.production_confidence:.0f}% -> adjustment {adjustment:+.1f}"
        ),
    }


def _weekend_prompt_lines(events: dict, weekend_context: "WeekendContext | None") -> list[str]:
    """Builds the WEEKEND CONTEXT LAYER prompt section (brief §16/§20) —
    synthesized aggregate state only, never raw evidence titles (brief
    §9/§14's structural double-count avoidance: MIE breaking signals
    below are individual headlines, this section is sector/company
    ROLLUPS, a different level of abstraction, so the same fact rarely
    reads as literally duplicated).

    Explicit double-count guard (brief §14/§38): when the Event Layer's
    MIE breaking signals and Weekend Intelligence's new-since-close
    developments share underlying Event ids, one instruction line is
    added telling the LLM not to treat them as independent confirmations
    — this is the part of double-count protection that source references
    make possible (WeekendContext.meaningful_development_event_ids).
    """
    if weekend_context is None:
        return []
    if weekend_context.status == "insufficient_evidence":
        return ["No meaningful weekend developments detected since the last close."]

    lines = [
        f"Weekend Intelligence ({weekend_context.status}, as of {weekend_context.target_trading_date}): "
        f"overall bias {weekend_context.overall_bias}, production confidence {weekend_context.production_confidence:.0f}%.",
    ]
    if weekend_context.top_sector_signals:
        top = weekend_context.top_sector_signals[:3]
        lines.append("Top weekend sector signals: " + ", ".join(f"{s.id} ({s.direction})" for s in top))
    if weekend_context.top_company_signals:
        top = weekend_context.top_company_signals[:3]
        lines.append("Top weekend company signals: " + ", ".join(f"{s.id} ({s.direction})" for s in top))
    if weekend_context.major_risks:
        lines.append("Weekend risks: " + "; ".join(r.description for r in weekend_context.major_risks[:2]))
    lines.append(f"{weekend_context.meaningful_development_count} meaningful development(s) since last close.")

    mie_ids = {ev.get("id") for ev in (events.get("mie_signals") or []) if ev.get("id")}
    overlap = weekend_context.meaningful_development_event_ids & mie_ids
    if overlap:
        lines.append(
            f"Note: {len(overlap)} of the weekend development(s) above are the SAME underlying event(s) "
            "already listed under Breaking Signals in the Event Layer — treat them as ONE confirmation, not two."
        )
    return lines


async def _run_ai(
    signals: dict, events: dict, historical: dict,
    weekend_context: "WeekendContext | None" = None, weekend_adjustment: dict | None = None,
) -> dict:
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

    weekend_lines = _weekend_prompt_lines(events, weekend_context)
    weekend_section = (
        "WEEKEND CONTEXT LAYER (only present when a valid Weekend Intelligence "
        "snapshot exists for THIS session — treat as supporting context, not a "
        "substitute for the fresher signals above; see brief §3):\n"
        + "\n".join(f"  • {l}" for l in weekend_lines) + "\n\n"
    ) if weekend_lines else ""

    prompt = (
        "Predict tomorrow's NSE Nifty 50 market opening based on the following data.\n\n"
        "SIGNAL LAYER:\n" + "\n".join(f"  • {l}" for l in signal_lines) + "\n\n"
        "EVENT LAYER:\n" + "\n".join(f"  • {l}" for l in event_lines) + "\n\n"
        "HISTORICAL CONTEXT:\n" + "\n".join(f"  {l}" for l in hist_lines) + "\n\n"
        + weekend_section +
        "Nifty 50 previous close: ~24,300 points.\n\n"
        "Task:\n"
        "  1. Identify dominant direction (Positive / Negative / Neutral)\n"
        "  2. Note any CONFLICTING signals between layers (SIGNAL/EVENT layers "
        "reflect this morning and take precedence over the WEEKEND layer if they conflict)\n"
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

    raw = await _call_with_fallback(prompt, system, max_tokens=700, priority="interactive")

    if not raw:
        return _fallback_prediction(signals, weekend_adjustment)

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
            # Side-channel diagnostic only (see module docstring) — the
            # AI's own direction/confidence above is NOT overwritten or
            # derived from this; it's the free-form LLM output, informed
            # by weekend_lines in the prompt but not decomposable into
            # base+adjustment the way the deterministic path is.
            "weekend_adjustment": weekend_adjustment,
        }
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        log.warning("opening_prediction.parse_error", raw=raw[:200])
        return _fallback_prediction(signals, weekend_adjustment)


def _base_fallback_score(signals: dict) -> dict:
    """Byte-for-byte the pre-Phase-1C _fallback_prediction formula,
    isolated so _weekend_adjusted_score can call it without triggering
    the weekend-aware wrapper below (which itself calls this function) —
    avoids infinite recursion and keeps "what did Monday-fresh signals
    alone say" a clean, separately-callable, unit-testable function."""
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


def _fallback_prediction(signals: dict, weekend_adjustment: dict | None = None) -> dict:
    """The real, returned fallback prediction — unlike the AI path, this
    IS a clean arithmetic formula, so when a weekend adjustment applies
    it genuinely shifts direction/confidence/range (not just a
    side-channel diagnostic), computed via the SAME weekend_adjustment
    triple already passed in (never recomputed — build_opening_prediction
    computes it once). With weekend_adjustment=None or not applied, this
    is byte-for-byte the pre-Phase-1C output (regression guarantee)."""
    result = _base_fallback_score(signals)

    if not weekend_adjustment or not weekend_adjustment.get("applied"):
        result["weekend_adjustment"] = weekend_adjustment
        return result

    direction  = weekend_adjustment["final_direction"]
    confidence = max(45, min(90, int(round(abs(weekend_adjustment["final_score"])))))
    base       = 25 if direction == "Positive" else -45 if direction == "Negative" else -10

    result["direction"]  = direction
    result["confidence"] = confidence
    result["range_low"]  = base
    result["range_high"] = base + 40
    result["primary_drivers"] = result["primary_drivers"][:2] + [
        f"Weekend intelligence: {weekend_adjustment['weekend_direction']} bias "
        f"({weekend_adjustment['weekend_confidence']:.0f}% confidence)"
    ]
    result["reasoning"] += (
        f" Weekend intelligence ({weekend_adjustment['weekend_direction']}, "
        f"{weekend_adjustment['weekend_confidence']:.0f}% confidence) adjusted the signal-only "
        f"score by {weekend_adjustment['adjustment']:+.1f}."
    )
    result["weekend_adjustment"] = weekend_adjustment
    return result
