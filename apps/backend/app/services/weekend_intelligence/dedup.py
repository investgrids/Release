"""
Re-export shim (Phase 5E.3) — the real implementation moved to
app/services/evidence_clustering/dedup.py, a neutral home shared with
Opportunity Radar and AI Search (this clustering logic was never
actually Weekend-Intelligence-specific; only its import path was).
Kept here unchanged so this package's own internal importers
(aggregator.py, materiality.py, sector_synthesis.py, company_synthesis.py
— and their tests) don't need to change. New code should import from
app.services.evidence_clustering directly.
"""
from __future__ import annotations

from app.services.evidence_clustering.dedup import EvidenceCluster, cluster_evidence

__all__ = ["EvidenceCluster", "cluster_evidence"]
