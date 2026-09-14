"""
PriceThresholdMonitor — polls key instruments every 2 min.
Generates a RawEvent on the EventIngestionBus when a threshold is breached.

Weekend Intelligence Phase 1A also piggybacks the trading-session close
capture onto this same 2-minute cycle (capture_close_snapshot) — see
WEEKEND_INTELLIGENCE_PHASE1_ARCHITECTURE.md §2/§4. That reuses this
module's existing cadence rather than adding a new scheduled job.
"""
from __future__ import annotations

import asyncio
import structlog
from datetime import datetime, timezone
from uuid import uuid4

log = structlog.get_logger(__name__)

# CR-3 (2026-09-13): session_class governs whether each instrument's
# threshold-loop fetch is gated by NSE trading hours. "nse" instruments
# (NIFTY/BANKNIFTY/VIX) only trade 9:15-15:30 IST weekdays -- a fetch
# outside that window just reconfirms the same frozen last-close price,
# a real, measured 2,160/day of pure waste. "weekday_continuous"
# (USDINR/BRENT) trade far more broadly (forex/global commodities,
# effectively ~24/5) -- deliberately NOT modeling their exact real
# trading sessions/holidays here (that would turn a bounded cost fix
# into market-calendar infrastructure); the locked, narrow rule is just
# "skip on Sat/Sun, keep the existing unconditional 2-min cadence every
# weekday" -- removes the clearest weekend waste (2,880 calls/week)
# without touching weekday behavior at all. See run_price_monitor_cycle's
# _should_fetch_instrument for the exact predicate.
#
# 2026-09-14 correction: _market_session() became holiday-aware (it now
# also reports "weekend" on a real NSE/BSE equity holiday, e.g. Ganesh
# Chaturthi) so the "nse" branch correctly treats a holiday like a
# closed market. "weekday_continuous" must NOT inherit that -- BRENT is
# a global commodity and USDINR trades on its own currency-market
# calendar, neither governed by NSE equity holidays (NSE's own notice
# for 2026-09-14 confirms equity/F&O/currency cash markets closed but
# commodity markets resuming an evening session). That branch is
# therefore gated on a separate, literal Sat/Sun signal
# (_is_calendar_weekend(), never holiday-aware) instead of the
# holiday-aware session value.
_INSTRUMENTS = {
    "NIFTY":     {"ticker": "^NSEI",     "name": "Nifty 50",    "threshold_pct": 0.75, "session_class": "nse"},
    "BANKNIFTY": {"ticker": "^NSEBANK",  "name": "Bank Nifty",  "threshold_pct": 1.0,  "session_class": "nse"},
    "USDINR":    {"ticker": "USDINR=X",  "name": "USD/INR",     "threshold_pct": 0.3,  "session_class": "weekday_continuous"},
    "BRENT":     {"ticker": "BZ=F",      "name": "Brent Crude", "threshold_pct": 1.5,  "session_class": "weekday_continuous"},
    "VIX":       {"ticker": "^INDIAVIX", "name": "India VIX",   "threshold_pct": 5.0,  "session_class": "nse"},
}

_last_prices: dict[str, float] = {}


def _is_calendar_weekend() -> bool:
    """Literal Sat/Sun check, deliberately never holiday-aware -- see
    _should_fetch_instrument's docstring for why weekday_continuous
    instruments (BRENT/USDINR) must not inherit NSE equity-holiday
    closures. A separate function (not inlined at the call site) so
    tests can mock it exactly like _market_session, independent of
    whatever the real calendar date happens to be on the day tests run."""
    from app.services.intelligence.engine import _IST
    return datetime.now(_IST).weekday() >= 5


