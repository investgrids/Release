"""
Article V2 Phase C2 — Evidence Set Builder (owner design, 2026-08-31).

C1 answers "should we investigate this event at all?" C2 answers a
different, narrower question: "for this specific development, which of
this company's linked evidence actually belongs to it?" Company identity
alone is not enough — a real order-win event must not pull in this same
company's unrelated AGM notice, dividend record date, or a prior
quarter's results just because they share an entity_id.

Produces an ArticleEvidenceSet: primary evidence (exactly one, when the
set is usable), supporting evidence, excluded evidence (each with a
machine-readable reason), detected conflicts, and a coherence status.
No article prose, no LLM call anywhere in this module, no interpretation
— purely a filtering/selection/grouping stage over real, already-linked
evidence.

Deterministic signals, all reused from existing primitives, nothing
reinvented:
  - development membership: Jaccard title/headline overlap
    (duplicate_detector.py's own _jaccard/_tokenize, the same primitive
    evidence_ranking.py's query-relevance term already uses) against the
    triggering event's own headline. A real, defensible, low bar for
    "topically related to this development" — deliberately lower than
    duplicate_detector.py's own 0.50 "these are the same article"
    threshold, since a raw NSE filing's title is naturally less similar
    to a paraphrased trigger headline than two headlines about the same
    story would be to each other.
  - staleness: among development-matched evidence, an item published
    materially earlier than the most recent development-matched item is
    stale context, not live corroboration for this development — a
    distinct real signal from topical relevance, not a duplicate of
    DIFFERENT_DEVELOPMENT logic.
  - duplication: a MUCH higher Jaccard bar between two evidence items'
    own titles (not against the query) — "these are copies/restatements
    of each other," not merely "both relevant." Guarded against a real
    found-via-testing failure mode: two titles differing only in one
    critical number ("Rs 500 crore" vs "Rs 700 crore", everything else
    identical) can still clear a high text-Jaccard bar since the number
    is a small fraction of the token set — a naive dedup would silently
    discard a genuine conflict as a redundant copy. A same-kind,
    materially-different numeric claim between two candidates
    disqualifies them from being treated as duplicates of each other,
    regardless of text similarity.
  - primary selection: source authority first (a real NSE/RBI/PIB/SEBI/
    Fed regulatory filing outranks an RSS news article ABOUT that filing,
    regardless of which has higher lexical overlap with the query — the
    owner's own explicit "results filing -> primary, article about the
    results -> supporting" requirement), then evidence_ranking.py's own
    substantiveness classification (reused via the same reasons-string
    markers candidate_gate.py's C1.1 hardening already established), then
    its combined rank_evidence() score as the final tie-breaker.
  - conflicts: numeric_validation.py's own extract_numeric_claims(),
    reused verbatim on evidence titles — two development-matched items
    both citing a real number of the SAME kind but a materially
    different value is a real, deterministic, auditable conflict signal.

Exclusion reason codes actually implemented, and only these — no
decorative codes with no real logic behind them:
  DIFFERENT_DEVELOPMENT — below the development-membership Jaccard bar.
  STALE_CONTEXT          — passes the Jaccard bar but is materially
                            older than the development's live evidence.
  DUPLICATE_EVIDENCE      — a near-duplicate of an already-accepted item.
ENTITY_MISMATCH, LOW_SOURCE_QUALITY, and INSUFFICIENT_EVENT_MATCH were
considered and deliberately NOT implemented: every evidence item reaching
this module is already entity-scoped by EvidenceEntityLink upstream (an
entity-mismatched item structurally cannot appear here), and LinkedEvidence
does not currently expose RawEvidence.quality or a real link_confidence
value (always None today — reserved for a probabilistic resolution
method not built yet) for this module to threshold on honestly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.aipe.duplicate_detector import _jaccard, _tokenize
from app.services.warehouse.article_evidence_bundle import build_article_evidence_bundle
from app.services.warehouse.evidence_ranking import RankedEvidence
from app.services.warehouse.numeric_validation import extract_numeric_claims
from app.services.warehouse.read_service import LinkedEvidence

# A real, deliberately low bar -- "topically related enough to belong to
# this development," not "near-identical text." A raw NSE filing title
# is naturally less similar to a paraphrased trigger headline than two
# headlines about the same story would be to each other, so this sits
# well below duplicate_detector.py's own 0.50 same-article threshold.
_DEVELOPMENT_MEMBERSHIP_THRESHOLD = 0.15

# A much higher bar than development membership -- "these are copies or
# restatements of each other," not merely "both relevant to this story."
_DUPLICATE_TITLE_THRESHOLD = 0.75

# Development-matched evidence published more than this many days before
# the most recent development-matched item is treated as stale context
# rather than live corroboration for the CURRENT development.
_STALE_WINDOW_DAYS = 14

# Regulatory/primary-source types outrank secondary (news/commentary)
# coverage for primary-evidence selection, regardless of lexical overlap
# with the query -- the owner's own explicit "results filing -> primary,
# article about results -> supporting" requirement. Real source_type
# values confirmed against RawEvidence.source_type's real vocabulary
# (raw_evidence.py's own _FIXED_SOURCE_IDS).
_SOURCE_AUTHORITY_RANK = {"nse": 0, "rbi": 0, "pib": 0, "sebi": 0, "fed": 0, "rss": 1}

_LOW_SUBSTANTIVENESS_MARKER = "low-substantiveness phrase"
_HIGH_SUBSTANTIVENESS_MARKER = "high-substantiveness phrase"

COHERENT = "COHERENT"
PARTIAL = "PARTIAL"
INSUFFICIENT = "INSUFFICIENT"

DIFFERENT_DEVELOPMENT = "DIFFERENT_DEVELOPMENT"
STALE_CONTEXT = "STALE_CONTEXT"
DUPLICATE_EVIDENCE = "DUPLICATE_EVIDENCE"


@dataclass(frozen=True)
class ExcludedEvidence:
    evidence: LinkedEvidence
    reason_code: str
    reason_detail: str


@dataclass(frozen=True)
class EvidenceConflict:
    kind: str  # "percent" | "currency_inr" | "currency_usd" | "currency_generic" | "ratio"
    values: list[float]
    evidence_ids: list[str]
    detail: str


@dataclass(frozen=True)
class ArticleEvidenceSet:
    entity_id: str | None
    symbol: str | None
    event_id: str | None
    event_headline: str
    status: str
    primary_evidence: LinkedEvidence | None
    supporting_evidence: list[LinkedEvidence] = field(default_factory=list)
    excluded_evidence: list[ExcludedEvidence] = field(default_factory=list)
    conflicts: list[EvidenceConflict] = field(default_factory=list)
    raw_evidence_count: int = 0  # before any C2 filtering (== bundle.evidence count)
    # The real, resolver-verified canonical company name (threaded from
    # build_article_evidence_bundle's own resolution, C6.1 hardening,
    # 2026-09-01) -- lets downstream headline/composition code prefer a
    # real verified name over re-extracting one from filing prose.
    company_name: str | None = None


def _matched_low_substantiveness(reasons: list[str] | None) -> bool:
    return bool(reasons) and any(_LOW_SUBSTANTIVENESS_MARKER in r for r in reasons)


def _matched_high_substantiveness(reasons: list[str] | None) -> bool:
    return bool(reasons) and any(_HIGH_SUBSTANTIVENESS_MARKER in r for r in reasons)


def _source_authority(source_type: str) -> int:
    return _SOURCE_AUTHORITY_RANK.get(source_type, 1)


def _numerically_conflicts(title_a: str | None, title_b: str | None) -> bool:
    """True when two titles cite a real number of the SAME kind
    (percent/currency_inr/currency_usd/currency_generic/ratio) at a
    materially different value (>1% relative, so rounding noise on the
    same real figure doesn't register). Guards duplicate detection --
    two titles can be near-identical text-wise while disagreeing on the
    one number that actually matters (e.g. "Rs 500 crore" vs "Rs 700
    crore" with everything else the same), which must never collapse
    into a single "duplicate" and silently discard the disagreement."""
    claims_a = extract_numeric_claims(title_a or "")
    claims_b = extract_numeric_claims(title_b or "")
    by_kind_a: dict[str, set[float]] = {}
    for c in claims_a:
        by_kind_a.setdefault(c.kind, set()).add(c.value)
    for c in claims_b:
        values_a = by_kind_a.get(c.kind)
        if not values_a:
            continue
        if all(abs(c.value - v) > v * 0.01 for v in values_a if v):
            return True
    return False


def _primary_sort_key(r: RankedEvidence) -> tuple[int, int, float]:
    """Lower sorts first: source authority (0=regulatory, 1=other), then
    substantiveness (0=HIGH, 1=UNKNOWN, 2=LOW), then the combined
    rank_evidence() score descending (as a real, already-computed
    tie-breaker, not a new number)."""
    if _matched_high_substantiveness(r.reasons):
        sub_rank = 0
    elif _matched_low_substantiveness(r.reasons):
        sub_rank = 2
    else:
        sub_rank = 1
    return (_source_authority(r.evidence.source_type), sub_rank, -r.score)


async def build_evidence_set(
    db: AsyncSession, *, symbol: str, event_headline: str, event_id: str | None = None,
) -> ArticleEvidenceSet:
    """The one real entry point. Same inputs as candidate_gate.evaluate_
    candidate() by design (not coupled to a CandidateDecision object) so
    C2 can be run independently or chained after a real CANDIDATE
    verdict without C1 needing to change."""
    bundle = await build_article_evidence_bundle(
        db, symbol, query_context=event_headline,
        include_historical=False, include_price_move=False, include_financial_context=False,
    )

    if not bundle.resolved or not bundle.ranked_evidence:
        return ArticleEvidenceSet(
            entity_id=bundle.entity_id, symbol=bundle.symbol, event_id=event_id,
            event_headline=event_headline, status=INSUFFICIENT, primary_evidence=None,
            raw_evidence_count=len(bundle.evidence), company_name=bundle.company_name,
        )

    excluded: list[ExcludedEvidence] = []

    # Stage 1 -- development membership via title/headline Jaccard.
    query_tokens = _tokenize(event_headline)
    matched: list[RankedEvidence] = []
    for r in bundle.ranked_evidence:
        similarity = _jaccard(query_tokens, _tokenize(r.evidence.title)) if r.evidence.title else 0.0
        if similarity < _DEVELOPMENT_MEMBERSHIP_THRESHOLD:
            excluded.append(ExcludedEvidence(
                evidence=r.evidence, reason_code=DIFFERENT_DEVELOPMENT,
                reason_detail=(
                    f"title/headline Jaccard {similarity:.2f} is below the development-membership "
                    f"threshold ({_DEVELOPMENT_MEMBERSHIP_THRESHOLD}) -- not topically related to "
                    f"this specific development"
                ),
            ))
        else:
            matched.append(r)

    # Stage 2 -- staleness. Anchor on the most recent development-matched
    # item's own publish time; anything materially older is stale
    # context for THIS development, not live corroboration.
    dated = [r for r in matched if r.evidence.published_at is not None]
    if dated:
        anchor_time = max(r.evidence.published_at for r in dated)
        cutoff = anchor_time - timedelta(days=_STALE_WINDOW_DAYS)
        still_live: list[RankedEvidence] = []
        for r in matched:
            if r.evidence.published_at is not None and r.evidence.published_at < cutoff:
                excluded.append(ExcludedEvidence(
                    evidence=r.evidence, reason_code=STALE_CONTEXT,
                    reason_detail=(
                        f"published {r.evidence.published_at} -- more than {_STALE_WINDOW_DAYS} days "
                        f"before this development's most recent matched evidence ({anchor_time})"
                    ),
                ))
            else:
                still_live.append(r)
        matched = still_live

    # Stage 3 -- deduplication among the remaining development-matched
    # set. Real near-duplicates (title Jaccard >= a much higher bar than
    # development membership) collapse to one representative -- the
    # highest-authority/substantiveness one by the same priority order
    # primary selection uses -- so duplication can't masquerade as
    # independent corroboration.
    matched_sorted = sorted(matched, key=_primary_sort_key)
    kept: list[RankedEvidence] = []
    for r in matched_sorted:
        dup_of = next(
            (k for k in kept if r.evidence.title and k.evidence.title
             and _jaccard(_tokenize(r.evidence.title), _tokenize(k.evidence.title)) >= _DUPLICATE_TITLE_THRESHOLD
             and not _numerically_conflicts(r.evidence.title, k.evidence.title)),
            None,
        )
        if dup_of is not None:
            excluded.append(ExcludedEvidence(
                evidence=r.evidence, reason_code=DUPLICATE_EVIDENCE,
                reason_detail=f"near-duplicate of already-accepted evidence {dup_of.evidence.raw_evidence_id} (title Jaccard >= {_DUPLICATE_TITLE_THRESHOLD})",
            ))
        else:
            kept.append(r)

    if not kept:
        return ArticleEvidenceSet(
            entity_id=bundle.entity_id, symbol=bundle.symbol, event_id=event_id,
            event_headline=event_headline, status=INSUFFICIENT, primary_evidence=None,
            excluded_evidence=excluded, raw_evidence_count=len(bundle.evidence),
            company_name=bundle.company_name,
        )

    # Stage 4 -- primary selection: authority first, not lexical score.
    # `kept` is already sorted by _primary_sort_key from stage 3.
    primary = kept[0]
    supporting = kept[1:]

    # Stage 5 -- conflict detection, deterministic, reusing
    # numeric_validation.py verbatim rather than reimplementing number
    # extraction. Two development-matched items citing a real number of
    # the same kind but a materially different value is a real conflict;
    # C2 records it, it does not adjudicate it.
    conflicts: list[EvidenceConflict] = []
    claims_by_item = [
        (r, extract_numeric_claims(r.evidence.title or "")) for r in ([primary] + supporting)
    ]
    seen_kinds: dict[str, list[tuple[float, str]]] = {}
    for r, claims in claims_by_item:
        for c in claims:
            seen_kinds.setdefault(c.kind, []).append((c.value, r.evidence.raw_evidence_id))
    for kind, entries in seen_kinds.items():
        values = {v for v, _ in entries}
        if len(values) > 1:
            # A real spread, not float noise -- flag only when the values
            # meaningfully differ (>1% relative), so two evidence items
            # rounding the same real figure slightly differently don't
            # register as a false conflict.
            vals_sorted = sorted(values)
            if vals_sorted[-1] > vals_sorted[0] * 1.01:
                conflicts.append(EvidenceConflict(
                    kind=kind, values=[v for v, _ in entries], evidence_ids=[eid for _, eid in entries],
                    detail=f"multiple development-matched items cite different {kind} values: {sorted(values)}",
                ))

    if supporting and not conflicts:
        status = COHERENT
    else:
        status = PARTIAL

    return ArticleEvidenceSet(
        entity_id=bundle.entity_id, symbol=bundle.symbol, event_id=event_id,
        event_headline=event_headline, status=status,
        primary_evidence=primary.evidence,
        supporting_evidence=[r.evidence for r in supporting],
        excluded_evidence=excluded, conflicts=conflicts,
        raw_evidence_count=len(bundle.evidence), company_name=bundle.company_name,
    )
