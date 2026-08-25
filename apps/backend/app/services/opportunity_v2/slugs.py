"""
Real V2 slug generation — reuses V1's exact _slug() scheme
(app/pipeline/opportunity_generator.py: lowercase, non-alphanumeric to
hyphen, truncate, append a suffix), imported rather than copy-pasted.

Assigned ONCE per opportunity (see orchestration.py::_process_cluster
and slug_backfill.py) and never regenerated afterward — see
OpportunityV2.slug's own column comment for why immutability matters
here.
"""
from __future__ import annotations

from app.pipeline.opportunity_generator import _slug


def compute_opportunity_slug(opportunity_id: str, title_or_anchor: str) -> str:
    return _slug(title_or_anchor, suffix=opportunity_id[:8])