def _should_fetch_instrument(session_class: str, market_session: str, is_calendar_weekend: bool) -> bool:
    """market_session is _market_session()'s own return value ("weekend",
    "pre_market", "live", "post_market") -- computed once per cycle by
    the caller, not per-instrument, so all 5 instruments in one tick
    agree on the same session snapshot.

    market_session is holiday-aware (2026-09-14 fix, app.services.
    market_calendar): it also reports "weekend" on a real NSE/BSE
    equity-segment holiday, which is exactly right for the "nse" branch
    below. It is deliberately NOT used for "weekday_continuous" --
    BRENT (a global commodity) and USDINR are not governed by NSE
    equity holidays (e.g. 2026-09-14 Ganesh Chaturthi: equity/F&O/
    currency cash markets closed, but commodity markets resume their
    evening session from 5 PM), so that branch keeps its own original,
    separate is_calendar_weekend signal (literal Sat/Sun only, never
    holiday-aware) rather than inheriting NSE holiday closures."""
    if session_class == "nse":
        return market_session == "live"
    if session_class == "weekday_continuous":
        return not is_calendar_weekend
    return True  # unknown class: fail open, never silently stop polling


def _fetch_price_sync(ticker: str) -> float | None:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        return float(info.last_price or 0) or None
    except Exception:
        return None


# In-process guard: which trading_date's close snapshot has already been
# captured (or attempted) this boot, so a session that stays "post_market"
# for hours doesn't retry every 2 minutes for no reason. This is purely an
# optimization — the real cross-restart idempotency guarantee is the DB's
# own ux_market_snapshots_close_per_day partial unique index (see
# db/schema_patches.py), since this in-process value resets on restart
# and a restart mid-post-market-session must not produce a duplicate row.
_captured_close_for: str | None = None

# Bounded post-close capture window, IST minutes-of-day. Deliberately NOT
# "any time _market_session() reports post_market" — that bucket covers
# the entire rest of the day (15:31 through 23:59), so without this
# separate, narrower check a backend restart hours after close (e.g. a
# Railway redeploy at 15:30, backend back up at 18:00, no row yet for
# today) would capture "close" data from whatever the providers return at
# 18:00 and silently mislabel it as the 15:30 close. Reviewed and added
# specifically to close that gap (2026-08 Phase 1A review) — V1's explicit
# choice is a missing close snapshot over a late, falsely-labeled
# reconstruction; see the module/function docstring and
# WEEKEND_INTELLIGENCE_PHASE1_ARCHITECTURE.md §22 (degrade honestly rather
# than fabricate). 10 minutes is generous enough for the existing 2-minute
# cycle to land inside it at least once, narrow enough that "close"
# remains a meaningful label.
_CLOSE_WINDOW_START_MIN = 15 * 60 + 30   # 15:30 IST
_CLOSE_WINDOW_END_MIN   = 15 * 60 + 40   # 15:40 IST


def _within_close_capture_window(now_ist: datetime) -> bool:
    mins = now_ist.hour * 60 + now_ist.minute
    return _CLOSE_WINDOW_START_MIN <= mins <= _CLOSE_WINDOW_END_MIN


