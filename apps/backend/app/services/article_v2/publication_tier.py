"""
Article V2 Phase C8.1 -- Publication Tier (owner design, 2026-09-01).

C7's real 500-event shadow run found the grounding architecture (C1-C6)
sound but the publication POLICY wrong: 88% of what C4 proposed as a
real, verified CREATE_NEW output was routine/administrative (AGM
notices, BRSR uploads, "Schedule of meet" filings) that shouldn't
become a standalone, Google-indexable Newsroom page even though every
fact on it is true. This module makes that usefulness distinction
STRUCTURAL rather than a one-off manual label.

Explicit instruction: "Don't turn the manual labels into another LLM
classifier. Encode the obvious deterministic classes first." This is a
pure, synchronous, deterministic function -- no LLM, no new evidence
gathering, no override of C4's own content_type/publication_action
(both stay exactly as C4 decided them; this is a NEW, additive axis).

## The rule, and why it needs no new taxonomy

The owner's own example -- "an AGM announcement and an AGM where a
material acquisition is approved are not equivalent" -- turns out to
be exactly what `evidence_ranking.py`'s existing HIGH_SUBSTANTIVENESS
phrase list already distinguishes (acquisition/merger/amalgamation/
credit rating/board approval/resignation/appointment/financial
results/dividend declaration), reused here via
`decision_engine._matches_recognized_high_substantiveness()` -- the
SAME self-contained check C4's own FULL_ARTICLE gate already uses, not
a second independently-invented classifier. A routine AGM notice
doesn't match any of those phrases; an AGM notice where the board ALSO
approved a real acquisition does, because the acquisition language is
right there in the same primary evidence text. No development-type
taxonomy is needed as a separate gate -- the phrase check already
captures the distinction directly, and real data confirms it: OIL and
AXISCADES's genuine business-development news both matched via "press
release" even though neither fits any of the small identity.py
development-type buckets built for C3/C5's own separate purposes.

ARTICLE-eligible when ANY of:
  - the primary evidence matches a real HIGH-substantiveness phrase
    (refined below for the "press release" wrapper case), OR
  - the primary evidence carries real, extractable numeric substance
    (a currency/percentage/ratio claim -- NOT a bare integer like an
    ESOP option count, which extract_numeric_claims() correctly never
    matches in the first place), OR
  - C4 already found genuine analytical depth
    ("SUFFICIENT_ANALYTICAL_CONTEXT" in decision.reason_codes -- real
    financial context, real independent substantive corroboration, or
    a material market move).

REJECT (a mechanical defect, not an editorial judgment) when the
primary evidence's own subject is degenerate -- e.g. a real, honest
"Notice of undefined" where the source filing's own subject field was
malformed and C5's extraction correctly refused to invent one rather
than fabricate a real topic. (Headline-hijack and truncation defects
are caught structurally in headline_engine.py itself, C8.2 -- by the
time a candidate reaches this classifier those are prevented, not
detected here.)

Everything else -- the overwhelming real-data majority -- is
EVENT_ONLY: real, verified, grounded, but not worth an indexable page
on its own. Per the owner's explicit architectural decision, an
EVENT_ONLY candidate is never composed into an article at all (see
scripts/article_v2_c8_shadow_run.py) -- the Event itself is the
canonical object.

## The "press release" wrapper refinement

A real gap found while building this module, not anticipated going in:
"press release" is itself a HIGH-substantiveness phrase, but EVERY NSE
filing that forwards a press release uses the exact same wrapper text
("...regarding a press release dated X, titled 'Y'"), regardless of
whether Y is genuine M&A news (AXISCADES's real acquisition) or pure
marketing fluff (CYIENT's real "New Brand Positioning" rebrand). A bare
phrase match on the wrapper can't tell these apart. Refined here (a
local addition to THIS classifier only, not a change to the shared,
frozen evidence_ranking.py module) by extracting the quoted inner
title when a press-release wrapper is present and re-checking
substantiveness against THAT text instead of the wrapper.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.article_v2.context_builder import ArticleContextBundle
from app.services.article_v2.decision_engine import (
    _MATERIAL_MARKET_MOVE_PCT, ArticleDecision, _has_numeric_substance, _matches_recognized_high_substantiveness,
)
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet

ARTICLE = "ARTICLE"
EVENT_ONLY = "EVENT_ONLY"
REJECT = "REJECT"

_PRESS_RELEASE_WRAPPER_RE = re.compile(
    r"press release[^\"']*[\"']([^\"']{4,300})[\"']", re.IGNORECASE,
)

# A real, narrow gap found via testing this module (not anticipated
# going in): evidence_ranking.py's HIGH_SUBSTANTIVENESS list has
# "acquisition" (noun) but not "acquire"/"acquiring" (verb forms) --
# AXISCADES's own real headline text ("...to Acquire Cloud Wave
# Technologies") uses the verb form and was missed once the press-
# release wrapper's own bare "press release" match was correctly
# excluded from counting as a signal on its own. Scoped locally to this
# classifier rather than widening the shared, frozen evidence_ranking.py
# list, which is used well beyond publication-tier decisions.
_SUPPLEMENTARY_HIGH_SIGNAL_PHRASES = ["acquire", "acquiring", "to be acquired", "merging with", "merge with"]


def _matches_supplementary_high_signal(text: str) -> bool:
    t = text.lower()
    return any(phrase in t for phrase in _SUPPLEMENTARY_HIGH_SIGNAL_PHRASES)

# A real, honest "the source filing's own subject was malformed" marker
# -- SIGACHI's real case ("Notice of undefined"). Not fabricated, but
# conveys nothing to a reader; a mechanical REJECT, not an editorial one.
# D-Link's real second-cohort case is the same class from the opposite
# direction: the raw NSE filing text itself has a genuinely BLANK name
# field ("Appointment of   as Non-Executive Independent Director" --
# three spaces where a real person's name should be, confirmed directly
# against the raw ingested evidence, not an artifact of this module's
# own extraction). `of\s{2,}as` catches this real, recurring upstream
# data-quality shape without inventing a name to fill the gap.
_DEGENERATE_SUBJECT_RE = re.compile(r"\bundefined\b|\bof\s{2,}as\b", re.IGNORECASE)


@dataclass(frozen=True)
class PublicationTierResult:
    tier: str
    reason_codes: list[str] = field(default_factory=list)


def _effective_substantiveness_text(primary_title: str) -> str:
    """The text to actually check for HIGH-substantiveness -- the
    press release's own quoted inner title when present, otherwise the
    primary evidence's own title unchanged."""
    m = _PRESS_RELEASE_WRAPPER_RE.search(primary_title)
    return m.group(1) if m else primary_title


