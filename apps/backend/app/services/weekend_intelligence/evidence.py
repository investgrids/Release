"""
Re-export shim (Phase 5E.3) — the real implementation moved to
app/services/evidence_clustering/evidence.py, a neutral home shared
with Opportunity Radar and AI Search (this logic was never actually
Weekend-Intelligence-specific; only its import path was). Kept here
unchanged so this package's own internal importers (historical_
integration.py, materiality.py, sector_synthesis.py, company_synthesis.py,
confidence.py, aggregator.py, evidence_window.py — 8 production files
plus their tests) don't need to change. New code should import from
app.services.evidence_clustering directly.
"""
from __future__ import annotations

from app.services.evidence_clustering.evidence import (
    DERIVED,
    DETERMINISTIC,
    HEURISTIC,
    LLM_SELF_RATED,
    UNKNOWN,
    EvidenceItem,
    normalize_announcement,
    normalize_company_signal,
    normalize_event,
    normalize_news,
    normalize_opportunity,
    normalize_policy,
)

__all__ = [
    "DERIVED", "DETERMINISTIC", "HEURISTIC", "LLM_SELF_RATED", "UNKNOWN",
    "EvidenceItem",
    "normalize_announcement", "normalize_company_signal", "normalize_event",
    "normalize_news", "normalize_opportunity", "normalize_policy",
]
