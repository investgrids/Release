"""
Workstream C (2026-11-10): search_indexable column, API exposure, schema
patch, and the one-time noindex backfill script's scope guards.
"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.insights import _list_row
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.schema_patches import _COLUMN_PATCHES, apply_schema_patches
from app.db.session import AsyncSessionLocal

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backfill_search_indexable_2026_11_10.py"
_spec = importlib.util.spec_from_file_location("backfill_search_indexable", _SCRIPT)
backfill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill)


def _article(slug: str, article_type: str = "policy_intelligence", status: str = "published") -> IntelligenceArticle:
    return IntelligenceArticle(
        id=slug, slug=slug, article_type=article_type, story_id=slug,
        story_version=1, lifecycle_status=status, status=status,
        update_count=0, update_history=[], angle="primary",
        headline=f"h {slug}", companies_affected=[], sectors_affected=[],
    )


async def _indexable(slugs: list[str]) -> dict[str, bool]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(IntelligenceArticle.slug, IntelligenceArticle.search_indexable)
            .where(IntelligenceArticle.slug.in_(slugs))
        )).all()
    return {r.slug: r.search_indexable for r in rows}


@pytest.fixture
async def seeded():
    tag = uuid.uuid4().hex[:8]
    s = {
        "target": f"pt-{tag}-target",
        "target2": f"pt-{tag}-target2",
        "not_listed": f"pt-{tag}-not-listed",
        "other_type": f"pt-{tag}-other-type",
        "draft": f"pt-{tag}-draft",
    }
    async with AsyncSessionLocal() as db:
        db.add_all([
            _article(s["target"]),
            _article(s["target2"]),
            _article(s["not_listed"]),
            _article(s["other_type"], article_type="company_intelligence"),
            _article(s["draft"], status="draft"),
        ])
        await db.commit()
    yield s
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.slug.in_(list(s.values()))))
        await db.commit()


def _listed(s: dict) -> list[str]:
    # Everything except not_listed; other_type/draft are listed to prove the scope guards hold.
    return [s["target"], s["target2"], s["other_type"], s["draft"], "slug-that-does-not-exist"]


@pytest.mark.asyncio
async def test_new_rows_default_indexable(seeded):
    assert all((await _indexable(list(seeded.values()))).values())


@pytest.mark.asyncio
async def test_list_row_exposes_search_indexable(seeded):
    async with AsyncSessionLocal() as db:
        a = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.slug == seeded["target"]))).scalar_one()
    assert _list_row(a)["search_indexable"] is True
    a.search_indexable = False
    assert _list_row(a)["search_indexable"] is False


@pytest.mark.asyncio
async def test_dry_run_changes_nothing(seeded):
    result = await backfill.run(_listed(seeded), "dry_run")
    assert result["matched_published_policy"] == 2
    assert result["would_change"] == 2
    assert result["not_found_or_out_of_scope"] == 3
    assert all((await _indexable(list(seeded.values()))).values())


@pytest.mark.asyncio
async def test_apply_flips_only_in_scope_rows(seeded):
    result = await backfill.run(_listed(seeded), "apply")
    assert result["changed"] == 2
    got = await _indexable(list(seeded.values()))
    assert got[seeded["target"]] is False
    assert got[seeded["target2"]] is False
    assert got[seeded["not_listed"]] is True
    assert got[seeded["other_type"]] is True
    assert got[seeded["draft"]] is True


@pytest.mark.asyncio
async def test_apply_is_idempotent_and_revert_restores(seeded):
    await backfill.run(_listed(seeded), "apply")
    again = await backfill.run(_listed(seeded), "apply")
    assert again["changed"] == 0
    assert again["already_in_target_state"] == 2

    reverted = await backfill.run(_listed(seeded), "revert")
    assert reverted["changed"] == 2
    assert all((await _indexable(list(seeded.values()))).values())


def test_committed_slug_file_is_clean():
    slugs = backfill.load_slugs()
    assert len(slugs) == 1439
    assert len(set(slugs)) == len(slugs)
    assert all(s and "/" not in s and "," not in s for s in slugs)


def test_schema_patch_registered():
    assert ("intelligence_articles", "search_indexable", "BOOLEAN NOT NULL DEFAULT 1") in _COLUMN_PATCHES


@pytest.mark.asyncio
async def test_schema_patch_adds_column_to_preexisting_table_defaulting_true():
    # Production already has intelligence_articles without this column; the
    # patch must add it and every existing row must read as indexable.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE intelligence_articles (id VARCHAR PRIMARY KEY, slug VARCHAR)"))
            await conn.execute(text("INSERT INTO intelligence_articles (id, slug) VALUES ('a', 'a'), ('b', 'b')"))
            await apply_schema_patches(conn)
            await apply_schema_patches(conn)  # second boot is a no-op
            vals = (await conn.execute(text("SELECT search_indexable FROM intelligence_articles"))).scalars().all()
        assert vals == [1, 1]
    finally:
        await engine.dispose()
