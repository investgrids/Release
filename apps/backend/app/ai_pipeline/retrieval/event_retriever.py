"""
Event Retriever — searches the Event table by query keywords (same
title/summary ILIKE pattern as `ai_search_service._search_events`), then
enriches the single MOST RELEVANT hit via `EventService.get_event_detail`
for its AI summary, affected companies/sectors, and risk/opportunity
bullets — this is meaningfully richer evidence than the raw search row.

"Most relevant" is a real ranking, not just "highest impact_score first":
`or_()` matching means every returned row already matched *some* query
word, but a row matching one incidental word is not as relevant as one
matching four. A larger candidate pool is pulled ordered by impact_score
(a reasonable SQL-level pre-filter), then re-ranked in Python by
(word-match count, impact_score) before picking the row to enrich —
otherwise, on a database with many generic high-impact-score rows (e.g.
routine NSE corporate announcements), the enriched "top hit" for a query
like "RBI rate cut impact" can end up being an unrelated filing that
merely outscored the real RBI event on impact_score alone.
"""
from __future__ import annotations

import re

import structlog
from sqlalchemy import or_, select

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.db.models.event import Event
from app.services.event_service import EventService

log = structlog.get_logger(__name__)

_CANDIDATE_POOL_SIZE = 20
_EVIDENCE_LIMIT = 8


def _words(query: str) -> list[str]:
    return [w for w in re.findall(r"\w+", query.lower()) if len(w) >= 2][:8]


def _polarity_from_impact(impact: str | None) -> str:
    return {"positive": "positive", "negative": "negative"}.get((impact or "").lower(), "neutral")


def _relevance(event: Event, words: list[str]) -> int:
    if not words:
        return 0
    text = f"{event.title or ''} {event.summary or ''}".lower()
    return sum(1 for w in words if w in text)


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    ws = _words(ctx.query)
    conds = [Event.title.ilike(f"%{w}%") for w in ws] + [Event.summary.ilike(f"%{w}%") for w in ws]
    stmt = (
        select(Event).where(or_(*conds)).order_by(Event.impact_score.desc()).limit(_CANDIDATE_POOL_SIZE)
        if conds else
        select(Event).order_by(Event.impact_score.desc()).limit(_EVIDENCE_LIMIT)
    )
    candidates = (await ctx.db.execute(stmt)).scalars().all()
    if not candidates:
        return []

    # Re-rank the candidate pool by real relevance (word-match count) before
    # truncating to the evidence limit or picking the enrichment target —
    # SQL only pre-filtered by impact_score, which is not a relevance signal.
    rows = sorted(
        candidates,
        key=lambda e: (_relevance(e, ws), float(e.impact_score or 0)),
        reverse=True,
    )[:_EVIDENCE_LIMIT]

    evidence: list[Evidence] = []
    for e in rows:
        magnitude = min(max(float(e.impact_score or 0) / 10.0, 0.0), 1.0)
        confidence = min(max(float(e.confidence or 0), 0.0), 1.0)
        evidence.append(Evidence(
            id=f"event:{e.id}",
            source="event",
            entity=(e.sectors or [None])[0] if e.sectors else None,
            claim=(e.summary or e.title or "")[:280],
            polarity="neutral",   # refined below for the enriched top hit
            magnitude=magnitude,
            confidence=confidence or 0.5,
            timestamp=e.event_date or e.published_at,
            raw={"id": e.id, "title": e.title, "category": e.category, "impact_score": e.impact_score},
        ))

    # Enrich the top hit with the full AI-analyzed detail — companies,
    # sectors, risk/opportunity bullets each become their own Evidence.
    top = rows[0]
    try:
        detail = await EventService(ctx.db).get_event_detail(top.id)
    except Exception as exc:
        log.warning("ai_pipeline.event_retriever.detail_failed", event_id=top.id, error=str(exc)[:200])
        detail = None

    if detail:
        summary = detail.get("summary", {})
        overall_polarity = _polarity_from_impact(summary.get("immediate_impact"))
        # Replace the shallow top-hit evidence with the enriched version
        evidence[0] = Evidence(
            id=f"event:{top.id}",
            source="event",
            entity=None,
            claim=summary.get("text") or (top.summary or top.title or "")[:280],
            polarity=overall_polarity,
            magnitude=min(max(float(detail.get("impactScore", 0)) / 10.0, 0.0), 1.0),
            confidence=min(max(float(detail.get("confidence", 0)), 0.0), 1.0) or 0.5,
            timestamp=top.event_date or top.published_at,
            raw=detail,
        )
        for c in detail.get("companies", [])[:5]:
            evidence.append(Evidence(
                id=f"event:{top.id}:company:{c.get('symbol')}",
                source="event",
                entity=c.get("symbol"),
                claim=c.get("reason") or f"{c.get('name')} is {c.get('impact_type', 'affected')} by this event",
                polarity={"beneficiary": "positive", "loser": "negative"}.get(c.get("impact_type"), "neutral"),
                magnitude=min(max(float(c.get("impact_score", 5.0)) / 10.0, 0.0), 1.0),
                confidence=0.6,
                timestamp=top.event_date or top.published_at,
                raw=c,
            ))
        for s in detail.get("affectedSectors", [])[:5]:
            evidence.append(Evidence(
                id=f"event:{top.id}:sector:{s.get('sector')}",
                source="event",
                entity=s.get("sector"),
                claim=f"{s.get('sector')} sector impact: {s.get('impact', 'neutral')}",
                polarity=_polarity_from_impact(s.get("impact")),
                magnitude=min(max(float(s.get("impact_score", 50.0)) / 100.0, 0.0), 1.0),
                confidence=0.55,
                timestamp=top.event_date or top.published_at,
                raw=s,
            ))

    return evidence


RETRIEVER_REGISTRY.register("event")(RetrieverSpec(key="event", fetch=_fetch, timeout_s=10.0))
