"""
Routine Filing Suppression R1 (2026-09-20) — a PURE, offline classifier
for whether a Development is a "routine filing": a mandatory/procedural
regulatory disclosure with no material investment content of its own,
as opposed to a genuinely consequential corporate action that merely
happens to also carry a routine-sounding compliance label (a postal
ballot CAN carry a genuine fundraise or merger resolution; a Regulation
30 disclosure CAN be a material acquisition).

Explicitly NOT a complete narrative-overclaim solution (the review audit
found unsupported expansion happens outside routine filings too — see
the audit's own report). This module only identifies one real, common
pattern: mandatory/procedural disclosures narrated with confident
investment language the filing itself doesn't establish.

Real-data constraint (verified live, 2026-09-20): the "structured
category" fields this classifier would ideally lean on entirely
(CompanyAnnouncement.category, Development.category, Event.category)
are effectively 100% unpopulated in real production data today (9,055/
9,055, 18,588/18,588, and ~20,128/20,133 NULL respectively). The one
well-populated real structured field is Event.event_type (corporate/
regulatory/earnings/macro/news/market/policy) — used here as a genuine
structured PRE-FILTER (only "corporate"/"regulatory" event types can
ever be considered routine at all; "earnings"/"macro"/"policy"/"market"/
"news" never are), combined with a conservative, disclosed title-pattern
match on the real canonical_title text, gated by an explicit
material-event escape list. This is a necessary compromise given real
data completeness, not a substitute for structured fields where they
exist.

No LLM call anywhere in this module. No database write. Nothing here
changes narrative_status or public eligibility — see
scripts/routine_filing_dry_run.py for the read-only analysis harness
that runs this against real data and reports results for human review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Event types that can NEVER be "routine" regardless of title text --
# earnings/macro/policy/market/news developments are, by construction,
# not procedural compliance filings.
_ROUTINE_ELIGIBLE_EVENT_TYPES = {"corporate", "regulatory", None}  # None = no linked Event at all (e.g. RSS-sourced)

# Real, observed routine-filing patterns (case-insensitive substring/regex
# match against Development.canonical_title). Includes the real misspelling
# "Srutinizers" seen verbatim in real production titles (NSE's own filing
# text, not a typo introduced here).
_ROUTINE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"postal ballot",
        r"scrutini[sz]ers?\s+report",
        r"srutini[sz]ers?\s+report",   # real observed misspelling in production data
        r"voting results",
        r"re-?appointment of director",
        r"appointment of senior management personnel",
        r"\bsmp\b",
        r"regulation 30",
        r"action\(s\)\s+taken or orders passed",
        r"annual general meeting",
        r"\bagm\b",
    ]
]

# Material-event escape keywords -- ANY match here means "not routine",
# full stop, regardless of how many routine patterns also matched. A
# postal ballot approving a merger, or a Regulation 30 disclosure of an
# acquisition, is not procedural just because the filing MECHANISM is
# routine.
_MATERIAL_ESCAPE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"acqui(re|sition)", r"merger", r"amalgamation", r"demerger",
        r"stake sale", r"divest",
        r"fundrais", r"rights issue", r"\bqip\b", r"preferential allotment", r"capital rais",
        r"resign", r"step(s|ped)? down", r"terminat",
        r"\bceo\b", r"\bcfo\b", r"\bmanaging director\b", r"\bchief executive\b", r"\bchairman\b", r"\bchairperson\b",
        r"delist", r"insolvency", r"bankrupt", r"fraud", r"\bscam\b",
        r"litigation", r"lawsuit", r"penalty", r"\bfine\b", r"show[- ]cause notice",
        r"credit rating", r"downgrad", r"\bdefault\b",
        r"buyback", r"joint venture", r"\bjv\b",
        r"scheme of arrangement", r"restructur",
    ]
]

# The separate synthetic-looking Development title pattern the review
# flagged for inventory -- NOT part of the routine-filing classifier
# itself (a different concern: these don't look like real reported news
# at all, distinct from "real news that happens to be procedural").
_SYNTHETIC_EXPOSURE_PATTERN = re.compile(r"^directly exposed to .+ opportunity through core operations\.?$", re.IGNORECASE)


@dataclass
class DevelopmentClassification:
    development_id: str
    is_routine: bool
    matched_routine_patterns: list[str] = field(default_factory=list)
    matched_escape_patterns: list[str] = field(default_factory=list)
    is_synthetic_exposure: bool = False
    reason: str = ""


def classify_development(
    development_id: str,
    canonical_title: str,
    linked_event_types: list[str | None],
) -> DevelopmentClassification:
    """Pure function -- no DB access, no LLM call. `linked_event_types` is
    the real Event.event_type value(s) for every event-sourced piece of
    DevelopmentEvidence linked to this Development (pass [] or [None] if
    none exist, e.g. an RSS-only-sourced Development)."""
    title = canonical_title or ""

    if _SYNTHETIC_EXPOSURE_PATTERN.match(title.strip()):
        return DevelopmentClassification(
            development_id=development_id, is_routine=False, is_synthetic_exposure=True,
            reason="synthetic-looking 'core operations exposure' title -- inventoried separately, not classified as routine or material",
        )

    escape_hits = [p.pattern for p in _MATERIAL_ESCAPE_PATTERNS if p.search(title)]
    if escape_hits:
        return DevelopmentClassification(
            development_id=development_id, is_routine=False, matched_escape_patterns=escape_hits,
            reason=f"material escape keyword(s) matched: {escape_hits}",
        )

    # Structured pre-filter: only corporate/regulatory (or no linked Event
    # at all) can ever be routine.
    ineligible_types = [t for t in linked_event_types if t not in _ROUTINE_ELIGIBLE_EVENT_TYPES]
    if ineligible_types:
        return DevelopmentClassification(
            development_id=development_id, is_routine=False,
            reason=f"linked Event.event_type {set(ineligible_types)} is never routine (earnings/macro/policy/market/news)",
        )

    routine_hits = [p.pattern for p in _ROUTINE_PATTERNS if p.search(title)]
    if not routine_hits:
        return DevelopmentClassification(
            development_id=development_id, is_routine=False,
            reason="no known routine-filing pattern matched the real title",
        )

    return DevelopmentClassification(
        development_id=development_id, is_routine=True, matched_routine_patterns=routine_hits,
        reason=f"routine pattern(s) matched, no material escape, event_type eligible: {routine_hits}",
    )


def classify_opportunity(dev_classifications: list[DevelopmentClassification]) -> bool:
    """An opportunity is flagged only if EVERY linked Development
    (excluding synthetic-exposure ones, which are inventoried separately
    and never drive this decision either way) is independently classified
    routine. A single genuinely material or unclassifiable Development is
    enough to keep the whole opportunity out of suppression scope."""
    real_devs = [c for c in dev_classifications if not c.is_synthetic_exposure]
    if not real_devs:
        return False  # nothing but synthetic-exposure entries -- never flagged either way
    return all(c.is_routine for c in real_devs)
