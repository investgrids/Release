"""
Regression suite — app.tasks.ingest_tasks._persist_macro_releases (Phase 7,
2026-08 audit). DB-touching, against the real configured DB (this
codebase's convention), unique test-scoped ids, explicit cleanup.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.db.models.macro_release import MacroRelease
from app.providers.base import RawItem
from app.tasks.ingest_tasks import _persist_macro_releases


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MacroRelease).where(MacroRelease.id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_creates_macro_release_only_for_parseable_items():
    parseable_id = f"pytest-macro-{uuid.uuid4().hex[:8]}"
    unparseable_id = f"pytest-macro-none-{uuid.uuid4().hex[:8]}"
    ids = [parseable_id, unparseable_id]
    await _cleanup(*ids)
    try:
        items = [
            RawItem(
                id=parseable_id,
                headline="CPI inflation eases to 4.2% in July 2026",
                summary="against 4.8% in June 2026",
                source="PIB", url="https://pib.gov.in/test", published_at="2026-08-12",
            ),
            RawItem(
                id=unparseable_id,
                headline="Finance Minister holds pre-budget consultations",
                summary="Meeting with industry stakeholders scheduled",
                source="PIB", url="https://pib.gov.in/test2", published_at="2026-08-12",
            ),
        ]
        async with AsyncSessionLocal() as db:
            saved = await _persist_macro_releases(db, items)
            assert saved == 1

            rows = (await db.execute(select(MacroRelease).where(MacroRelease.id.in_(ids)))).scalars().all()
        by_id = {r.id: r for r in rows}
        assert parseable_id in by_id
        assert unparseable_id not in by_id
        assert by_id[parseable_id].metric == "CPI"
        assert by_id[parseable_id].release_value == 4.2
        assert by_id[parseable_id].event_id == parseable_id  # shares id with the Event row, no separate FK
    finally:
        await _cleanup(*ids)


@pytest.mark.asyncio
async def test_does_not_duplicate_on_repeated_ingestion():
    test_id = f"pytest-macro-dup-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        item = RawItem(
            id=test_id, headline="GST revenue collection for July 2026 stands at ₹1,87,000 crore",
            summary="", source="PIB", url="https://pib.gov.in/test3", published_at="2026-08-12",
        )
        async with AsyncSessionLocal() as db:
            first = await _persist_macro_releases(db, [item])
            second = await _persist_macro_releases(db, [item])
        assert first == 1
        assert second == 0  # already exists — must not create a duplicate row

        async with AsyncSessionLocal() as db:
            count = (await db.execute(
                select(MacroRelease).where(MacroRelease.id == test_id)
            )).scalars().all()
        assert len(count) == 1
    finally:
        await _cleanup(test_id)
