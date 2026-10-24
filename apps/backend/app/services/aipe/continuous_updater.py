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


# ── Event scope (Workstream B, 2026-10-24) ───────────────────────────────────
# The CD2 overlap filter (run cycle, below) lets an event update an article when
# their sectors OR tickers intersect. That correctly blocks an unrelated single
# company's event, but a market-wide development tagged with broad sectors (or an
# index ticker) legitimately overlaps many articles' sectors — so the single
# highest-urgency such event was stamped, identically, as the "LATEST:" takeaway
# of dozens of unrelated company/question/theme/sector/ripple articles (confirmed
# live: 93 cross-type duplicate-takeaway groups / 425 articles published on/after
# the 2026-09-01 CD2 fix; newest 2026-10-07). Scope classification here is
# deliberately CONSERVATIVE and metadata-only — it never keyword-sniffs a
# headline (so "RBI"/"crude" in text does not by itself make an event macro).
# Market-wide requires an explicit signal: a known index ticker, the event's own
# is_structural flag, or breadth across several distinct sectors with no single-
# company subject. A broad single-sector tag alone does NOT make an event
# market-wide (safeguard 1).
_INDEX_TICKERS = {
    "NIFTY", "NIFTY50", "NIFTYBANK", "BANKNIFTY", "SENSEX", "FINNIFTY",
    "NIFTYIT", "NIFTYMIDCAP", "NIFTYNEXT50", "NIFTY500", "NIFTYFMCG",
    "NIFTYAUTO", "NIFTYPHARMA", "NIFTYMETAL", "NIFTYREALTY", "NIFTYENERGY",
    "INDIAVIX", "GIFTNIFTY", "SGXNIFTY", "BANKEX",
}

# An event carrying no single-company ticker but spanning at least this many
# distinct sectors is treated as market-wide (documented deterministic fallback).
_MARKET_WIDE_SECTOR_COUNT = 3


def _norm_sym(x: Any) -> str:
    return str(x).strip().upper()


def _compact_sym(x: Any) -> str:
    return _norm_sym(x).replace(" ", "").replace("-", "").replace("_", "").replace(".", "")


_INDEX_COMPACT = {_compact_sym(t) for t in _INDEX_TICKERS}


def _event_tickers(ev: dict[str, Any]) -> set[str]:
    return {_norm_sym(t) for t in (ev.get("tickers") or []) if t}


def _event_sectors(ev: dict[str, Any]) -> set[str]:
    return {_norm_sym(s) for s in (ev.get("sectors") or []) if s}


def _article_companies(article: IntelligenceArticle) -> set[str]:
    return {
        _norm_sym(c.get("symbol", c) if isinstance(c, dict) else c)
        for c in (article.companies_affected or []) if c
    }


def _article_sectors(article: IntelligenceArticle) -> set[str]:
    return {
        _norm_sym(s.get("name", s) if isinstance(s, dict) else s)
        for s in (article.sectors_affected or []) if s
    }


def _event_scope(ev: dict[str, Any]) -> str:
    """Deterministic, metadata-only event scope. One of:
      "entity"      — carries a specific (non-index) company ticker
      "market_wide" — only an index ticker, is_structural, or >= N sectors
      "sector"      — one or two sector tags, no specific ticker
      "unscoped"    — no sectors and no tickers
    A specific company ticker always wins (an event about a named company that
    also tags Nifty is entity-scoped, not market-wide), so legitimate company
    updates are never suppressed (safeguard 3)."""
    compact = {_compact_sym(t) for t in (ev.get("tickers") or []) if t}
    specific = compact - _INDEX_COMPACT
    if specific:
        return "entity"
    sectors = ev.get("sectors") or []
    if (compact & _INDEX_COMPACT) or ev.get("is_structural") or len(sectors) >= _MARKET_WIDE_SECTOR_COUNT:
        return "market_wide"
    if sectors:
        return "sector"
    return "unscoped"


def _event_sets_takeaway(ev: dict[str, Any], article: IntelligenceArticle) -> bool:
    """Whether `ev` is scope-eligible to SET this article's own takeaway / update
    note — a stricter gate than the caller's membership filter. An entity-level
    article needs a real company-ticker overlap; a bare sector overlap is not
    enough. A pure sector/theme article (no specific companies) may take a
    narrowly sector-scoped event. A market-wide or unscoped event never becomes a
    specific article's own takeaway here — the cross-type contamination this
    closes. (A dedicated market-wide article type that should carry a market-wide
    takeaway is a documented follow-up, not handled here.)"""
    scope = _event_scope(ev)
    if scope == "entity":
        return bool(_event_tickers(ev) & _article_companies(article))
    if scope == "sector":
        return (not _article_companies(article)) and bool(_event_sectors(ev) & _article_sectors(article))
    if scope == "unscoped":
        # No sector/ticker metadata at all: not provable evidence of a
        # market-wide development, and in the live pipeline such an event never
        # reaches here anyway (the caller's overlap filter requires a real
        # sector/ticker intersection). Allow it rather than suppress a possibly
        # legitimate update; only an explicitly market-wide event is blocked.
        return True
    return False  # market_wide