async def capture_close_snapshot() -> None:
    """
    Persist exactly one immutable MarketSnapshot(snapshot_type="close") row
    per trading session — the "trading-session close baseline" design doc
    §2 calls for, reusing this module's existing 2-minute cadence instead
    of a new scheduled job. Fires only inside the bounded 15:30-15:40 IST
    window (_within_close_capture_window) on a day the reused, canonical
    `_market_session()` helper (app.services.intelligence.engine — the
    same helper app/api/mie.py already imports across module boundaries,
    not a new independent session implementation) reports "post_market".

    Outside that window — including a boot/restart hours after close with
    no row yet for today — this deliberately does NOT capture. A missing
    close snapshot for a given day is the intended, honest outcome; it is
    never reconstructed later from stale-relative-to-close data. See
    _within_close_capture_window's own comment for why.

    Every secondary source (VIX, sector performance, FII/DII, PCR, top
    movers, current ThemeState/MarketStory) is fetched independently and
    degrades to None/[] on its own failure — only the Nifty level (the
    "primary market state", design doc §7) blocks the whole capture; if
    even that fails, nothing is written and the next 2-minute tick retries
    rather than persisting a near-empty row.

    Known Phase 1A limitations, deliberately not solved here (see design
    doc §6/§8/§9/§18/§19):
      - advances/declines are left NULL — the only breadth signal this
        codebase has today is a scaled estimate from a sampled subset of
        stocks (market.py's market_overview()), not a real exchange-wide
        advance/decline count, and this table's columns don't carry
        "this is a sample estimate" metadata. Storing the estimate here
        as if it were authoritative breadth would be misleading.
      - fii_net is NSE's own "previous session" figure (see
        _fetch_fii_dii's docstring) — it is NOT same-session flow as of
        the moment this snapshot is captured. Stored as-is since that's
        the real, honest semantics of the only FII/DII source that
        exists, not because it's same-session data.
      - "post_market" is computed purely from IST weekday/time
        (_market_session), with no real NSE/BSE trading-holiday calendar
        behind it — a holiday would currently be miscaptured as a normal
        trading-day close. Tracked as a pre-existing gap, not fixed here.
    """
    global _captured_close_for
    from app.services.intelligence.engine import _market_session, _IST

    if _market_session() != "post_market":
        return

    now_ist = datetime.now(_IST)
    if not _within_close_capture_window(now_ist):
        log.info(
            "price_monitor.close_snapshot_window_missed",
            hour=now_ist.hour, minute=now_ist.minute,
        )
        return

    trading_date = now_ist.date().isoformat()
    if _captured_close_for == trading_date:
        return

    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence import MarketSnapshot, MarketStory, ThemeState
    from app.services.market_data import _fetch_quote, _SECTOR_ETFS, get_top_movers

    loop = asyncio.get_event_loop()

    async with AsyncSessionLocal() as db:
        already = (await db.execute(
            select(MarketSnapshot.id).where(
                MarketSnapshot.trading_date == trading_date,
                MarketSnapshot.snapshot_type == "close",
            )
        )).scalar_one_or_none()
        if already:
            _captured_close_for = trading_date
            return

        nifty = await loop.run_in_executor(None, _fetch_quote, _INSTRUMENTS["NIFTY"]["ticker"])
        if not nifty:
            # Primary source missing — don't persist a near-empty snapshot;
            # a later tick this same post_market session will retry.
            log.warning("price_monitor.close_snapshot_no_primary", trading_date=trading_date)
            return

        banknifty = await loop.run_in_executor(None, _fetch_quote, _INSTRUMENTS["BANKNIFTY"]["ticker"])
        vix_q     = await loop.run_in_executor(None, _fetch_quote, _INSTRUMENTS["VIX"]["ticker"])

        from app.api.market import _fetch_fii_dii, _fetch_pcr_data

        try:
            fii_dii = await loop.run_in_executor(None, _fetch_fii_dii)
        except Exception as exc:
            log.warning("price_monitor.close_snapshot_fii_dii_failed", error=str(exc)[:160])
            fii_dii = {"fii_net": None}

        try:
            pcr_data = await loop.run_in_executor(None, _fetch_pcr_data)
        except Exception as exc:
            log.warning("price_monitor.close_snapshot_pcr_failed", error=str(exc)[:160])
            pcr_data = {"pcr": None, "max_pain": None}

        sector_ranks: list[dict] = []
        try:
            for name, ticker in _SECTOR_ETFS.items():
                q = await loop.run_in_executor(None, _fetch_quote, ticker)
                if q:
                    sector_ranks.append({"name": name, "pct": round(q["pct"], 2), "positive": q["positive"]})
            sector_ranks.sort(key=lambda r: r["pct"], reverse=True)
        except Exception as exc:
            log.warning("price_monitor.close_snapshot_sectors_failed", error=str(exc)[:160])
            sector_ranks = []

        top_movers: list[dict] = []
        try:
            movers = await get_top_movers()
            for row in (movers.get("gainers", []) + movers.get("losers", [])):
                try:
                    pct = float(str(row["value"]).replace("+", "").replace("%", ""))
                except (KeyError, ValueError):
                    continue
                top_movers.append({"symbol": row.get("ticker"), "change_pct": round(pct, 2)})
        except Exception as exc:
            log.warning("price_monitor.close_snapshot_movers_failed", error=str(exc)[:160])
            top_movers = []

        top_themes: list[dict] = []
        try:
            rows = (await db.execute(
                select(ThemeState.theme, ThemeState.score).order_by(ThemeState.score.desc()).limit(5)
            )).all()
            top_themes = [{"theme": r[0], "score": r[1]} for r in rows]
        except Exception as exc:
            log.warning("price_monitor.close_snapshot_themes_failed", error=str(exc)[:160])

        mood, story_hash = None, None
        try:
            story_row = (await db.execute(
                select(MarketStory.mood, MarketStory.story_hash).order_by(MarketStory.generated_at.desc()).limit(1)
            )).first()
            if story_row:
                mood, story_hash = story_row[0], story_row[1]
        except Exception as exc:
            log.warning("price_monitor.close_snapshot_story_failed", error=str(exc)[:160])

        snapshot = MarketSnapshot(
            id=str(uuid4()),
            snapshot_type="close",
            trading_date=trading_date,
            nifty_level=nifty["price"],
            nifty_change_pct=round(nifty["pct"], 2),
            banknifty_level=banknifty["price"] if banknifty else None,
            banknifty_change_pct=round(banknifty["pct"], 2) if banknifty else None,
            vix=vix_q["price"] if vix_q else None,
            advances=None,   # see docstring — no honest exchange-wide source exists yet
            declines=None,
            fii_net=fii_dii.get("fii_net"),
            pcr=pcr_data.get("pcr"),
            max_pain=pcr_data.get("max_pain"),
            top_movers=top_movers,
            sector_ranks=sector_ranks,
            top_themes=top_themes,
            mood=mood,
            story_hash=story_hash,
        )
        db.add(snapshot)
        try:
            await db.commit()
            _captured_close_for = trading_date
            log.info("price_monitor.close_snapshot_captured", trading_date=trading_date)
        except Exception as exc:
            # DB unique index caught a race (e.g. overlapping ticks) —
            # another capture already landed for this trading_date, which
            # is exactly what the guard is for, not a real failure.
            await db.rollback()
            _captured_close_for = trading_date
            log.info("price_monitor.close_snapshot_race_skipped", trading_date=trading_date, error=str(exc)[:160])


