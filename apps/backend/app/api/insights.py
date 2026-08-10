"""
Public Intelligence Insights API — read-only, published articles only.

Serves the public /insights pages (SEO article surface). This is distinct
from /api/publishing, which is the internal ops/monitoring dashboard API
and exposes ops-only fields (validation internals, trigger data) that stay
internal. `views` is public — it's a real engaged-read counter, incremented
via POST /{slug}/view (see below), not an ops metric.

GET  /api/insights/            -> paginated list of published articles
GET  /api/insights/{slug}      -> full public detail for one article
POST /api/insights/{slug}/view -> record one engaged read (deduped per
                                   visitor per day via Redis)
POST /api/insights/{slug}/share -> record one share-channel click (no dedup)
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi.util import get_remote_address
from sqlalchemy import func, select, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_get, cache_set
from app.db.models.generated_media import GeneratedMedia
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import get_db
from app.services.seo_intelligence import resolve_headline_angle
from app.services.symbol_normalization import normalize_symbol

router = APIRouter()


def _normalized_companies(companies: list[dict] | None) -> list[dict]:
    """
    Serve-time symbol normalization (AI Newsroom redesign, 2026-08-10) —
    applied here rather than only at publish time so it also fixes articles
    published before symbol_normalization.py existed, without a data
    backfill. Never drops a company mention: only replaces a malformed
    symbol (e.g. the BSE numeric "BOM:500400" form) with either its
    resolved NSE ticker or None (never a fabricated one) — the company's
    name/reason/impact stay intact either way, only the linkability changes.
    """
    out: list[dict] = []
    for c in (companies or []):
        if not isinstance(c, dict):
            continue
        resolved = normalize_symbol(c.get("symbol"), c.get("name"))
        out.append({**c, "symbol": resolved})
    return out


def _normalized_related_companies(related: list[dict] | None) -> list[dict]:
    """Same serve-time fix as _normalized_companies, for the
    related_companies shape ({symbol, name, link}) — a company that can't
    be resolved is dropped rather than kept with a broken link, since
    related_companies (unlike companies_affected) exists purely to be
    clicked."""
    out: list[dict] = []
    for c in (related or []):
        if not isinstance(c, dict):
            continue
        resolved = normalize_symbol(c.get("symbol"), c.get("name"))
        if resolved:
            out.append({**c, "symbol": resolved, "link": f"/companies/{resolved}"})
    return out


async def _fetch_hero_images(db: AsyncSession, article_ids: list[str]) -> dict[str, str]:
    """One batched query for a page of articles' hero images, not one query
    per article. Only the newest *generated* row per article counts — an
    older failed/superseded attempt for the same article must not win."""
    if not article_ids:
        return {}
    result = await db.execute(
        select(GeneratedMedia.article_id, GeneratedMedia.url, GeneratedMedia.generated_at)
        .where(GeneratedMedia.article_id.in_(article_ids))
        .where(GeneratedMedia.media_type == "hero")
        .where(GeneratedMedia.status == "generated")
        .order_by(GeneratedMedia.generated_at.desc())
    )
    hero_map: dict[str, str] = {}
    for article_id, url, _ in result.all():
        hero_map.setdefault(article_id, url)  # first hit per id = newest, thanks to the ORDER BY
    return hero_map

_WORDS_PER_MINUTE = 200

# Curated grouping of the real article_type values into the Library's
# filter-pill categories — every value here is one AIPE actually generates
# (see content_templates.py), not a hypothetical taxonomy.
_CATEGORY_TYPES: dict[str, list[str]] = {
    "market":        ["morning_intelligence", "market_wrap", "sector_intelligence", "historical_intelligence", "educational_intelligence"],
    "companies":      ["company_intelligence"],
    "events":         ["policy_intelligence", "ripple_intelligence", "breaking_intelligence", "question_intelligence"],
    "themes":         ["theme_intelligence"],
    "opportunities":  ["opportunity_intelligence"],
}

# Entity-ranking weights: a mention in the headline is a much stronger
# signal of "this is what the article is about" than one more mention
# buried in paragraph six.
_WEIGHT_HEADLINE = 10
_WEIGHT_OPENING = 5
_WEIGHT_BODY_MENTION = 1


def _rank_primary_entity(a: IntelligenceArticle) -> tuple[Optional[dict], list[dict]]:
    """
    Ranks companies_affected by real textual prominence — headline mention,
    then opening-paragraph mention, then repeat mentions through the body —
    rather than trusting extraction order (which reflects nothing about
    which company the article is actually about).

    Returns (primary_entity, secondary_entities). primary_entity is None for
    a pure macro/policy article with no companies attached — never forced.
    """
    companies = a.companies_affected or []
    if not companies:
        return None, []
    if len(companies) == 1:
        return companies[0], []

    headline = (a.headline or "").lower()
    opening = (a.executive_summary or a.why_it_matters or "")[:280].lower()
    body = " ".join(filter(None, [
        a.executive_summary, a.key_takeaway, a.why_it_matters, a.what_happened,
    ])).lower()

    def score(company: dict) -> int:
        full_name = company.get("name") or ""
        names = {n for n in (company.get("symbol"), full_name) if n}
        # Financial journalism almost never spells out the full registered
        # name or ticker in a headline ("Adani Stocks", not "Adani
        # Enterprises" or "ADANIENT") — match on the brand word too. Guarded
        # to 4+ chars so this doesn't match on generic short words like
        # "The" or "SBI"-style initialisms that could false-positive against
        # unrelated text.
        first_word = full_name.split()[0] if full_name else ""
        if len(first_word) >= 4:
            names.add(first_word)

        total = 0
        for name in names:
            needle = name.lower()
            if not needle:
                continue
            if needle in headline:
                total += _WEIGHT_HEADLINE
            if needle in opening:
                total += _WEIGHT_OPENING
            total += body.count(needle) * _WEIGHT_BODY_MENTION
        return total

    ranked = sorted(companies, key=score, reverse=True)
    return ranked[0], ranked[1:]


def _read_time_minutes(a: IntelligenceArticle) -> int:
    """Real word count across the article's own body fields, not a fabricated
    estimate — read_time is never invented, just derived from actual content
    already on the row (including fields _list_row doesn't otherwise expose)."""
    text = " ".join(filter(None, [
        a.executive_summary, a.key_takeaway, a.why_it_matters, a.what_happened,
    ]))
    words = len(text.split())
    return max(1, round(words / _WORDS_PER_MINUTE))


def _list_row(a: IntelligenceArticle, hero_image_url: str | None = None) -> dict:
    # Ranking runs against the article's own real headline/body text, so it
    # must see the original (unnormalized) symbols/names — normalization is
    # a display-time concern, applied to the entities only after ranking.
    primary_entity, secondary_entities = _rank_primary_entity(a)
    normalized_companies = _normalized_companies(a.companies_affected)
    primary_entity = _normalized_companies([primary_entity])[0] if primary_entity else None
    secondary_entities = _normalized_companies(secondary_entities)
    return {
        "id":                 a.id,
        "slug":               a.slug,
        "article_type":       a.article_type,
        "angle":              a.angle,
        "angle_entity":       a.angle_entity,
        "is_evergreen":       a.is_evergreen,
        "hero_image_url":     hero_image_url,
        "headline":           a.headline,
        "key_takeaway":       a.key_takeaway,
        "executive_summary":  a.executive_summary,
        "seo_title":          a.seo_title,
        "meta_description":   a.meta_description,
        "companies_affected": normalized_companies,
        "primary_entity":     primary_entity,
        "secondary_entities": secondary_entities,
        "sectors_affected":   a.sectors_affected,
        "confidence_score":   a.confidence_score,
        # SEO Intelligence (Phase 3, wired into the article surface as part
        # of the AI Newsroom redesign, 2026-08-10) — computed at publish
        # time by seo_intelligence.py and stored on the row; headline_angle
        # is translated through the legacy taxonomy map here so pre-redesign
        # articles (stored under the old 7-value taxonomy) read the same as
        # new ones without a data migration.
        "headline_angle":     resolve_headline_angle(a.headline_angle),
        "primary_keyword":    a.primary_keyword,
        # event_score is already the same real 0-100 relevance score the rest
        # of the app calls "impact_score" (Events, etc.) — aliased here for
        # naming consistency across the homepage's article and event cards.
        "impact_score":       a.event_score,
        "read_time_minutes":  _read_time_minutes(a),
        "views":              a.views,
        "share_count":        a.share_count,
        "update_count":       a.update_count,
        # SQLite reads DateTime(timezone=True) columns back tz-naive (see
        # get_verified_historical_events/tools.py for the same footgun) even
        # though every write path here uses datetime.now(timezone.utc) — so
        # a bare .isoformat() silently drops the UTC offset. Browsers then
        # parse that offset-less string as LOCAL time, not UTC, making
        # freshly published articles display with wildly wrong "Xh ago"
        # labels. Reattach the UTC tzinfo before serializing so every
        # consumer gets a real, unambiguous offset.
        "published_at":       a.published_at.replace(tzinfo=timezone.utc).isoformat() if a.published_at else None,
        "last_updated":       a.last_updated.replace(tzinfo=timezone.utc).isoformat() if a.last_updated else None,
        # Siblings (per-company/per-angle articles off the same underlying
        # event) share this ID — list consumers need it too, not just the
        # detail page, to merge siblings into one row instead of showing
        # near-duplicate rows per company.
        "parent_event_group_id": a.parent_event_group_id,
    }


def _detail_row(a: IntelligenceArticle, hero_image_url: str | None = None) -> dict:
    base = _list_row(a, hero_image_url)
    # internal_link_candidates was computed at publish time (see
    # publisher.py) — its company links are re-normalized here too, for the
    # same reason companies_affected is: articles published before
    # symbol_normalization.py existed still have raw/unresolved symbols
    # baked into the stored JSON, and this fixes them for every reader
    # without a data migration.
    raw_candidates = a.internal_link_candidates or []
    internal_link_candidates = [
        link for link in raw_candidates
        if link.get("type") != "company" or normalize_symbol(
            (link.get("href") or "").rsplit("/", 1)[-1], link.get("label"),
        )
    ]
    base.update({
        "why_it_matters":      a.why_it_matters,
        "what_happened":       a.what_happened,
        "opportunities":       a.opportunities,
        "risks":               a.risks,
        "historical_events":   a.historical_events,
        "ripple_effect":       a.ripple_effect,
        "what_to_watch_next":  a.what_to_watch_next,
        "faqs":                a.faqs,
        "sources":             a.sources,
        "internal_links":      a.internal_links,
        "related_companies":   _normalized_related_companies(a.related_companies),
        "related_themes":      a.related_themes,
        # SEO Intelligence (rest of the fields — headline_angle/primary_keyword
        # already surfaced in _list_row above since cards/list consumers use
        # those too; these four are only needed on the full article page).
        "secondary_keywords":       a.secondary_keywords,
        "entity_keywords":          a.entity_keywords,
        "question_keywords":        a.question_keywords,
        "internal_link_candidates": internal_link_candidates,
        "story_version":       a.story_version,
        "update_history":      a.update_history,
        "created_at":          a.created_at.replace(tzinfo=timezone.utc).isoformat() if a.created_at else None,
        "canonical_url":       a.canonical_url,
        "json_ld":             a.json_ld,
        # Generic structured-data slot — comparison_intelligence articles
        # (SEO Phase 2, §2.2 research pages) stash the full decision
        # comparison here (holding/target analysis, dimension table,
        # tradeoff) rather than adding new fixed columns for one article
        # type. Empty/None for every other article type.
        "market_context":      a.market_context,
        "related_articles":    [],  # filled in by get_insight() — needs a DB lookup
    })
    return base


@router.get("/")
async def list_insights(
    article_type: Optional[str] = Query(None),
    category:     Optional[str] = Query(None, description="market|companies|events|themes|opportunities — a curated group of article_types, for the Library's filter pills"),
    sort_by:      str           = Query("newest", pattern="^(newest|views|confidence)$"),
    limit:        int           = Query(20, le=100),
    offset:       int           = Query(0),
    db:           AsyncSession  = Depends(get_db),
):
    q = select(IntelligenceArticle).where(IntelligenceArticle.status == "published")
    cq = select(func.count()).select_from(IntelligenceArticle).where(IntelligenceArticle.status == "published")

    if article_type:
        q = q.where(IntelligenceArticle.article_type == article_type)
        cq = cq.where(IntelligenceArticle.article_type == article_type)
    elif category:
        types = _CATEGORY_TYPES.get(category, [])
        q = q.where(IntelligenceArticle.article_type.in_(types))
        cq = cq.where(IntelligenceArticle.article_type.in_(types))

    if sort_by == "views":
        q = q.order_by(IntelligenceArticle.views.desc(), IntelligenceArticle.published_at.desc())
    elif sort_by == "confidence":
        q = q.order_by(IntelligenceArticle.confidence_score.desc(), IntelligenceArticle.published_at.desc())
    else:
        q = q.order_by(IntelligenceArticle.published_at.desc())
    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    articles = result.scalars().all()
    total = (await db.execute(cq)).scalar() or 0
    hero_images = await _fetch_hero_images(db, [a.id for a in articles])

    return {
        "total":  total,
        "offset": offset,
        "limit":  limit,
        "items":  [_list_row(a, hero_images.get(a.id)) for a in articles],
    }


@router.get("/company/{symbol}")
async def get_company_insights(
    symbol: str,
    limit: int = Query(10, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Company Intelligence Hub feed: real AIPE articles mentioning this
    company (as a primary companies_affected entry or a related_companies
    cross-link) plus real historical_market_events coverage — backs the
    "Latest Intelligence" section on /companies/{symbol}, replacing what
    used to be hardcoded placeholder story cards there.
    """
    symbol = symbol.strip().upper()

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .order_by(IntelligenceArticle.published_at.desc())
        .limit(300)
    )
    all_articles = result.scalars().all()

    def _mentions(a: IntelligenceArticle) -> bool:
        for c in (a.companies_affected or []):
            if isinstance(c, dict) and str(c.get("symbol", "")).upper() == symbol:
                return True
        for c in (a.related_companies or []):
            if isinstance(c, dict) and str(c.get("symbol", "")).upper() == symbol:
                return True
        return False

    matched = [a for a in all_articles if _mentions(a)][:limit]
    group_ids = {a.parent_event_group_id for a in matched if a.parent_event_group_id}

    # P3.5: routed through the shared verified-outcome filter — this used
    # to query HistoricalMarketEvent directly with no outcome-data check,
    # so an auto-harvested same-day row tagged with this company would
    # show up as a "historical event" for it before any real outcome existed.
    from app.db.models.historical_memory import HistoricalMarketEvent
    from app.services.historical_memory_service import get_verified_historical_events
    from app.db.json_utils import json_array_contains
    # Was HistoricalMarketEvent.companies.contains([symbol]) — silently
    # broken on this deployment's SQLite database (see json_utils.py's
    # module docstring): confirmed live, returned 0 rows against 9 real
    # matches for a real symbol before this fix.
    historical = await get_verified_historical_events(
        db, extra_filters=[json_array_contains(HistoricalMarketEvent.companies, symbol)], limit=8,
    )
    hero_images = await _fetch_hero_images(db, [a.id for a in matched])

    return {
        "symbol": symbol,
        "articles": [_list_row(a, hero_images.get(a.id)) for a in matched],
        "campaign_count": len(group_ids),
        "historical_events": [
            {
                "event": h.event_title,
                "date": h.event_date.strftime("%b %Y") if h.event_date else None,
                "category": h.category,
                "outcome": h.nifty_1d,
                "key_lesson": h.key_lesson,
            }
            for h in historical
        ],
    }


@router.get("/comparisons")
async def get_comparisons(
    symbol: Optional[str] = Query(None, description="Return comparison_intelligence articles that include this company"),
    sector: Optional[str] = Query(None, description="Return comparison_intelligence articles tagged with this sector"),
    limit:  int           = Query(20, le=100),
    db:     AsyncSession  = Depends(get_db),
):
    """
    Real comparison_intelligence articles filtered by company or sector —
    backs the "Compare {symbol} With" section on company pages, the
    "Popular Comparisons" section on sector pages, and AI Search's related-
    research surfacing. All three want the same real, published-only query
    against comparison_publisher.py's output, just filtered differently —
    one endpoint, not three near-duplicate ones.

    Symbol filtering reuses get_company_insights' own scan-and-filter
    approach (companies_affected is JSON, not a column SQLite can index
    directly) — bounded to comparison_intelligence rows only, so even at
    hundreds of comparison pages this stays a cheap in-memory filter over
    a few hundred rows, not a full-table scan of every article type.
    """
    symbol_u = symbol.strip().upper() if symbol else None

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.article_type == "comparison_intelligence")
        .order_by(IntelligenceArticle.published_at.desc())
        .limit(500)
    )
    all_comparisons = result.scalars().all()

    def _matches(a: IntelligenceArticle) -> bool:
        if symbol_u:
            found = any(
                isinstance(c, dict) and str(c.get("symbol", "")).upper() == symbol_u
                for c in (a.companies_affected or [])
            )
            if not found:
                return False
        if sector:
            from app.api.sectors import _words_overlap
            sector_words = set(sector.lower().split())
            found = any(
                isinstance(s, dict) and s.get("name") and _words_overlap(sector_words, set(str(s["name"]).lower().split()))
                for s in (a.sectors_affected or [])
            )
            if not found:
                return False
        return True

    matched = [a for a in all_comparisons if _matches(a)][:limit]
    hero_images = await _fetch_hero_images(db, [a.id for a in matched])

    return {
        "symbol": symbol_u,
        "sector": sector,
        "items": [_list_row(a, hero_images.get(a.id)) for a in matched],
    }


@router.get("/stats")
async def insights_stats(db: AsyncSession = Depends(get_db)):
    """
    Real aggregate stats for the AI Newsroom's trust/freshness banner —
    every value is a live query, nothing precomputed or fabricated.
    """
    _IST = timezone(timedelta(hours=5, minutes=30))
    today_ist = datetime.now(_IST).replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = today_ist.astimezone(timezone.utc)
    published = IntelligenceArticle.status == "published"

    total = (await db.execute(select(func.count()).select_from(IntelligenceArticle).where(published))).scalar() or 0
    today = (await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(published).where(IntelligenceArticle.published_at >= today_utc)
    )).scalar() or 0
    week_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    this_week = (await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(published).where(IntelligenceArticle.published_at >= week_cutoff)
    )).scalar() or 0
    avg_confidence = (await db.execute(
        select(func.avg(IntelligenceArticle.confidence_score)).where(published)
    )).scalar()
    last_updated = (await db.execute(
        select(func.max(IntelligenceArticle.published_at)).where(published)
    )).scalar()
    events_covered = (await db.execute(
        select(func.count(func.distinct(IntelligenceArticle.trigger_event_id)))
        .where(published).where(IntelligenceArticle.trigger_event_id.isnot(None))
    )).scalar() or 0

    # Companies/sectors/themes covered — real distinct entities pulled from
    # the JSON columns of every published article, not a separate tracked
    # count that could drift from what's actually referenced.
    rows = (await db.execute(
        select(
            IntelligenceArticle.companies_affected,
            IntelligenceArticle.sectors_affected,
            IntelligenceArticle.related_themes,
        ).where(published)
    )).all()
    companies: set[str] = set()
    sectors: set[str] = set()
    themes: set[str] = set()
    for companies_affected, sectors_affected, related_themes in rows:
        for c in (companies_affected or []):
            sym = (c or {}).get("symbol") or (c or {}).get("name")
            if sym:
                companies.add(sym)
        for s in (sectors_affected or []):
            name = (s or {}).get("name")
            if name:
                sectors.add(name)
        for t in (related_themes or []):
            name = (t or {}).get("theme") or (t or {}).get("name")
            if name:
                themes.add(name)

    return {
        "total_articles":     total,
        "today_articles":     today,
        "this_week_articles": this_week,
        "companies_covered":  len(companies),
        "sectors_covered":    len(sectors),
        "events_covered":     events_covered,
        "themes_covered":     len(themes),
        "avg_confidence":     round(avg_confidence, 2) if avg_confidence is not None else None,
        "last_updated":       last_updated.replace(tzinfo=timezone.utc).isoformat() if last_updated else None,
    }


@router.get("/trending")
async def trending_today(limit: int = Query(4, le=20), db: AsyncSession = Depends(get_db)):
    """
    Real view-ranked articles from TODAY (IST calendar day, same convention
    as insights_stats' today_articles) — powers the Library's "Trending
    Today" rail. Deliberately a separate endpoint from sort_by=views on the
    generic list, which ranks across all time and was silently surfacing
    weeks-old high-view articles under a "Today" label (confirmed live:
    July articles topping a rail labeled "Trending Today").

    published_at reads back tz-naive from SQLite (see _list_row's comment),
    so the today-cutoff is applied in Python against a bounded recent
    fetch rather than pushed into a WHERE clause that would silently
    string-compare a tz-aware cutoff against a naive stored value.
    """
    _IST = timezone(timedelta(hours=5, minutes=30))
    today_ist = datetime.now(_IST).replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = today_ist.astimezone(timezone.utc)

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .order_by(IntelligenceArticle.published_at.desc())
        .limit(500)
    )
    recent = result.scalars().all()
    todays = [
        a for a in recent
        if a.published_at and a.published_at.replace(tzinfo=timezone.utc) >= today_utc
    ]
    todays.sort(key=lambda a: (a.views or 0), reverse=True)
    top = todays[:limit]
    hero_images = await _fetch_hero_images(db, [a.id for a in top])
    return {"items": [_list_row(a, hero_images.get(a.id)) for a in top]}


@router.get("/search")
async def search_insights(
    q:      str          = Query(..., min_length=2, max_length=200),
    limit:  int          = Query(20, le=50),
    db:     AsyncSession = Depends(get_db),
):
    """
    Real keyword search across published articles — headline, summary
    fields, and company/sector names (the JSON columns), via SQL LIKE.
    Not a ranked/fuzzy search engine; a real substring match over real
    content, which is what the search bar actually needs today.
    """
    like = f"%{q}%"
    text_match = (
        IntelligenceArticle.headline.ilike(like)
        | IntelligenceArticle.key_takeaway.ilike(like)
        | IntelligenceArticle.executive_summary.ilike(like)
        | IntelligenceArticle.seo_title.ilike(like)
    )
    # SQLite stores JSON columns as TEXT under the hood, so a plain LIKE
    # against the serialized column finds company/sector names inside the
    # JSON without needing a JSON-path function (which also wouldn't be
    # portable to the planned Postgres migration anyway).
    entity_match = (
        IntelligenceArticle.companies_affected.cast(String).ilike(like)
        | IntelligenceArticle.sectors_affected.cast(String).ilike(like)
        | IntelligenceArticle.related_themes.cast(String).ilike(like)
    )

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .where(text_match | entity_match)
        .order_by(IntelligenceArticle.published_at.desc())
        .limit(limit)
    )
    articles = result.scalars().all()
    hero_images = await _fetch_hero_images(db, [a.id for a in articles])
    return {"query": q, "total": len(articles), "items": [_list_row(a, hero_images.get(a.id)) for a in articles]}


@router.get("/{slug}")
async def get_insight(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.slug == slug)
        .where(IntelligenceArticle.status == "published")
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")

    hero_images = await _fetch_hero_images(db, [art.id])
    row = _detail_row(art, hero_images.get(art.id))

    # Other angles on the same underlying event (primary + per-company +
    # sector-rollup siblings) — only set on articles published after the
    # multi-angle fan-out shipped, so older articles simply have none.
    if art.parent_event_group_id:
        sib_result = await db.execute(
            select(IntelligenceArticle)
            .where(IntelligenceArticle.parent_event_group_id == art.parent_event_group_id)
            .where(IntelligenceArticle.id != art.id)
            .where(IntelligenceArticle.status == "published")
        )
        siblings = sib_result.scalars().all()
        row["related_articles"] = [
            {
                "slug": s.slug, "headline": s.headline, "angle": s.angle,
                "angle_entity": s.angle_entity, "article_type": s.article_type,
            }
            for s in siblings
        ]

    return row


@router.post("/{slug}/view")
async def record_view(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Record one engaged read. Called by the frontend after a reader has
    actually spent time with the article (not fired on page load — a bounce
    shouldn't count), so this is a real "people who read at least part of
    this" counter, not a raw hit counter.

    Deduped per visitor per article per day via Redis so reloading the same
    article doesn't inflate the count — returns counted=False (current
    count, unchanged) on a repeat within the window rather than erroring,
    since the caller doesn't need to treat that as a failure.
    """
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.slug == slug)
        .where(IntelligenceArticle.status == "published")
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")

    visitor_hash = hashlib.sha256(f"{get_remote_address(request)}:{slug}".encode()).hexdigest()[:16]
    dedup_key = f"article_view:{visitor_hash}"
    if await cache_get(dedup_key):
        return {"views": art.views, "counted": False}

    art.views += 1
    await db.commit()
    await cache_set(dedup_key, "1", ttl=86400)
    return {"views": art.views, "counted": True}


@router.post("/{slug}/share")
async def record_share(slug: str, db: AsyncSession = Depends(get_db)):
    """
    Record one share action — called each time a reader actually clicks a
    share channel or copies the link (not when the share popover merely
    opens). No dedup: unlike a view, sharing to three platforms in one
    visit is genuinely three shares, not an inflated count of one.
    """
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.slug == slug)
        .where(IntelligenceArticle.status == "published")
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")

    art.share_count += 1
    await db.commit()
    return {"share_count": art.share_count}
