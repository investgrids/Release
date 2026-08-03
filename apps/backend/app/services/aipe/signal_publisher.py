"""
Live Intelligence signal pages (Homepage audit, Priority 1) — permanent,
indexable /intelligence/signal/{slug} pages for each of the 4 real card
types live_intelligence.py detects.

Before this module, a detected signal (a real sector cluster, a real
policy ripple chain, a real rising theme, a real historical precedent)
existed only as an ephemeral dict, cached in Redis for 5 minutes and never
persisted — so a user who saw "11 IT companies showing simultaneous
activity" on the homepage had no page to click into, nothing to share, and
nothing for Google to index. This module gives each detected signal a
permanent row, reusing IntelligenceArticle exactly the way
comparison_publisher.py does (article_type discriminates the kind, the
generic market_context JSON field holds the type-specific payload) rather
than adding a new table/migration for what's structurally the same "AI-
generated, permanently-published, SEO-indexable content" the rest of AIPE
already models.

Slug strategy differs by type, matching how "current" each signal type
really is:
  - anomaly            dated slug ({sector}-cluster-{date}) — a cluster is
                        a point-in-time snapshot, re-detecting it tomorrow
                        is a genuinely different, newly-published page.
  - policy_ripple /
    early_theme /
    historical_match    topic-scoped slug (policy-{seed}, theme-{name},
                        historical-{event}) — upserted in place so the
                        same real-world thread accumulates one durable
                        page rather than fragmenting across re-detections.
                        first_detected_at is preserved across updates;
                        last_seen_at and occurrence_count track recurrence
                        without building a full evolution state machine
                        (Growing/Confirmed/Peak) — that's future work, not
                        invented here.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.intelligence_article import IntelligenceArticle

_ARTICLE_TYPE = "live_signal"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _today_str() -> str:
    ist = datetime.now(timezone.utc)
    return ist.strftime("%Y-%m-%d")


def slug_for_item(item: dict) -> str:
    t = item.get("type")
    if t == "anomaly":
        return f"{_slugify(item.get('sector') or 'sector')}-cluster-{_today_str()}"
    if t == "policy_ripple":
        return f"policy-{_slugify(item.get('headline') or 'ripple')}"
    if t == "early_theme":
        return f"theme-{_slugify(item.get('headline') or 'theme')}"
    if t == "historical_match":
        return f"historical-{_slugify(item.get('headline') or 'pattern')}"
    return f"signal-{_slugify(item.get('headline') or uuid.uuid4().hex[:8])}"


_TYPE_LABEL = {
    "anomaly": "Intelligence Detection",
    "policy_ripple": "Policy Intelligence",
    "early_theme": "Emerging Theme",
    "historical_match": "Pattern Detected",
}


def _headline_for_item(item: dict) -> str:
    return item.get("headline") or "Live Intelligence Signal"


def _summary_for_item(item: dict) -> str:
    t = item.get("type")
    if t == "anomaly":
        return item.get("why_it_matters") or _headline_for_item(item)
    if t == "policy_ripple":
        path = " → ".join(item.get("path") or [])
        return f"Causal chain: {path}" if path else _headline_for_item(item)
    if t == "early_theme":
        score = item.get("opportunity_score")
        return f"Rising theme with an opportunity score of {score}." if score is not None else _headline_for_item(item)
    if t == "historical_match":
        return item.get("key_lesson") or _headline_for_item(item)
    return _headline_for_item(item)


def _companies_for_item(item: dict) -> list[dict]:
    out = []
    for sym in (item.get("companies") or []):
        out.append({"name": sym, "symbol": sym, "impact": "neutral", "reason": _TYPE_LABEL.get(item.get("type"), "Live signal")})
    if item.get("type") == "historical_match":
        for sym in (item.get("winners") or []):
            out.append({"name": sym, "symbol": sym, "impact": "positive", "reason": "Historical winner"})
        for sym in (item.get("losers") or []):
            out.append({"name": sym, "symbol": sym, "impact": "negative", "reason": "Historical loser"})
    return out


async def publish_signal(db: AsyncSession, item: dict) -> dict:
    """Upserts one detected item as a permanent IntelligenceArticle row.
    Never fails the caller — live_intelligence.py's feed must keep working
    even if persistence has a problem, so this only raises on a genuine
    programming error, not on "nothing to publish" (every real detector
    output is publishable; there's no quality gate here like the
    comparison pages have, because these are simple structured facts, not
    LLM prose that can come back degraded)."""
    slug = slug_for_item(item)
    now = datetime.now(timezone.utc)
    site_url = (settings.frontend_url or "https://www.marketripple.in").rstrip("/")
    canonical_url = f"{site_url}/intelligence/signal/{slug}"
    headline = _headline_for_item(item)
    summary = _summary_for_item(item)
    label = _TYPE_LABEL.get(item.get("type"), "Live Intelligence")
    is_dated = item.get("type") == "anomaly"

    existing = (await db.execute(
        select(IntelligenceArticle).where(IntelligenceArticle.slug == slug)
    )).scalar_one_or_none()

    prior_ctx = (existing.market_context or {}) if existing else {}
    first_detected_at = prior_ctx.get("first_detected_at") or item.get("detected_at") or now.isoformat()
    occurrence_count = int(prior_ctx.get("occurrence_count") or 0) + 1

    market_context = {
        "kind": "live_signal",
        "signal_type": item.get("type"),
        "payload": item,
        "first_detected_at": first_detected_at,
        "last_seen_at": item.get("detected_at") or now.isoformat(),
        "occurrence_count": occurrence_count,
    }

    json_ld = {
        "@context": "https://schema.org",
        # Same distinction as publisher.py — this is a real-time detection
        # reported as it happens, the exact shape NewsArticle exists for.
        "@type": "NewsArticle",
        "headline": headline,
        "description": summary,
        "datePublished": first_detected_at,
        "dateModified": now.isoformat(),
        "author": {"@type": "Organization", "name": "MarketRipple AI Intelligence Engine"},
        "publisher": {"@type": "Organization", "name": "MarketRipple"},
        "mainEntityOfPage": canonical_url,
        "breadcrumb": {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "MarketRipple", "item": site_url},
                {"@type": "ListItem", "position": 2, "name": "Live Intelligence", "item": f"{site_url}/#live-intelligence"},
                {"@type": "ListItem", "position": 3, "name": headline, "item": canonical_url},
            ],
        },
    }

    companies_affected = _companies_for_item(item)
    sectors_affected = [{"name": item["sector"], "impact": "neutral", "magnitude": "medium"}] if item.get("sector") else []

    if existing:
        existing.headline = headline
        existing.executive_summary = summary
        existing.key_takeaway = summary
        existing.companies_affected = companies_affected
        existing.sectors_affected = sectors_affected
        existing.seo_title = f"{headline} - {label}"
        existing.meta_description = summary[:160]
        existing.canonical_url = canonical_url
        existing.json_ld = json_ld
        existing.market_context = market_context
        existing.last_updated = now
        existing.update_count = (existing.update_count or 0) + 1
        # A dated (anomaly) slug is naturally unique per day — a fresh
        # detection under the same slug today is a re-run of the same
        # cache cycle, not a new story, so published_at stays as first-seen.
        if not is_dated:
            pass
    else:
        db.add(IntelligenceArticle(
            id=str(uuid.uuid4()), slug=slug, article_type=_ARTICLE_TYPE,
            angle="primary", is_evergreen=not is_dated,
            lifecycle_status="published", status="published",
            headline=headline, executive_summary=summary, key_takeaway=summary,
            companies_affected=companies_affected, sectors_affected=sectors_affected,
            sources=["MarketRipple Live Intelligence Engine"],
            seo_title=f"{headline} - {label}", meta_description=summary[:160],
            canonical_url=canonical_url, json_ld=json_ld, market_context=market_context,
            published_at=now, last_updated=now,
        ))

    await db.commit()
    return {"slug": slug, "headline": headline}


# ── Async enrichment ──────────────────────────────────────────────────────
#
# publish_signal above is deliberately fast and LLM-free — it runs inside a
# real user's request (live_intelligence.py's /feed endpoint, on a cache
# miss), and blocking that on an LLM call would make a live page load wait
# on AI generation. What it stores is genuinely thin though (SEO audit's
# Stage-2 "Live Feed explanations" gap, and the roadmap's own "one-click
# article generation from every feed item" ask): why_it_matters/
# what_happened/opportunities/risks/faqs are never set.
#
# Enrichment is a SEPARATE, scheduled, async pass — same decoupling
# principle already proven safe in this codebase by image_worker.py (hero
# images generate after publish, on the worker's own schedule, never
# blocking the request that created the row).

_ENRICH_MIN_WHY_LEN = 40  # below this, treat why_it_matters as "still thin"


async def _needs_enrichment(a: IntelligenceArticle) -> bool:
    return len(a.why_it_matters or "") < _ENRICH_MIN_WHY_LEN


async def enrich_signal_article(db: AsyncSession, article: IntelligenceArticle) -> bool:
    """One real LLM call to give a thin live_signal row genuine analysis —
    why it matters, what happened, real opportunities/risks, FAQs — reusing
    article_generator.py's existing schema/template rather than building a
    parallel prompt. The signal-specific identity (headline, companies_
    affected, market_context payload, canonical_url) is never overwritten;
    only the narrative fields a real reader would expect are filled in."""
    from app.services.aipe.article_generator import generate_intelligence_article
    from app.services.aipe.market_story_engine import get_mie_context

    ctx = (article.market_context or {})
    payload = ctx.get("payload") or {}
    event = {
        "headline": article.headline,
        "summary": article.executive_summary or "",
        "sectors": [payload["sector"]] if payload.get("sector") else [],
        "tickers": [c.get("symbol") for c in (article.companies_affected or []) if c.get("symbol")],
    }
    try:
        mie_context = await get_mie_context()
    except Exception:
        mie_context = {}

    # breaking_intelligence is the closest existing template to "explain
    # this just-detected real-time signal" — reused rather than adding a
    # parallel prompt for what's conceptually the same kind of content.
    generated = await generate_intelligence_article("breaking_intelligence", event, mie_context, historical=[])
    if not generated:
        return False

    article.why_it_matters = generated.get("why_it_matters") or article.why_it_matters
    article.what_happened = generated.get("what_happened") or article.what_happened
    article.opportunities = generated.get("opportunities") or article.opportunities
    article.risks = generated.get("risks") or article.risks
    article.faqs = generated.get("faqs") or article.faqs
    if generated.get("faqs"):
        types = article.json_ld.get("@type") if article.json_ld else None
        if article.json_ld and types and "FAQPage" not in (types if isinstance(types, list) else [types]):
            article.json_ld = {
                **article.json_ld,
                "@type": [types, "FAQPage"] if isinstance(types, str) else [*types, "FAQPage"],
                "mainEntity": [
                    {"@type": "Question", "name": f.get("question", ""),
                     "acceptedAnswer": {"@type": "Answer", "text": f.get("answer", "")}}
                    for f in generated["faqs"][:5]
                ],
            }
    now = datetime.now(timezone.utc)
    article.last_updated = now
    article.update_count = (article.update_count or 0) + 1
    article.touch_json_ld_modified(now)
    db.add(article)
    await db.commit()
    return True


async def run_signal_enrichment_cycle(max_per_cycle: int = 3) -> int:
    """Scheduled job (see scheduler.py) — enriches up to max_per_cycle thin
    live_signal articles per run. Small batch + a real LLM call each,
    matching the same rate-limit reasoning comparison_scheduler.py already
    documents for its own cycle."""
    import structlog
    log = structlog.get_logger(__name__)
    from app.db.session import AsyncSessionLocal

    enriched = 0
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(IntelligenceArticle)
            .where(IntelligenceArticle.article_type == _ARTICLE_TYPE)
            .where(IntelligenceArticle.status == "published")
            .order_by(IntelligenceArticle.published_at.desc())
            .limit(50)
        )).scalars().all()

        for a in rows:
            if enriched >= max_per_cycle:
                break
            if not await _needs_enrichment(a):
                continue
            try:
                ok = await enrich_signal_article(db, a)
            except Exception as exc:
                log.warning("signal_enrichment.failed", slug=a.slug, error=str(exc)[:200])
                continue
            if ok:
                enriched += 1
                log.info("signal_enrichment.done", slug=a.slug)

    return enriched
