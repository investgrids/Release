"""
Article V2 Phase P1 — Publication Translation Contract (owner design,
2026-09-04, locked after 4 corrections on 2026-09-06). Maps a fully-
composed, upstream-approved V2 article onto the real, production
`IntelligenceArticle` schema (`app/db/models/intelligence_article.py`)
-- field by field, with an explicit, deliberate disposition for every
column:

  V2 SOURCE     -- populated from real C1-C6 data.
  DETERMINISTIC -- code-composed from V2's own already-verified fields,
                   never a second LLM call, never re-interpreting
                   anything C6 already decided.
  EMPTY         -- a real V1-only concept V2.0 does not populate
                   (`[]`/`None`) -- an honest scope limitation, not an
                   oversight.
  PROHIBITED    -- a V1 concept V2 must NEVER populate, even by
                   accident (e.g. a stray default reintroducing it).

This module only TRANSLATES -- it takes an already fully-authorized,
already-enforced set of sections (P2's job, upstream of this) and
produces a dict of `IntelligenceArticle` constructor kwargs. It never
authorizes a claim itself, never persists anything, and never decides
whether publication should happen at all (that is the Final Publication
Validator + Publisher's job, both downstream of P1+P2 in the locked
pipeline boundary: EventTriage -> C1-C8.5 -> ComposedArticle -> P1 ->
P2 -> Final Publication Validator -> ONE V2 Publisher -> IntelligenceArticle).

## The `confidence_score` correction (owner review, 2026-09-04)

`IntelligenceArticle.confidence_score` is `Float, nullable=False,
default=0.0` -- a real, confirmed schema constraint, not something this
module can simply leave `None`. V2 must NOT fabricate a compatibility
metric to fill it (no manufactured "confidence" that looks like a real
score app-wide). This module always emits `0.0` -- the column's own
real schema default, never a computed value -- and flags making the
column nullable as a real, separate migration item (`P4_MIGRATION_TODO`
below), not something to work around here by inventing a number.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.aipe.historical_forecast_guard import scan_historical_forecast_collapse
from app.services.aipe.recommendation_language import scan_recommendation_language
from app.services.article_v2.company_name import resolve_company_name
from app.services.article_v2.composer import ComposedArticle, ComposedClaim
from app.services.article_v2.decision_engine import ArticleDecision
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.article_v2.headline_engine import HeadlineResult
from app.services.article_v2.identity import ArticleIdentity, PublicationResolution

# A real, separate migration item this translation surfaced -- NOT
# worked around here. `confidence_score` should become nullable so a
# pipeline that deliberately has no confidence concept (V2.0) can store
# a real absence instead of a value indistinguishable from a real 0.0
# score. Left as a constant so a future migration PR has a concrete
# anchor to grep for.
P4_MIGRATION_TODO = (
    "IntelligenceArticle.confidence_score should become nullable so V2 "
    "articles (which have no confidence concept by design) can store a "
    "real absence instead of a value indistinguishable from a real 0.0 score."
)


def _slugify(text: str) -> str:
    # Same simple implementation already duplicated locally in
    # comparison_publisher.py/signal_publisher.py -- kept local here too,
    # matching this codebase's established precedent for this helper
    # rather than centralizing it.
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def build_slug(headline: str, article_id: str) -> str:
    """A real, stable slug -- headline text plus a short id suffix so two
    articles that happen to produce the same slugified headline never
    collide (same discipline as V1's own `_slug()` in
    `opportunity_generator.py`: truncate, then append a short, real,
    non-guessable suffix, never rely on headline text alone for
    uniqueness)."""
    base = _slugify(headline)[:100].strip("-") or "article"
    return f"{base}-{article_id[:8]}"


def _first_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    m = re.search(r"[.!?](?:\s|$)", stripped)
    return stripped[: m.end()].strip() if m else stripped


def _compose_executive_summary(composed: ComposedArticle) -> str | None:
    """DETERMINISTIC -- the first real sentence of the first section that
    has one, never a second LLM call. What Happened is always present
    (composer.py's own guarantee), so this only returns None if every
    section's text is somehow empty, which composer.py's own refusal
    contract already prevents."""
    for section in composed.sections:
        sentence = _first_sentence(section.text)
        if sentence:
            return sentence
    return None


def _compose_key_takeaway(composed: ComposedArticle) -> str | None:
    """DETERMINISTIC -- same discipline as executive_summary, but drawn
    from `why_it_matters` when present (the section that actually
    explains significance), falling back to `what_happened` otherwise.
    Never a second LLM call, never re-interpreted prose."""
    for name in ("why_it_matters", "what_happened"):
        for section in composed.sections:
            if section.name == name:
                sentence = _first_sentence(section.text)
                if sentence:
                    return sentence
    return _compose_executive_summary(composed)


def _sources_from_claims(all_claims: list[ComposedClaim], evidence_set: ArticleEvidenceSet) -> list[dict]:
    """V2 SOURCE -- real evidence actually cited by a surviving claim,
    never every evidence item C2 originally gathered (which may include
    items a dropped claim referenced, or items never claimed at all).
    Deliberately built from `all_claims` (post P2-enforcement, the
    caller passes the SURVIVING claims only) rather than
    `evidence_set.primary_evidence`/`.supporting_evidence` directly."""
    cited_ids = {eid for claim in all_claims for eid in claim.evidence_ids}
    all_evidence = [evidence_set.primary_evidence] + list(evidence_set.supporting_evidence)
    sources = []
    for ev in all_evidence:
        if ev is None or ev.raw_evidence_id not in cited_ids:
            continue
        sources.append({
            "title": ev.title, "source_type": ev.source_type,
            "source_url": ev.source_url, "published_at": ev.published_at.isoformat() if ev.published_at else None,
        })
    return sources


def _scan_field(field_name: str, value: str | None) -> list[str]:
    """Runs both established generation-time guards
    (recommendation_language.py / historical_forecast_guard.py) against
    one arbitrary field by name -- both scanners only ever look at their
    own hardcoded `key_takeaway` key, so this builds the small dict shape
    they expect rather than reimplementing either scan."""
    if not value:
        return []
    probe = {"key_takeaway": value}
    return [
        f"{field_name}: {v}" for v in (*scan_recommendation_language(probe), *scan_historical_forecast_collapse(probe))
    ]


@dataclass(frozen=True)
class TranslationResult:
    fields: dict
    scan_violations: list[str]  # empty = clean; non-empty must fail the publish closed


def translate_composed_article(
    *, article_id: str, decision: ArticleDecision, evidence_set: ArticleEvidenceSet,
    identity: ArticleIdentity, resolution: PublicationResolution, headline_result: HeadlineResult,
    composed: ComposedArticle,
) -> TranslationResult:
    """The one real entry point. `composed` must already be the
    P2-enforced ComposedArticle (unauthorized claims/sections already
    dropped) -- this module does not call P2 itself, it only translates
    what P2 already approved. Runs the recommendation-language/
    historical-forecast-collapse scans on every field it composes,
    exactly as P1's own lock requires -- a non-empty `scan_violations`
    means the Publisher must refuse to persist, never store-then-flag."""
    company_name = resolve_company_name(
        verified_company_name=evidence_set.company_name,
        primary_evidence_title=evidence_set.primary_evidence.title if evidence_set.primary_evidence else None,
        symbol=evidence_set.symbol,
    )
    executive_summary = _compose_executive_summary(composed)
    key_takeaway = _compose_key_takeaway(composed)
    why_it_matters = next((s.text for s in composed.sections if s.name == "why_it_matters"), None)
    what_happened = next((s.text for s in composed.sections if s.name == "what_happened"), None)
    meta_description = executive_summary[:160] if executive_summary else None
    seo_title = composed.headline[:512]

    sources = _sources_from_claims(composed.all_claims, evidence_set)

    fields = {
        "id": article_id,
        "slug": build_slug(composed.headline, article_id),
        # DETERMINISTIC -- the real V1/V2 discriminator (locked P1 note).
        "article_type": "company_intelligence",
        "story_id": identity.identity_key,
        "story_version": 1,
        "parent_story_id": resolution.matched_article_id if resolution.publication_action == "UPDATE_EXISTING" else None,
        # EMPTY -- no V1 multi-angle fan-out in V2.0 (explicit scope limitation).
        "angle": "primary",
        "angle_entity": None,
        "parent_event_group_id": None,
        "is_evergreen": False,
        "lifecycle_status": "generated",
        "status": "draft",
        "update_count": 0,
        "headline": composed.headline,
        "executive_summary": executive_summary,
        "key_takeaway": key_takeaway,
        "why_it_matters": why_it_matters,
        "what_happened": what_happened,
        "companies_affected": [{"symbol": evidence_set.symbol, "name": company_name}] if evidence_set.symbol else [],
        "sectors_affected": [],
        # EMPTY -- real V1-only concepts V2.0 does not populate.
        "opportunities": [],
        "risks": [],
        "historical_events": [],
        "what_to_watch_next": [],
        "faqs": [],
        "sources": sources,
        # PROHIBITED -- V1 concept V2 must never populate.
        "ripple_effect": [],
        "seo_title": seo_title,
        "meta_description": meta_description,
        # DETERMINISTIC -- the real V1/V2 discriminator (locked P1 note).
        "trigger_type": "article_v2_pipeline",
        "trigger_event_id": decision.event_id,
        "trigger_data": {
            "content_type": composed.content_type, "publication_action": resolution.publication_action,
            "identity_key": identity.identity_key, "llm_status": composed.llm_status,
            "depth_gate_downgraded": composed.depth_gate_downgraded,
        },
        # PROHIBITED -- V2 has no confidence concept; see this module's
        # own docstring and P4_MIGRATION_TODO. Never a manufactured value.
        "confidence_score": 0.0,
        "validation_passed": True,
        "validation_results": {
            "llm_status": composed.llm_status, "llm_attempts": composed.llm_attempts,
            "llm_validation_notes": composed.llm_validation_notes, "word_count": composed.word_count,
        },
    }

    scan_violations = [
        *_scan_field("meta_description", meta_description),
        *_scan_field("executive_summary", executive_summary),
        *_scan_field("key_takeaway", key_takeaway),
    ]

    return TranslationResult(fields=fields, scan_violations=scan_violations)
