"""
Article V2 Phase C4 — Article Decision Engine (owner design, 2026-08-31).

Answers: "given the candidate (C1), its coherent evidence (C2), and its
verified context (C3), what -- if anything -- should MarketRipple
publish?" This is where the three internal stages become one editorial
decision. Deterministic by explicit instruction -- no LLM judging
publication-worthiness. Produces decision metadata only: no article
prose, no headline, no Newsroom record, no production wiring.

Two independent axes, kept separate on purpose (the owner's own framing
-- this becomes load-bearing for Phase D Search Console work, preventing
SEO cannibalization by design):

  content_type       = FULL_ARTICLE | FACTUAL_UPDATE | SKIP
  publication_action = CREATE | UPDATE_EXISTING | NONE

A pure, synchronous function -- every real fact it needs is already on
the three upstream dataclasses (CandidateDecision, ArticleEvidenceSet,
ArticleContextBundle), no DB access, no new evidence gathering.

## The FULL_ARTICLE bar

"One authoritative source is not automatically insufficient" (owner's
explicit instruction) -- but the reverse trap found while designing this
module deserves stating plainly: a board-meeting-to-CONSIDER-something
notice (CANBK's own real shape from the C3 shadow run: "Board Meeting...
to consider Fund raising") is not "detailed results" or "a major order"
just because it scores well on evidence_ranking's substantiveness/
relevance signal and C3 happened to find real background financial
metrics for the company. The owner's own FACTUAL_UPDATE example --
"Company announces board meeting for fundraising proposal... publish a
concise factual update" -- is exactly this shape. A real, deterministic
"is this a completed/substantive filing or merely a proposal/scheduling
notice" signal is required before background context can elevate
anything to FULL_ARTICLE: a primary evidence title matching a real
proposal/scheduling phrase ("to consider", "scheduled", "proposed") is
capped at FACTUAL_UPDATE UNLESS the evidence text itself also carries
real extractable numeric substance (a genuine reported figure, not just
an announcement that a meeting will happen) -- reusing
numeric_validation.extract_numeric_claims() verbatim, the same
primitive C2's conflict detection already reuses.

FULL_ARTICLE requires ALL of:
  1. Not proposal-only (see above), UNLESS real numeric substance exists
     in the primary evidence's own text despite the proposal framing.
  2. Primary evidence itself matches a recognized HIGH-substantiveness
     phrase (evidence_ranking.py's own real taxonomy, checked directly
     against the title -- self-contained) OR carries real extractable
     numeric detail. Deliberately NOT C1's combined rank_evidence()
     score: a real shadow-run finding (2 real BLS events, 1 FIRSTCRY
     event) showed the combined score can be inflated to 0.7+ purely by
     query-self-matching -- for NSE-triaged events the EventTriage
     headline is often near-identical to the evidence's own title, so
     an UNKNOWN-substantiveness routine ESG/BRSR disclosure can score as
     "strong" without being strong at all. C1.1 closed this hole for
     C1's own CANDIDATE/SKIP boundary; this closes the same hole for
     C4's separate, later strength gate, which C1.1 never covered.
  3. At least one genuine source of analytical depth: real event-aware
     financial context (C3), real independent corroborating evidence
     (a supporting item that ITSELF matches a high-substantiveness
     phrase or carries real numbers -- not just "another filing exists
     in the same cluster," which real BLS data proved is not
     corroboration of anything), a material market reaction (a real,
     non-trivial magnitude -- market presence alone, any nonzero move,
     is not "material"), or real extractable numeric substance in the
     primary evidence itself (the "detailed results"/"Rs 5,000 crore
     order" case -- this alone, on a single authoritative source, is
     enough; matches the owner's explicit instruction).

Everything real and accepted (C2 COHERENT/PARTIAL) that doesn't clear
this bar defaults to FACTUAL_UPDATE -- verified, real, useful, but not
worth manufactured analytical depth. C2 INSUFFICIENT is always SKIP
(the owner's explicit rule) -- C1 is a candidate filter, not a
publishing entitlement. C3 NONE does NOT automatically mean SKIP -- the
numeric-substance-in-primary-evidence path above is exactly how a
genuinely substantive single source still gets a real decision even
when C3 found no event-aware financial context or usable market window.

## Existing coverage (C1 CANDIDATE vs UPDATE_CANDIDATE)

A genuinely new development (C1 outcome=CANDIDATE) can become
FULL_ARTICLE/FACTUAL_UPDATE/SKIP as above, with publication_action=
CREATE (or NONE if SKIP). An UPDATE_CANDIDATE (C1 already found real
existing coverage) never gets CREATE -- it either has real corroborated
evidence to contribute (C2 COHERENT/PARTIAL, i.e. real primary evidence
exists) and becomes publication_action=UPDATE_EXISTING, content_type=
FACTUAL_UPDATE (an update is definitionally not a fresh full article),
or has nothing real to add (C2 INSUFFICIENT) and becomes
publication_action=NONE, content_type=SKIP.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.article_v2.candidate_gate import UPDATE_CANDIDATE, CandidateDecision
from app.services.article_v2.candidate_gate import SKIP as C1_SKIP
from app.services.article_v2.context_builder import ArticleContextBundle
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet, INSUFFICIENT
from app.services.warehouse.evidence_ranking import _HIGH_SUBSTANTIVENESS, _LOW_SUBSTANTIVENESS
from app.services.warehouse.numeric_validation import extract_numeric_claims

FULL_ARTICLE = "FULL_ARTICLE"
FACTUAL_UPDATE = "FACTUAL_UPDATE"
SKIP = "SKIP"

CREATE = "CREATE"
UPDATE_EXISTING = "UPDATE_EXISTING"
NONE_ACTION = "NONE"

# A real, non-trivial market move -- distinguishes "the stock genuinely
# reacted" from "the stock moved by ordinary daily noise," which is not
# itself a source of analytical depth.
_MATERIAL_MARKET_MOVE_PCT = 3.0

# A primary evidence title matching one of these describes an intent/
# scheduling notice, not a completed, substantive filing -- the exact
# real CANBK ("...to consider Fund raising") shape the owner's own
# FACTUAL_UPDATE example names directly.
_PROPOSAL_ONLY_MARKERS = ["to consider", "scheduled", "proposal", "proposed to", "intends to"]


@dataclass(frozen=True)
class ArticleDecision:
    entity_id: str | None
    symbol: str | None
    event_id: str | None
    event_headline: str
    content_type: str
    publication_action: str
    reason_codes: list[str] = field(default_factory=list)
    reason_detail: str = ""


def _has_numeric_substance(title: str | None) -> bool:
    return bool(title) and len(extract_numeric_claims(title)) > 0


def _is_proposal_only(title: str | None) -> bool:
    if not title:
        return False
    t = title.lower()
    return any(marker in t for marker in _PROPOSAL_ONLY_MARKERS)


def _matches_recognized_high_substantiveness(title: str | None) -> bool:
    """Reuses evidence_ranking.py's own real HIGH-substantiveness phrase
    list directly against the title -- self-contained, does not rely on
    the combined rank_evidence() score, which real shadow data proved
    exploitable: when the EventTriage headline is near-identical to the
    evidence's own title (routine for NSE-triaged events, since the
    headline is often derived from the filing's own subject line), the
    query-relevance term alone can push an UNKNOWN-substantiveness item
    (e.g. a routine BRSR/ESG disclosure) above a raw score threshold --
    confirmed live: BLS/FIRSTCRY's real BRSR filings scored 0.7 via a
    perfect 1.00 Jaccard self-match, not real substantiveness. C1.1
    already closed this exact class of hole for LOW-substantiveness
    items; this closes the same hole for the FULL_ARTICLE strength gate,
    which C1.1 never covered (C1.1 only gates C1's own CANDIDATE/SKIP
    boundary, not C4's separate, later editorial-strength decision)."""
    if not title:
        return False
    t = title.lower()
    return any(phrase in t for phrase in _HIGH_SUBSTANTIVENESS)


def _matches_recognized_low_substantiveness(title: str | None) -> bool:
    """Reuses evidence_ranking.py's own real, deterministic administrative-
    phrase list directly against the primary evidence's own text --
    self-contained, doesn't depend on the caller having passed a fresh
    CandidateDecision.top_evidence_reasons (which C1.1 can legitimately
    reassign to a corroborating item, or which a hand-built/test
    CandidateDecision may not carry at all)."""
    if not title:
        return False
    t = title.lower()
    return any(phrase in t for phrase in _LOW_SUBSTANTIVENESS)


def decide(
    candidate: CandidateDecision, evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None,
) -> ArticleDecision:
    common = dict(
        entity_id=evidence_set.entity_id or candidate.entity_id,
        symbol=evidence_set.symbol or candidate.symbol,
        event_id=evidence_set.event_id, event_headline=evidence_set.event_headline,
    )

    # C1 already said no -- nothing downstream can overrule that; this
    # function is only ever meaningfully invoked for a real CANDIDATE/
    # UPDATE_CANDIDATE, but handles a raw SKIP input gracefully for the
    # full-120-event shadow harness that runs everything through C1-C4
    # uniformly rather than only survivors.
    if candidate.outcome == C1_SKIP:
        return ArticleDecision(
            **common, content_type=SKIP, publication_action=NONE_ACTION,
            reason_codes=["EVIDENCE_INSUFFICIENT" if candidate.reason_code == "INSUFFICIENT_EVIDENCE" else candidate.reason_code],
            reason_detail=f"C1 already rejected this candidate ({candidate.reason_code}); C4 does not overrule C1.",
        )

    # C2 INSUFFICIENT -- always SKIP, regardless of C1's own verdict.
    # C1 is a candidate filter, not a publishing entitlement.
    if evidence_set.status == INSUFFICIENT or evidence_set.primary_evidence is None:
        publication_action = NONE_ACTION
        return ArticleDecision(
            **common, content_type=SKIP, publication_action=publication_action,
            reason_codes=["EVIDENCE_INSUFFICIENT"],
            reason_detail="C2 found no usable primary evidence for this development -- nothing to publish.",
        )

    primary = evidence_set.primary_evidence
    proposal_only = _is_proposal_only(primary.title)
    primary_has_numbers = _has_numeric_substance(primary.title)

    # -- Existing-coverage branch (C1 UPDATE_CANDIDATE) --
    if candidate.outcome == UPDATE_CANDIDATE:
        return ArticleDecision(
            **common, content_type=FACTUAL_UPDATE, publication_action=UPDATE_EXISTING,
            reason_codes=["MATERIAL_NEW_EVIDENCE", "EXISTING_COVERAGE"],
            reason_detail=(
                f"real coverage already exists (article {candidate.matched_article_id}); this development's "
                f"real, C2-accepted evidence is routed as an update to that existing story, never a new URL."
            ),
        )

    # -- Genuinely new development (C1 CANDIDATE) --
    reason_codes: list[str] = []
    depth_reasons: list[str] = []

    # Independent, non-gameable corroboration: a supporting item only
    # counts toward "multiple independent evidence items" if IT ITSELF
    # carries real signal (a recognized high-substantiveness phrase or
    # real extractable numbers) -- not just "another filing exists in
    # the same cluster." A pile of administrative filings (BRSR + Web
    # Link Letter + Media Release + dividend record date, BLS's real
    # shape) is not corroboration of anything.
    substantive_supporting = [
        s for s in evidence_set.supporting_evidence
        if _matches_recognized_high_substantiveness(s.title) or _has_numeric_substance(s.title)
    ]
    has_financial_context = bool(context and context.financial_context)
    has_multi_source = len(substantive_supporting) >= 1
    has_material_market = bool(
        context and context.market_reaction and abs(context.market_reaction.price_move_pct) >= _MATERIAL_MARKET_MOVE_PCT
    )

    if has_financial_context:
        depth_reasons.append("SUFFICIENT_ANALYTICAL_CONTEXT")
    if has_multi_source:
        depth_reasons.append("SUFFICIENT_ANALYTICAL_CONTEXT")
    if has_material_market:
        depth_reasons.append("SUFFICIENT_ANALYTICAL_CONTEXT")
    if primary_has_numbers:
        depth_reasons.append("SINGLE_AUTHORITATIVE_SOURCE")

    # The FULL_ARTICLE strength gate is the primary evidence's own
    # recognized substantiveness or real extractable numeric detail --
    # NOT the raw combined rank_evidence() score, which real shadow data
    # proved can be inflated by query-self-matching alone (see
    # _matches_recognized_high_substantiveness's own docstring).
    strong_primary = _matches_recognized_high_substantiveness(primary.title) or primary_has_numbers

    eligible_for_full = (
        strong_primary
        and bool(depth_reasons)
        and (not proposal_only or primary_has_numbers)
    )

    if eligible_for_full:
        reason_codes.append("STRONG_PRIMARY_EVIDENCE")
        reason_codes += depth_reasons
        return ArticleDecision(
            **common, content_type=FULL_ARTICLE, publication_action=CREATE,
            reason_codes=sorted(set(reason_codes)),
            reason_detail=(
                f"primary evidence is a recognized high-substantiveness filing or carries real numeric "
                f"detail (not just a query-relevance-inflated score) and genuine analytical depth exists: "
                f"{depth_reasons}."
            ),
        )

    # Not FULL_ARTICLE -- but real, C2-accepted evidence exists, so this
    # is a real, verified development, not noise. Distinguish a genuine
    # SKIP (administrative, nothing of note) from a real FACTUAL_UPDATE.
    # The administrative signal is the primary evidence's own recognized
    # low-substantiveness classification (AGM/ESOP/record-date/newspaper
    # publication/etc, evidence_ranking.py's own real phrase list) --
    # NOT the proposal-only heuristic, which answers a different
    # question (completed vs. merely scheduled) and would otherwise miss
    # real administrative filings that aren't phrased as a "proposal"
    # (e.g. "Copy of Newspaper Publication" is a completed filing, not a
    # scheduling notice, but is still genuinely administrative).
    is_administrative_noise = (
        _matches_recognized_low_substantiveness(primary.title)
        and not primary_has_numbers
        and not has_financial_context
        and not has_multi_source
        and not has_material_market
    )

    if is_administrative_noise:
        return ArticleDecision(
            **common, content_type=SKIP, publication_action=NONE_ACTION,
            reason_codes=["ADMINISTRATIVE_ONLY"],
            reason_detail="primary evidence matches a recognized administrative/low-substantiveness phrase with zero real analytical depth signals -- nothing of public interest to publish.",
        )

    reason_codes.append("LIMITED_CONTEXT" if not depth_reasons else "SINGLE_AUTHORITATIVE_SOURCE")
    if proposal_only and not primary_has_numbers:
        reason_codes.append("LIMITED_CONTEXT")
    return ArticleDecision(
        **common, content_type=FACTUAL_UPDATE, publication_action=CREATE,
        reason_codes=sorted(set(reason_codes)),
        reason_detail=(
            f"real, verified development (score {candidate.top_evidence_score}) but does not clear the "
            f"FULL_ARTICLE bar -- publish as a concise factual update, not manufactured analysis."
        ),
    )
