"""
Phase 1E lifecycle test harness — shared fixtures.

Design (brief §4/§36 — "control time through dependency injection/
monkeypatching", "prefer isolation... do not fill the user's persistent
local dev DB"):

  - `isolated_db`: a fresh in-memory SQLite DB per test (StaticPool, same
    pattern as tests/ai_pipeline/conftest.py), schema built from the REAL
    current model metadata (Base.metadata.create_all — always up to date,
    unlike schema_patches.py which only matters for already-deployed
    tables) plus a real run of apply_schema_patches() for full parity
    with a real boot (the market_snapshots close-per-day unique index is
    only created that way, not via __table_args__).

    Several existing functions open their OWN AsyncSessionLocal()
    internally rather than accepting an injected session
    (capture_close_snapshot, prediction_service.store_prediction/
    record_evaluation/get_due_predictions/recompute_calibration,
    prediction_recording._already_recorded) — this is real, pre-existing
    architecture (not something Phase 1E redesigns, per §22). To keep
    those calls inside the SAME isolated DB rather than silently writing
    to the real ig_dev.db, this fixture monkeypatches the two places
    AsyncSessionLocal is actually bound: app.db.session.AsyncSessionLocal
    (picked up by every DEFERRED `from app.db.session import
    AsyncSessionLocal` at call time) and
    app.services.prediction_service.AsyncSessionLocal (that module
    imports it at module load time, so the deferred-import trick doesn't
    reach it — patched separately).

  - `frozen_time`: monkeypatches the `datetime` name inside
    app.services.intelligence.engine and app.services.intelligence.
    price_monitor (both do `from datetime import datetime`, a
    module-local name — the standard, well-established way to make that
    patchable without touching source) so `_market_session()` and
    `capture_close_snapshot()`'s `datetime.now(_IST)` calls return a
    fixed instant. `resolve_weekend_session`/`run_checkpoint`/
    `resolve_opening_prediction_session` already accept an explicit
    `reference`/`checkpoint_time`/`now_ist` parameter (no patching
    needed for those — real dependency injection, preferred where it
    already exists per §4).

Test dates (real Fri/Sat/Sun/Mon, far future, never collide with real
data): 2099-01-02 (Fri), 03 (Sat), 04 (Sun), 05 (Mon).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base

FRIDAY = date(2099, 1, 2)
SATURDAY = date(2099, 1, 3)
SUNDAY = date(2099, 1, 4)
MONDAY = date(2099, 1, 5)
TUESDAY = date(2099, 1, 6)

_IST = timezone(timedelta(hours=5, minutes=30))


def ist(d: date, hour: int, minute: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=_IST)


@pytest_asyncio.fixture
async def isolated_db(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from app.db.schema_patches import apply_schema_patches
        await apply_schema_patches(conn)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    import app.db.session as db_session_module
    import app.services.prediction_service as prediction_service_module
    monkeypatch.setattr(db_session_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(prediction_service_module, "AsyncSessionLocal", session_factory)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def frozen_time(monkeypatch):
    """Returns a `set(dt)` function — call it with an IST-aware datetime
    to make every wall-clock read in the lifecycle behave as if "now"
    were exactly that instant: _market_session()/capture_close_snapshot()
    (engine.py, price_monitor.py) AND versioning.create_next_version's
    generated_at=_now() (versioning.py). The last one matters more than
    it looks: without it, a snapshot created during a test using a fake
    2099 checkpoint_time would still get a REAL 2026 generated_at,
    which would then make get_weekend_context_for_session's staleness
    check (comparing "now" to generated_at) computes a multi-decade age
    and reject every snapshot as stale — freezing all three keeps the
    whole simulated timeline internally consistent."""
    import app.services.intelligence.engine as engine_module
    import app.services.intelligence.price_monitor as price_monitor_module
    import app.services.weekend_intelligence.versioning as versioning_module

    state = {"now": None}

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            fixed = state["now"]
            if tz is not None:
                return fixed.astimezone(tz)
            return fixed

    monkeypatch.setattr(engine_module, "datetime", _FrozenDatetime)
    monkeypatch.setattr(price_monitor_module, "datetime", _FrozenDatetime)
    monkeypatch.setattr(versioning_module, "datetime", _FrozenDatetime)

    def _set(dt: datetime):
        state["now"] = dt

    return _set


@pytest.fixture(autouse=True)
def _reset_close_capture_guard():
    """price_monitor._captured_close_for is a module-level global (not
    request-scoped) — reset before/after every test in this package so
    one test's close-capture doesn't silently suppress another's."""
    import app.services.intelligence.price_monitor as price_monitor_module
    price_monitor_module._captured_close_for = None
    yield
    price_monitor_module._captured_close_for = None


