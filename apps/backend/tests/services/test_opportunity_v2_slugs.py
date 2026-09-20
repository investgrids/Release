"""
opportunity_v2/slugs.py + slug_backfill.py — real DB-backed contract
tests. Same isolation precedent as test_opportunity_v2_orchestration.py
(tests/conftest.py's session-wide scratch-DB guardrail applies here too,
never the real dev DB).

Scope, per the 2026-09-19 Opportunity V2 production gate follow-up:
compute_opportunity_slug's real determinism/collision behavior, and
backfill_opportunity_v2_slugs's "only touch NULL rows, idempotent"
contract. Deliberately tests the REAL collision-avoidance mechanism
(the opportunity_id[:8] suffix) rather than inventing a check-and-retry
loop the code does not have (there is none -- see opportunity_v2.py's
own column comment: no DB-level UNIQUE constraint, deferred until
promotion).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.opportunity_v2 import OpportunityV2
from app.db.session import AsyncSessionLocal
from app.services.opportunity_v2.slug_backfill import backfill_opportunity_v2_slugs
from app.services.opportunity_v2.slugs import compute_opportunity_slug


def _make_opp(*, id_: str | None = None, current_title: str | None = None,
              formation_title: str | None = None, thesis_anchor: str = "company:testco",
              slug: str | None = None) -> OpportunityV2:
    now = datetime.now(timezone.utc)
    return OpportunityV2(
        id=id_ or str(uuid.uuid4()), thesis_anchor=thesis_anchor, thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status="shadow",
        formation_title=formation_title, formation_score=50.0, formation_at=now,
        current_title=current_title, current_summary="Real test summary.", current_score=55.0,
        sectors=[], companies=[], slug=slug, contradictions=[],
        created_at=now, updated_at=now,
    )


async def _cleanup(opportunity_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(opportunity_ids)))
        await db.commit()


# ── compute_opportunity_slug — deterministic output ──────────────────────

def test_same_id_and_title_always_produce_the_same_slug():
    opp_id = str(uuid.uuid4())
    title = "Real Test Opportunity Title"
    first = compute_opportunity_slug(opp_id, title)
    second = compute_opportunity_slug(opp_id, title)
    assert first == second


def test_slug_is_a_real_lowercase_hyphenated_transform_of_the_title():
    opp_id = str(uuid.uuid4())
    slug = compute_opportunity_slug(opp_id, "Aditya Birla Capital Gold Loan Expansion")
    assert slug.startswith("aditya-birla-capital-gold-loan-expansion-")
    assert slug == slug.lower()
    assert " " not in slug


# ── Collision handling — the REAL mechanism (id-prefix suffix entropy) ──

def test_two_different_opportunities_with_the_identical_title_get_different_slugs():
    """No check-and-retry loop exists (see opportunity_v2.py's own column
    comment) -- the real, only collision defense is the opportunity_id[:8]
    suffix. This proves that defense actually works for two distinct real
    ids sharing the same title, not that a retry mechanism exists."""
    id_a, id_b = str(uuid.uuid4()), str(uuid.uuid4())
    title = "Identical Real Title Shared By Two Theses"
    slug_a = compute_opportunity_slug(id_a, title)
    slug_b = compute_opportunity_slug(id_b, title)
    assert slug_a != slug_b
    assert slug_a.endswith(id_a[:8])
    assert slug_b.endswith(id_b[:8])


def test_slug_suffix_is_derived_from_the_real_opportunity_id_not_random():
    opp_id = str(uuid.uuid4())
    slug = compute_opportunity_slug(opp_id, "Some Real Title")
    assert slug.endswith(opp_id[:8])


# ── Backfill — only touches missing slugs, idempotent ────────────────────

@pytest.mark.asyncio
async def test_backfill_only_touches_rows_with_null_slug():
    opp_with_slug = _make_opp(current_title="Already Has A Real Slug", slug="pre-existing-real-slug-abcd1234")
    opp_without_slug = _make_opp(current_title="Needs A Real Backfilled Slug", slug=None)
    async with AsyncSessionLocal() as db:
        db.add(opp_with_slug)
        db.add(opp_without_slug)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await backfill_opportunity_v2_slugs(db)

        async with AsyncSessionLocal() as db:
            refreshed_with = await db.get(OpportunityV2, opp_with_slug.id)
            refreshed_without = await db.get(OpportunityV2, opp_without_slug.id)

        assert refreshed_with.slug == "pre-existing-real-slug-abcd1234", "backfill must never overwrite an existing real slug"
        assert refreshed_without.slug is not None
        assert refreshed_without.slug.endswith(opp_without_slug.id[:8])
        assert result["updated"] >= 1
    finally:
        await _cleanup([opp_with_slug.id, opp_without_slug.id])


@pytest.mark.asyncio
async def test_backfill_prefers_current_title_then_formation_title_then_thesis_anchor():
    opp_current = _make_opp(current_title="Real Current Title", formation_title="Real Formation Title", slug=None)
    opp_formation_only = _make_opp(current_title=None, formation_title="Real Formation Only Title", slug=None)
    opp_anchor_only = _make_opp(current_title=None, formation_title=None, thesis_anchor="company:fallbackanchor", slug=None)
    async with AsyncSessionLocal() as db:
        db.add(opp_current)
        db.add(opp_formation_only)
        db.add(opp_anchor_only)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            await backfill_opportunity_v2_slugs(db)

        async with AsyncSessionLocal() as db:
            r_current = await db.get(OpportunityV2, opp_current.id)
            r_formation = await db.get(OpportunityV2, opp_formation_only.id)
            r_anchor = await db.get(OpportunityV2, opp_anchor_only.id)

        assert r_current.slug.startswith("real-current-title-")
        assert r_formation.slug.startswith("real-formation-only-title-")
        assert r_anchor.slug.startswith("company-fallbackanchor-")
    finally:
        await _cleanup([opp_current.id, opp_formation_only.id, opp_anchor_only.id])


@pytest.mark.asyncio
async def test_backfill_is_idempotent_a_second_run_changes_nothing():
    opp = _make_opp(current_title="Idempotency Real Test Title", slug=None)
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            first_result = await backfill_opportunity_v2_slugs(db)
        async with AsyncSessionLocal() as db:
            after_first = await db.get(OpportunityV2, opp.id)
            slug_after_first = after_first.slug

        async with AsyncSessionLocal() as db:
            second_result = await backfill_opportunity_v2_slugs(db)
        async with AsyncSessionLocal() as db:
            after_second = await db.get(OpportunityV2, opp.id)

        assert slug_after_first is not None
        assert after_second.slug == slug_after_first, "a second backfill run must never regenerate an existing slug"
        assert first_result["updated"] >= 1
        # Not asserting second_result["updated"] == 0 in absolute terms --
        # the scratch DB is shared across the whole test session (see
        # tests/conftest.py), so another well-behaved test could legitimately
        # have its own null-slug row present concurrently. The real
        # idempotency proof is that THIS row's slug is provably unchanged
        # above; second_result is only checked to confirm the function
        # still runs cleanly on a second call.
        assert second_result["candidates"] >= 0
    finally:
        await _cleanup([opp.id])
