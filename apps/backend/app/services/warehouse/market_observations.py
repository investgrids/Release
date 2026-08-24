"""
Canonical Market Observations capture — Phase 1B Batch 1 (owner
instruction, 2026-08-23).

Reuses the EXISTING canonical fetchers already proven reliable by the
Phase 1A audit (never reimplements a fetch) — this module is the first
shared persistence point for signals that were previously fetched
correctly and then discarded on every call: India VIX, Bank Nifty,
USD/INR, Brent, 12 sector ETF proxies, GIFT Nifty, FII/DII, PCR/Max Pain.

Matches the pattern price_monitor.py::capture_close_snapshot already
established in this codebase: every secondary source degrades to a
source_failure row on its own individual failure rather than blocking
the whole capture, and nothing here reimplements a fetch that already
exists elsewhere.

Real, explicit persistence cadence for this batch: called once per
invocation (see run_market_observations_capture_cycle) — intended to be
scheduled at a real interval (recommend reusing price_monitor.py's
existing 2-minute cycle with a 15-minute gate, matching the cadence most
of these underlying fetchers already cache at) once Batch 1 is verified
live. NOT yet wired into the scheduler — that's the next step after this
module is confirmed correct against one real run.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.market_observation import MarketObservation

log = structlog.get_logger(__name__)

# Batch 1D (owner instruction, 2026-08-23): scheduler wiring must not
# create duplicate rows on restart. observation_time is bucketed to the
# nearest 15-minute mark (not exact wall-clock time) specifically so a
# restart that re-fires within the same window produces the SAME
# identity (metric, source_id, observation_time) as the original
# capture, and is caught by the pre-check / UNIQUE constraint rather
# than silently creating a fresh duplicate-in-spirit row every tick.
_BUCKET_MINUTES = 15

# In-process guard, same pattern as price_monitor.py's own
# _captured_close_for — a cheap fast-path that avoids even querying the
# DB on every 2-minute tick within an already-captured bucket. Resets on
# restart; the DB-level pre-check below is the real cross-restart
# guarantee, same reasoning as capture_close_snapshot's own comment.
_last_captured_bucket: str | None = None

# metric -> (source_id, ticker, unit)
_YFINANCE_QUOTES = {
    "INDIAVIX": ("yfinance_india_vix", "^INDIAVIX", "index_points"),
    "BANKNIFTY": ("yfinance_banknifty", "^NSEBANK", "index_points"),
    "USDINR": ("yfinance_usdinr", "USDINR=X", "rate"),
    "BRENT": ("yfinance_brent", "BZ=F", "usd_per_barrel"),

    # Phase 1C Batch 3A (owner instruction, 2026-08-23) — canonical
    # producer chosen per metric per the "no duplicate persistence
    # pipelines" instruction. Global indices sourced from
    # app/api/market.py::_GLOBAL_INDICES (a real superset of
    # market_data.py's own narrower, overlapping _US_INDICES/
    # _ASIAN_MARKETS — that duplicate is left in place as-is for its
    # existing live-render callers, per "retire the duplicate later,"
    # just never used as a second source for this table).
    "GLOBAL_DOW_JONES": ("yfinance_global_indices", "^DJI", "index_points"),
    "GLOBAL_SP500": ("yfinance_global_indices", "^GSPC", "index_points"),
    "GLOBAL_NASDAQ": ("yfinance_global_indices", "^IXIC", "index_points"),
    "GLOBAL_FTSE100": ("yfinance_global_indices", "^FTSE", "index_points"),
    "GLOBAL_DAX": ("yfinance_global_indices", "^GDAXI", "index_points"),
    "GLOBAL_CAC40": ("yfinance_global_indices", "^FCHI", "index_points"),
    "GLOBAL_NIKKEI225": ("yfinance_global_indices", "^N225", "index_points"),
    "GLOBAL_HANGSENG": ("yfinance_global_indices", "^HSI", "index_points"),
    "GLOBAL_SHANGHAI": ("yfinance_global_indices", "000001.SS", "index_points"),
    "GLOBAL_KOSPI": ("yfinance_global_indices", "^KS11", "index_points"),
    "US_VIX": ("yfinance_us_vix", "^VIX", "index_points"),   # distinct instrument from India VIX above

    "US_FUT_SP500": ("yfinance_us_futures", "ES=F", "index_points"),
    "US_FUT_NASDAQ100": ("yfinance_us_futures", "NQ=F", "index_points"),
    "US_FUT_DOW": ("yfinance_us_futures", "YM=F", "index_points"),

    # Commodities: canonical producer is commodities.py's ticker set
    # (more complete than market_data.py's own overlapping, narrower
    # _COMMODITIES dict — Gold/Silver already present in both under the
    # same yfinance tickers, so this is a real single-producer choice,
    # not a silent behavior change for either file's existing callers).
    "COMMODITY_GOLD": ("yfinance_commodities", "GC=F", "usd_per_oz"),
    "COMMODITY_SILVER": ("yfinance_commodities", "SI=F", "usd_per_oz"),
    "COMMODITY_COPPER": ("yfinance_commodities", "HG=F", "usd_per_lb"),
    "COMMODITY_PLATINUM": ("yfinance_commodities", "PL=F", "usd_per_oz"),
    "COMMODITY_WTI": ("yfinance_commodities", "CL=F", "usd_per_barrel"),
    "COMMODITY_NATGAS": ("yfinance_commodities", "NG=F", "usd_per_mmbtu"),
    "COMMODITY_DXY": ("yfinance_commodities", "DX-Y.NYB", "index_points"),   # only market_data.py has this ticker

    "CURRENCY_EURINR": ("yfinance_currency_pairs", "EURINR=X", "rate"),
    "CURRENCY_GBPINR": ("yfinance_currency_pairs", "GBPINR=X", "rate"),
}


def _market_date_and_session() -> tuple[date, str]:
    from app.services.intelligence.engine import _market_session, _IST
    now_ist = datetime.now(_IST)
    return now_ist.date(), _market_session()


def _bucket_now() -> tuple[datetime, date, str, str]:
    """Returns (observation_time bucketed to the nearest 15min mark, UTC
    -aware; market_date; session; bucket_key for the in-process guard)."""
    from app.services.intelligence.engine import _market_session, _IST
    now_ist = datetime.now(_IST)
    bucket_minute = (now_ist.minute // _BUCKET_MINUTES) * _BUCKET_MINUTES
    bucketed_ist = now_ist.replace(minute=bucket_minute, second=0, microsecond=0)
    observation_time = bucketed_ist.astimezone(timezone.utc)
    bucket_key = bucketed_ist.strftime("%Y-%m-%dT%H:%M")
    return observation_time, now_ist.date(), _market_session(), bucket_key


async def _capture_yfinance_quotes(db: AsyncSession, now: datetime, market_date: date, session: str) -> list[MarketObservation]:
    from app.services.market_data import _fetch_quote
    loop = asyncio.get_event_loop()
    rows: list[MarketObservation] = []
    for metric, (source_id, ticker, unit) in _YFINANCE_QUOTES.items():
        try:
            quote = await loop.run_in_executor(None, _fetch_quote, ticker)
        except Exception as exc:
            log.warning("warehouse.market_obs.quote_failed", metric=metric, error=str(exc)[:160])
            quote = None
        rows.append(MarketObservation(
            id=str(uuid4()), metric=metric, value=quote["price"] if quote else None, unit=unit,
            observation_time=now, market_date=market_date, session=session, source_id=source_id,
            captured_at=now, quality="fresh" if quote else "source_failure",
            extra={"pct": quote["pct"]} if quote else None,
        ))
    return rows


async def _capture_sector_performance(db: AsyncSession, now: datetime, market_date: date, session: str) -> list[MarketObservation]:
    from app.services.market_data import _fetch_quote, _SECTOR_ETFS
    loop = asyncio.get_event_loop()
    rows: list[MarketObservation] = []
    for name, ticker in _SECTOR_ETFS.items():
        try:
            quote = await loop.run_in_executor(None, _fetch_quote, ticker)
        except Exception as exc:
            log.warning("warehouse.market_obs.sector_failed", sector=name, error=str(exc)[:160])
            quote = None
        rows.append(MarketObservation(
            id=str(uuid4()), metric=f"SECTOR_{name.upper().replace(' ', '_')}",
            value=quote["pct"] if quote else None, unit="pct_change",
            observation_time=now, market_date=market_date, session=session, source_id="yfinance_sector_etfs",
            captured_at=now, quality="fresh" if quote else "source_failure", extra=None,
        ))
    return rows


async def _capture_gift_nifty(db: AsyncSession, now: datetime, market_date: date, session: str) -> MarketObservation:
    from app.services.gift_nifty_service import get_gift_nifty_sync
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, get_gift_nifty_sync)
        available = result.status in ("live", "stale") and result.price is not None
    except Exception as exc:
        log.warning("warehouse.market_obs.gift_nifty_failed", error=str(exc)[:160])
        result, available = None, False
    return MarketObservation(
        id=str(uuid4()), metric="GIFT_NIFTY", value=result.price if available else None, unit="index_points",
        observation_time=now, market_date=market_date, session=session, source_id="nse_gift_nifty",
        captured_at=now, quality="fresh" if available else "source_failure",
        extra={"status": result.status, "premium_pct": result.premium_pct} if result else None,
    )


async def _capture_fii_dii(db: AsyncSession, now: datetime, market_date: date, session: str) -> MarketObservation:
    """Batch 3B (owner instruction, 2026-08-23): explicit derived-signal
    metadata — quality/method/as_of/source_lag — rather than presenting
    this as equivalent to a direct exchange observation. NSE's own
    fii_net figure is genuinely the PREVIOUS session's net flow, not
    same-session; that was already true in Batch 1, just not labeled
    this explicitly."""
    from app.api.market import _fetch_fii_dii
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, _fetch_fii_dii)
        fii_net = data.get("fii_net")
    except Exception as exc:
        log.warning("warehouse.market_obs.fii_dii_failed", error=str(exc)[:160])
        fii_net = None
    return MarketObservation(
        id=str(uuid4()), metric="FII_NET", value=fii_net, unit="inr_crore",
        observation_time=now, market_date=market_date, session=session, source_id="nse_fii_dii",
        captured_at=now, quality="estimated" if fii_net is not None else "source_failure",
        extra={
            "method": "NSE previous-session FII/DII net flow (nseindia.com/api/fiidiiTradeReact)",
            "source_lag": "previous_session",
            "as_of": str(market_date),
        } if fii_net is not None else None,
    )


async def _capture_pcr_max_pain(db: AsyncSession, now: datetime, market_date: date, session: str) -> list[MarketObservation]:
    """Batch 3B: PCR and Max Pain are both COMPUTED from live NSE
    option-chain open-interest data — real-time in the sense of the
    underlying OI snapshot, but a derived ratio/computation, not a
    directly observed single exchange price. Labeled quality=estimated
    with an explicit method, not silently equated to a raw index quote."""
    from app.api.market import _fetch_pcr_data
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, _fetch_pcr_data)
        pcr, max_pain = data.get("pcr"), data.get("max_pain")
    except Exception as exc:
        log.warning("warehouse.market_obs.pcr_failed", error=str(exc)[:160])
        pcr, max_pain = None, None
    method = "computed from live NSE option-chain open interest (nseindia.com/api/option-chain-indices)"
    return [
        MarketObservation(
            id=str(uuid4()), metric="PCR_NIFTY", value=pcr, unit="ratio",
            observation_time=now, market_date=market_date, session=session, source_id="nse_option_chain_pcr",
            captured_at=now, quality="estimated" if pcr is not None else "source_failure",
            extra={"method": method, "source_lag": "live", "as_of": str(market_date)} if pcr is not None else None,
        ),
        MarketObservation(
            id=str(uuid4()), metric="MAX_PAIN_NIFTY", value=max_pain, unit="index_points",
            observation_time=now, market_date=market_date, session=session, source_id="nse_option_chain_pcr",
            captured_at=now, quality="estimated" if max_pain is not None else "source_failure",
            extra={"method": method, "source_lag": "live", "as_of": str(market_date)} if max_pain is not None else None,
        ),
    ]


async def _capture_adrs(db: AsyncSession, now: datetime, market_date: date, session: str) -> list[MarketObservation]:
    """Batch 3A — ADR price + premium/discount vs. the NSE-listed price,
    scaled by each ADR's real conversion ratio (app/api/market.py::
    _ADR_TICKERS), matching the existing Pre-Market page's own
    calculation rather than inventing a new one."""
    from app.services.market_data import _fetch_quote
    from app.api.market import _ADR_TICKERS
    loop = asyncio.get_event_loop()

    # A real, live USD/INR rate — never a hardcoded constant — for the
    # premium-vs-NSE calculation below. Reuses the same _fetch_quote
    # call already made for the USDINR metric rather than adding a
    # second independent fetch path for the same rate.
    try:
        usdinr_quote = await loop.run_in_executor(None, _fetch_quote, "USDINR=X")
        usdinr_rate = usdinr_quote["price"] if usdinr_quote else None
    except Exception:
        usdinr_rate = None

    rows: list[MarketObservation] = []
    for adr_symbol, meta in _ADR_TICKERS.items():
        try:
            adr_quote = await loop.run_in_executor(None, _fetch_quote, adr_symbol)
            nse_quote = await loop.run_in_executor(None, _fetch_quote, meta["nse"])
        except Exception as exc:
            log.warning("warehouse.market_obs.adr_failed", symbol=adr_symbol, error=str(exc)[:160])
            adr_quote, nse_quote = None, None
        premium_pct = None
        if adr_quote and nse_quote and nse_quote["price"] and usdinr_rate:
            implied_inr = adr_quote["price"] * meta["ratio"] * usdinr_rate
            premium_pct = round((implied_inr - nse_quote["price"]) / nse_quote["price"] * 100, 2)
        rows.append(MarketObservation(
            id=str(uuid4()), metric=f"ADR_{adr_symbol}", value=adr_quote["price"] if adr_quote else None, unit="usd",
            observation_time=now, market_date=market_date, session=session, source_id="yfinance_adrs",
            captured_at=now, quality="fresh" if adr_quote else "source_failure",
            extra={"name": meta["name"], "ratio": meta["ratio"], "premium_pct_vs_nse": premium_pct} if adr_quote else None,
        ))
    return rows


async def _capture_macro_rates(db: AsyncSession, now: datetime, market_date: date, session: str) -> list[MarketObservation]:
    """Batch 3A — reuses the existing, real, cached
    macro_rates.service.get_macro_rate_state() (the SAME function
    opening_prediction_service.py/weekend_intelligence already call) as
    the canonical producer, rather than calling the three underlying
    sources independently. India's WSS data is explicitly weekly-cadence
    — the real observed_at date from the source is used, never today's
    date substituted for it."""
    from app.services.macro_rates.service import get_macro_rate_state
    try:
        state = await get_macro_rate_state()
    except Exception as exc:
        log.warning("warehouse.market_obs.macro_rates_failed", error=str(exc)[:160])
        state = None

    def _row(metric: str, value, unit: str, source_id: str, status_ok: bool, as_of=None, extra_note: str | None = None):
        return MarketObservation(
            id=str(uuid4()), metric=metric, value=value, unit=unit,
            observation_time=now, market_date=market_date, session=session, source_id=source_id,
            captured_at=now, quality="fresh" if status_ok and value is not None else "source_failure",
            extra={"as_of": str(as_of) if as_of else None, "note": extra_note} if (status_ok and value is not None) else None,
        )

    if state is None:
        return [
            _row("US_TREASURY_2Y", None, "pct", "macro_rates_us_treasury", False),
            _row("US_TREASURY_10Y", None, "pct", "macro_rates_us_treasury", False),
            _row("US_FED_FUNDS_RATE", None, "pct", "macro_rates_fed_funds", False),
            _row("INDIA_REPO_RATE", None, "pct", "macro_rates_rbi_wss", False),
            _row("INDIA_10Y_GSEC", None, "pct", "macro_rates_rbi_wss", False),
        ]

    us_ok = state.us_data_status == "live"
    india_ok = state.india_data_status == "live"
    return [
        _row("US_TREASURY_2Y", state.us_2y, "pct", "macro_rates_us_treasury", us_ok),
        _row("US_TREASURY_10Y", state.us_10y, "pct", "macro_rates_us_treasury", us_ok),
        _row("US_FED_FUNDS_RATE", state.us_fed_funds_rate, "pct", "macro_rates_fed_funds", us_ok),
        _row("INDIA_REPO_RATE", state.india_repo_rate, "pct", "macro_rates_rbi_wss", india_ok,
             extra_note="RBI WSS weekly-cadence data — not daily"),
        _row("INDIA_10Y_GSEC", state.india_10y_gsec, "pct", "macro_rates_rbi_wss", india_ok,
             as_of=state.india_10y_gsec_observed_at, extra_note="RBI WSS weekly-cadence data — not daily"),
    ]


async def _capture_market_breadth(db: AsyncSession, now: datetime, market_date: date, session: str) -> list[MarketObservation]:
    """Batch 3B — a genuine SAMPLE-based estimate (49-symbol Nifty 500
    sample, app/services/market_data.py::get_top_movers/
    _NIFTY500_SAMPLE), not real exchange-wide advance/decline data — the
    Phase 1A audit's own finding was that no honest source for real
    breadth exists in this codebase. Always quality=estimated with an
    explicit method, never presented as equivalent to a real breadth
    feed."""
    from app.services.market_data import get_top_movers
    try:
        movers = await get_top_movers()
        advancing = movers.get("advancing_count")
        declining = movers.get("declining_count")
    except Exception as exc:
        log.warning("warehouse.market_obs.breadth_failed", error=str(exc)[:160])
        advancing, declining = None, None
    method = "sampled — 49-symbol Nifty 500 subset, not a real exchange-wide feed"
    return [
        MarketObservation(
            id=str(uuid4()), metric="MARKET_BREADTH_ADVANCING", value=advancing, unit="count",
            observation_time=now, market_date=market_date, session=session, source_id="market_breadth_nifty500_sample",
            captured_at=now, quality="estimated" if advancing is not None else "source_failure",
            extra={"method": method, "sample_size": 49} if advancing is not None else None,
        ),
        MarketObservation(
            id=str(uuid4()), metric="MARKET_BREADTH_DECLINING", value=declining, unit="count",
            observation_time=now, market_date=market_date, session=session, source_id="market_breadth_nifty500_sample",
            captured_at=now, quality="estimated" if declining is not None else "source_failure",
            extra={"method": method, "sample_size": 49} if declining is not None else None,
        ),
    ]


async def capture_market_observations(
    db: AsyncSession,
    observation_time: datetime | None = None,
    market_date: date | None = None,
    session: str | None = None,
) -> dict:
    """One real collection cycle — fetches every wired signal (reusing
    existing canonical fetchers only) and persists real MarketObservation
    rows. Never raises on an individual source's failure; a failed source
    still gets a source_failure row rather than being silently skipped,
    so the warehouse-health measurement can see it.

    observation_time/market_date/session default to a fresh bucketed
    "now" when not supplied (manual/ad hoc invocation, e.g. a one-off
    verification run) — the scheduled path (capture_market_observations_
    if_due) always passes these explicitly so every row in one cycle
    shares the exact same bucketed identity."""
    if observation_time is None or market_date is None or session is None:
        observation_time, market_date, session, _ = _bucket_now()
    now = observation_time

    rows: list[MarketObservation] = []
    rows.extend(await _capture_yfinance_quotes(db, now, market_date, session))
    rows.extend(await _capture_sector_performance(db, now, market_date, session))
    rows.append(await _capture_gift_nifty(db, now, market_date, session))
    rows.append(await _capture_fii_dii(db, now, market_date, session))
    rows.extend(await _capture_pcr_max_pain(db, now, market_date, session))
    # Phase 1C Batch 3A/3B (owner instruction, 2026-08-23)
    rows.extend(await _capture_adrs(db, now, market_date, session))
    rows.extend(await _capture_macro_rates(db, now, market_date, session))
    rows.extend(await _capture_market_breadth(db, now, market_date, session))

    for row in rows:
        db.add(row)
    try:
        await db.commit()
    except Exception as exc:
        # A concurrent/overlapping cycle already landed this exact
        # (metric, source_id, observation_time) bucket — same race
        # handling as price_monitor.py::capture_close_snapshot.
        await db.rollback()
        log.info("warehouse.market_obs.race_skipped", observation_time=str(now), error=str(exc)[:160])
        return {"total": 0, "fresh": 0, "estimated": 0, "source_failure": 0, "duplicate_suppressed": len(rows),
                "market_date": str(market_date), "session": session}

    # Batch 3B (owner instruction, 2026-08-23) introduced quality=
    # "estimated" (FII/DII, PCR/Max Pain, market breadth) as a real,
    # honest SUCCESS state — distinct from "fresh" (a direct exchange
    # quote) but not a failure. Both count toward successful_metric_rows;
    # only source_failure is a real failure.
    fresh = sum(1 for r in rows if r.quality == "fresh")
    estimated = sum(1 for r in rows if r.quality == "estimated")
    failed = sum(1 for r in rows if r.quality == "source_failure")
    log.info("warehouse.market_obs.captured", total=len(rows), fresh=fresh, estimated=estimated, failed=failed, session=session)
    return {"total": len(rows), "fresh": fresh, "estimated": estimated, "source_failure": failed, "duplicate_suppressed": 0,
            "market_date": str(market_date), "session": session}


async def capture_market_observations_if_due(db: AsyncSession) -> dict:
    """Scheduled entrypoint — called every 2 minutes from
    run_price_monitor_cycle (reusing that existing cadence, not a new
    independent poller), gated to a real capture only once per 15-minute
    bucket during NSE regular trading hours ("live" session). Returns the
    exact per-cycle metrics requested (owner instruction, 2026-08-23):
    capture_attempts, successful_metric_rows, source_failure_rows,
    duplicate_suppressed — useful for the eventual BEFORE/AFTER daily-
    growth measurement."""
    global _last_captured_bucket
    observation_time, market_date, session, bucket_key = _bucket_now()

    if session != "live":
        return {"skipped": True, "skip_reason": "off_hours", "session": session,
                "capture_attempts": 0, "successful_metric_rows": 0, "source_failure_rows": 0, "duplicate_suppressed": 0}

    if _last_captured_bucket == bucket_key:
        # Cheap in-process fast path — avoids a DB round-trip on every
        # 2-minute tick within an already-captured 15-minute bucket.
        return {"skipped": True, "skip_reason": "already_captured_this_bucket_inprocess", "bucket": bucket_key,
                "capture_attempts": 0, "successful_metric_rows": 0, "source_failure_rows": 0, "duplicate_suppressed": 0}

    existing_count = (await db.execute(
        select(func.count()).select_from(MarketObservation).where(MarketObservation.observation_time == observation_time)
    )).scalar()
    if existing_count > 0:
        # Real cross-restart guarantee — this bucket was already captured
        # by a prior process (in-process guard resets on restart, this
        # DB check doesn't). Don't re-fetch at all; nothing to gain.
        # duplicate_suppressed is the REAL count already in this bucket —
        # never a hardcoded metric count, which would drift out of sync
        # every time a new signal family is added (Batch 3, 2026-08-23).
        _last_captured_bucket = bucket_key
        log.info("warehouse.market_obs.bucket_already_captured", bucket=bucket_key, existing_count=existing_count)
        return {"skipped": True, "skip_reason": "already_captured_this_bucket_db", "bucket": bucket_key,
                "capture_attempts": 0, "successful_metric_rows": 0, "source_failure_rows": 0, "duplicate_suppressed": existing_count}

    result = await capture_market_observations(db, observation_time=observation_time, market_date=market_date, session=session)
    _last_captured_bucket = bucket_key
    return {
        "skipped": False, "bucket": bucket_key, "session": session,
        "capture_attempts": result["total"] + result["duplicate_suppressed"],
        # fresh + estimated are both real successes (Batch 3B) — only
        # source_failure is a real failure.
        "successful_metric_rows": result["fresh"] + result["estimated"],
        "source_failure_rows": result["source_failure"],
        "duplicate_suppressed": result["duplicate_suppressed"],
    }
