"""
Development Memory — Phase 6A.

Gives app/services/evidence_clustering/'s EvidenceCluster a persistent
identity (app/db/models/development.py). See identity.py for the
matching/merge lifecycle and sync.py for the scheduled job that feeds it.
"""
from __future__ import annotations

from app.services.development_memory.identity import resolve_development

__all__ = ["resolve_development"]
