"""
Historical Question-Intelligence Title Remediation -- real, DB-backed tests
for POST /api/admin/repair-question-titles, the temporary admin-protected
execution surface for the frozen 62-row title-completeness repair manifest.

Per feedback_production_write_discipline: this endpoint (not a raw SSH
session) is the reviewable, auditable mechanism for the actual production
write -- these tests prove the HTTP layer's auth gate, dry_run default,
idempotency/state-verification guard, and exact-scope behavior work
end-to-end through the real app, against a temporary manifest file pointed
at real seeded rows (never the real 62-row production manifest itself).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle

client = TestClient(app)
_HEADERS = {"X-Admin-Key": settings.admin_api_key}


async def _seed(article_id: str, **overrides) -> None:
    now = datetime.now(timezone.utc)
    base = dict(
        id=article_id, slug=f"test-titlerepair-{uuid.uuid4().hex[:8]}",
        article_type="question_intelligence", angle="question", angle_entity="TESTCO",
        lifecycle_status="published", status="published",
        headline="Should I Buy TestCo? Some Truncated Broken Fragment...",
        seo_title="Should I Buy TestCo? Some Truncated Broken",
        json_ld={"headline": "Should I Buy TestCo? Some Truncated Broken Fragment...", "@type": "NewsArticle"},
        executive_summary="s", key_takeaway="k",
        companies_affected=[{"symbol": "TESTCO", "name": "TestCo Ltd", "impact": "positive"}],
        sectors_affected=[], sources=["NSE"],
        market_context={"session": "post_market"}, published_at=now, last_updated=now,
    )
    base.update(overrides)
    async with AsyncSessionLocal() as db:
        db.add(IntelligenceArticle(**base))
        await db.commit()


async def _cleanup(*article_ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(article_ids)))
        await db.commit()


async def _fetch(article_id: str) -> IntelligenceArticle:
    async with AsyncSessionLocal() as db:
        return await db.get(IntelligenceArticle, article_id)


def _write_test_manifest(tmp_path: Path, entries: list[dict]) -> Path:
    manifest = {"description": "test manifest", "repair_count": len(entries), "entries": entries}
    p = tmp_path / "test_manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


def test_missing_admin_key_is_rejected():
    resp = client.post("/api/admin/repair-question-titles")
    assert resp.status_code == 401


def test_wrong_admin_key_is_rejected():
    resp = client.post("/api/admin/repair-question-titles", headers={"X-Admin-Key": "definitely-wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dry_run_is_the_default_and_does_not_write(monkeypatch, tmp_path):
    aid = str(uuid.uuid4())
    await _seed(aid)
    try:
        entry = {
            "id": aid,
            "before": {
                "headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",
                "seo_title": "Should I Buy TestCo? Some Truncated Broken",
                "json_ld_headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",
            },
            "proposed": {
                "headline": "Should I Buy TestCo? What Investors Need To Know",
                "seo_title": "Should I Buy TestCo? What Investors Need To Know",
                "json_ld_headline": "Should I Buy TestCo? What Investors Need To Know",
            },
        }
        manifest_path = _write_test_manifest(tmp_path, [entry])
        monkeypatch.setattr("app.api.admin._TITLE_REPAIR_MANIFEST_PATH", manifest_path)

        resp = client.post("/api/admin/repair-question-titles", headers=_HEADERS)  # dry_run omitted -> defaults True
        assert resp.status_code == 200
        body = resp.json()
        assert body["dry_run"] is True
        assert body["would_update"] == 1
        assert body["updated"] == 0

        article = await _fetch(aid)
        assert article.headline == "Should I Buy TestCo? Some Truncated Broken Fragment...", "dry_run must never write"
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_real_execution_updates_headline_seo_title_and_json_ld_only(monkeypatch, tmp_path):
    aid = str(uuid.uuid4())
    await _seed(aid)
    try:
        entry = {
            "id": aid,
            "before": {
                "headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",
                "seo_title": "Should I Buy TestCo? Some Truncated Broken",
                "json_ld_headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",
            },
            "proposed": {
                "headline": "Should I Buy TestCo? What Investors Need To Know",
                "seo_title": "Should I Buy TestCo? What Investors Need To Know",
                "json_ld_headline": "Should I Buy TestCo? What Investors Need To Know",
            },
        }
        manifest_path = _write_test_manifest(tmp_path, [entry])
        monkeypatch.setattr("app.api.admin._TITLE_REPAIR_MANIFEST_PATH", manifest_path)

        resp = client.post("/api/admin/repair-question-titles?dry_run=false", headers=_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["updated"] == 1

        article = await _fetch(aid)
        assert article.headline == "Should I Buy TestCo? What Investors Need To Know"
        assert article.seo_title == "Should I Buy TestCo? What Investors Need To Know"
        assert article.json_ld["headline"] == "Should I Buy TestCo? What Investors Need To Know"
        # untouched fields
        assert article.slug.startswith("test-titlerepair-")
        assert article.companies_affected == [{"symbol": "TESTCO", "name": "TestCo Ltd", "impact": "positive"}]
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_repeat_call_after_real_execution_is_a_clean_idempotent_skip(monkeypatch, tmp_path):
    """Second call with the SAME manifest, after the row has already been
    repaired -- must skip (state no longer matches the frozen `before`
    snapshot), never re-apply or error."""
    aid = str(uuid.uuid4())
    await _seed(aid)
    try:
        entry = {
            "id": aid,
            "before": {
                "headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",
                "seo_title": "Should I Buy TestCo? Some Truncated Broken",
                "json_ld_headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",
            },
            "proposed": {
                "headline": "Should I Buy TestCo? What Investors Need To Know",
                "seo_title": "Should I Buy TestCo? What Investors Need To Know",
                "json_ld_headline": "Should I Buy TestCo? What Investors Need To Know",
            },
        }
        manifest_path = _write_test_manifest(tmp_path, [entry])
        monkeypatch.setattr("app.api.admin._TITLE_REPAIR_MANIFEST_PATH", manifest_path)

        first = client.post("/api/admin/repair-question-titles?dry_run=false", headers=_HEADERS).json()
        assert first["updated"] == 1

        second = client.post("/api/admin/repair-question-titles?dry_run=false", headers=_HEADERS).json()
        assert second["updated"] == 0
        assert second["skipped_state_changed"] == 1

        article = await _fetch(aid)
        assert article.headline == "Should I Buy TestCo? What Investors Need To Know", "must remain the repaired value, not be double-touched"
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_row_whose_state_diverged_from_snapshot_is_skipped_not_overwritten(monkeypatch, tmp_path):
    """A row that changed (e.g. a continuous-update pass touched it) since
    the manifest snapshot was taken must be skipped, never blindly
    overwritten with a stale proposed value."""
    aid = str(uuid.uuid4())
    await _seed(aid, headline="A DIFFERENT headline than the manifest expects")
    try:
        entry = {
            "id": aid,
            "before": {
                "headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",  # stale expectation
                "seo_title": "Should I Buy TestCo? Some Truncated Broken",
                "json_ld_headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",
            },
            "proposed": {
                "headline": "Should I Buy TestCo? What Investors Need To Know",
                "seo_title": "Should I Buy TestCo? What Investors Need To Know",
                "json_ld_headline": "Should I Buy TestCo? What Investors Need To Know",
            },
        }
        manifest_path = _write_test_manifest(tmp_path, [entry])
        monkeypatch.setattr("app.api.admin._TITLE_REPAIR_MANIFEST_PATH", manifest_path)

        resp = client.post("/api/admin/repair-question-titles?dry_run=false", headers=_HEADERS).json()
        assert resp["updated"] == 0
        assert resp["skipped_state_changed"] == 1

        article = await _fetch(aid)
        assert article.headline == "A DIFFERENT headline than the manifest expects"
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_unrelated_article_not_in_manifest_is_never_touched(monkeypatch, tmp_path):
    aid_in_manifest = str(uuid.uuid4())
    aid_unrelated = str(uuid.uuid4())
    await _seed(aid_in_manifest)
    await _seed(aid_unrelated, headline="An unrelated article headline, untouched")
    try:
        entry = {
            "id": aid_in_manifest,
            "before": {
                "headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",
                "seo_title": "Should I Buy TestCo? Some Truncated Broken",
                "json_ld_headline": "Should I Buy TestCo? Some Truncated Broken Fragment...",
            },
            "proposed": {
                "headline": "Should I Buy TestCo? What Investors Need To Know",
                "seo_title": "Should I Buy TestCo? What Investors Need To Know",
                "json_ld_headline": "Should I Buy TestCo? What Investors Need To Know",
            },
        }
        manifest_path = _write_test_manifest(tmp_path, [entry])
        monkeypatch.setattr("app.api.admin._TITLE_REPAIR_MANIFEST_PATH", manifest_path)

        client.post("/api/admin/repair-question-titles?dry_run=false", headers=_HEADERS)

        unrelated = await _fetch(aid_unrelated)
        assert unrelated.headline == "An unrelated article headline, untouched"
    finally:
        await _cleanup(aid_in_manifest, aid_unrelated)


@pytest.mark.asyncio
async def test_missing_row_in_db_is_reported_not_an_error(monkeypatch, tmp_path):
    nonexistent_id = str(uuid.uuid4())
    entry = {
        "id": nonexistent_id,
        "before": {"headline": "x", "seo_title": "x", "json_ld_headline": "x"},
        "proposed": {"headline": "y", "seo_title": "y", "json_ld_headline": "y"},
    }
    manifest_path = _write_test_manifest(tmp_path, [entry])
    monkeypatch.setattr("app.api.admin._TITLE_REPAIR_MANIFEST_PATH", manifest_path)

    resp = client.post("/api/admin/repair-question-titles?dry_run=false", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped_missing"] == 1
    assert body["updated"] == 0