# ── Evidence fixture builders — real ORM rows through real normalizers ─────
# (brief §7: "Do not bypass normalizers by constructing final Weekend
# Intelligence output manually" — every helper below inserts a real row
# of the real source model; the pipeline under test is always the real
# collect_evidence_since -> cluster_evidence -> synthesis path.)

_id_counter = {"n": 0}


def _next_id(prefix: str) -> str:
    _id_counter["n"] += 1
    return f"{prefix}-{_id_counter['n']:04d}"


def _utc(when: datetime) -> datetime:
    """Real, general SQLite+SQLAlchemy footgun, confirmed by direct
    reproduction while building this harness (matches the known "SQLite
    datetime-as-string comparisons silently misfilter" issue class):
    SQLite's DateTime(timezone=True) columns do NOT actually preserve
    tzinfo — a stored aware datetime comes back naive, holding only the
    original WALL-CLOCK value. If that wall-clock value was IST
    (+5:30) while collect_evidence_since's since/until bounds are
    UTC-aware, the comparison silently becomes a lexicographic STRING
    comparison between two different clocks 5.5 hours apart — evidence
    at real IST 9am can compare as "later than" a UTC 9:30am bound,
    silently dropping it from the window with no error. Every evidence
    fixture builder below stores `when` normalized to UTC first,
    matching how the real application actually populates these columns
    (ingestion always computes `datetime.now(timezone.utc)`-based
    timestamps, never raw local wall-clock) — this is a fixture-realism
    fix, not a workaround for a bug in the code under test."""
    return when.astimezone(timezone.utc)


async def make_event(
    db, *, title, when: datetime, companies=None, sectors=None, category=None,
    impact_score=7.0, confidence=0.8,
):
    from app.db.models.event import Event
    row = Event(
        id=_next_id("evt"), title=title, summary=title, description=title,
        source="test", event_type="news", event_date=_utc(when), published_at=_utc(when),
        impact_score=impact_score, confidence=confidence,
        sectors=sectors or [], companies=companies or [], category=category,
        enrichment_status="complete",
    )
    db.add(row)
    await db.flush()
    return row


async def make_event_triage(db, event_id: str, *, urgency=8, importance=8, headline=None):
    from app.db.models.intelligence import EventTriage
    row = EventTriage(
        id=_next_id("triage"), event_id=event_id, source="synthetic", headline=headline or event_id,
        urgency=urgency, importance=importance, confidence=80, sentiment="bullish",
    )
    db.add(row)
    await db.flush()
    return row


async def make_news(db, *, headline, when: datetime, companies=None, impact_score=6.5):
    from app.db.models_legacy import NewsArticle
    row = NewsArticle(
        id=_next_id("news"), headline=headline, summary=headline, source="test-wire",
        published_at=_utc(when).isoformat(), companies=companies or [], impact_score=impact_score,
        created_at=_utc(when),
    )
    db.add(row)
    await db.flush()
    return row


async def make_policy(db, *, title, when: datetime):
    from app.db.models.event import GovernmentPolicy
    row = GovernmentPolicy(
        external_id=_next_id("policy"), title=title, ministry="Test Ministry",
        summary=title, created_at=_utc(when),
    )
    db.add(row)
    await db.flush()
    return row


async def make_announcement(db, *, subject, when: datetime, symbol=None, is_high_impact=False, sectors=None):
    from app.db.models.company_announcements import CompanyAnnouncement
    row = CompanyAnnouncement(
        id=_next_id("ann"), symbol=symbol, subject=subject, description=subject,
        announcement_date=_utc(when), ingested_at=_utc(when), is_high_impact=is_high_impact,
        sectors=sectors or [], impact_score=8 if is_high_impact else 3,
    )
    db.add(row)
    await db.flush()
    return row


async def make_opportunity(db, *, title, when: datetime, sectors=None, confidence=0.7, score=75.0):
    from app.db.models.opportunity import Opportunity
    row = Opportunity(
        slug=_next_id("opp"), title=title, summary=title, opportunity_score=score,
        confidence=confidence, sectors=sectors or [], created_at=_utc(when), updated_at=_utc(when),
    )
    db.add(row)
    await db.flush()
    return row


async def make_company_signal(
    db, *, symbol, when: datetime, source_type="article", source_id=None,
    signed_magnitude=10.0, confidence=0.7, sector=None, reason=None,
):
    from app.db.models.company_signal import AICompanySignal
    row = AICompanySignal(
        source_type=source_type, source_id=source_id or _next_id("src"), symbol=symbol,
        sector=sector, signed_magnitude=signed_magnitude, confidence=confidence,
        quality=0.8, reason=reason or f"{symbol} test signal", signal_at=_utc(when),
    )
    db.add(row)
    await db.flush()
    return row
