"""Structured Event.source_url contract (2026-10-25) — migration, persistence,
schema, serializer consistency, and legacy-rebuild consistency. Local/mocked;
no network, no production."""
from __future__ import annotations

import inspect
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.event import Event
from app.db.schema_patches import _COLUMN_PATCHES, apply_schema_patches, relax_events_score_columns
from app.providers import RawItem
from app.schemas.event_detail import EventInfo
import app.services.event_service as event_service
from app.tasks import ingest_tasks


def test_source_url_patch_registered():
    assert ("events", "source_url", "VARCHAR(1000)") in _COLUMN_PATCHES


@pytest.mark.asyncio
async def test_source_url_column_added_to_pre_migration_events():
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_async_engine(f"sqlite+aiosqlite:///{Path(tmp) / 'pre.db'}")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                # simulate a genuinely pre-migration events table
                await conn.execute(text("ALTER TABLE events DROP COLUMN source_url"))
            async with engine.begin() as conn:
                cols = {r[1] for r in (await conn.execute(text("PRAGMA table_info(events)"))).fetchall()}
                assert "source_url" not in cols, "setup failed to simulate pre-migration table"
            async with engine.begin() as conn:
                await apply_schema_patches(conn)
            async with engine.begin() as conn:
                cols = {r[1] for r in (await conn.execute(text("PRAGMA table_info(events)"))).fetchall()}
                assert "source_url" in cols, "apply_schema_patches must add events.source_url"
            async with engine.begin() as conn:
                await apply_schema_patches(conn)  # idempotent re-run (every boot)
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_create_events_persists_source_url_and_none():
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_async_engine(f"sqlite+aiosqlite:///{Path(tmp) / 'ev.db'}")
        Session = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            with_url = RawItem(id="edgar-1", headline="A", summary="s", source="SEC EDGAR",
                               url="https://www.sec.gov/x-index.htm", event_type="filing")
            no_url = RawItem(id="edgar-2", headline="B", summary="s", source="SEC EDGAR",
                             url="", event_type="filing")
            async with Session() as db:
                n = await ingest_tasks._create_events(db, [with_url, no_url], {"edgar-1", "edgar-2"}, "filing")
                assert n == 2
            async with Session() as db:
                e1 = (await db.execute(select(Event).where(Event.id == "edgar-1"))).scalar_one()
                e2 = (await db.execute(select(Event).where(Event.id == "edgar-2"))).scalar_one()
                assert e1.source_url == "https://www.sec.gov/x-index.htm"
                assert e2.source_url is None  # empty url -> None, never ""
        finally:
            await engine.dispose()


def test_event_info_schema_has_source_url():
    assert EventInfo(id="x", title="t").source_url is None            # backward compatible default
    assert EventInfo(id="x", title="t", source_url="u").source_url == "u"


def test_serializer_event_block_includes_source_url():
    # the top-level "event" block of the EventDetail serializer carries it
    assert '"source_url": event.source_url' in inspect.getsource(event_service)


def test_relax_rebuild_mirrors_source_url():
    # the legacy events-rebuild must preserve the new column (DDL + copy)
    src = inspect.getsource(relax_events_score_columns)
    assert "source_url VARCHAR(1000)" in src            # events_rebuilt DDL
    assert "source, source_url, event_type" in src       # INSERT ... SELECT column order
