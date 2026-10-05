"""
Answer Experience V2 (AEV2) — evidence-first AI Search answer redesign.

Design closed 2026-09-21 (Rev. 3 + implementation errata, owner-approved).
This package is the FOUNDATION slice only: rollout mode plumbing, the
additive response schema, the deterministic recommendation-language gate,
sanitized telemetry, and the cache-safe assembly point. Full field
restructuring (companies_affected attribution, evidence[] claim
citations, related_intelligence canonical links) is explicitly deferred
to the next slice — see each module's own docstring for exactly what is
and isn't implemented yet.

Nothing in this package is reachable from a live request until
AI_SEARCH_AEV2_MODE is set to something other than "off" — see mode.py.
"""
