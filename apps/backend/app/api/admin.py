"""Protected operational endpoints — admin-key gated, not for end users.

Distinct from /api/publishing (ops dashboard, its own admin-gated endpoints
for content review) — this is infra/db status, for spotting misconfigurations
like an unmounted volume before they cause data loss.
"""
from __future__ import annotations

import hashlib

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin_key
from app.db.session import get_db

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/db-status", dependencies=[Depends(require_admin_key)])
async def db_status_endpoint():
    from app.db.session import engine
    from app.db.health import db_status
    return await db_status(engine)


@router.post("/backfill-seo-intelligence", dependencies=[Depends(require_admin_key)])
async def backfill_seo_intelligence(
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
):
    """
    One-time metadata backfill for the AI Newsroom redesign (2026-08-10,
    Decision 1 of 2 per the user's follow-up: "do 1 unconditionally, do 2
    as its own project"). Populates headline_angle/primary_keyword/
    secondary_keywords/entity_keywords/question_keywords/
    internal_link_candidates on articles published BEFORE the SEO
    Intelligence layer existed (those columns are simply NULL on them —
    publisher.py only started writing them going forward).

    Deliberately narrow: computed entirely from each article's own already-
    stored real companies_affected/sectors_affected/headline/article_type —
    no LLM call, no new data. Never touches headline, seo_title,
    meta_description, or any other visibly-published text — this is
    invisible-to-readers metadata only. Rewriting the visible SEO title/
    meta description for already-indexed URLs is a separate, deliberately
    NOT-included follow-up (needs its own batched rollout with Search
    Console monitoring, per the user's explicit call).

    Idempotent and safe to re-run: only touches rows where
    headline_angle IS NULL, so articles already backfilled (or published
    after the SEO Intelligence layer went live) are never re-processed.
    limit caps how many rows one call processes, so a very large backlog
    can be worked through in safe batches rather than one giant transaction.
    """
    from app.db.models.intelligence_article import IntelligenceArticle
    from app.services.seo_intelligence import compute_seo_intelligence
    from app.services.symbol_normalization import normalize_symbol
    from app.services.aipe.publisher import _sector_link

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.headline_angle.is_(None))
        .limit(limit)
    )
    articles = result.scalars().all()

    updated = 0
    for a in articles:
        seo_intel = compute_seo_intelligence(
            article_type=a.article_type,
            headline=a.headline or "",
            companies_affected=a.companies_affected or [],
            sectors_affected=a.sectors_affected or [],
            themes=[t.get("theme") for t in (a.related_themes or []) if isinstance(t, dict) and t.get("theme")],
            has_historical=bool(a.historical_events),
            sector_link_fn=_sector_link,
            normalize_symbol_fn=normalize_symbol,
        )
        a.headline_angle = seo_intel["headline_angle"]
        a.primary_keyword = seo_intel["primary_keyword"]
        a.secondary_keywords = seo_intel["secondary_keywords"]
        a.entity_keywords = seo_intel["entity_keywords"]
        a.question_keywords = seo_intel["question_keywords"]
        a.internal_link_candidates = seo_intel["internal_link_candidates"]
        updated += 1

    await db.commit()

    remaining = await db.execute(
        select(IntelligenceArticle.id)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.headline_angle.is_(None))
        .limit(1)
    )
    has_more = remaining.scalar_one_or_none() is not None

    return {"updated": updated, "has_more": has_more}


