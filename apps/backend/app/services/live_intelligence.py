"""
Live Intelligence (Phase 3, Priority 2) — the "why investors should care"
stream beneath the homepage hero. Four real, independently-detected
intelligence types, each grounded in data that already exists elsewhere
in this codebase — nothing here is a second competing narrative source,
and nothing is invented when the underlying signal isn't there:

  - anomaly      — sector event-clustering, from EventTriage (real, already
                    ingested/triaged events — never a synthesized "unusual
                    activity" claim, just a real count crossing a threshold)
  - policy_ripple — a real multi-hop causal path via
                    ai_search_service._build_ripple_chain, reusing the exact
                    same seeded intelligence graph traversal Phase 2A wired
                    into AI Search's Ripple Graph (Investment Watch/Ripple
                    Graph's own proven mechanism, not a new one)
  - early_theme  — a real ThemeState row with momentum="rising", cross-
                    referenced against a real Opportunity row's score when
                    one exists for that theme
  - historical_match — a real precedent via
                    historical_memory_service.find_similar_events, seeded
                    from today's real sector/sentiment context (the same
                    AIPE morning_intelligence article the homepage hero uses)

A "capital_flow" (FII/DII sector-level flow) type from the original spec is
deliberately NOT built — no data source in this app tracks FII/DII flow at
sector granularity (only the market-wide net figure exists, see
api/market.py's _fetch_fii_dii), and fabricating a sector attribution for it
would violate this app's core "never invent a claim" rule. Flagged here
rather than silently dropped.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence import EventTriage, ThemeState
from app.db.models.opportunity import Opportunity

log = structlog.get_logger(__name__)

_MIN_CLUSTER_COMPANIES = 3
_CLUSTER_WINDOW_HOURS = 72
# Same categorical->weight scale homepage_intelligence.py uses for its own
# sector-magnitude ranking — duplicated rather than imported since the two
# modules' magnitude scales are conceptually independent (this one's only
# use is picking which sectors matter most for a historical-similarity
# query, not a persisted score).
_MAGNITUDE_WEIGHT = {"low": 1, "medium": 2, "high": 3}
_MIN_EVENT_URGENCY = 5


async def _detect_anomaly(db: AsyncSession) -> dict | None:
    """Real sector event-clustering: N>=3 distinct real companies whose own
    sector genuinely matches, with real, recently-triaged, meaningfully-
    urgent events in that sector within a real time window. This is a
    genuine count, not a model guess.

    Live-audit bug (2026-07-28): a "11 IT companies" card was found showing
    BHARTIARTL/CIPLA/DRREDDY/HDFCBANK/ICICIBANK — because EventTriage.sectors
    is a list per event (one event can be tagged with several sectors at
    once, e.g. a Union Budget story), and every ticker on that event was
    being credited to every one of its tags. Fixed by only counting a ticker
    under a sector when that company's OWN real sector (from _NSE_UNIVERSE)
    actually matches the tag — via the same word-overlap+alias check
    sectors.py uses for the identical "IT" vs "Technology" naming variance."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_CLUSTER_WINDOW_HOURS)
    rows = (await db.execute(
        select(EventTriage)
        .where(EventTriage.triaged_at >= cutoff)
        .where(EventTriage.urgency >= _MIN_EVENT_URGENCY)
    )).scalars().all()

    from app.api.companies import _NSE_UNIVERSE
    from app.api.sectors import _words_overlap
    symbol_sector = {co["symbol"]: (co.get("sector") or "") for co in _NSE_UNIVERSE}
    real_symbols = set(symbol_sector)

    by_sector: dict[str, dict] = {}
    for r in rows:
        for sector in (r.sectors or []):
            key = sector.strip()
            if not key:
                continue
            bucket = by_sector.setdefault(key, {"tickers": set(), "headlines": [], "latest": None})
            key_words = set(key.lower().split())
            matched_this_event = False
            for t in (r.tickers or []):
                sym = t.replace("NSE:", "")
                # Real companies only — event tickers also include indices
                # (NIFTY50, SENSEX, BANKNIFTY) and macro symbols (INR), which
                # aren't "companies" and would inflate the cluster count.
                if sym not in real_symbols:
                    continue
                # ...and only when the company's OWN sector actually matches
                # this tag, not merely because the event carried multiple tags.
                sym_words = set(symbol_sector[sym].lower().split())
                if _words_overlap(key_words, sym_words):
                    bucket["tickers"].add(sym)
                    matched_this_event = True
            if matched_this_event:
                bucket["headlines"].append(r.one_liner or r.headline)
                if r.triaged_at and (bucket["latest"] is None or r.triaged_at > bucket["latest"]):
                    bucket["latest"] = r.triaged_at

    candidates = [(s, b) for s, b in by_sector.items() if len(b["tickers"]) >= _MIN_CLUSTER_COMPANIES]
    if not candidates:
        return None
    sector, bucket = max(candidates, key=lambda c: len(c[1]["tickers"]))

    try:
        from app.services.historical_memory_service import find_similar_events
        hist = await find_similar_events({"sectors": [sector]}, limit=1, min_similarity=40.0)
        similarity = hist[0]["similarity"] if hist else None
    except Exception:
        similarity = None

    return {
        "type": "anomaly",
        "headline": f"{len(bucket['tickers'])} {sector} companies showing simultaneous activity",
        "why_it_matters": bucket["headlines"][0] if bucket["headlines"] else None,
        "companies": sorted(bucket["tickers"])[:6],
        "similarity": similarity,
        "sector": sector,
        "detected_at": bucket["latest"].isoformat() if bucket["latest"] else None,
    }


