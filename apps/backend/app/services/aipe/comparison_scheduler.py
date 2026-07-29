"""
Comparison pages — automated scaling + freshness (SEO roadmap, Priority 1:
"Publish 500-1,000 comparison pages... maintained through a database table,
not by creating files").

This is the scheduled companion to comparison_publisher.py (which does the
actual generate+quality-gate+upsert work, unchanged here). This module only
answers two questions, matched to the recommended architecture:

  1. WHICH pairs get a page? — a curated high-intent seed list (the exact
     examples given: HAL vs BEL, TCS vs Infosys, etc.) plus a real,
     programmatically-derived pool: every large-cap pair within each real
     NSE sector in _NSE_UNIVERSE. This is how the count grows toward
     hundreds without hand-maintaining a list that size — the sector
     groupings and cap tier are real data, not guessed pairings.
  2. WHEN does a page regenerate? — never on a fixed calendar alone. A
     published comparison is only a candidate for regeneration once it's
     older than _STALE_AFTER_DAYS AND at least one of the two companies
     has had a real, meaningfully-urgent event since the article's own
     last_updated (checked against EventTriage.tickers). No new event for
     either company just means yesterday's real analysis is still today's
     real analysis — regenerating it would just burn an LLM call to
     reproduce the same content with drift risk, not actually refresh
     anything.

Rate-limited on purpose: _MAX_PER_CYCLE caps how many pairs this
attempts per run (matches the AIPE evergreen/historical cycles' own
per-day caps) — comparison_publisher.py's own retry logic already takes
several minutes per pair under the free-tier LLM provider chain's real
rate limits (observed live this session), so a cycle that tried all
pending pairs at once would just queue up timeouts, not publish faster.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from itertools import combinations

import structlog
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.models.intelligence import EventTriage
from app.services.aipe.comparison_publisher import publish_comparison_article, _slugify

log = structlog.get_logger(__name__)

_MAX_PER_CYCLE = 5
_STALE_AFTER_DAYS = 14
_MIN_EVENT_URGENCY = 6

# The user's own explicit high-intent examples — tried first, every cycle,
# ahead of the sector-derived pool below.
_CURATED_PAIRS: list[tuple[str, str]] = [
    ("HAL", "BEL"), ("BEL", "BDL"), ("TCS", "INFY"), ("INFY", "WIPRO"),
    ("HDFCBANK", "ICICIBANK"), ("TITAN", "KALYANKJIL"), ("TATAMOTORS", "M&M"),
    ("SUNPHARMA", "CIPLA"),
]


def _sector_derived_pairs(sector_priority: dict[str, int] | None = None) -> list[tuple[str, str]]:
    """Every large-cap pair within each real NSE sector — the systematic
    path to hundreds of pages without hand-listing them. Capped at the top
    6 large-cap names per sector (C(6,2)=15 pairs max/sector) so one huge
    sector (e.g. Banking) doesn't dominate the whole pool with low-intent
    pairings between minor names.

    sector_priority (real total views, see _sector_engagement_scores)
    reorders which sector's pairs get tried FIRST when _MAX_PER_CYCLE caps
    how many this cycle can reach — the traffic-feedback piece the SEO
    audit's roadmap named (views/share_count collected but never read by
    any generation/scheduling code). Sectors with no signal yet keep their
    original relative order (Python's sort is stable), so a brand-new
    sector is never starved, just not artificially prioritized either."""
    from app.api.companies import _NSE_UNIVERSE

    by_sector: dict[str, list[str]] = {}
    for co in _NSE_UNIVERSE:
        if co.get("cap") != "large":
            continue
        by_sector.setdefault(co["sector"], []).append(co["symbol"])

    sector_names = list(by_sector.keys())
    if sector_priority:
        sector_names.sort(key=lambda s: sector_priority.get(s, 0), reverse=True)

    pairs: list[tuple[str, str]] = []
    for sector in sector_names:
        top = sorted(by_sector[sector])[:6]
        pairs.extend(combinations(top, 2))
    return pairs


async def _sector_engagement_scores(db) -> dict[str, int]:
    """Real per-sector total views, the concrete traffic-feedback signal
    for _sector_derived_pairs above. Aggregated through each article's real
    companies_affected symbols -> _sector_for(symbol) (the same NSE_UNIVERSE
    lookup _sector_derived_pairs itself groups companies by), NOT through
    articles' own sectors_affected free-text tags — confirmed live that
    those two vocabularies disagree (AI-authored tags like "IT", "Pharma",
    "Auto & EV" vs. NSE_UNIVERSE's "Technology", "Pharmaceuticals",
    "Automotive"), which silently zeroed out most of the real signal before
    this fix. Same category of accuracy bug already caught once this
    session on the Best Stocks pages — worth the extra join here too rather
    than shipping a feedback loop that mostly measures name-matching luck."""
    from sqlalchemy import select
    from app.db.models.intelligence_article import IntelligenceArticle

    rows = (await db.execute(
        select(IntelligenceArticle.companies_affected, IntelligenceArticle.views)
        .where(IntelligenceArticle.status == "published")
    )).all()
    scores: dict[str, int] = {}
    for companies_affected, views in rows:
        seen_sectors_this_row: set[str] = set()
        for c in (companies_affected or []):
            symbol = (c.get("symbol") if isinstance(c, dict) else None) or ""
            if not symbol:
                continue
            sector = _sector_for(symbol.upper())
            # Count each sector once per article even if it names several
            # of that sector's companies — this measures "how many views
            # has content about this sector gotten," not "how many company
            # mentions," which would double/triple count multi-company
            # roundup articles.
            if sector and sector not in seen_sectors_this_row:
                scores[sector] = scores.get(sector, 0) + (views or 0)
                seen_sectors_this_row.add(sector)
    return scores


def _name_for(symbol: str) -> str:
    from app.api.companies import _NSE_UNIVERSE
    for co in _NSE_UNIVERSE:
        if co["symbol"] == symbol:
            return co["name"]
    return symbol


def _sector_for(symbol: str) -> str | None:
    from app.api.companies import _NSE_UNIVERSE
    for co in _NSE_UNIVERSE:
        if co["symbol"] == symbol:
            return co["sector"]
    return None


async def _has_fresh_event_since(db, symbol: str, since: datetime) -> bool:
    rows = (await db.execute(
        select(EventTriage.id)
        .where(EventTriage.triaged_at > since)
        .where(EventTriage.urgency >= _MIN_EVENT_URGENCY)
        .limit(200)
    )).all()
    if not rows:
        return False
    tag = f"NSE:{symbol}"
    matched = (await db.execute(
        select(EventTriage.id)
        .where(EventTriage.triaged_at > since)
        .where(EventTriage.urgency >= _MIN_EVENT_URGENCY)
        .where(EventTriage.tickers.contains([tag]))
        .limit(1)
    )).first()
    return matched is not None


def _aware(dt: datetime | None) -> datetime | None:
    """SQLAlchemy's DateTime(timezone=True) is honored by Postgres but
    SQLite (this app's actual DATABASE_URL — see config) silently drops
    tzinfo on read regardless of the column declaration, returning a naive
    datetime. `now - article.last_updated` below then raises "can't
    subtract offset-naive and offset-aware datetimes" — confirmed live:
    this crashed the comparison cycle on its very first loop iteration
    every single run (hal-vs-bel, the first curated pair, already existed
    from an earlier publish, so the age check below was always reached
    immediately and always raised, aborting the entire cycle via the outer
    try/except before it ever got to attempt a single new pair). This is
    the actual root cause of "only 4 comparisons ever published" — not a
    quality-gate or rate-limit issue."""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


async def run_comparison_cycle() -> None:
    """Scheduled job (see scheduler.py) — publishes/refreshes up to
    _MAX_PER_CYCLE comparison pairs per run. Every actual generation still
    goes through comparison_publisher.py's own retry+quality-gate; this
    function only decides which pairs are due and never force-publishes a
    degraded result (publish_comparison_article already returns None on
    failure, in which case the existing published article — if any — is
    left exactly as it was)."""
    _cycle_start = time.monotonic()
    published_this_cycle = 0
    try:
        async with AsyncSessionLocal() as db:
            existing = (await db.execute(
                select(IntelligenceArticle)
                .where(IntelligenceArticle.article_type == "comparison_intelligence")
            )).scalars().all()
            existing_by_slug = {a.slug: a for a in existing}

            sector_priority = await _sector_engagement_scores(db)
            if sector_priority:
                top5 = sorted(sector_priority.items(), key=lambda x: -x[1])[:5]
                log.info("comparison_cycle.sector_priority", top_sectors=top5)
            candidates = _CURATED_PAIRS + _sector_derived_pairs(sector_priority)
            now = datetime.now(timezone.utc)

            for sym_a, sym_b in candidates:
                if published_this_cycle >= _MAX_PER_CYCLE:
                    break
                slug = f"{_slugify(sym_a)}-vs-{_slugify(sym_b)}"
                article = existing_by_slug.get(slug)

                if article:
                    anchor = _aware(article.last_updated) or _aware(article.published_at) or now
                    age = now - anchor
                    if age < timedelta(days=_STALE_AFTER_DAYS):
                        continue
                    fresh = await _has_fresh_event_since(db, sym_a, anchor) \
                        or await _has_fresh_event_since(db, sym_b, anchor)
                    if not fresh:
                        continue  # old enough to refresh, but nothing new to say

                sector = _sector_for(sym_a) or _sector_for(sym_b)
                result = await publish_comparison_article(
                    db, sym_a, sym_b, _name_for(sym_a), _name_for(sym_b), sector=sector,
                )
                if result:
                    published_this_cycle += 1
                    log.info("comparison_cycle.published", slug=result["slug"], is_refresh=bool(article))
                else:
                    log.info("comparison_cycle.quality_gate_skip", pair=f"{sym_a}-{sym_b}")

        log.info("comparison_cycle.done", published=published_this_cycle,
                  duration_s=round(time.monotonic() - _cycle_start, 1))
    except Exception as exc:
        log.error("comparison_cycle.failed", exc=str(exc)[:300])