@router.post("/backfill-comparison-content", dependencies=[Depends(require_admin_key)])
async def backfill_comparison_content(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    One-time repair for every already-published comparison_intelligence
    article, after a live bug report (2026-08-11): companies_affected
    hardcoded reason="Comparison subject" and impact="neutral" for BOTH
    companies on every comparison, and key_takeaway was set to the bare
    stance word alone (e.g. "Neutral") with no context — both rendered as
    generic/unhelpful placeholders on the article page's "Why These Are
    Affected" and "30-Second Answer" sections, even though the article's
    OWN already-stored market_context.decision_intelligence (from the
    original run_ai_search call) carried real per-company theses and a
    real decision summary the whole time.

    Recomputes from each article's own already-stored market_context —
    no fresh run_ai_search call, no new AI generation, nothing invented.
    Idempotent and safe to re-run: articles whose companies_affected no
    longer contain the literal placeholder string are skipped.
    """
    from app.db.models.intelligence_article import IntelligenceArticle
    from app.services.aipe.comparison_publisher import _build_companies_affected, compose_key_takeaway

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.article_type == "comparison_intelligence")
        .limit(limit)
    )
    articles = result.scalars().all()

    updated = 0
    skipped = 0
    for a in articles:
        companies = a.companies_affected or []
        still_placeholder = any((c.get("reason") or "") == "Comparison subject" for c in companies)
        if not still_placeholder:
            skipped += 1
            continue

        di = (a.market_context or {}).get("decision_intelligence") or {}
        if not di:
            skipped += 1
            continue

        # Real symbols/names come from the article's own already-stored
        # companies_affected — never re-derived or guessed.
        if len(companies) != 2:
            skipped += 1
            continue
        name_a, symbol_a = companies[0].get("name", ""), companies[0].get("symbol", "")
        name_b, symbol_b = companies[1].get("name", ""), companies[1].get("symbol", "")

        a.companies_affected = _build_companies_affected(di, name_a, symbol_a, name_b, symbol_b)
        decision_summary = a.executive_summary or di.get("decision_summary") or ""
        a.key_takeaway = compose_key_takeaway(di, decision_summary)
        updated += 1

    await db.commit()
    return {"updated": updated, "skipped": skipped, "total_checked": len(articles)}


# ── TEMPORARY -- P7-C1 ownership-only observation status (owner-authorized,
# 2026-09-18). A durable cloud-scheduled routine polls this hourly to watch
# for the first naturally-qualifying candidate `should_withhold_for_v2_canary`
# withholds, beyond the one known historical specimen (nse-58efd351d6,
# Sunshine, 2026-09-15). Read-only -- no db.commit() anywhere in this
# function, nothing here can ever change a flag, predicate, or row. The
# cloud sandbox that calls this has no Railway CLI/SSH access at all, so a
# small HTTP surface (gated by the same X-Admin-Key check every other admin
# route already uses) is the narrowest way to give it a look, without
# handing it any Railway-level credential. Meant for removal once P7-C1
# ownership-only observation concludes (either a real specimen is found and
# reviewed, or the owner decides to stop watching).
_P7_BASELINE_TRIAGE_EVENT_ID = "nse-58efd351d6"


@router.get("/p7-withhold-status", dependencies=[Depends(require_admin_key)])
async def p7_withhold_status(db: AsyncSession = Depends(get_db)):
    """Reports the live effective P7 flag state (read directly from this
    process's own settings, not re-parsed from `railway variables` output --
    the authoritative answer to "did the config actually take effect") plus
    whether any article_v2_canary_withholds row exists beyond the known
    historical baseline. If one does, also reports its complete trace and
    whether it has ever been attempted or resulted in a real published
    article -- everything a human needs to make the public-write decision,
    with zero write capability in this function itself."""
    from app.core.config import settings
    from app.db.models.article_v2_canary_withhold import ArticleV2CanaryWithhold
    from app.db.models.intelligence_article import IntelligenceArticle

    result: dict = {
        "article_v2_canary_ownership_enabled": settings.article_v2_canary_ownership_enabled,
        "article_v2_canary_public_write_enabled": settings.article_v2_canary_public_write_enabled,
    }

    rows = (await db.execute(
        select(ArticleV2CanaryWithhold)
        .where(ArticleV2CanaryWithhold.triage_event_id != _P7_BASELINE_TRIAGE_EVENT_ID)
        .order_by(ArticleV2CanaryWithhold.withheld_at.asc())
    )).scalars().all()

    result["new_specimen_found"] = len(rows) > 0
    result["new_specimen_count"] = len(rows)
    if not rows:
        return result

    specimens = []
    for row in rows:
        published_articles = (await db.execute(
            select(IntelligenceArticle.id)
            .where(IntelligenceArticle.trigger_type == "article_v2_pipeline")
            .where(IntelligenceArticle.trigger_event_id == row.triage_event_id)
        )).scalars().all()
        specimens.append({
            "triage_event_id": row.triage_event_id,
            "withheld_at": row.withheld_at,
            "attempted": row.attempted,
            "outcome": row.outcome,
            "published_article_id": row.published_article_id,
            "reason_predicates": row.reason_predicates,
            "public_v2_articles_for_this_event": published_articles,
        })
    result["specimens"] = specimens
    return result


# ── TEMPORARY -- Opportunity V2 one-row public canary (owner-authorized,
# 2026-09-20). Promotes exactly one pre-selected, pre-verified OpportunityV2
# row out of shadow while `settings.opportunity_read_source` stays "v1" --
# the read-source flag governs which engine's LIST/detail data actually
# serves users; this canary is reachable only via its own real V2 slug
# (radar.py's dual-lookup route), never surfaced on any V1 list/hub
# surface. Each endpoint does an exact primary-key UPDATE guarded by the
# CURRENT public_status in the WHERE clause, inside one transaction,
# and refuses to report success unless exactly one row was affected --
# never a blind "public_status = X" write with no guard, never a
# multi-row update. Meant for removal once the single-canary review
# concludes (either kept public as the first real promoted row, or
# reverted after review).
#
# Item 7 enforcement (2026-09-20): this is the ONE real write path to
# public_status="public" in the whole codebase (confirmed by a full grep
# audit -- orchestration.py only ever sets "shadow" at creation), so
# gating it here is sufficient to close the promotion-eligibility gate
# everywhere. evaluate_promotion_eligibility() runs BEFORE the guarded
# UPDATE and makes no database write of its own; a rejection returns a
# machine-readable reason and touches nothing -- no row mutation, no
# narrative rewrite/delete, no score/identity/candidate_status/
# narrative_status change.
@router.post("/opportunity-v2-canary-promote", dependencies=[Depends(require_admin_key)])
async def opportunity_v2_canary_promote(opportunity_id: str, db: AsyncSession = Depends(get_db)):
    from app.db.models.opportunity_v2 import OpportunityV2
    from app.services.opportunity_v2.promotion_gate import evaluate_promotion_eligibility

    eligibility = await evaluate_promotion_eligibility(db, opportunity_id)
    if not eligibility.allowed:
        raise HTTPException(
            status_code=422,
            detail={"reason": eligibility.reason, "evaluated": eligibility.evaluated},
        )

    result = await db.execute(
        update(OpportunityV2)
        .where(OpportunityV2.id == opportunity_id, OpportunityV2.public_status == "shadow")
        .values(public_status="public")
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Expected exactly 1 row affected (id matched a shadow row), got {result.rowcount}. No change made.",
        )
    await db.commit()

    row = (await db.execute(select(OpportunityV2).where(OpportunityV2.id == opportunity_id))).scalar_one()
    return {
        "id": row.id, "slug": row.slug, "public_status": row.public_status,
        "current_title": row.current_title, "updated_at": row.updated_at,
    }


@router.post("/opportunity-v2-canary-revert", dependencies=[Depends(require_admin_key)])
async def opportunity_v2_canary_revert(opportunity_id: str, db: AsyncSession = Depends(get_db)):
    from app.db.models.opportunity_v2 import OpportunityV2

    result = await db.execute(
        update(OpportunityV2)
        .where(OpportunityV2.id == opportunity_id, OpportunityV2.public_status == "public")
        .values(public_status="shadow")
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Expected exactly 1 row affected (id matched a public row), got {result.rowcount}. No change made.",
        )
    await db.commit()

    row = (await db.execute(select(OpportunityV2).where(OpportunityV2.id == opportunity_id))).scalar_one()
    return {"id": row.id, "slug": row.slug, "public_status": row.public_status}


# ── Editorial override (2026-09-20) ─────────────────────────────────────────
# A canary/editorial safety valve, not the scalable fix for narrative
# overreach -- that needs an evidence-bounded generation strategy in the
# pipeline itself (see opportunity_v2.py's own column comment and
# read_service.py's _effective_title/_effective_summary, the only two
# functions every public read goes through). This is the ONE write path
# for editorial_title/editorial_summary/editorial_reason/
# editorial_updated_at in the whole codebase -- generated_title/
# generated_summary (current_title/current_summary) are never touched here,
# so the original AI output stays fully auditable regardless of how many
# times an override is set or cleared.
#
# Deliberately restricted to public_status="shadow" rows: this exists to
# let a human sign off on a strictly-evidence-traceable title/summary
# BEFORE a candidate is ever promoted, not to silently rewrite something
# already live. Promotion itself still goes through
# opportunity-v2-canary-promote above and its own promotion_gate check --
# nothing here changes public_status.


def _generated_content_hash(row) -> str:
    return hashlib.sha256(f"{row.current_title or ''}\n{row.current_summary or ''}".encode("utf-8")).hexdigest()


def _editorial_content_hash(title: str, summary: str) -> str:
    return hashlib.sha256(f"{title}\n{summary}".encode("utf-8")).hexdigest()


class EditorialOverrideRequest(BaseModel):
    title: str
    summary: str
    reason: str
    expected_generated_hash: str


class EditorialClearRequest(BaseModel):
    reason: str
    expected_generated_hash: str


@router.post("/opportunity-v2-editorial-override", dependencies=[Depends(require_admin_key)])
async def opportunity_v2_editorial_override(
    opportunity_id: str, body: EditorialOverrideRequest, db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    from app.db.models.opportunity_v2 import OpportunityV2

    if not body.reason.strip():
        raise HTTPException(status_code=422, detail={"reason": "reason_required"})

    row = (await db.execute(select(OpportunityV2).where(OpportunityV2.id == opportunity_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})

    if row.public_status != "shadow":
        raise HTTPException(status_code=422, detail={"reason": "not_shadow", "public_status": row.public_status})

    actual_hash = _generated_content_hash(row)
    if actual_hash != body.expected_generated_hash:
        raise HTTPException(
            status_code=409,
            detail={"reason": "stale_generated_hash", "expected": body.expected_generated_hash, "actual": actual_hash},
        )

    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(OpportunityV2)
        .where(OpportunityV2.id == opportunity_id, OpportunityV2.public_status == "shadow")
        .values(
            editorial_title=body.title, editorial_summary=body.summary,
            editorial_reason=body.reason, editorial_updated_at=now,
        )
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Expected exactly 1 row affected (id matched a shadow row), got {result.rowcount}. No change made.",
        )
    await db.commit()

    row = (await db.execute(select(OpportunityV2).where(OpportunityV2.id == opportunity_id))).scalar_one()
    log.info(
        "opportunity_v2.editorial_override.applied",
        opportunity_id=opportunity_id, reason=body.reason,
        generated_content_hash=actual_hash,
        editorial_content_hash=_editorial_content_hash(body.title, body.summary),
    )
    from app.services.opportunity_v2.read_service import _effective_title, _effective_summary
    return {
        "id": row.id, "slug": row.slug, "public_status": row.public_status,
        "editorial_title": row.editorial_title, "editorial_summary": row.editorial_summary,
        "editorial_reason": row.editorial_reason, "editorial_updated_at": row.editorial_updated_at,
        "effective_title": _effective_title(row), "effective_summary": _effective_summary(row),
    }


@router.post("/opportunity-v2-editorial-clear", dependencies=[Depends(require_admin_key)])
async def opportunity_v2_editorial_clear(
    opportunity_id: str, body: EditorialClearRequest, db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    from app.db.models.opportunity_v2 import OpportunityV2

    if not body.reason.strip():
        raise HTTPException(status_code=422, detail={"reason": "reason_required"})

    row = (await db.execute(select(OpportunityV2).where(OpportunityV2.id == opportunity_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason": "not_found"})

    if row.public_status != "shadow":
        raise HTTPException(status_code=422, detail={"reason": "not_shadow", "public_status": row.public_status})

    actual_hash = _generated_content_hash(row)
    if actual_hash != body.expected_generated_hash:
        raise HTTPException(
            status_code=409,
            detail={"reason": "stale_generated_hash", "expected": body.expected_generated_hash, "actual": actual_hash},
        )

    before_editorial_hash = (
        _editorial_content_hash(row.editorial_title, row.editorial_summary)
        if row.editorial_title is not None or row.editorial_summary is not None
        else None
    )

    # Idempotent by design -- clearing an already-cleared row is a
    # successful no-op (rowcount 0 here means nothing needed to change,
    # not an error), matching DELETE-style idempotency rather than
    # requiring an override to currently exist.
    await db.execute(
        update(OpportunityV2)
        .where(OpportunityV2.id == opportunity_id, OpportunityV2.public_status == "shadow")
        .values(editorial_title=None, editorial_summary=None, editorial_reason=None, editorial_updated_at=None)
    )
    await db.commit()

    row = (await db.execute(select(OpportunityV2).where(OpportunityV2.id == opportunity_id))).scalar_one()
    log.info(
        "opportunity_v2.editorial_override.cleared",
        opportunity_id=opportunity_id, reason=body.reason,
        generated_content_hash=actual_hash,
        editorial_content_hash_before=before_editorial_hash,
    )
    from app.services.opportunity_v2.read_service import _effective_title, _effective_summary
    return {
        "id": row.id, "slug": row.slug, "public_status": row.public_status,
        "editorial_title": row.editorial_title, "editorial_summary": row.editorial_summary,
        "editorial_reason": row.editorial_reason, "editorial_updated_at": row.editorial_updated_at,
        "effective_title": _effective_title(row), "effective_summary": _effective_summary(row),
    }