async def _detect_policy_ripple(db: AsyncSession) -> dict | None:
    """A real multi-hop causal path — reuses _build_ripple_chain verbatim
    (same mechanism Phase 2A's Ripple Graph already proved), seeded from a
    real recent policy-flagged event's own headline when one exists.

    Live-audit finding (2026-07-28): when no policy_row exists, this fell
    through to a hardcoded evergreen seed pool and returned it exactly like
    a live signal — "Union Budget Defence Boost" under a "Policy
    Intelligence" card with no indication it wasn't today's news. The chain
    itself is still real (not fabricated), but the freshness claim was
    false. `is_fallback` now marks that distinction so the frontend can be
    honest about it instead of implying "detected right now.\""""
    from app.services.ai_search_service import _build_ripple_chain

    cutoff = datetime.now(timezone.utc) - timedelta(hours=_CLUSTER_WINDOW_HOURS)
    policy_row = (await db.execute(
        select(EventTriage)
        .where(EventTriage.triaged_at >= cutoff)
        .where(EventTriage.source == "policy")
        .order_by(EventTriage.urgency.desc())
        .limit(1)
    )).scalars().first()

    seeds = [(policy_row.headline, False)] if policy_row else []
    # Real, already-seeded policy nodes (intelligence_graph_service) as a
    # fallback pool — tried in order, first one that produces a real
    # traversal wins. Never a fabricated path, but never today's real news
    # either — is_fallback=True marks every seed in this pool as such.
    seeds += [(s, True) for s in
              ("Union Budget Defence Boost", "PLI Manufacturing", "RBI Rate Cut", "Union Budget Infra Boost")]

    for seed, is_fallback in seeds:
        if not seed:
            continue
        try:
            chain = await _build_ripple_chain(seed)
        except Exception:
            chain = []
        if chain:
            path = [n["label"] for level in chain for n in level["nodes"][:1]]
            # _build_ripple_chain only traverses the macro graph (policy/
            # sector/theme/commodity nodes) — it never returns company
            # leaves (that's ripple_graph.py's job, one layer up, for a
            # specific AI Search response). Real companies for the last
            # sector the chain actually reached, pulled the same way
            # ripple_graph.py's own _competitors_for does.
            companies = _companies_for_chain(chain)
            return {
                "type": "policy_ripple",
                "headline": seed,
                "path": path[:5],
                "companies": companies,
                "is_fallback": is_fallback,
                "detected_at": None if is_fallback else policy_row.triaged_at.isoformat(),
            }
    return None


def _companies_for_chain(chain: list[dict]) -> list[str]:
    from app.api.companies import _NSE_UNIVERSE

    sector_labels = [
        n["label"] for level in reversed(chain) for n in level["nodes"] if n["type"] == "sector"
    ]
    for sector_label in sector_labels:
        matches = [co["symbol"] for co in _NSE_UNIVERSE if co["sector"].lower() == sector_label.lower()]
        if matches:
            return matches[:5]
    return []