def classify_publication_tier(
    decision: ArticleDecision, evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None,
) -> PublicationTierResult:
    """The one real entry point. Only meaningful for a decision that
    already reached CREATE/UPDATE_EXISTING with real C2 primary
    evidence -- callers should not call this for a C4 SKIP or a C5
    NO_PUBLICATION (matching every other C1-C6 stage's own convention
    of trusting the caller has already checked the upstream gate)."""
    primary_title = evidence_set.primary_evidence.title if evidence_set.primary_evidence else None

    if primary_title and _DEGENERATE_SUBJECT_RE.search(primary_title):
        return PublicationTierResult(REJECT, ["DEGENERATE_SUBJECT"])

    if not primary_title:
        return PublicationTierResult(REJECT, ["NO_PRIMARY_TEXT"])

    substantiveness_text = _effective_substantiveness_text(primary_title)
    is_high_substantive = (
        _matches_recognized_high_substantiveness(substantiveness_text)
        or _matches_supplementary_high_signal(substantiveness_text)
    )
    has_real_numbers = _has_numeric_substance(primary_title)
    # Real bug found via the C8 500-event rerun, not anticipated: C4's
    # own decide() only ever appends the literal "SUFFICIENT_ANALYTICAL_
    # CONTEXT" string to its returned reason_codes inside the
    # FULL_ARTICLE branch -- for a FACTUAL_UPDATE (the overwhelming
    # majority of real decisions), that signal never reaches
    # reason_codes at all, even when real financial context or a
    # material market move genuinely exists. Checking decision.
    # reason_codes silently broke this escalation for exactly the case
    # it was built to catch (CANBK: real CET1/AT1 context, FACTUAL_
    # UPDATE content_type, zero HIGH-substantiveness phrase match --
    # mis-tiered EVENT_ONLY on the first rerun). Fixed by computing the
    # SAME real signal directly from `context`, matching what C4
    # internally computes but doesn't expose for this content_type.
    has_analytical_context = bool(context) and (
        bool(context.financial_context)
        or (context.market_reaction is not None and abs(context.market_reaction.price_move_pct) >= _MATERIAL_MARKET_MOVE_PCT)
    )

    reasons = []
    if is_high_substantive:
        reasons.append("HIGH_SUBSTANTIVENESS_MATCH")
    if has_real_numbers:
        reasons.append("REAL_NUMERIC_SUBSTANCE")
    if has_analytical_context:
        reasons.append("ANALYTICAL_CONTEXT_PRESENT")

    if reasons:
        return PublicationTierResult(ARTICLE, reasons)

    return PublicationTierResult(EVENT_ONLY, ["ROUTINE_NO_SUBSTANTIVE_SIGNAL"])