async def run_price_monitor_cycle() -> None:
    """Called by APScheduler every 2 minutes."""
    from app.services.intelligence.event_bus import get_event_bus, RawEvent

    try:
        await capture_close_snapshot()
    except Exception as exc:
        log.warning("price_monitor.close_snapshot_cycle_error", error=str(exc)[:200])

    # Phase 1B Batch 1D (owner instruction, 2026-08-23) — reuses this
    # existing 2-minute cadence rather than a new independent scheduled
    # job, same pattern as capture_close_snapshot above. Internally gated
    # to once per 15-minute bucket during NSE regular trading hours; a
    # no-op call on every other tick.
    try:
        from app.db.session import AsyncSessionLocal
        from app.services.warehouse.market_observations import capture_market_observations_if_due
        async with AsyncSessionLocal() as db:
            result = await capture_market_observations_if_due(db)
            if not result.get("skipped"):
                log.info("price_monitor.market_observations_captured", **{
                    k: v for k, v in result.items() if k != "skipped"
                })
    except Exception as exc:
        log.warning("price_monitor.market_observations_cycle_error", error=str(exc)[:200])

    bus = get_event_bus()
    loop = asyncio.get_event_loop()

    from app.services.intelligence.engine import _market_session
    current_session = _market_session()
    is_calendar_weekend = _is_calendar_weekend()

    for key, cfg in _INSTRUMENTS.items():
        if not _should_fetch_instrument(cfg["session_class"], current_session, is_calendar_weekend):
            continue
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
                        origin="Live Price Monitor",
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