async def _detect_early_theme(db: AsyncSession, exclude: str | None = None) -> dict | None:
    """A real rising-momentum theme, cross-referenced against a real
    Opportunity row's score when one exists for it (never invented)."""
    themes = (await db.execute(
        select(ThemeState).where(ThemeState.momentum == "rising").order_by(ThemeState.score.desc())
    )).scalars().all()
    themes = [t for t in themes if t.theme != exclude]
    if not themes:
        return None
    theme = themes[0]

    opp = (await db.execute(select(Opportunity))).scalars().all()
    match = next((o for o in opp if theme.theme.lower() in (o.title or "").lower()
                  or any(theme.theme.lower() in (s or "").lower() for s in (o.sectors or []))), None)
    opportunity_score = round(match.opportunity_score) if match else round(theme.score)

    top_stocks = [
        (s.get("sym") if isinstance(s, dict) else str(s)) for s in (theme.top_stocks or [])
    ][:5]

    return {
        "type": "early_theme",
        "headline": theme.theme,
        "opportunity_score": opportunity_score,
        "companies": top_stocks,
        "opportunity_id": match.id if match else None,
        "detected_at": theme.updated_at.isoformat() if theme.updated_at else None,
    }


async def _detect_historical_match(article) -> dict | None:
    """A real historical precedent for TODAY — seeded from the same
    morning_intelligence article the homepage hero already uses (not a
    second, competing market-context source). Only the most significant
    sectors go into the query (not all of them) — sector-Jaccard similarity
    dilutes fast with each extra sector added, and a diluted score would
    misrepresent how close the real match actually is.

    min_similarity is intentionally low (10, not the 25+ AI Search uses):
    this query only ever carries sector overlap (no category/sentiment
    signal like AI Search's query-text-derived one has), so its ceiling is
    structurally lower — a modest real score here is still a real, honest
    signal, not a weaker version of the same claim."""
    from app.services.ai_search_service import _infer_historical_category
    from app.services.historical_memory_service import find_similar_events

    sectors = sorted(
        (s for s in (article.sectors_affected or []) if s.get("impact") != "neutral" and s.get("name")),
        key=lambda s: _MAGNITUDE_WEIGHT.get((s.get("magnitude") or "").lower(), 0), reverse=True,
    )
    sector_names = [s["name"] for s in sectors[:2]]
    # Same real keyword->category inference AI Search's own historical
    # matching uses (ai_search_service._infer_historical_category), applied
    # to the article's own real headline/summary text — category is worth
    # more of the similarity score (30 pts) than sectors alone (25 pts), so
    # skipping it would understate how close a real match actually is.
    text = f"{article.headline or ''} {article.executive_summary or ''}".lower()
    category = _infer_historical_category(text)
    if not sector_names and not category:
        return None
    query = {"sectors": sector_names, "category": category}
    matches = await find_similar_events(query, limit=1, min_similarity=10.0)
    if not matches:
        return None
    m = matches[0]
    return {
        "type": "historical_match",
        "headline": m["event_title"],
        "similarity": m["similarity"],
        "winners": [w.get("symbol") or w.get("name") for w in (m.get("historical_winners") or [])][:4],
        "losers": [l.get("symbol") or l.get("name") for l in (m.get("historical_losers") or [])][:4],
        "key_lesson": m.get("key_lesson"),
        "detected_at": article.published_at.isoformat() if article.published_at else None,
    }


async def get_live_intelligence(db: AsyncSession, article=None) -> list[dict]:
    """Assembles the feed — each detector is independently best-effort; one
    failing (e.g. no cluster found today) never blocks the others."""
    items: list[dict] = []

    for fn in (_detect_anomaly, _detect_policy_ripple):
        try:
            item = await fn(db)
            if item:
                items.append(item)
        except Exception as exc:
            log.warning("live_intelligence.detector_fail", detector=fn.__name__, exc=str(exc)[:160])

    try:
        exclude = None
        if article:
            positive = [s for s in (article.sectors_affected or []) if s.get("impact") == "positive"]
            exclude = positive[0]["name"] if positive else None
        item = await _detect_early_theme(db, exclude=exclude)
        if item:
            items.append(item)
    except Exception as exc:
        log.warning("live_intelligence.detector_fail", detector="early_theme", exc=str(exc)[:160])

    if article:
        try:
            item = await _detect_historical_match(article)
            if item:
                items.append(item)
        except Exception as exc:
            log.warning("live_intelligence.detector_fail", detector="historical_match", exc=str(exc)[:160])

    return items
