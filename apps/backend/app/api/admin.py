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


# ── TEMPORARY -- Deep Filing Evidence Production Phase DFE-PROD-1 ──────────
# One-off, bounded population of the 7 named candidates the owner explicitly
# authorized on 2026-09-18 (see scripts/dfe_prod1_population_candidates.json
# for the full manifest + per-candidate rationale -- deliberately containing
# positive, partial-evidence, R1-normalization, second-cohort, fail-closed,
# and TargetFact-R1 cases, never a broad query). Per
# feedback_production_write_discipline, this goes through a reviewable,
# auditable endpoint rather than raw SSH -- this session has no direct
# production DB connection.
#
# Calls the real, already-deployed application functions verbatim
# (fetch_source_document, extract_transaction_facts,
# persist_transaction_facts) -- never reimplements their logic here.
#
# fetch_source_document() always commits its own SourceDocument row by
# design (a SourceDocument is an immutable evidence capture, not a value
# under repair the way the NSE-title-repair precedent's Event.title was)
# and is already idempotent by content_hash -- refetching the same URL for
# the same raw_evidence_id returns the EXISTING row rather than duplicating
# it. persist_transaction_facts() is likewise idempotent, upserting by
# (source_document_id, field_code). dry_run therefore does not gate the
# fetch step; it gates only whether the real extraction result is actually
# persisted as TransactionFact rows -- a real, deliberate difference from
# the title-repair precedent, not an oversight.
#
# Meant for removal (endpoint + manifest-loading helper, not the manifest
# data file) once population is confirmed against production.
_DFE_PROD1_MANIFEST_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent / "scripts" / "dfe_prod1_population_candidates.json"
)


def _load_dfe_prod1_manifest() -> list[dict]:
    return json.loads(_DFE_PROD1_MANIFEST_PATH.read_text(encoding="utf-8"))["entries"]


