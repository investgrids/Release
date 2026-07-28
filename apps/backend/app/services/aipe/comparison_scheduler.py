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


def _sector_derived_pairs() -> list[tuple[str, str]]:
    """Every large-cap pair within each real NSE sector — the systematic
    path to hundreds of pages without hand-listing them. Capped at the top
    6 large-cap names per sector (C(6,2)=15 pairs max/sector) so one huge
    sector (e.g. Banking) doesn't dominate the whole pool with low-intent
    pairings between minor names."""
    from app.api.companies import _NSE_UNIVERSE

    by_sector: dict[str, list[str]] = {}
    for co in _NSE_UNIVERSE:
        if co.get("cap") != "large":
            continue
        by_sector.setdefault(co["sector"], []).append(co["symbol"])

    pairs: list[tuple[str, str]] = []
    for symbols in by_sector.values():
        top = sorted(symbols)[:6]
        pairs.extend(combinations(top, 2))
    return pairs


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

            candidates = _CURATED_PAIRS + _sector_derived_pairs()
            now = datetime.now(timezone.utc)

            for sym_a, sym_b in candidates:
                if published_this_cycle >= _MAX_PER_CYCLE:
                    break
                slug = f"{_slugify(sym_a)}-vs-{_slugify(sym_b)}"
                article = existing_by_slug.get(slug)

                if article:
                    age = now - (article.last_updated or article.published_at or now)
                    if age < timedelta(days=_STALE_AFTER_DAYS):
                        continue
                    fresh = await _has_fresh_event_since(db, sym_a, article.last_updated or now) \
                        or await _has_fresh_event_since(db, sym_b, article.last_updated or now)
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
