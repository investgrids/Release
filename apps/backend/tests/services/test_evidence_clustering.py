"""
Phase 5E.3 — the shared evidence-clustering package extracted from
weekend_intelligence/{evidence,dedup}.py. Full behavioral coverage
already exists (test_weekend_intelligence_dedup.py,
test_weekend_intelligence_evidence.py) since this is the SAME code,
re-exported unchanged from its new home — this file just proves the
new import path is real, independent of weekend_intelligence, and that
the re-export shim is a true identity (not a copy that could drift).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.evidence_clustering.dedup import EvidenceCluster, cluster_evidence
from app.services.evidence_clustering.evidence import (
    DETERMINISTIC,
    HEURISTIC,
    EvidenceItem,
)


def test_new_home_is_importable_independent_of_weekend_intelligence():
    item = EvidenceItem(
        source_type="event", source_id="evt-1", observed_at=datetime.now(timezone.utc),
        title="Test Event", score_kind=DETERMINISTIC,
    )
    assert item.source_type == "event"


def test_weekend_intelligence_shim_is_the_same_object_not_a_copy():
    """Guards against future drift: if someone edits the moved file but
    not the shim (or vice versa), this catches it immediately rather
    than two divergent implementations silently coexisting."""
    from app.services.weekend_intelligence.evidence import EvidenceItem as WI_Item
    from app.services.weekend_intelligence.dedup import EvidenceCluster as WI_Cluster
    assert WI_Item is EvidenceItem
    assert WI_Cluster is EvidenceCluster


@pytest.mark.asyncio
async def test_cluster_evidence_merges_same_story_two_sources(monkeypatch):
    """The exact scenario Phase 5E was scoped around: the same real
    development (e.g. an NSE filing also covered by a news outlet)
    must cluster into ONE EvidenceCluster, not two independent ones."""
    now = datetime.now(timezone.utc)
    a = EvidenceItem(
        source_type="event", source_id="evt-1", observed_at=now,
        title="Kotak Mahindra Bank Limited has informed the Exchange about Investor Presentation",
        companies=["KOTAKBANK"], score_kind=DETERMINISTIC,
    )
    b = EvidenceItem(
        source_type="announcement", source_id="ann-1", observed_at=now,
        title="Kotak Mahindra Bank informs Exchange of Investor Presentation",
        companies=["KOTAKBANK"], score_kind=HEURISTIC,
    )
    c = EvidenceItem(
        source_type="event", source_id="evt-2", observed_at=now,
        title="Reliance Industries announces new refinery capacity expansion plan",
        companies=["RELIANCE"], score_kind=DETERMINISTIC,
    )

    class _FakeDB:
        async def execute(self, *a, **kw):
            class _R:
                def all(self): return []
            return _R()

    clusters = await cluster_evidence(_FakeDB(), [a, b, c])
    by_size = sorted(clusters, key=lambda cl: -len(cl.members))
    assert len(by_size[0].members) == 2  # a + b merged
    assert by_size[0].source_types == {"event", "announcement"}
    assert len(by_size[1].members) == 1  # c stays separate (different company/story)