@router.post("/dfe-prod1-populate", dependencies=[Depends(require_admin_key)])
async def dfe_prod1_populate(
    dry_run: bool = True,
    labels: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Runs the real Deep Filing Evidence pipeline (SourceDocument capture
    -> TransactionFact extraction -> persistence) against the frozen,
    named 7-candidate manifest only. See module comment above for the full
    safety contract. Returns full per-candidate provenance -- extraction
    status, content hash, page count, every extracted field's status/value,
    and (when dry_run=false) how many TransactionFact rows were persisted.

    `labels` (owner instruction, 2026-09-18): an optional comma-separated
    subset of the manifest's own `label` values (e.g. "ZODIAC" or
    "ZODIAC,GUJENERGY") for staged, one-candidate-at-a-time qualification
    -- still only ever selects FROM the fixed manifest, never accepts an
    arbitrary raw_evidence_id/URL the caller supplies. Omit for the full
    manifest."""
    from app.db.models.source_document import EXTRACTED
    from app.services.warehouse.source_document import fetch_source_document
    from app.services.warehouse.transaction_fact_extractor import extract_transaction_facts, persist_transaction_facts

    entries = _load_dfe_prod1_manifest()
    if labels:
        wanted = {l.strip() for l in labels.split(",") if l.strip()}
        entries = [e for e in entries if e["label"] in wanted]
    results = []
    for entry in entries:
        result: dict = {"label": entry["label"], "raw_evidence_id": entry["raw_evidence_id"]}
        doc = await fetch_source_document(db, raw_evidence_id=entry["raw_evidence_id"], url=entry["url"])
        result["source_document_id"] = doc.id
        result["extraction_status"] = doc.extraction_status
        result["content_hash"] = doc.content_hash
        result["page_count"] = doc.page_count
        if doc.extraction_status != EXTRACTED:
            results.append(result)
            continue

        pages = json.loads(doc.page_texts_json)
        try:
            candidates = extract_transaction_facts(pages)
        except Exception as exc:
            result["extraction_crash"] = f"{type(exc).__name__}: {exc}"
            results.append(result)
            continue

        result["transaction_facts"] = [
            {"field": c.field_code, "status": c.extraction_status, "value_text": c.value_text, "value_numeric": c.value_numeric}
            for c in candidates
        ]
        if not dry_run:
            persisted = await persist_transaction_facts(
                db, source_document_id=doc.id, raw_evidence_id=entry["raw_evidence_id"], candidates=candidates,
            )
            result["persisted_count"] = len(persisted)
        results.append(result)

    return {"dry_run": dry_run, "manifest_size": len(entries), "results": results}


# ── TEMPORARY -- Deep Filing Evidence Production Phase DFE-PROD-1: shadow ──
# run (owner-authorized, 2026-09-18). Runs the real Article V2 pipeline
# (C3 context -> C5.3 headline -> C6 composition -> P1/P2/SG1 validation)
# against the already-persisted, named 7-candidate manifest, for
# comparison against local revalidation results. NEVER calls
# publish_v2_article -- no IntelligenceArticle row is ever created by this
# endpoint, real or draft. Both P7 flags (article_v2_canary_ownership_
# enabled, article_v2_canary_public_write_enabled) remain False throughout;
# this endpoint doesn't read or depend on either -- it is structurally
# incapable of a public write regardless of their value, since it never
# imports or calls the one function that would perform one.
#
# Real, live LLM calls happen here (headline generation, Why It Matters)
# -- a genuine external side effect (cost, provider rate-limit usage), but
# never a database write beyond composer.py's/publisher.py's own normal,
# already-reviewed in-memory computation. Meant for removal once shadow
# verification is confirmed against production, same as the population
# endpoint above.
@router.post("/dfe-prod1-shadow-run", dependencies=[Depends(require_admin_key)])
async def dfe_prod1_shadow_run(
    labels: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Builds a real ArticleEvidenceSet for each named candidate from its
    already-persisted RawEvidence, runs it through the real C3/C5.3/C6/P1/
    P2/SG1 pipeline, and returns the full composed result -- headline,
    What Happened, Why It Matters, key facts, SG1 outcome, and every
    surviving claim's type (FACT/INTERPRETATION). Never publishes."""
    from sqlalchemy import select as sa_select

    from app.db.models.raw_evidence import RawEvidence
    from app.services.article_v2.composer import compose_article
    from app.services.article_v2.context_builder import build_context
    from app.services.article_v2.decision_engine import CREATE, FULL_ARTICLE, ArticleDecision
    from app.services.article_v2.evidence_set_builder import COHERENT, ArticleEvidenceSet
    from app.services.article_v2.headline_engine import generate_headline
    from app.services.article_v2.identity import CREATE_NEW, PublicationResolution, compute_identity
    from app.services.article_v2.publisher import PublicationRefusal, build_and_validate
    from app.services.warehouse.read_service import LinkedEvidence

    entries = _load_dfe_prod1_manifest()
    if labels:
        wanted = {l.strip() for l in labels.split(",") if l.strip()}
        entries = [e for e in entries if e["label"] in wanted]

    results = []
    for entry in entries:
        result: dict = {"label": entry["label"], "raw_evidence_id": entry["raw_evidence_id"]}
        raw = (await db.execute(
            sa_select(RawEvidence).where(RawEvidence.id == entry["raw_evidence_id"])
        )).scalar_one_or_none()
        if raw is None:
            result["error"] = "raw_evidence_not_found -- run dfe-prod1-populate first"
            results.append(result)
            continue

        symbol = entry["symbol"]
        evidence = LinkedEvidence(
            raw_evidence_id=raw.id, title=entry["title"], source_type="nse",
            published_at=raw.observed_at, source_url=entry["url"],
            relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
        )
        es = ArticleEvidenceSet(
            entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt1", event_headline=entry["title"],
            status=COHERENT, primary_evidence=evidence, supporting_evidence=[], company_name=f"{symbol} Limited",
        )
        identity = compute_identity(es)
        ctx = await build_context(db, es)
        result["context_status"] = ctx.status
        result["context_omitted_reasons"] = ctx.omitted_reasons

        resolution = PublicationResolution(
            identity=identity, publication_action=CREATE_NEW, matched_identity_key=None,
            matched_article_id=None, reason="dfe-prod1-shadow-run",
        )
        headline_result = await generate_headline(es, ctx, identity, other_accepted_headlines={})
        result["headline_status"] = headline_result.status
        result["headline"] = headline_result.h1

        decision = ArticleDecision(
            entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
            content_type=FULL_ARTICLE, publication_action=CREATE,
        )
        composed = await compose_article(decision, es, ctx, identity, resolution, headline_result)
        result["llm_status"] = composed.llm_status
        result["all_claim_types"] = sorted({c.claim_type for c in composed.all_claims})

        try:
            build_result = build_and_validate(
                article_id=f"shadow-{entry['label'].lower()}", decision=decision, evidence_set=es, identity=identity,
                resolution=resolution, headline_result=headline_result, composed=composed,
            )
            result["sg1_result"] = "PASSED"
            fields = build_result.fields
            result["final_headline"] = fields.get("headline")
            result["what_happened"] = fields.get("what_happened")
            result["why_it_matters"] = fields.get("why_it_matters")
            result["key_facts"] = fields.get("key_facts")
        except PublicationRefusal as exc:
            result["sg1_result"] = "REFUSED"
            result["sg1_reason"] = str(exc)

        results.append(result)

    return {"manifest_size": len(entries), "results": results}
