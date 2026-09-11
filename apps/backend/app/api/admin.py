"""Protected operational endpoints — admin-key gated, not for end users.

Distinct from /api/publishing (ops dashboard, its own admin-gated endpoints
for content review) — this is infra/db status, for spotting misconfigurations
like an unmounted volume before they cause data loss.
"""
from __future__ import annotations

import json
import pathlib
from collections import Counter

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


# ── TEMPORARY — Historical NSE Title Truncation Repair ──────────────────────
# One-off, bounded execution surface for the 2026-09-10 NSE event/news title
# truncation incident (nse_provider._clip_headline, fixed in 53aaedc/fb051e0/
# 85ad0a7). Per feedback_production_write_discipline this session has no
# direct production DB connection, so the write must go through a
# reviewable, auditable endpoint — same shape as the question-title repair
# endpoint (edb3348, since removed): an explicit, committed, frozen manifest
# (never a broad WHERE-style query), dry_run defaults True, real writes
# require dry_run=false explicitly.
#
# Extra safeguard beyond the question-title precedent (owner's explicit
# instruction, 2026-09-10): a row's expected replacement is RECOMPUTED from
# its own current `summary` column, using the real deployed _clip_headline,
# immediately before writing — not just trusted from the frozen manifest.
# A row is only written if BOTH the frozen "before" still matches current
# state AND the live recompute still equals the frozen "after". Either
# mismatch is a skip, never an overwrite of unknown/drifted state.
#
# Only Event.title / NewsArticle.headline are ever written — slug, id,
# summary, canonical identity, timestamps, and every other column are never
# touched by this route. Meant for removal (endpoint + manifest-loading
# code, not the manifest data files) once the repair is confirmed against
# production.
_EVENT_TITLE_REPAIR_MANIFEST_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent / "scripts" / "nse_event_title_repair_manifest.json"
)
_NEWS_HEADLINE_REPAIR_MANIFEST_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent / "scripts" / "nse_news_headline_repair_manifest.json"
)


def _load_nse_repair_manifest(path: pathlib.Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["entries"]


async def _repair_nse_title_table(
    db: AsyncSession,
    model,
    title_attr: str,
    summary_attr: str,
    entries: list[dict],
    dry_run: bool,
    batch_size: int,
) -> dict:
    from app.providers.nse_provider import _clip_headline

    ids = [e["id"] for e in entries]
    rows_by_id: dict[str, object] = {}
    for i in range(0, len(ids), batch_size):
        chunk = ids[i : i + batch_size]
        result = await db.execute(select(model).where(model.id.in_(chunk)))
        for row in result.scalars().all():
            rows_by_id[row.id] = row

    counters: Counter = Counter(
        skipped_missing=0, skipped_state_changed=0, skipped_recompute_mismatch=0,
        would_update=0, updated=0,
    )
    report = []

    for i, entry in enumerate(entries):
        row = rows_by_id.get(entry["id"])
        if row is None:
            counters["skipped_missing"] += 1
            report.append({"id": entry["id"], "outcome": "skipped_missing"})
            continue

        current_title = getattr(row, title_attr)
        if current_title != entry["before"]:
            counters["skipped_state_changed"] += 1
            report.append({"id": entry["id"], "outcome": "skipped_state_changed", "current": current_title})
            continue

        current_summary = getattr(row, summary_attr) or ""
        recomputed = _clip_headline(current_summary)
        if recomputed != entry["after"]:
            counters["skipped_recompute_mismatch"] += 1
            report.append({
                "id": entry["id"], "outcome": "skipped_recompute_mismatch",
                "frozen_after": entry["after"], "recomputed": recomputed,
            })
            continue

        if dry_run:
            counters["would_update"] += 1
            report.append({"id": entry["id"], "outcome": "would_update", "old": current_title, "new": entry["after"]})
        else:
            setattr(row, title_attr, entry["after"])
            counters["updated"] += 1
            report.append({"id": entry["id"], "outcome": "updated", "old": current_title, "new": entry["after"]})

        if not dry_run and (i + 1) % batch_size == 0:
            await db.commit()

    if not dry_run:
        await db.commit()

    return {"manifest_size": len(entries), **counters, "results": report}


@router.post("/repair-nse-titles", dependencies=[Depends(require_admin_key)])
async def repair_nse_titles(
    dry_run: bool = True,
    batch_size: int = 250,
    db: AsyncSession = Depends(get_db),
):
    """Applies the frozen, pre-reviewed manifests of deterministic title/
    headline repairs for NSE-sourced events and news_articles whose title
    was truncated into a grammatically incomplete fragment by the
    since-fixed nse_provider._clip_headline bug. See module comment above
    for the full safety contract (frozen-state check + live recompute
    check, both required, before any write)."""
    from app.db.models.event import Event
    from app.db.models_legacy import NewsArticle

    event_entries = _load_nse_repair_manifest(_EVENT_TITLE_REPAIR_MANIFEST_PATH)
    news_entries = _load_nse_repair_manifest(_NEWS_HEADLINE_REPAIR_MANIFEST_PATH)

    events_result = await _repair_nse_title_table(
        db, Event, "title", "summary", event_entries, dry_run, batch_size
    )
    news_result = await _repair_nse_title_table(
        db, NewsArticle, "headline", "summary", news_entries, dry_run, batch_size
    )

    return {"dry_run": dry_run, "events": events_result, "news_articles": news_result}
