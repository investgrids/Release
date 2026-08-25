"""
is_opportunity_evidence_worthy() — "can this Development contribute to an
investable thesis?", deliberately separate from
development_memory/graph_link.py's is_graph_worthy() ("does this
Development deserve persistence in the Intelligence Graph?"). Those are
different questions (owner correction, 2026-08-22): a Development can be
worth graphing (corroboration OR materiality) without being a strong
enough anchor for an investment thesis, and this check must never assume
graph_link.py has already run — it reads Development's OWN fields only,
never `dev.ig_node_id`, so it stays fully independent of whether the
graph-linking job has processed this row yet.

Deliberately does NOT hard-require Development.category or .themes —
confirmed live (2026-08-22 audit): both are unpopulated on 100% of real
Development rows today (category always NULL, themes always `[]`). A gate
requiring either would pass nothing. They're read opportunistically
elsewhere once real data starts flowing (see coherence.py's STRONG-tier
theme/policy check); this gate doesn't depend on them.

Thresholds are set from the real local distribution, not guessed:
current_confidence >= 0.5 alone passes ~59% of real rows (317+166+92 of
973); impact tier passes ~13% (Critical+High+Medium ~13% real rows) —
excludes Low (49%) and unset (36%), which the sample data shows dominated
by routine NSE exchange-filing noise ("X Limited has informed the
Exchange about General Updates..."). Combined with the real-anchor check
below (80% of rows), the gate is selective without being so strict it
starves the pipeline.
"""
from __future__ import annotations

from app.db.models.development import Development

_MIN_CONFIDENCE = 0.5
_MEANINGFUL_TIERS = {"critical", "high", "medium"}


def is_opportunity_evidence_worthy(dev: Development) -> bool:
    # Real evidence must exist at all (trivially true for almost every
    # real row, but a Development can in principle have evidence_count=0
    # mid-transaction — never treat that as worthy).
    if (dev.evidence_count or 0) < 1:
        return False

    # A real anchor for what this is even about — company and/or sector
    # tags on the Development itself, independent of Intelligence Graph
    # linkage (see module docstring). Company-less AND sector-less
    # Developments carry no real subject to build a thesis around.
    has_anchor = bool(dev.primary_company) or bool(dev.companies) or bool(dev.sectors)
    if not has_anchor:
        return False

    # Meaningful confidence OR meaningful impact tier — either real signal
    # is enough on its own; a Development doesn't need both a strong tier
    # AND strong confidence, since the two axes measure different things
    # (impact_strength's own sparse/inconsistent nature is why Development
    # stores confidence as the reliable numeric axis — see
    # db/models/development.py's own docstring).
    tier = (dev.current_impact_tier or dev.formation_impact_tier or "").strip().lower()
    confidence = dev.current_confidence if dev.current_confidence is not None else dev.formation_confidence

    meaningful_tier = tier in _MEANINGFUL_TIERS
    meaningful_confidence = (confidence or 0.0) >= _MIN_CONFIDENCE

    return meaningful_tier or meaningful_confidence
