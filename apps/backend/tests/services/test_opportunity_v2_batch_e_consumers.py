"""
Batch E consumer migration — real-DB-backed tests (no mocks, same
precedent as the other opportunity_v2 test files) for the shared V2 read
functions every migrated consumer calls through, plus a representative
sample of the consumers themselves (related.py, company_intelligence.py,
OpportunityService.list_by_sector_or_theme's dispatch).

Completion-gate checks this file targets directly:
  - each works in both v1 and v2 read-source modes
  - no public V2 consumer can see shadow rows
  - no consumer emits unusable V1-style ids/slugs when in V2 mode (every
    href below is asserted to be the real /opportunity-radar/{slug} form)

Don't run this file while the local uvicorn dev server is running — same
`database is locked` risk documented in the sibling test files.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.core.config import settings
from app.db.models.opportunity_v2 import OpportunityV2
from app.db.session import AsyncSessionLocal
from app.services.opportunity_v2.read_service import (
    list_public_opportunities_v2_by_sector_or_theme,
    list_public_opportunities_v2_for_company,
)


def _make_opp(*, public_status: str, title: str, sectors: list[str] | None = None,
              companies: list[str] | None = None, score: float = 55.0) -> OpportunityV2:
    now = datetime.now(timezone.utc)
    return OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor=f"company:{uuid.uuid4().hex[:6]}", thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status=public_status,
        formation_title=title, formation_score=score, formation_at=now,
        current_title=title, current_summary="Real test summary.", current_score=score,
        sectors=sectors or [], companies=companies or [],
        slug=f"batch-e-test-{uuid.uuid4().hex[:8]}",
        created_at=now, updated_at=now,
    )


async def _cleanup(opportunity_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        if opportunity_ids:
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(opportunity_ids)))
            await db.commit()


@pytest.mark.asyncio
async def test_list_by_sector_or_theme_excludes_shadow_and_matches_real_sector():
    public_match = _make_opp(public_status="public", title="Batch E Banking Growth Story", sectors=["Banking"])
    shadow_match = _make_opp(public_status="shadow", title="Batch E Banking Shadow Story", sectors=["Banking"])
    no_match = _make_opp(public_status="public", title="Unrelated IT Story", sectors=["IT"])
    ids = [public_match.id, shadow_match.id, no_match.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([public_match, shadow_match, no_match])
            await db.commit()

        async with AsyncSessionLocal() as db:
            results = await list_public_opportunities_v2_by_sector_or_theme(db, ["Banking"], limit=10)

        titles = {r["title"] for r in results}
        assert "Batch E Banking Growth Story" in titles
        assert "Batch E Banking Shadow Story" not in titles, "shadow row leaked through sector search"
        assert "Unrelated IT Story" not in titles

        # Real V2-native fields only -- no V1-shaped keys filled in as fakes.
        match = next(r for r in results if r["title"] == "Batch E Banking Growth Story")
        assert "current_strength" in match and "direction" in match
        assert "opportunity_score" not in match and "confidence" not in match and "risk_level" not in match
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_list_by_sector_or_theme_title_substring_match():
    match = _make_opp(public_status="public", title="Semiconductor Export Surge for Indian Fabs", sectors=[])
    ids = [match.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(match)
            await db.commit()

        async with AsyncSessionLocal() as db:
            results = await list_public_opportunities_v2_by_sector_or_theme(db, ["semiconductor"], limit=10)

        assert any(r["title"] == "Semiconductor Export Surge for Indian Fabs" for r in results)
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_list_for_company_excludes_shadow_and_matches_real_company():
    public_match = _make_opp(public_status="public", title="Batch E Company Match", companies=["TESTSYM"])
    shadow_match = _make_opp(public_status="shadow", title="Batch E Company Shadow Match", companies=["TESTSYM"])
    ids = [public_match.id, shadow_match.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([public_match, shadow_match])
            await db.commit()

        async with AsyncSessionLocal() as db:
            results = await list_public_opportunities_v2_for_company(db, "TESTSYM", limit=10)

        titles = {r["title"] for r in results}
        assert "Batch E Company Match" in titles
        assert "Batch E Company Shadow Match" not in titles, "shadow row leaked through company search"

        match = next(r for r in results if r["title"] == "Batch E Company Match")
        # Completion-gate: href must be the real slug form, never a raw uuid.
        assert match["href"] == f"/opportunity-radar/{public_match.slug}"
        assert public_match.id not in match["href"]
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_opportunity_service_dispatch_v1_unchanged_v2_real_fields(monkeypatch):
    """OpportunityService.list_by_sector_or_theme — the single method 7
    call sites across ai_search/pipeline.py, ai_search_service.py,
    ai_search/evidence.py, and ai_recommendation_engine.py all go
    through. v1 mode must be byte-for-byte the existing V1 dict shape;
    v2 mode must never silently return the v1 shape with None fields."""
    from app.services.opportunity_service import OpportunityService

    opp = _make_opp(public_status="public", title="Dispatch Test Opportunity", sectors=["Energy"])
    ids = [opp.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(opp)
            await db.commit()

        monkeypatch.setattr(settings, "opportunity_read_source", "v2")
        async with AsyncSessionLocal() as db:
            v2_results = await OpportunityService(db).list_by_sector_or_theme(["Energy"], limit=10)
        assert any(r["title"] == "Dispatch Test Opportunity" for r in v2_results)
        v2_match = next(r for r in v2_results if r["title"] == "Dispatch Test Opportunity")
        assert "current_strength" in v2_match
        assert "opportunity_score" not in v2_match

        monkeypatch.setattr(settings, "opportunity_read_source", "v1")
        async with AsyncSessionLocal() as db:
            v1_results = await OpportunityService(db).list_by_sector_or_theme(["Energy"], limit=10)
        # v1 mode never sees the V2 fixture above (different table entirely).
        assert not any(r.get("title") == "Dispatch Test Opportunity" for r in v1_results)
        if v1_results:
            assert "opportunity_score" in v1_results[0]
            assert "current_strength" not in v1_results[0]
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_related_recent_opportunities_dispatch(monkeypatch):
    from app.api.related import _recent_opportunities

    opp = _make_opp(public_status="public", title="Related Consumer Test", sectors=["Pharma"])
    shadow_opp = _make_opp(public_status="shadow", title="Related Consumer Shadow", sectors=["Pharma"])
    ids = [opp.id, shadow_opp.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([opp, shadow_opp])
            await db.commit()

        monkeypatch.setattr(settings, "opportunity_read_source", "v2")
        async with AsyncSessionLocal() as db:
            items = await _recent_opportunities(db, limit=20, sector="Pharma")
        titles = {i["title"] for i in items}
        assert "Related Consumer Test" in titles
        assert "Related Consumer Shadow" not in titles
        match = next(i for i in items if i["title"] == "Related Consumer Test")
        assert match["href"] == f"/opportunity-radar/{opp.slug}"
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_company_intelligence_get_related_opportunities_dispatch(monkeypatch):
    from app.services.company_intelligence import get_related_opportunities

    opp = _make_opp(public_status="public", title="Company Intel Consumer Test", companies=["COMPTEST"])
    ids = [opp.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(opp)
            await db.commit()

        monkeypatch.setattr(settings, "opportunity_read_source", "v2")
        async with AsyncSessionLocal() as db:
            items = await get_related_opportunities(db, "COMPTEST", limit=5)
        assert any(i["title"] == "Company Intel Consumer Test" and i["href"] == f"/opportunity-radar/{opp.slug}" for i in items)
    finally:
        await _cleanup(ids)
