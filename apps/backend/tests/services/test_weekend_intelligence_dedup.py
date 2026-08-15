"""
Evidence clustering tests — brief §6/§30 ("duplicate representations of
same event" is an explicitly required test case).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.opportunity import Opportunity, OpportunityEvent
from app.db.session import AsyncSessionLocal
from app.services.weekend_intelligence.dedup import cluster_evidence
from app.services.weekend_intelligence.evidence import DETERMINISTIC, HEURISTIC, EvidenceItem

_NOW = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)


def _item(source_type: str, source_id: str, title: str, companies=None, observed_at=_NOW, direction=None,
          score_kind=HEURISTIC) -> EvidenceItem:
    return EvidenceItem(
        source_type=source_type, source_id=source_id, observed_at=observed_at, title=title,
        companies=companies or [], direction=direction, score_kind=score_kind,
    )


@pytest.mark.asyncio
async def test_unrelated_items_stay_in_separate_clusters():
    async with AsyncSessionLocal() as db:
        evidence = [
            _item("news", "n1", "RBI holds repo rate steady", companies=["HDFCBANK"]),
            _item("news", "n2", "Reliance announces new refinery capacity", companies=["RELIANCE"]),
        ]
        clusters = await cluster_evidence(db, evidence)
        assert len(clusters) == 2


@pytest.mark.asyncio
async def test_same_story_different_sources_merges_via_title_and_company_heuristic():
    """The exact brief §6 scenario: one real development represented as
    NewsArticle + Event with overlapping title/company, close in time —
    must merge into ONE cluster, not count as two independent
    confirmations."""
    async with AsyncSessionLocal() as db:
        evidence = [
            _item("news", "n1", "Tata Motors reports strong Q1 earnings beat", companies=["TATAMOTORS"],
                  observed_at=_NOW, direction="positive"),
            _item("event", "e1", "Tata Motors Q1 earnings beat market expectations", companies=["TATAMOTORS"],
                  observed_at=_NOW, direction="positive", score_kind=DETERMINISTIC),
        ]
        clusters = await cluster_evidence(db, evidence)
        assert len(clusters) == 1
        assert clusters[0].source_types == {"news", "event"}
        assert {r["source_id"] for r in clusters[0].evidence_refs()} == {"n1", "e1"}


@pytest.mark.asyncio
async def test_distant_in_time_does_not_merge_even_with_matching_title():
    old = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)
    async with AsyncSessionLocal() as db:
        evidence = [
            _item("news", "n1", "Tata Motors reports strong Q1 earnings beat", companies=["TATAMOTORS"], observed_at=old),
            _item("event", "e1", "Tata Motors reports strong Q1 earnings beat", companies=["TATAMOTORS"], observed_at=_NOW),
        ]
        clusters = await cluster_evidence(db, evidence)
        assert len(clusters) == 2


@pytest.mark.asyncio
async def test_opportunity_event_real_link_merges_regardless_of_title():
    """Tier-1 exact relational link (OpportunityEvent junction table) —
    must merge even when the titles look nothing alike, because this is
    a REAL DB relationship, not a heuristic guess."""
    opp_id = None
    event_id = f"pytest-dedup-evt-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            opp = Opportunity(slug=f"pytest-dedup-{uuid.uuid4().hex[:8]}", title="Defence manufacturing opportunity",
                               summary="s", sectors=["Defence"])
            db.add(opp)
            await db.flush()
            opp_id = opp.id
            db.add(OpportunityEvent(opportunity_id=opp_id, event_id=event_id, title="link"))
            await db.commit()

        async with AsyncSessionLocal() as db:
            evidence = [
                _item("opportunity", str(opp_id), "Totally different wording here", companies=["BEL"]),
                _item("event", event_id, "Completely unrelated-looking headline", companies=["HAL"],
                      score_kind=DETERMINISTIC),
            ]
            clusters = await cluster_evidence(db, evidence)
            assert len(clusters) == 1
            assert clusters[0].companies == {"BEL", "HAL"}
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(OpportunityEvent).where(OpportunityEvent.event_id == event_id))
            if opp_id is not None:
                await db.execute(delete(Opportunity).where(Opportunity.id == opp_id))
            await db.commit()


@pytest.mark.asyncio
async def test_company_signal_opportunity_source_id_encoding_links_correctly():
    """AICompanySignal(source_type='opportunity', source_id=X) must link
    to the Opportunity EvidenceItem with source_id==X, via the
    'opportunity:<id>' encoding evidence.py's normalizer already
    produces."""
    async with AsyncSessionLocal() as db:
        evidence = [
            _item("opportunity", "42", "Some opportunity", companies=["INFY"]),
            _item("company_signal", "opportunity:42", "INFY signal from that opportunity", companies=["INFY"],
                  score_kind=HEURISTIC),
        ]
        clusters = await cluster_evidence(db, evidence)
        assert len(clusters) == 1
        assert clusters[0].source_types == {"opportunity", "company_signal"}


@pytest.mark.asyncio
async def test_cluster_net_direction_mixed_on_contradiction():
    async with AsyncSessionLocal() as db:
        evidence = [
            _item("news", "n1", "Company X wins large order boosting outlook", companies=["INFY"], direction="positive"),
            _item("event", "e1", "Company X wins large order boosting outlook", companies=["INFY"], direction="negative",
                  score_kind=DETERMINISTIC),
        ]
        clusters = await cluster_evidence(db, evidence)
        assert len(clusters) == 1
        assert clusters[0].net_direction == "mixed"


@pytest.mark.asyncio
async def test_representative_prefers_deterministic_member():
    async with AsyncSessionLocal() as db:
        evidence = [
            _item("news", "n1", "Company X wins large order for expansion", companies=["INFY"]),
            _item("event", "e1", "Company X wins large order for expansion", companies=["INFY"], score_kind=DETERMINISTIC),
        ]
        clusters = await cluster_evidence(db, evidence)
        assert clusters[0].representative.source_type == "event"


@pytest.mark.asyncio
async def test_empty_evidence_produces_no_clusters():
    async with AsyncSessionLocal() as db:
        clusters = await cluster_evidence(db, [])
        assert clusters == []


@pytest.mark.asyncio
async def test_two_company_less_items_merge_on_title_and_time_alone():
    """Tier-2 fix: GovernmentPolicy (and any other source) never carries
    a companies list, so the OLD "AND at least one shared company" rule
    made it structurally impossible for two independently-ingested
    reports of the same broad-market/macro development (e.g. an RBI
    policy decision covered by two outlets, neither tagging a specific
    company) to ever merge — an empty list can never overlap with
    anything. Two company-less items with matching titles and close
    timing must now merge."""
    async with AsyncSessionLocal() as db:
        evidence = [
            _item("news", "n1", "RBI holds repo rate steady citing inflation concerns"),
            _item("policy", "p1", "RBI holds repo rate steady amid inflation concerns"),
        ]
        clusters = await cluster_evidence(db, evidence)
        assert len(clusters) == 1
        assert clusters[0].source_types == {"news", "policy"}


@pytest.mark.asyncio
async def test_company_specific_item_does_not_merge_with_company_less_item():
    """A company-less broad-market item and a company-specific item must
    NOT merge just because of generic shared title words — the
    company-compatibility gate still applies whenever either side names
    a company."""
    async with AsyncSessionLocal() as db:
        evidence = [
            _item("news", "n1", "Market rallies on strong quarterly earnings across the board"),
            _item("event", "e1", "Market rallies as TCS posts strong quarterly earnings", companies=["TCS"],
                  score_kind=DETERMINISTIC),
        ]
        clusters = await cluster_evidence(db, evidence)
        assert len(clusters) == 2


@pytest.mark.asyncio
async def test_two_different_companies_do_not_merge_on_generic_title_overlap():
    async with AsyncSessionLocal() as db:
        evidence = [
            _item("news", "n1", "Company posts strong quarterly earnings beat", companies=["TCS"]),
            _item("news", "n2", "Company posts strong quarterly earnings beat", companies=["INFY"]),
        ]
        clusters = await cluster_evidence(db, evidence)
        assert len(clusters) == 2