def _select_takeaway_event(
    article: IntelligenceArticle | None,
    new_events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Pick the single event that may set this article's takeaway / update note:
    the highest-urgency candidate that is both (a) genuinely AI-sourced — not a
    rule_based_fallback/unknown raw headline (2026-10-19 provenance contract) —
    and (b) scope-eligible for this article (Workstream B). Returns None when no
    such event exists, so the caller leaves the existing takeaway untouched
    rather than manufacturing one. `article is None` keeps the legacy pure-
    function behavior (provenance filter only, no scope restriction)."""
    if not new_events:
        return None
    candidates = sorted(new_events, key=lambda e: e.get("urgency", 0), reverse=True)
    candidates = [e for e in candidates if e.get("triage_source") not in ("rule_based_fallback", "unknown")]
    if article is not None:
        candidates = [e for e in candidates if _event_sets_takeaway(e, article)]
    return candidates[0] if candidates else None


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

    # Regenerate dynamic sections. A single scope- and provenance-eligible event
    # (if any) drives BOTH the takeaway and the why_it_matters update note, so a
    # market-wide development cannot become this specific article's own takeaway
    # via a bare sector overlap (Workstream B, 2026-10-24).
    chosen_event = _select_takeaway_event(article, new_triage_events)
    new_takeaway = None
    if chosen_event and chosen_event.get("one_liner"):
        new_takeaway = f"LATEST: {chosen_event['one_liner']}"[:400]
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
        # Workstream B provenance (2026-10-24): which event (if any) set this
        # cycle's takeaway, its deterministic scope, and its triage provenance.
        # Stored in the existing update_history JSON column — no schema change.
        # get_high_urgency_triage already surfaces the real triage_source on the
        # event dict, so this records the true "ai"/"rule_based_fallback"; the
        # "unknown" default only guards a dict that omits the key entirely.
        "takeaway_source_event_id": (chosen_event or {}).get("event_id"),
        "takeaway_event_scope":     _event_scope(chosen_event) if chosen_event else None,
        "triage_source":            (chosen_event or {}).get("triage_source", "unknown"),
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
        # Workstream B (2026-10-24): the note's own one_liner now comes only from
        # chosen_event — the single scope- AND provenance-eligible event (see
        # _select_takeaway_event) — so a market-wide or out-of-scope event's raw
        # one_liner can no longer be stamped as this specific article's own
        # "Update". Fallbacks, in order:
        #   1. chosen_event.one_liner — a genuinely in-scope, AI-sourced dev.
        #   2. market_move_reason — inherently article-scoped (the move IS this
        #      article's own index/sector/price), legitimate context.
        #   3. the global market-narrative story — ONLY for a non-entity article
        #      (no companies of its own). Owner review #4 (2026-10-24): a
        #      specific-company article must not be left with an unrelated
        #      market-wide explanation when this cycle produced no in-scope
        #      event, so for such an article we stamp NO note instead. (The
        #      2026-10-19 provenance suite's fixture is a no-company article, so
        #      its global-story fallback behavior is preserved.)
        note_text: str | None
        if chosen_event and chosen_event.get("one_liner"):
            note_text = chosen_event["one_liner"]
        elif market_move_reason:
            note_text = market_move_reason
        elif not _article_companies(article):
            note_text = mie_context.get("story", update_reason)
        else:
            note_text = None
        if note_text:
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
    # Provenance contract (2026-10-19): a rule_based_fallback/unknown event's
    # one_liner is a raw, unprocessed triage headline, not a synthesized
    # takeaway -- never publish it prefixed as "LATEST:". Workstream B
    # (2026-10-24): and the chosen event must be scope-eligible for THIS article
    # (see _event_sets_takeaway) so a market-wide development can't become an
    # unrelated, entity-specific article's own takeaway via a bare sector
    # overlap. Both rules live in _select_takeaway_event; None => no grounded,
    # in-scope takeaway this cycle, leave the existing one in place.
    top = _select_takeaway_event(article, new_events)
    if top is None:
        return None
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

    # Same provenance rule as _generate_updated_takeaway(): skip
    # rule_based_fallback/unknown candidates rather than publish an
    # unprocessed raw headline as a watch-next item.
    eligible = [e for e in new_events if e.get("triage_source") not in ("rule_based_fallback", "unknown")]
    for ev in eligible[:2]:
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
    Instrumented (2026-10-11): any LLM attempt made inside is tagged "article_update". The audit found no LLM call site here, so this should record none; if it ever does, it now shows.
    """
    from app.services import ai_usage
    with ai_usage.operation("article_update"):
        return await _run_continuous_update_cycle_impl(db, mie_context, new_triage_events)


async def _run_continuous_update_cycle_impl(
    db: AsyncSession,
    mie_context: dict[str, Any],
    new_triage_events: list[dict[str, Any]],
) -> int:
    """
    The unchanged update cycle. Returns number of articles updated.
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
