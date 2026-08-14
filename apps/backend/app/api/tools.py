"""
Standalone data-tools API — user-facing surfaces built directly on top of
this platform's own coverage/quality signals, rather than internal-only
metrics. Tool 1: Portfolio Data Confidence — for each holding a user pastes
in, reports how much real, recent event/news activity this platform is
actually tracking on it, honestly, including "not tracked at all."

Deliberately excludes two signals investigated for this tool and found not
usable/worth building right now:
  - ai_search's thin_evidence flag: currently just a structured-log field
    on ai_search.done/ai_search_v3.routed with no persistence table or
    aggregation job — there's no query path from "flag on a log line" to
    "how often has symbol X been flagged," short of building new
    infrastructure, which is out of scope here.
  - AISearchVerdictSnapshot-based verdict-stability: real and queryable,
    but only has rows for symbols someone has already searched (sparse for
    an arbitrary new portfolio), and the "stability" framing is redundant
    with the confidence field already sitting on the same row — a real
    signal exists there already, verdict-flip-counting would just be a
    noisier proxy for it.

Event coverage is matched by symbol (Event.companies is a list of
{"symbol": ...} dicts, populated at ingestion regardless of AI-enrichment
status — the richer relational event_companies table is NOT used here
because it's only populated during AI enrichment, which is paused as of
this session's incident; using it now would understate coverage for
anything ingested recently). News coverage is matched by company name
(NewsArticle.companies is a list of plain name strings, extracted via a
fixed ~35-name keyword list in news_fetcher.py — NOT the full universe),
so a 0 there means "not in our extraction list or genuinely no coverage,"
not a confident zero. The response is phrased to keep that distinction
honest rather than implying full news coverage everywhere.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.event import Event
from app.db.models_legacy import NewsArticle
from app.api.companies import _NSE_UNIVERSE, _fetch_prices
from app.services.ai_search.entities import _match_companies, suggest_companies

router = APIRouter()

_WINDOW_DAYS = 90
_BY_SYMBOL = {c["symbol"]: c for c in _NSE_UNIVERSE}

# A single-day move at or beyond this magnitude is the honest bar for
# "worth surfacing" — chosen because it's a real, live signal (not an
# AI-assessed one; job_enrich_events is paused, so impact_score is null on
# every recent event — see the Portfolio Ripples/Brief section below).
# Below this, price noise isn't a "development."
_MOVE_THRESHOLD_PCT = 2.0


class PortfolioConfidenceRequest(BaseModel):
    holdings: list[str]


def _resolve(raw: str) -> dict | None:
    """Reuses the same word-boundary-aware alias matcher ai_search uses for
    free-text queries — a portfolio holding is really just a one-entity
    query. Takes the first match; a holding line naming more than one
    company is a user-input edge case, not something to silently merge."""
    text = raw.strip().lower()
    if not text:
        return None
    matches = _match_companies(text)
    if matches:
        return _BY_SYMBOL.get(matches[0])
    return None


def _news_matches(company: dict, news_companies: list) -> bool:
    names = {company["name"].lower()} | {a.lower() for a in (company.get("aliases") or [])}
    for c in news_companies or []:
        if isinstance(c, str) and c.lower() in names:
            return True
    return False


def _event_matches(symbol: str, event_companies: list) -> bool:
    # Event.companies is stored inconsistently depending on which ingestion
    # path wrote the row — sometimes [{"symbol": "X", ...}], sometimes a
    # plain [str] of raw ticker symbols (confirmed live: NSE-sourced rows
    # commonly store the bare symbol string). Same dual-shape handling
    # events.py's own _to_summary already uses, not a new assumption.
    for c in event_companies or []:
        if isinstance(c, dict) and c.get("symbol") == symbol:
            return True
        if isinstance(c, str) and c.strip().upper() == symbol.upper():
            return True
    return False


def _summary(symbol: str, name: str, event_count: int, news_count: int) -> tuple[str, str]:
    """Returns (level, message). level is "strong" | "light" | "thin" —
    thresholds are deliberately coarse (not a fabricated precise score)
    since the underlying counts are themselves a rough real-activity proxy,
    not a calibrated model output."""
    if event_count >= 5:
        return "strong", f"Strong coverage: {event_count} event{'s' if event_count != 1 else ''} in the last {_WINDOW_DAYS} days" + (f", {news_count} article{'s' if news_count != 1 else ''} matched" if news_count else "") + "."
    if event_count >= 1 or news_count >= 1:
        return "light", f"Light coverage: {event_count} event{'s' if event_count != 1 else ''}" + (f", {news_count} article{'s' if news_count != 1 else ''}" if news_count else "") + f" in the last {_WINDOW_DAYS} days — real, but not much of it."
    return "thin", f"Thin coverage: 0 events in the last {_WINDOW_DAYS} days — we're not tracking much real-time activity on {name} yet."


def _price_message(name: str, pct: float, event_count: int) -> str:
    direction = "up" if pct >= 0 else "down"
    base = f"{name} shares are {direction} {abs(pct):.2f}% today."
    if event_count:
        return base + f" {event_count} tracked event{'s' if event_count != 1 else ''} in the last {_WINDOW_DAYS} days."
    return base + " No tracked events behind it yet — this is a live price move only."


async def _build_brief(results: list[dict]) -> dict:
    """Portfolio Intelligence Brief additions: real live price movement
    (Needs Attention / Positive Developments) and real cross-holding theme
    exposure (Portfolio Ripples) for resolved holdings.

    Deliberately built as an orchestration layer over signals that already
    exist elsewhere (companies.py's live-price fetch, the intelligence
    engine's theme cache) rather than a new intelligence engine — see
    tools.py's module docstring for why the richer AI-assessed event impact
    (Event.impact_score) isn't used: job_enrich_events is paused platform-
    wide, so every recent event's impact_score/impact is null/"Neutral"
    right now. Price movement is the honest substitute: real, live, and
    unblocked for the full universe.
    """
    resolved = [r for r in results if r["resolved"]]
    symbols = [r["symbol"] for r in resolved]

    prices = await _fetch_prices(symbols)

    needs_attention, positive = [], []
    for r in resolved:
        p = prices.get(r["symbol"])
        if not p:
            r["price"] = None
            r["price_pct"] = None
            continue
        r["price"] = p["price"]
        r["price_pct"] = p["pct"]
        item = {
            "symbol": r["symbol"],
            "name": r["name"],
            "price": p["price"],
            "pct": p["pct"],
            "event_count": r["event_count"],
            "message": _price_message(r["name"], p["pct"], r["event_count"]),
        }
        if p["pct"] <= -_MOVE_THRESHOLD_PCT:
            needs_attention.append(item)
        elif p["pct"] >= _MOVE_THRESHOLD_PCT:
            positive.append(item)
    needs_attention.sort(key=lambda x: x["pct"])
    positive.sort(key=lambda x: -x["pct"])

    ripples = []
    if symbols:
        try:
            from app.services.intelligence.engine import read_themes
            themes = await read_themes()
        except Exception:
            themes = []
        held = set(symbols)
        by_symbol = {r["symbol"]: r["name"] for r in resolved}
        for t in themes or []:
            matched = [s["sym"] for s in (t.get("top_stocks") or []) if s["sym"] in held]
            if not matched:
                continue
            ripples.append({
                "theme": t.get("theme"),
                "momentum": t.get("momentum"),
                "score": t.get("score"),
                "holdings": [{"symbol": s, "name": by_symbol.get(s, s)} for s in matched],
            })
        ripples.sort(key=lambda x: (-len(x["holdings"]), -(x["score"] or 0)))

    return {
        "needs_attention": needs_attention,
        "positive_developments": positive,
        "ripples": ripples,
        "prices_available": bool(prices),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/portfolio-confidence")
async def portfolio_confidence(body: PortfolioConfidenceRequest):
    cutoff = datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)

    # Filtering the window in the WHERE clause (Event.published_at >= cutoff)
    # looked fine until checked against real data: SQLite stores these as
    # plain TEXT ('2026-08-09 12:41:57...', space-separated, no tz suffix),
    # while a tz-aware Python datetime serializes to the query with a 'T'
    # separator and offset ('2026-05-11T12:45:14...+00:00'). SQLite then
    # compares them as strings, and ' ' sorts before 'T' in ASCII — so every
    # space-separated row (i.e. every genuinely recent one) was silently
    # excluded regardless of actual date, confirmed live: a filtered query
    # for a 90-day cutoff returned June rows and dropped today's. Sidestep
    # entirely by fetching bounded-but-unfiltered and comparing already-
    # deserialized Python datetimes, not asking SQLite to compare strings.
    # Table sizes here (~350 events, ~3k news rows) make this cheap; a
    # generous ORDER BY ... LIMIT still bounds the worst case.
    async with AsyncSessionLocal() as db:
        event_result = (await db.execute(
            select(Event.companies, Event.published_at)
            .order_by(Event.published_at.desc()).limit(3000)
        )).all()
        event_rows = [ec for ec, published_at in event_result
                      if published_at and published_at.replace(tzinfo=timezone.utc) >= cutoff]

        news_result = (await db.execute(
            select(NewsArticle.companies, NewsArticle.created_at)
            .order_by(NewsArticle.created_at.desc()).limit(3000)
        )).all()
        news_rows = [nc for nc, created_at in news_result
                     if created_at and created_at.replace(tzinfo=timezone.utc) >= cutoff]

    results = []
    for raw in body.holdings:
        company = _resolve(raw)
        if not company:
            suggestions = suggest_companies(raw.strip().lower(), limit=3)
            results.append({
                "input": raw,
                "resolved": False,
                "symbol": None,
                "name": None,
                "in_universe": False,
                "event_count": 0,
                "news_count": 0,
                "level": "not_tracked",
                "message": "We don't track this company at all yet." if not suggestions
                    else f"We don't track this exact name yet — did you mean {suggestions[0]['name']} ({suggestions[0]['symbol']})?",
                "suggestions": suggestions,
                "ai_search_query": f"What's happening with {raw.strip()}?",
            })
            continue

        symbol, name = company["symbol"], company["name"]
        event_count = sum(1 for ec in event_rows if _event_matches(symbol, ec))
        news_count = sum(1 for nc in news_rows if _news_matches(company, nc))
        level, message = _summary(symbol, name, event_count, news_count)

        results.append({
            "input": raw,
            "resolved": True,
            "symbol": symbol,
            "name": name,
            "sector": company.get("sector"),
            "in_universe": True,
            "event_count": event_count,
            "news_count": news_count,
            "level": level,
            "message": message,
            "suggestions": [],
            "ai_search_query": f"What's the latest on {name}?" if level != "thin" else f"Why is there so little coverage on {name}?",
        })

    brief = await _build_brief(results)

    return {
        "window_days": _WINDOW_DAYS,
        "holdings": results,
        "summary": {
            "strong": sum(1 for r in results if r["level"] == "strong"),
            "light": sum(1 for r in results if r["level"] == "light"),
            "thin": sum(1 for r in results if r["level"] == "thin"),
            "not_tracked": sum(1 for r in results if r["level"] == "not_tracked"),
        },
        "brief": brief,
    }
