"""
Historical NSE Event/News Title Truncation Repair -- real, DB-backed tests
for POST /api/admin/repair-nse-titles, the temporary admin-protected
execution surface for the frozen NSE title-truncation repair manifests
(3,398 events / 3,382 news_articles, 2026-09-10 incident).

Per feedback_production_write_discipline: this endpoint (not a raw SSH
session) is the reviewable, auditable mechanism for the actual production
write. These tests prove the HTTP layer's auth gate, dry_run default,
state-verification guard, the extra live-recompute-before-write safeguard,
and exact-scope behavior work end-to-end through the real app, against
temporary manifest files pointed at real seeded rows (never the real
production manifests themselves).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models.event import Event
from app.db.models_legacy import NewsArticle

client = TestClient(app)
_HEADERS = {"X-Admin-Key": settings.admin_api_key}

_BEFORE = "Some Company Limited has informed the Exchange about a routine matter that got cut off…"
_SUMMARY = (
    "Some Company Limited has informed the Exchange about a routine matter that got "
    "cut off before the sentence finished, here is the rest of it now recovered."
)
_AFTER = _SUMMARY  # short enough that _clip_headline passes it through verbatim


async def _seed_event(event_id: str, **overrides) -> None:
    base = dict(id=event_id, title=_BEFORE, summary=_SUMMARY, slug=f"test-nse-{uuid.uuid4().hex[:8]}")
    base.update(overrides)
    async with AsyncSessionLocal() as db:
        db.add(Event(**base))
        await db.commit()


async def _seed_news(news_id: str, **overrides) -> None:
    base = dict(
        id=news_id, headline=_BEFORE, summary=_SUMMARY, source="NSE",
        published_at="2026-09-10T00:00:00Z", companies=[], impact_score=0.0,
    )
    base.update(overrides)
    async with AsyncSessionLocal() as db:
        db.add(NewsArticle(**base))
        await db.commit()


async def _cleanup_events(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id.in_(ids)))
        await db.commit()


async def _cleanup_news(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(NewsArticle).where(NewsArticle.id.in_(ids)))
        await db.commit()


async def _fetch_event(event_id: str) -> Event:
    async with AsyncSessionLocal() as db:
        return await db.get(Event, event_id)


async def _fetch_news(news_id: str) -> NewsArticle:
    async with AsyncSessionLocal() as db:
        return await db.get(NewsArticle, news_id)


def _write_manifest(tmp_path: Path, name: str, entries: list[dict]) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps({"description": "test", "repair_count": len(entries), "entries": entries}), encoding="utf-8")
    return p


def _patch_manifests(monkeypatch, tmp_path, event_entries=None, news_entries=None):
    monkeypatch.setattr(
        "app.api.admin._EVENT_TITLE_REPAIR_MANIFEST_PATH",
        _write_manifest(tmp_path, "events_manifest.json", event_entries or []),
    )
    monkeypatch.setattr(
        "app.api.admin._NEWS_HEADLINE_REPAIR_MANIFEST_PATH",
        _write_manifest(tmp_path, "news_manifest.json", news_entries or []),
    )


def test_missing_admin_key_is_rejected():
    resp = client.post("/api/admin/repair-nse-titles")
    assert resp.status_code == 401


def test_wrong_admin_key_is_rejected():
    resp = client.post("/api/admin/repair-nse-titles", headers={"X-Admin-Key": "definitely-wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dry_run_is_the_default_and_does_not_write(monkeypatch, tmp_path):
    eid = str(uuid.uuid4())
    await _seed_event(eid)
    try:
        _patch_manifests(monkeypatch, tmp_path, event_entries=[{"id": eid, "before": _BEFORE, "after": _AFTER, "slug": "x"}])

        resp = client.post("/api/admin/repair-nse-titles", headers=_HEADERS)  # dry_run omitted -> defaults True
        assert resp.status_code == 200
        body = resp.json()
        assert body["dry_run"] is True
        assert body["events"]["would_update"] == 1
        assert body["events"]["updated"] == 0

        event = await _fetch_event(eid)
        assert event.title == _BEFORE, "dry_run must never write"
    finally:
        await _cleanup_events(eid)


@pytest.mark.asyncio
async def test_real_execution_updates_title_only_events(monkeypatch, tmp_path):
    eid = str(uuid.uuid4())
    await _seed_event(eid)
    try:
        _patch_manifests(monkeypatch, tmp_path, event_entries=[{"id": eid, "before": _BEFORE, "after": _AFTER, "slug": "x"}])

        resp = client.post("/api/admin/repair-nse-titles?dry_run=false", headers=_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["events"]["updated"] == 1

        event = await _fetch_event(eid)
        assert event.title == _AFTER
        # untouched fields
        assert event.summary == _SUMMARY
        assert event.slug.startswith("test-nse-")
    finally:
        await _cleanup_events(eid)


@pytest.mark.asyncio
async def test_real_execution_updates_headline_only_news_articles(monkeypatch, tmp_path):
    nid = str(uuid.uuid4())
    await _seed_news(nid)
    try:
        _patch_manifests(monkeypatch, tmp_path, news_entries=[{"id": nid, "before": _BEFORE, "after": _AFTER}])

        resp = client.post("/api/admin/repair-nse-titles?dry_run=false", headers=_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["news_articles"]["updated"] == 1

        news = await _fetch_news(nid)
        assert news.headline == _AFTER
        assert news.summary == _SUMMARY
        assert news.source == "NSE"
    finally:
        await _cleanup_news(nid)


@pytest.mark.asyncio
async def test_repeat_call_after_real_execution_is_a_clean_idempotent_skip(monkeypatch, tmp_path):
    eid = str(uuid.uuid4())
    await _seed_event(eid)
    try:
        _patch_manifests(monkeypatch, tmp_path, event_entries=[{"id": eid, "before": _BEFORE, "after": _AFTER, "slug": "x"}])

        first = client.post("/api/admin/repair-nse-titles?dry_run=false", headers=_HEADERS).json()
        assert first["events"]["updated"] == 1

        second = client.post("/api/admin/repair-nse-titles?dry_run=false", headers=_HEADERS).json()
        assert second["events"]["updated"] == 0
        assert second["events"]["skipped_state_changed"] == 1

        event = await _fetch_event(eid)
        assert event.title == _AFTER, "must remain the repaired value, not be double-touched"
    finally:
        await _cleanup_events(eid)


@pytest.mark.asyncio
async def test_row_whose_state_diverged_from_snapshot_is_skipped_not_overwritten(monkeypatch, tmp_path):
    eid = str(uuid.uuid4())
    await _seed_event(eid, title="A DIFFERENT title than the manifest expects")
    try:
        _patch_manifests(monkeypatch, tmp_path, event_entries=[{"id": eid, "before": _BEFORE, "after": _AFTER, "slug": "x"}])

        resp = client.post("/api/admin/repair-nse-titles?dry_run=false", headers=_HEADERS).json()
        assert resp["events"]["updated"] == 0
        assert resp["events"]["skipped_state_changed"] == 1

        event = await _fetch_event(eid)
        assert event.title == "A DIFFERENT title than the manifest expects"
    finally:
        await _cleanup_events(eid)


@pytest.mark.asyncio
async def test_row_whose_summary_changed_since_classification_is_skipped_via_recompute_mismatch(monkeypatch, tmp_path):
    """The extra safeguard: even if `title` still matches the frozen
    `before` snapshot exactly, if the row's CURRENT `summary` no longer
    recomputes to the frozen `after` value (e.g. summary was corrected or
    re-ingested differently since classification), the write must be
    skipped -- never trust the frozen `after` blindly."""
    eid = str(uuid.uuid4())
    await _seed_event(eid, summary="A completely different summary that recomputes to something else entirely.")
    try:
        _patch_manifests(monkeypatch, tmp_path, event_entries=[{"id": eid, "before": _BEFORE, "after": _AFTER, "slug": "x"}])

        resp = client.post("/api/admin/repair-nse-titles?dry_run=false", headers=_HEADERS).json()
        assert resp["events"]["updated"] == 0
        assert resp["events"]["skipped_recompute_mismatch"] == 1

        event = await _fetch_event(eid)
        assert event.title == _BEFORE, "must not overwrite when live recompute disagrees with the frozen expectation"
    finally:
        await _cleanup_events(eid)


@pytest.mark.asyncio
async def test_unrelated_event_not_in_manifest_is_never_touched(monkeypatch, tmp_path):
    eid_in_manifest = str(uuid.uuid4())
    eid_unrelated = str(uuid.uuid4())
    await _seed_event(eid_in_manifest)
    await _seed_event(eid_unrelated, title="An unrelated event title, untouched")
    try:
        _patch_manifests(monkeypatch, tmp_path, event_entries=[{"id": eid_in_manifest, "before": _BEFORE, "after": _AFTER, "slug": "x"}])

        client.post("/api/admin/repair-nse-titles?dry_run=false", headers=_HEADERS)

        unrelated = await _fetch_event(eid_unrelated)
        assert unrelated.title == "An unrelated event title, untouched"
    finally:
        await _cleanup_events(eid_in_manifest, eid_unrelated)


@pytest.mark.asyncio
async def test_missing_row_in_db_is_reported_not_an_error(monkeypatch, tmp_path):
    nonexistent_id = str(uuid.uuid4())
    _patch_manifests(monkeypatch, tmp_path, event_entries=[{"id": nonexistent_id, "before": "x", "after": "y", "slug": "x"}])

    resp = client.post("/api/admin/repair-nse-titles?dry_run=false", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["events"]["skipped_missing"] == 1
    assert body["events"]["updated"] == 0


@pytest.mark.asyncio
async def test_both_tables_processed_in_a_single_call(monkeypatch, tmp_path):
    eid = str(uuid.uuid4())
    nid = str(uuid.uuid4())
    await _seed_event(eid)
    await _seed_news(nid)
    try:
        _patch_manifests(
            monkeypatch, tmp_path,
            event_entries=[{"id": eid, "before": _BEFORE, "after": _AFTER, "slug": "x"}],
            news_entries=[{"id": nid, "before": _BEFORE, "after": _AFTER}],
        )

        resp = client.post("/api/admin/repair-nse-titles?dry_run=false", headers=_HEADERS).json()
        assert resp["events"]["updated"] == 1
        assert resp["news_articles"]["updated"] == 1

        event = await _fetch_event(eid)
        news = await _fetch_news(nid)
        assert event.title == _AFTER
        assert news.headline == _AFTER
    finally:
        await _cleanup_events(eid)
        await _cleanup_news(nid)
