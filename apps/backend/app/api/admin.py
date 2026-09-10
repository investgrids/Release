"""Protected operational endpoints — admin-key gated, not for end users.

Distinct from /api/publishing (ops dashboard, its own admin-gated endpoints
for content review) — this is infra/db status, for spotting misconfigurations
like an unmounted volume before they cause data loss.
"""
from __future__ import annotations

import json
import pathlib

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin_key
from app.db.session import get_db

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


# ── TEMPORARY — Historical Question-Intelligence Title Remediation ─────────
# One-off, bounded execution surface for the 62-row title-completeness fix
# (2026-09-09/10 session). This session has no direct production DB
# connection (per this whole engagement's established discipline — see
# feedback_production_write_discipline), so the write must go through a
# reviewable, auditable endpoint whose own request/response is a captured
# artifact — not a raw SSH command. Same shape as the
# admin-protected article retirement endpoint and the 2026-08-09
# 429-backlog-reset trigger: an explicit, committed, frozen manifest (never
# a broad WHERE-style query), dry_run defaults True, real writes require
# dry_run=false explicitly. Meant for removal (together with the manifest
# loader here, not the manifest file itself) once the repair is confirmed —
# do not leave a production-DB-write endpoint sitting in the repo for later.
_TITLE_REPAIR_MANIFEST_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent / "scripts" / "question_title_repair_manifest.json"
)


def _load_title_repair_manifest() -> list[dict]:
    data = json.loads(_TITLE_REPAIR_MANIFEST_PATH.read_text(encoding="utf-8"))
    return data["entries"]


@router.post("/repair-question-titles", dependencies=[Depends(require_admin_key)])
async def repair_question_titles(dry_run: bool = True, db: AsyncSession = Depends(get_db)):
    """Applies the frozen, pre-reviewed manifest of 62 deterministic title
    repairs for published question_intelligence articles whose headline
    was truncated into a grammatically incomplete fragment by the
    since-fixed content_planner.py bug. Each entry's `before` values were
    captured in the same read-only inventory pass this manifest was
    generated from -- if a row's CURRENT stored headline no longer matches
    that snapshot (e.g. a continuous-update pass touched it since), this
    skips that row rather than blindly overwriting unknown current state,
    which also makes a repeat call idempotent (already-repaired or
    already-diverged rows are cleanly skipped, never double-applied or
    clobbered). Only headline/seo_title/json_ld.headline are ever written;
    slug, canonical_url, body, evidence, companies_affected, published_at,
    created_at, and every other column are never touched by this route."""
    from app.db.models.intelligence_article import IntelligenceArticle

    entries = _load_title_repair_manifest()
    ids = [e["id"] for e in entries]

    result = await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id.in_(ids)))
    articles_by_id = {a.id: a for a in result.scalars().all()}

    report = []
    updated = 0
    would_update = 0
    skipped_missing = 0
    skipped_state_changed = 0

    for entry in entries:
        article = articles_by_id.get(entry["id"])
        if article is None:
            skipped_missing += 1
            report.append({"id": entry["id"], "outcome": "skipped_missing"})
            continue

        current_json_ld_headline = (article.json_ld or {}).get("headline") if isinstance(article.json_ld, dict) else None
        expected_before = entry["before"]
        state_matches = (
            article.headline == expected_before["headline"]
            and article.seo_title == expected_before["seo_title"]
            and current_json_ld_headline == expected_before["json_ld_headline"]
        )
        if not state_matches:
            skipped_state_changed += 1
            report.append({
                "id": entry["id"], "outcome": "skipped_state_changed",
                "current_headline": article.headline,
            })
            continue

        proposed = entry["proposed"]
        if dry_run:
            would_update += 1
            report.append({
                "id": entry["id"], "outcome": "would_update",
                "old_headline": article.headline, "new_headline": proposed["headline"],
            })
        else:
            article.headline = proposed["headline"]
            article.seo_title = proposed["seo_title"]
            if isinstance(article.json_ld, dict):
                article.json_ld = {**article.json_ld, "headline": proposed["json_ld_headline"]}
            updated += 1
            report.append({
                "id": entry["id"], "outcome": "updated",
                "old_headline": expected_before["headline"], "new_headline": proposed["headline"],
            })

    if not dry_run and updated:
        await db.commit()

    return {
        "dry_run": dry_run,
        "manifest_size": len(entries),
        "matched_current_state": len(entries) - skipped_missing - skipped_state_changed,
        "skipped_missing": skipped_missing,
        "skipped_state_changed": skipped_state_changed,
        "would_update": would_update,
        "updated": updated,
        "results": report,
    }
