"""
Continuous Update Engine — articles are living documents.

Every cycle (5 min), the updater checks published articles that:
  1. Were published in the current trading day
  2. Have a significant MIE story change (new mie_story_hash)
  3. Have new high-urgency triage events related to their sectors/companies

When an update is warranted, it regenerates the key_takeaway, why_it_matters,
and what_to_watch_next sections using fresh context, then appends an entry
to update_history.

Update tracking on each article:
  update_count  — incremented each time
  last_updated  — datetime of most recent update
  update_history — [{at: ISO, version: n, reason: str, summary: str}]
  lifecycle_status → "updated"
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle
from app.services.aipe.market_story_engine import get_mie_context, _story_hash
from app.services.aipe import perf_stats

log = structlog.get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))

# Only update articles published within this window
_UPDATE_WINDOW_HOURS = 12

# Minimum time between updates for the same article (avoid thrashing)
_MIN_UPDATE_GAP_MINUTES = 45

# A move at or beyond this magnitude on the article's own relevant index/
# sector — regardless of whether the MIE story-hash changed — is itself a
# reason to refresh ("Bank Nifty +2%" should update an RBI/banking article
# even if the overall market narrative text hasn't changed).
_MARKET_MOVE_THRESHOLD_PCT = 1.5

# A share is a stronger engagement signal than a view — a reader chose to
# hand this specific article to someone else. Same weighting used by
# comparison_scheduler.py's _sector_engagement_scores.
_SHARE_WEIGHT = 5

# A genuinely shared article that's gone this long without any update — even
# with zero market trigger today — is itself worth a freshness pass. Real
# reader engagement previously had no path into refresh *eligibility* at
# all (views only affected ordering among already-eligible candidates,
# below); share_count was collected (insights.py's /share endpoint) but
# never read by any engine decision anywhere in the pipeline.
_ENGAGEMENT_REFRESH_STALE_HOURS = 6


def _engagement_score(article: IntelligenceArticle) -> int:
    return (article.views or 0) + (article.share_count or 0) * _SHARE_WEIGHT


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite silently drops tzinfo on read even with DateTime(timezone=True)
    — same fix already applied in comparison_scheduler.py, needed here too
    since this module now does real Python-level datetime subtraction
    against last_updated/published_at for the engagement-staleness check
    below (previously this file only ever compared datetimes inside a SQL
    WHERE clause, which SQLAlchemy translates rather than subtracting in
    Python, so the naive/aware mismatch never surfaced here before)."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

# article sectors_affected name (lowercased, substring match) -> tracked
# sector-performance id from market_data_service.get_sector_performance()
_SECTOR_MOVE_MAP: dict[str, str] = {
    "bank": "Banking", "financial": "Banking", "nbfc": "Banking", "housing finance": "Banking",
    "it": "IT", "technology": "IT", "software": "IT",
    "pharma": "Pharma", "healthcare": "Pharma",
    "auto": "Auto",
    "energy": "Energy", "power": "Energy", "oil": "Energy",
    "fmcg": "FMCG", "consumer": "FMCG",
    "infra": "Infra", "infrastructure": "Infra", "capital goods": "Infra",
    "metal": "Metal", "mining": "Metal",
    "realty": "Realty", "real estate": "Realty",
}


async def get_market_moves() -> dict[str, float]:
    """
    Fetch today's % change for every tracked sector plus the broad Nifty 50
    index. Best-effort — returns {} on any provider error so a market-data
    hiccup never blocks the (still-valid) story-hash-based update path.
    """
    try:
        from app.services.market_data_service import market_data_service
        sectors, indices = await asyncio.gather(
            market_data_service.get_sector_performance(),
            market_data_service.get_indices(),
            return_exceptions=True,
        )
        moves: dict[str, float] = {}
        if isinstance(sectors, list):
            for s in sectors:
                moves[s.name] = s.change_percent
        if isinstance(indices, list):
            for i in indices:
                if i.name == "NIFTY 50":
                    moves["NIFTY 50"] = i.change_percent
        return moves
    except Exception as exc:
        log.warning("continuous_updater.market_moves_fetch_failed", error=str(exc))
        return {}


def _relevant_market_move(article: IntelligenceArticle, moves: dict[str, float]) -> tuple[bool, str | None]:
    """Does this article's own sector/the broad market move enough today to justify a refresh?"""
    if not moves:
        return False, None
    sector_names = [
        str(s.get("name", "")) if isinstance(s, dict) else str(s)
        for s in (article.sectors_affected or [])
    ]
    for sector_name in sector_names:
        low = sector_name.lower()
        for kw, tracked_name in _SECTOR_MOVE_MAP.items():
            if kw in low and tracked_name in moves:
                pct = moves[tracked_name]
                if abs(pct) >= _MARKET_MOVE_THRESHOLD_PCT:
                    return True, f"{tracked_name} moved {pct:+.1f}% today"
    nifty = moves.get("NIFTY 50")
    if nifty is not None and abs(nifty) >= _MARKET_MOVE_THRESHOLD_PCT:
        return True, f"Nifty 50 moved {nifty:+.1f}% today"
    return False, None


