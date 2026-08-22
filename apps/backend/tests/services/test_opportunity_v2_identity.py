"""
opportunity_v2/identity.py — thesis identity computation (pure, no DB)
and the real DB-backed merge-vs-create match.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.development import Development
from app.db.models.opportunity_v2 import OpportunityV2
from app.db.session import AsyncSessionLocal
from app.services.opportunity_v2.coherence import CoherentCluster
from app.services.opportunity_v2.identity import (
    compute_thesis_identity,
    find_matching_open_opportunity,
)


def _dev(*, direction: str | None = "positive", primary_company: str | None = None,
          sectors: list[str] | None = None) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title="Test", status="open",
        primary_company=primary_company, companies=[], sectors=sectors or [], themes=[],
        first_observed_at=now, last_observed_at=now, current_direction=direction,
        evidence_count=1, schema_version="test",
    )


def test_prefers_a_real_company_graph_anchor_over_theme_or_sector():
    dev = _dev()
    cluster = CoherentCluster(developments=[dev], strong_node_ids={"theme:rate-cut-cycle", "company:hdfcbank"})
    identity = compute_thesis_identity(cluster)
    assert identity is not None
    assert identity.anchor == "company:hdfcbank"


def test_falls_back_to_a_theme_policy_or_commodity_anchor_when_no_company_present():
    dev = _dev()
    cluster = CoherentCluster(developments=[dev], strong_node_ids={"theme:rate-cut-cycle"})
    identity = compute_thesis_identity(cluster)
    assert identity is not None
    assert identity.anchor == "theme:rate-cut-cycle"


def test_falls_back_to_raw_development_fields_when_no_graph_anchor_exists():
    dev = _dev(primary_company="INFY")
    cluster = CoherentCluster(developments=[dev], strong_node_ids=set())
    identity = compute_thesis_identity(cluster)
    assert identity is not None
    assert identity.anchor == "raw_company:INFY"


def test_raw_anchor_is_never_confused_with_a_real_graph_node_id():
    dev = _dev(primary_company="INFY")
    cluster = CoherentCluster(developments=[dev], strong_node_ids=set())
    identity = compute_thesis_identity(cluster)
    assert identity is not None
    assert not identity.anchor.startswith("company:")
    assert identity.anchor.startswith("raw_company:")


def test_raw_anchor_falls_back_to_the_development_id_when_no_primary_company():
    """Regression guard (owner correction, 2026-08-22): a sector-keyed raw
    anchor used to let two unrelated company-less Developments sharing
    only a sector silently merge into one opportunity — the exact Aditya
    Birla/Goldman regression, reproduced one layer up in the identity
    match instead of coherence. There must be no `raw_sector:` anchor
    path left at all."""
    dev = _dev(primary_company=None, sectors=["Banking"])
    cluster = CoherentCluster(developments=[dev], strong_node_ids=set())
    identity = compute_thesis_identity(cluster)
    assert identity is not None
    assert identity.anchor == f"raw_dev:{dev.id}"
    assert not identity.anchor.startswith("raw_sector:")


def test_two_company_less_same_sector_developments_never_share_an_anchor():
    """The direct regression test for the fix: same sector, same
    direction, no company/graph anchor on either — under the old
    raw_sector fallback these would collide into one identity."""
    dev_a = _dev(primary_company=None, sectors=["Banking"])
    dev_b = _dev(primary_company=None, sectors=["Banking"])
    identity_a = compute_thesis_identity(CoherentCluster(developments=[dev_a], strong_node_ids=set()))
    identity_b = compute_thesis_identity(CoherentCluster(developments=[dev_b], strong_node_ids=set()))
    assert identity_a is not None and identity_b is not None
    assert identity_a.anchor != identity_b.anchor


def test_returns_none_when_the_cluster_has_no_developments_at_all():
    cluster = CoherentCluster(developments=[], strong_node_ids=set())
    assert compute_thesis_identity(cluster) is None


def test_direction_is_the_real_majority_vote_mixed_on_tie():
    dev_pos = _dev(direction="positive")
    dev_neg = _dev(direction="negative")
    cluster = CoherentCluster(developments=[dev_pos, dev_neg], strong_node_ids={"company:hdfcbank"})
    identity = compute_thesis_identity(cluster)
    assert identity is not None
    assert identity.direction == "mixed"


def test_anchor_choice_is_deterministic_across_repeated_calls():
    dev = _dev()
    cluster = CoherentCluster(developments=[dev], strong_node_ids={"company:zeecorp", "company:axisbank"})
    a1 = compute_thesis_identity(cluster)
    a2 = compute_thesis_identity(cluster)
    assert a1 is not None and a2 is not None
    assert a1.anchor == a2.anchor == "company:axisbank"  # alphabetically first, real and stable


@pytest.mark.asyncio
async def test_finds_a_real_open_opportunity_with_matching_thesis():
    from app.services.opportunity_v2.identity import ThesisIdentity

    opp = OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor="company:hdfcbank", thesis_direction="positive",
        status="open", source="opportunity_v2_shadow",
    )
    try:
        async with AsyncSessionLocal() as db:
            db.add(opp)
            await db.commit()
            found = await find_matching_open_opportunity(db, ThesisIdentity(anchor="company:hdfcbank", direction="positive"))
            assert found is not None
            assert found.id == opp.id
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id == opp.id))
            await db.commit()


@pytest.mark.asyncio
async def test_does_not_match_a_closed_opportunity_with_the_same_thesis():
    from app.services.opportunity_v2.identity import ThesisIdentity

    opp = OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor="company:hdfcbank", thesis_direction="positive",
        status="closed", source="opportunity_v2_shadow",
    )
    try:
        async with AsyncSessionLocal() as db:
            db.add(opp)
            await db.commit()
            found = await find_matching_open_opportunity(db, ThesisIdentity(anchor="company:hdfcbank", direction="positive"))
            assert found is None
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id == opp.id))
            await db.commit()


@pytest.mark.asyncio
async def test_does_not_match_the_same_anchor_with_opposite_direction():
    from app.services.opportunity_v2.identity import ThesisIdentity

    opp = OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor="company:hdfcbank", thesis_direction="positive",
        status="open", source="opportunity_v2_shadow",
    )
    try:
        async with AsyncSessionLocal() as db:
            db.add(opp)
            await db.commit()
            found = await find_matching_open_opportunity(db, ThesisIdentity(anchor="company:hdfcbank", direction="negative"))
            assert found is None
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id == opp.id))
            await db.commit()
