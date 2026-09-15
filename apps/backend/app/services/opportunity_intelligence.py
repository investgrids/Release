"""
Opportunity Radar 2.0 — the Event → Ripple → Opportunity → Companies →
Confidence → Timeline → Catalysts → Historical Similarity → Investment
Verdict chain. Three genuinely new pieces; everything else in that chain
was already real data sitting unused or unlinked:

  - primary_event   — OpportunityEvent links every opportunity to the
                       NewsArticle ids it was generated from, but that
                       column has no DB-enforced FK and is never existence-
                       checked against the real `events` table (Opportunity
                       `primary_event` Integrity Audit, 2026-09-15: 79.6% of
                       real production opportunities had a dangling
                       top-ranked event — RSS-sourced articles are
                       deliberately never promoted to a real Event at
                       ingestion, see ingest_tasks.py's own "RSS items do
                       NOT become Events" comment, and only a narrow
                       Critical/High-tier triage bridge closes some of that
                       gap). `select_primary_event()` below picks the
                       highest-importance event among only the ones that
                       actually resolve to a real Event, so /events/{id} is
                       never a dead link — never a fix to the write-time
                       contract itself, which is separate future work
                       (Opportunity PE-2).
  - ripple graph     — OpportunityGraphNode/Edge already exist, real,
                       populated by the pipeline (verified live: a real
                       opportunity->sector/company star graph) — just never
                       rendered by the frontend before this.
  - investment_verdict — genuinely new: a deterministic label from the
                       opportunity's own real opportunity_score/confidence/
                       risk_level/trend (no LLM call, same "don't add a
                       call if deterministic data already answers it"
                       stance as the rest of this app).
  - historical_similarity — reuses historical_memory_service.find_similar_events
                       verbatim (the same engine Live Intelligence's
                       Pattern Detected card and AI Search's own historical
                       evidence already use), seeded from the opportunity's
                       real sectors.
  - catalysts        — reuses investment_watch.py's real calendar-matching
                       helpers verbatim (the same real, admin-curated
                       calendar_events table Investment Watch already
                       surfaces on company pages), filtered to this
                       opportunity's sectors.
"""
from __future__ import annotations


async def select_primary_event(db, events: list) -> object | None:
    """Opportunity PE-1 — Public Link Integrity (2026-09-15). `events` is
    `OpportunityDetailResponse.events` (each a real OpportunityEvent row's
    event_id/importance/title/etc, EventSchema-shaped) -- a write-time
    snapshot with no DB-enforced FK to `events.id` and no existence check
    at write time (see this module's own docstring for the audit that
    found 79.6% of real opportunities dangling here).

    One batched existence query (never N queries), checked against BOTH
    Event.id and Event.slug -- matching EventService.get_event_detail's
    own id-then-slug resolution, so an event_id that only resolves via
    slug still counts. Returns the highest-importance event among ONLY
    the ones that actually resolve; None when nothing does. Never
    substitutes the underlying NewsArticle route, never synthesizes an
    Event, never returns the dangling top-ranked row just because it
    ranks highest -- missing evidence means the Triggering Event surface
    disappears, the same discipline this app already applies elsewhere,
    not a special case invented here."""
    if not events:
        return None
    ids = {e.event_id for e in events if e.event_id}
    if not ids:
        return None

    from sqlalchemy import or_, select
    from app.db.models.event import Event

    result = await db.execute(
        select(Event.id, Event.slug).where(or_(Event.id.in_(ids), Event.slug.in_(ids)))
    )
    valid: set[str] = set()
    for eid, slug in result.all():
        valid.add(eid)
        if slug:
            valid.add(slug)

    resolvable = [e for e in events if e.event_id in valid]
    return max(resolvable, key=lambda e: e.importance) if resolvable else None


def compute_investment_verdict(opportunity_score: float, confidence: float, risk_level: str, trend: str) -> dict:
    """Deterministic — no LLM call. confidence here is 0-1 (Opportunity.confidence's
    real scale); opportunity_score is 0-100."""
    conf_pct = confidence * 100 if confidence <= 1 else confidence
    risk = (risk_level or "").lower()
    trend_l = (trend or "").lower()

    if opportunity_score >= 85 and conf_pct >= 75 and risk != "high":
        label, tone = "Strong Conviction", "positive"
    elif opportunity_score >= 70 and conf_pct >= 60 and risk != "high":
        label, tone = "Positive", "positive"
    elif risk == "high" or opportunity_score < 50:
        label, tone = "Cautious", "negative"
    else:
        label, tone = "Neutral", "neutral"

    reasons = [f"Opportunity score {round(opportunity_score)}/100", f"{round(conf_pct)}% confidence", f"{risk_level or 'Medium'} risk"]
    if trend_l:
        reasons.append(f"{trend} trend")

    return {"label": label, "tone": tone, "reasoning": " · ".join(reasons)}


async def get_catalysts(sectors: list[str], limit: int = 3) -> list[dict]:
    """Reuses investment_watch.py's real, already-proven calendar-matching
    — same admin-curated calendar_events table, same keyword-overlap logic,
    just matched against this opportunity's sectors instead of a single
    company's name."""
    from app.db.session import AsyncSessionLocal
    from app.services.ai_search import investment_watch as iw

    async with AsyncSessionLocal() as db:
        rows = await iw._relevant_calendar_rows(db)

    if not sectors:
        return [{"label": r["title"], "category": r["category"], "date": r["date"], "days_until": r["days_until"]} for r in rows[:limit]]

    matched = []
    sector_words = {s.lower() for s in sectors}
    for r in rows:
        text = (r["title"] + " " + r["description"]).lower()
        if any(w in text for w in sector_words) or r["category"] in ("RBI", "Government", "Macro"):
            matched.append(r)
        if len(matched) >= limit:
            break
    pool = matched or rows[:limit]
    return [{"label": r["title"], "category": r["category"], "date": r["date"], "days_until": r["days_until"]} for r in pool[:limit]]


async def get_historical_similarity(sectors: list[str], title: str = "") -> dict | None:
    """Same real precedent-matching engine used everywhere else in this
    app (historical_memory_service) — never a second, weaker version.

    Only the first 2 sectors go into the query — sector-Jaccard similarity
    dilutes fast with each extra sector added (see live_intelligence.py's
    _detect_historical_match, same fix, same reasoning), and category
    (inferred from the opportunity's own title, same keyword inference AI
    Search's historical matching already uses) is worth more of the score
    than sectors alone."""
    from app.services.ai_search.retrieval import _infer_historical_category
    from app.services.historical_memory_service import find_similar_events

    category = _infer_historical_category(title.lower()) if title else None
    if not sectors and not category:
        return None
    matches = await find_similar_events(
        {"sectors": sectors[:2], "category": category}, limit=1, min_similarity=10.0,
    )
    if not matches:
        return None
    m = matches[0]
    return {
        "event_title": m["event_title"], "similarity": m["similarity"],
        "key_lesson": m.get("key_lesson"),
        "winners": [w.get("symbol") or w.get("name") for w in (m.get("historical_winners") or [])][:4],
        "losers": [l.get("symbol") or l.get("name") for l in (m.get("historical_losers") or [])][:4],
    }
