"""
Article V2 Phase P4 — Publisher + persistence layer (owner design,
2026-09-06). The ONE place a V2 `IntelligenceArticle` row gets built.

Locked pipeline boundary:

  EventTriage -> C1-C8.5 -> ComposedArticle -> P1 (publication_translator)
  -> P2 (claim_translation) -> Final Publication Validator -> ONE V2
  Publisher (this module) -> IntelligenceArticle

"Persistence without activation" (owner's own framing): this module can
build and persist a real row against any session it's handed -- a test
DB, a rollback-guarded session -- but it is never called from a
scheduler job, an API route, or any other production entry point in
this phase. Wiring a real entry point is P5's job, not this module's.
Nothing in this file imports or references `aipe_publish_cycle`, any
router, or an `ARTICLE_PIPELINE_MODE`-style flag -- those stay out of
scope until the phases that are actually authorized to add them.

## Why enforcement happens HERE, not just in claim_translation.py

P2 (`claim_translation.py`) knows how to authorize one claim and enforce
one section. It does not decide what an article-level failure means, or
own the "never store-then-flag" rule for the scan-based checks P1 runs.
The Final Publication Validator below is the one place that combines
P1+P2's outputs into a single publish/refuse decision -- mirroring
`composer.py`'s own `ComposerRefusal` precedent: a hard invariant,
checked once, raised immediately, never a best-effort partial write.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle
from app.services.article_v2.claim_translation import TranslationContext, enforce_section_authorization
from app.services.article_v2.composer import ComposedArticle
from app.services.article_v2.decision_engine import ArticleDecision
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.article_v2.headline_engine import HeadlineResult
from app.services.article_v2.identity import ArticleIdentity, PublicationResolution
from app.services.article_v2.publication_translator import translate_composed_article


class PublicationRefusal(ValueError):
    """Raised when the Publisher must refuse to persist -- a hard
    invariant, matching composer.py's ComposerRefusal precedent exactly.
    Never a best-effort partial write; no `IntelligenceArticle` row is
    added to the session when this is raised."""


@dataclass(frozen=True)
class EnforcedComposition:
    composed: ComposedArticle
    dropped_claim_count: int
    omitted_section_names: list[str]


def _enforce_all_sections(composed: ComposedArticle, ctx: TranslationContext) -> EnforcedComposition:
    """Runs P2 enforcement over every section, then rebuilds the
    ComposedArticle from only the surviving sections/claims. Recomputes
    `all_claims`/`word_count` from what actually survived -- never
    trusts the original composed.all_claims/word_count once enforcement
    may have dropped something."""
    surviving_sections = []
    surviving_claims = []
    dropped_count = 0
    omitted_names: list[str] = []

    for section in composed.sections:
        result = enforce_section_authorization(section, ctx)
        dropped_count += len(result.dropped_claims)
        if result.section is None:
            omitted_names.append(section.name)
            continue
        surviving_sections.append(result.section)
        surviving_claims.extend(result.section.claims)

    word_count = sum(len(s.text.split()) for s in surviving_sections)
    enforced = replace(
        composed, sections=surviving_sections, all_claims=surviving_claims, word_count=word_count,
    )
    return EnforcedComposition(composed=enforced, dropped_claim_count=dropped_count, omitted_section_names=omitted_names)


def build_and_validate(
    *, article_id: str, decision: ArticleDecision, evidence_set: ArticleEvidenceSet,
    identity: ArticleIdentity, resolution: PublicationResolution, headline_result: HeadlineResult,
    composed: ComposedArticle, translation_ctx: TranslationContext | None = None,
) -> dict:
    """Runs P2 enforcement, then P1 translation, then the Final
    Publication Validator. Returns the validated `IntelligenceArticle`
    constructor kwargs on success. Raises `PublicationRefusal` on any
    failure -- never returns a partially-valid result."""
    ctx = translation_ctx or TranslationContext()

    enforced = _enforce_all_sections(composed, ctx)
    # `what_happened` is the one section composer.py itself guarantees is
    # always present for any real ComposedArticle -- the anchor content,
    # never optional (see composer.py's own docstring: "What Happened, at
    # minimum, is always present"). If enforcement dropped it, this is
    # exactly the "empties a required section" case the locked P2 rule
    # requires failing closed for -- checking merely "some section
    # survived" is not enough, since a trivial boilerplate section with
    # zero claims (source_updated) always survives on its own and would
    # otherwise let a content-free stub through.
    what_happened_survived = any(s.name == "what_happened" and s.text.strip() for s in enforced.composed.sections)
    if not what_happened_survived:
        raise PublicationRefusal(
            "claim-authorization enforcement dropped the required what_happened section -- nothing real left to "
            f"publish (dropped_claim_count={enforced.dropped_claim_count}, omitted_sections={enforced.omitted_section_names})"
        )

    result = translate_composed_article(
        article_id=article_id, decision=decision, evidence_set=evidence_set, identity=identity,
        resolution=resolution, headline_result=headline_result, composed=enforced.composed,
    )
    if result.scan_violations:
        raise PublicationRefusal(
            f"generation-time content guards rejected the translated fields: {result.scan_violations}"
        )
    if not result.fields.get("headline"):
        raise PublicationRefusal("no usable headline -- refusing to publish.")

    return result.fields


async def publish_v2_article(
    db: AsyncSession, *, article_id: str, decision: ArticleDecision, evidence_set: ArticleEvidenceSet,
    identity: ArticleIdentity, resolution: PublicationResolution, headline_result: HeadlineResult,
    composed: ComposedArticle, translation_ctx: TranslationContext | None = None,
) -> IntelligenceArticle:
    """The one real write path. Adds and flushes a new `IntelligenceArticle`
    against the given session -- does NOT commit. The caller owns the
    transaction boundary (a test's rollback-guarded session today; a
    real production commit only once P5/P6/P7 authorize it). Raises
    `PublicationRefusal` before touching the session at all if the
    Final Publication Validator refuses -- no half-written row on
    failure."""
    fields = build_and_validate(
        article_id=article_id, decision=decision, evidence_set=evidence_set, identity=identity,
        resolution=resolution, headline_result=headline_result, composed=composed, translation_ctx=translation_ctx,
    )
    article = IntelligenceArticle(**fields)
    db.add(article)
    await db.flush()
    return article
