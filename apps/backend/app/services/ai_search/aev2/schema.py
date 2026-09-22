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

# aev2.4 (2026-09-22): added the optional `event_impact` field — a
# single-Event, structured-evidence-only presenter (see
# aev2/event_impact.py). aev2.3 added `comparison`, the neutral, no-
# holding-relationship counterpart to switch_analysis. Bumped again
# here since a consumer pinned to aev2.3's exact key set now sees one
# more top-level field.
SCHEMA_VERSION = "aev2.4"


def build_validated_claim(text: str, evidence_refs: list[str], *, had_violation: bool) -> dict:
    """The one shared shape for a citation-validated free-text claim —
    direct_conclusion today, switch_analysis.direct_comparison as of
    aev2.2, and any future per-mode claim after that (2026-09-22 spec:
    "avoid separate validity booleans for each UI mode"). `validation_
    status` replaces what used to be an implicit signal (empty
    evidence_refs might mean a rejected claim, or might just mean a
    genuinely uncited-but-valid one — see citation_validator.py's own
    coverage-limitation note) with one explicit, mode-agnostic status
    every claim carries the same way. Maps 1:1 onto assemble.py's
    existing internal `had_violation` bool — this only serializes a
    signal assemble.py already computed, never adds a new check."""
    return {
        "text": text,
        "evidence_refs": evidence_refs,
        "validation_status": "unvalidated" if had_violation else "validated",
    }


def empty_validated_claim() -> dict:
    return build_validated_claim("", [], had_violation=False)


def empty_direct_conclusion() -> dict:
    return empty_validated_claim()


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
    switch_analysis: dict | None = None,
    comparison: dict | None = None,
    event_impact: dict | None = None,
) -> dict:
    """Assembles the full AEV2 shape from whichever real pieces the
    caller has computed, honest-empty defaults for everything else. The
    one function every assembly path (foundation's minimal version today,
    the fuller response-restructuring version later) should build its
    return value through, so the shape stays defined in exactly one place.

    `switch_analysis` (aev2.2), `comparison` (aev2.3, 2026-09-22), and
    `event_impact` (aev2.4, 2026-09-22) are None for any query their own
    assembler doesn't apply to — see aev2/switch_analysis.py's
    assemble_switch_analysis, aev2/comparison.py's assemble_comparison,
    and aev2/event_impact.py's assemble_event_impact. Unlike every other
    field above, none has an `empty_*()` stand-in: None IS the honest
    empty state (there is no "an event_impact exists but is blank" shape
    to show). More than one of the three can be non-None on the SAME
    response — only ui_mode decides which one a layout actually
    renders."""
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
        "switch_analysis": switch_analysis,
        "comparison": comparison,
        "event_impact": event_impact,
        "schema_version": SCHEMA_VERSION,
    }
