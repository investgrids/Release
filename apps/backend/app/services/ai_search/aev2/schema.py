"""
The additive answer_experience_v2 response schema (spec Rev. 3 + errata,
design closed 2026-09-21). See the approved spec for the full field-by-
field rationale; this module is the schema expressed as executable code,
not a restatement of the design document.

Foundation-slice scope: this module defines the FULL shape every AEV2
response carries, but only `direct_conclusion` is populated with real
V3-derived content in this slice (see assemble.py). Every other field is
built at its honest, empty default — `companies_affected` attribution
(Event.companies matching), `evidence[]` + claim citations, and
`related_intelligence` canonical links are explicitly the next slice
("response restructuring and citations"), not this one. Nothing here
claims more than it delivers.
"""
from __future__ import annotations

SCHEMA_VERSION = "aev2.1"


def empty_direct_conclusion() -> dict:
    return {"text": "", "evidence_refs": []}


def empty_what_happened() -> dict:
    return {"summary": "", "evidence_refs": [], "items": []}


def empty_why_it_matters() -> dict:
    return {"text": "", "evidence_refs": [], "is_fallback": False}


def empty_companies_affected() -> dict:
    return {"currently_higher": [], "currently_lower": [], "omitted_unattributed": []}


def empty_time_horizon() -> dict:
    return {"primary_horizon": None, "timeline_phases": []}


def empty_risks_and_invalidation() -> dict:
    return {"kind": "analysis", "risks": [], "invalidates_if": [], "watch_for": []}


def empty_related_intelligence() -> dict:
    return {"opportunities": [], "events": [], "ripple": None}


def empty_confidence() -> dict:
    return {"score": None, "level": "unscored", "components_available": []}


def build_response(
    *,
    direct_conclusion: dict | None = None,
    what_happened: dict | None = None,
    why_it_matters: dict | None = None,
    companies_affected: dict | None = None,
    time_horizon: dict | None = None,
    risks_and_invalidation: dict | None = None,
    evidence: list | None = None,
    related_intelligence: dict | None = None,
    follow_up_groups: list | None = None,
    confidence: dict | None = None,
) -> dict:
    """Assembles the full AEV2 shape from whichever real pieces the
    caller has computed, honest-empty defaults for everything else. The
    one function every assembly path (foundation's minimal version today,
    the fuller response-restructuring version later) should build its
    return value through, so the shape stays defined in exactly one place."""
    return {
        "direct_conclusion": direct_conclusion or empty_direct_conclusion(),
        "what_happened": what_happened or empty_what_happened(),
        "why_it_matters": why_it_matters or empty_why_it_matters(),
        "companies_affected": companies_affected or empty_companies_affected(),
        "time_horizon": time_horizon or empty_time_horizon(),
        "risks_and_invalidation": risks_and_invalidation or empty_risks_and_invalidation(),
        "evidence": evidence or [],
        "related_intelligence": related_intelligence or empty_related_intelligence(),
        "follow_up_groups": follow_up_groups or [],
        "confidence": confidence or empty_confidence(),
        "schema_version": SCHEMA_VERSION,
    }