# Real shares mostly accumulate well after the first 12h — bounding the
# engagement-refresh path to _UPDATE_WINDOW_HOURS would make it almost
# always redundant with the market-triggered path above (confirmed while
# testing this: the one real article in the local DB with share_count > 0
# was 172h old, entirely outside the 12h window). This window is separate
# and much wider so genuine engagement can matter independent of how
# recently the article was first published.
_ENGAGEMENT_WINDOW_DAYS = 30


async def find_updatable_articles(
    db: AsyncSession,
    current_mie_hash: str,
    market_moves: dict[str, float] | None = None,
) -> list[tuple[IntelligenceArticle, str | None]]:
    """
    Return (article, reason) pairs for published articles that should
    receive an update — because the MIE story-hash changed, because the
    article's own relevant sector/the broad market moved beyond
    _MARKET_MOVE_THRESHOLD_PCT today (both within _UPDATE_WINDOW_HOURS of
    first publish), or because a genuinely shared article has gone stale
    (within the wider _ENGAGEMENT_WINDOW_DAYS, independent of the market).
    reason is None only for the story-hash-only trigger.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=_UPDATE_WINDOW_HOURS)
    min_gap = now - timedelta(minutes=_MIN_UPDATE_GAP_MINUTES)

    # Evergreen articles (comparisons, educational explainers) are about a
    # timeless topic, not today's market — this updater's whole output is
    # built from mie_context's CURRENT global mood/top-urgency-event (see
    # _generate_updated_takeaway below), which has no connection to e.g. an
    # ITC-vs-HUL comparison's own topic. Without this exclusion, any
    # evergreen article republished/refreshed within the window became
    # "eligible" purely because the market's story-hash moved on, and had
    # its key_takeaway overwritten with unrelated content — confirmed live
    # (an ITC-vs-HUL comparison page showing a Cholamandalam Finance
    # takeaway). Comparisons already have their own dedicated staleness-
    # aware refresh (comparison_scheduler.py, 14-day cycle). Shared by both
    # queries below.
    base_query = (
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.lifecycle_status.notin_(["archived", "merged"]))
        .where(IntelligenceArticle.is_evergreen.isnot(True))
        .where(
            (IntelligenceArticle.last_updated == None) |  # noqa: E711
            (IntelligenceArticle.last_updated <= min_gap)
        )
    )

    market_result = await db.execute(
        base_query.where(IntelligenceArticle.published_at >= cutoff)
        .order_by(IntelligenceArticle.published_at.asc())
    )
    articles = market_result.scalars().all()

    out: list[tuple[IntelligenceArticle, str | None]] = []
    seen_ids: set[str] = set()
    for a in articles:
        if a.mie_story_hash != current_mie_hash:
            out.append((a, None))
            seen_ids.add(a.id)
            continue
        moved, reason = _relevant_market_move(a, market_moves or {})
        if moved:
            out.append((a, reason))
            seen_ids.add(a.id)

    # Engagement-driven path — genuinely shared articles, independent of
    # the 12h market window and of today's market-hash/move triggers.
    engagement_cutoff = now - timedelta(days=_ENGAGEMENT_WINDOW_DAYS)
    engagement_result = await db.execute(
        base_query
        .where(IntelligenceArticle.published_at >= engagement_cutoff)
        .where(IntelligenceArticle.share_count >= 1)
        .order_by(IntelligenceArticle.share_count.desc())
        .limit(20)
    )
    for a in engagement_result.scalars().all():
        if a.id in seen_ids:
            continue
        anchor = _aware(a.last_updated) or _aware(a.published_at) or now
        stale_hours = (now - anchor).total_seconds() / 3600
        if stale_hours >= _ENGAGEMENT_REFRESH_STALE_HOURS:
            out.append((a, f"{a.share_count} share(s) on a stale article — refreshing for a genuinely engaged reader base"))
            seen_ids.add(a.id)
    return out


async def update_article(
    db: AsyncSession,
    article: IntelligenceArticle,
    mie_context: dict[str, Any],
    new_triage_events: list[dict[str, Any]],
    market_move_reason: str | None = None,
) -> bool:
    """
    Update an article's dynamic sections with fresh market context.
    Returns True if updated, False if skipped.
    """
    now = datetime.now(timezone.utc)
    new_version = article.story_version + 1

    # Build update reason
    reasons = []
    if market_move_reason:
        reasons.append(market_move_reason)
    if mie_context.get("story"):
        reasons.append(f"Market narrative updated: {mie_context['mood']}")
    if new_triage_events:
        high = [e for e in new_triage_events if e.get("urgency", 0) >= 7]
        if high:
            reasons.append(f"{len(high)} high-urgency development(s)")
    if not reasons:
        return False

    update_reason = " | ".join(reasons)
    _update_start = time.monotonic()

    # Regenerate dynamic sections
    new_takeaway = _generate_updated_takeaway(article, mie_context, new_triage_events)
    new_watch_next = _generate_watch_next(mie_context, new_triage_events)

    # Update history entry — captures a before/after AI-opinion snapshot
    # (not just the reason) so the frontend can show "Original AI Opinion ->
    # Current AI Opinion" evolution, not just a changelog of reasons.
    history_entry = {
        "at":               now.isoformat(),
        "version":          new_version,
        "reason":           update_reason,
        # P0-CD2: was f"Updated: {mie_context['mood']}" — the frontend
        # falls back to rendering this exact field as the article's "new"
        # AI opinion whenever new_takeaway is unavailable, so it inherited
        # the same global-mood contamination new_takeaway just got fixed
        # for. update_reason (already article-scoped: market move / new
        # triage overlap / story-hash change) is the honest description of
        # what happened this cycle.
        "summary":          update_reason,
        "previous_takeaway": article.key_takeaway,
        "new_takeaway":      new_takeaway or article.key_takeaway,
        "confidence":        article.confidence_score,
    }

    current_history = article.update_history or []
    updated_history = current_history + [history_entry]

    # Apply updates
    article.key_takeaway     = new_takeaway or article.key_takeaway
    article.what_to_watch_next = new_watch_next or article.what_to_watch_next
    article.story_version    = new_version
    article.update_count     = (article.update_count or 0) + 1
    article.update_history   = updated_history
    article.last_updated     = now
    article.mie_story_hash   = mie_context.get("story_hash")
    article.lifecycle_status = "updated"
    article.touch_json_ld_modified(now)

    # Replace (not append) the update note on why_it_matters. The old dedup
    # check (`update_note[:50] not in current`) always included the fresh
    # timestamp in those 50 chars, so it never actually matched — confirmed
    # live: one article accumulated 34 stacked "**Update HH:MM AM IST:**"
    # blocks (8.7KB, many near-identical) across 35 update cycles. Splitting
    # on the first delimiter keeps the original base explanation and swaps
    # in only the single latest update note each time.
    #
    # P0-CD2 (2026-09-01): this used to fire on bare `mie_context.get(
    # "story")` — true on essentially every cycle, since the MIE always has
    # SOME current global narrative — stamping that raw global text into
    # why_it_matters for every touched article regardless of whether this
    # article had anything to do with it. Same contamination class as the
    # key_takeaway fix above (new_triage_events is now pre-filtered to this
    # article's own overlap by the caller, run_continuous_update_cycle;
    # market_move_reason is inherently article-scoped too — mie_context
    # ["story"] alone is not). Gated the same way: only a genuine
    # article-relevant trigger earns an update note.
    if market_move_reason or new_triage_events:
        # Prefer the actual article-relevant event's own content over the
        # global market story — falls back to the global story only for a
        # pure market_move_reason trigger, where the move itself already IS
        # this article's own sector/price, so the broader narrative is
        # legitimate context, not contamination.
        if new_triage_events:
            top_event = sorted(new_triage_events, key=lambda e: e.get("urgency", 0), reverse=True)[0]
            note_text = top_event.get("one_liner") or mie_context.get("story", update_reason)
        else:
            note_text = market_move_reason or mie_context.get("story", update_reason)
        update_note = f"\n\n**Update {now.strftime('%I:%M %p IST')}:** {note_text}"
        base = (article.why_it_matters or "").split("\n\n**Update ", 1)[0]
        article.why_it_matters = base + update_note

    db.add(article)
    await db.commit()
    perf_stats.record("update", time.monotonic() - _update_start)

    log.info(
        "continuous_updater.updated",
        article_id=article.id,
        version=new_version,
        reason=update_reason,
    )
    return True


def _generate_updated_takeaway(
    article: IntelligenceArticle,
    mie_context: dict[str, Any],
    new_events: list[dict[str, Any]],
) -> str | None:
    """Generate a fresh key takeaway from developments genuinely connected
    to THIS article's own subject — never from the global market mood/
    opportunity/risk narrative.

    P0-CD2 Generation Containment (2026-09-01): this used to blend
    mie_context's mood/opportunity/risk/investor_watch — the CURRENT
    GLOBAL market narrative, identical for every article being updated in
    the same cycle — directly into key_takeaway, with no connection to
    whatever this specific article is actually about. Confirmed live: a
    company-specific article (Ambuja) acquired an unrelated global "Nifty
    swing-buy" opportunity string as its own takeaway, and (a related,
    already-partially-fixed case) an ITC-vs-HUL comparison showed a
    Cholamandalam Finance takeaway. `new_events` is now pre-filtered by the
    caller (run_continuous_update_cycle) to only the events that actually
    overlap this article's own sectors/companies — see that function's own
    comment — so the single remaining source here is genuinely
    article-specific. No article-relevant development this cycle means no
    grounded takeaway can be produced: return None and leave the existing
    key_takeaway in place (update_article already does `new_takeaway or
    article.key_takeaway`), rather than manufacturing one from global
    narrative that has nothing to do with this article's subject.
    """
    if not new_events:
        return None
    top = sorted(new_events, key=lambda e: e.get("urgency", 0), reverse=True)[0]
    one_liner = top.get("one_liner")
    return f"LATEST: {one_liner}"[:400] if one_liner else None


def _generate_watch_next(
    mie_context: dict[str, Any],
    new_events: list[dict[str, Any]],
) -> list[str] | None:
    """Generate updated watch-next items."""
    items = []

    if mie_context.get("investor_watch"):
        items.append(mie_context["investor_watch"])
    if mie_context.get("trader_watch"):
        items.append(mie_context["trader_watch"])

    for ev in new_events[:2]:
        if ev.get("one_liner"):
            items.append(ev["one_liner"])

    return items[:5] if items else None


async def run_continuous_update_cycle(
    db: AsyncSession,
    mie_context: dict[str, Any],
    new_triage_events: list[dict[str, Any]],
) -> int:
    """
    Run the update cycle. Returns number of articles updated.
    """
    current_hash = mie_context.get("story_hash", "")
    if not current_hash:
        return 0

    _cycle_start = time.monotonic()
    try:
        market_moves = await get_market_moves()
        candidates = await find_updatable_articles(db, current_hash, market_moves)
    except Exception as exc:
        perf_stats.mark_engine_run("Continuous Updater", success=False, error=str(exc)[:200], duration_s=time.monotonic() - _cycle_start)
        raise
    if not candidates:
        perf_stats.mark_engine_run("Continuous Updater", success=True, duration_s=time.monotonic() - _cycle_start)
        return 0

    updated = 0
    # Only update articles related to the new events' sectors/tickers
    # (market-move-triggered candidates skip this check — the move itself
    # is already a sector-specific relevance signal).
    relevant_sectors = set()
    relevant_tickers = set()
    for ev in new_triage_events:
        relevant_sectors.update(ev.get("sectors") or [])
        relevant_tickers.update(ev.get("tickers") or [])

    # Real user behavior now factors into WHICH eligible articles get one
    # of the cycle's 3 update slots, not just market intelligence — the
    # roadmap's Stage 5 "Learning Engine" ask. Eligibility itself is mostly
    # unchanged (still find_updatable_articles' market-driven criteria, plus
    # the engagement-staleness path above); this reorders among already-
    # eligible candidates by combined views+shares so a genuinely popular
    # or shared article gets refreshed before an equally-eligible but
    # rarely-read one, when there isn't capacity for both. Same reasoning
    # and same real-data source as comparison_scheduler.py's sector-priority
    # ordering.
    candidates = sorted(candidates, key=lambda pair: _engagement_score(pair[0]), reverse=True)

    for article, market_move_reason in candidates[:3]:  # Cap at 3 updates per cycle
        art_sectors = {s.get("name", s) if isinstance(s, dict) else s
                       for s in (article.sectors_affected or [])}
        art_companies = {c.get("symbol", c) if isinstance(c, dict) else c
                         for c in (article.companies_affected or [])}

        sector_overlap = relevant_sectors & art_sectors
        company_overlap = relevant_tickers & art_companies

        # P0-CD2 (2026-09-01): an article used to become "eligible" purely
        # because mie_context's story_hash moved on (this OR branch, last),
        # with zero sector/company overlap required — and once eligible,
        # got the FULL, unfiltered new_triage_events list passed through,
        # so _generate_updated_takeaway's "top urgency event" pick could be
        # about a completely different company/sector than this article's
        # own subject. Filtering to this article's own overlap here means
        # a story-hash-only trigger (no real overlap) correctly passes an
        # empty event list through — _generate_updated_takeaway already
        # returns None for that, which is the honest "no article-specific
        # development this cycle" answer, not a manufactured one.
        article_relevant_events = [
            ev for ev in new_triage_events
            if (set(ev.get("sectors") or []) & art_sectors) or (set(ev.get("tickers") or []) & art_companies)
        ]

        if market_move_reason or sector_overlap or company_overlap or mie_context.get("story_hash") != article.mie_story_hash:
            ok = await update_article(db, article, mie_context, article_relevant_events, market_move_reason)
            if ok:
                updated += 1

    perf_stats.mark_engine_run("Continuous Updater", success=True, duration_s=time.monotonic() - _cycle_start)
    return updated
