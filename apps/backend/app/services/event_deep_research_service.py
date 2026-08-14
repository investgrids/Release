"""
Deep Research (Layer 2) — 2026-08 event page redesign.

Consolidates what used to be up to 5 independent AI-backed component
fetches (InvestmentThesisCard -> /api/thesis, ScenarioAnalysis ->
/api/scenario, MonitoringChecklist -> /api/checklist,
PatternIntelligenceCard -> /api/pattern, MultiHorizonOutlookCard ->
/api/intelligence/horizon) into ONE endpoint that makes AT MOST ONE new AI
call for the whole section (scenarios) and reuses already-computed real
data for everything else:

  - Timeline            -> EventRepository.get_timeline (already stored)
  - Historical patterns -> EventService.get_event_detail's own
                            historicalEvents (real similarity search,
                            already run for the main event response —
                            re-run here, not re-invented, since this is a
                            separate lazy-loaded request; still zero AI
                            calls)
  - Second-order effects -> a direct, READ-ONLY check against the Ripple
                            Engine's own table. Never generates a new
                            ripple graph from this endpoint — if one
                            doesn't already exist, the page says so and
                            links to the full Ripple page instead of
                            paying for a fresh AI generation just because
                            Deep Research was opened.
  - Risks                -> merged from the event's own real
                            risk_factors/opportunities (no separate
                            "monitoring checklist" or "pattern
                            intelligence" AI call — those endpoints still
                            exist for their other callers (company/story/
                            opportunity/ripple/search), just not reused
                            here since they'd duplicate this exact
                            content)
  - Scenarios            -> the ONE reused call, generate_scenario_analysis
                            (already existed, already cached 2h per
                            entity) — not reimplemented, just composed in
                            here instead of fetched by a separate
                            component.
  - Reasoning/sources     -> real confidence/timestamps/source list already
                            on the event, no new call.

Real-data-only guarantee: generate_scenario_analysis's own fallback path
returns a `degraded: True`, 100%-templated response when the AI call fails
(confirmed live in ai_service.py — generic boilerplate like "Strong
performance... driven by favourable macro conditions" with invented
"25-40% returns" language, identical for every entity). That flag was
never checked by the old frontend ScenarioAnalysis component, which
rendered it exactly like a real scenario. This service checks it and
sets scenarios_available=False instead of shipping fabricated content.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ripple import RippleGraph
from app.repositories.event_repository import EventRepository
from app.schemas.event_deep_research import (
    DeepResearchResponse, HistoricalPattern, Reasoning, RiskItem, Scenario,
    SecondOrderEffect, TimelineStep,
)
from app.services.event_service import EventService


def _confidence_bucket(value: float | int | None) -> str | None:
    """0-100 (or 0-1, normalized) numeric confidence -> qualitative tier.
    Never surfaced as the raw number — see module docstring."""
    if value is None:
        return None
    v = float(value)
    if v <= 1.0:
        v *= 100
    if v >= 66:
        return "High"
    if v >= 33:
        return "Medium"
    return "Low"


def _scenario_worthy(impact_score: float | None, confidence: float | None) -> bool:
    """Materiality + genuine uncertainty gate — deliberately reuses the
    event's own already-computed impact_score/confidence rather than
    inventing a new 'uncertainty' signal. High impact alone isn't enough
    (a rate decision everyone expected has a clear, well-understood
    direction — no real Bull/Base/Bear split); the AI's own confidence
    being middling-to-low on a high-impact event is what actually signals
    multiple plausible real paths worth framing as scenarios. Low-impact
    events (a routine corporate announcement) never qualify regardless of
    confidence. This also means Scenario Analysis's one AI call only fires
    for a minority of events, not every Deep Intelligence open."""
    if impact_score is None or impact_score < 65:
        return False
    if confidence is None:
        return True  # unscored confidence — materiality alone is enough to ask
    return confidence < 70


async def _get_scenarios(title: str, description: str, sector: str, event_id: str) -> tuple[list[Scenario], str]:
    """The one reused AI call — only made at all when _scenario_worthy
    gates it in. Returns (scenarios, status); status is 'unavailable'
    whenever the call degraded or failed, so the caller never presents
    fabricated content as real."""
    try:
        from app.services.ai_service import generate_scenario_analysis
        raw = await generate_scenario_analysis(
            entity_type="event", entity_id=event_id, title=title,
            description=description, sector=sector, priority="interactive",
        )
    except Exception:
        return [], "unavailable"

    if not raw or raw.get("degraded") or not raw.get("bull"):
        return [], "unavailable"

    scenarios: list[Scenario] = []
    for key, label in (("bull", "Bull"), ("base", "Base"), ("bear", "Bear")):
        s = raw.get(key)
        if not s or not s.get("outcome"):
            continue
        scenarios.append(Scenario(
            label=label,  # type: ignore[arg-type]
            outcome=s["outcome"],
            key_drivers=(s.get("key_drivers") or [])[:3],
            confidence=_confidence_bucket(s.get("confidence")),  # type: ignore[arg-type]
        ))
    return scenarios, ("shown" if scenarios else "unavailable")


async def _get_second_order_effects(db: AsyncSession, event_id: str) -> list[SecondOrderEffect]:
    """Read-only — never generates a ripple graph. A real, already-stored
    graph's insights become 'observed' facts; nothing is invented when
    none exists yet."""
    row = (await db.execute(
        select(RippleGraph)
        .where(RippleGraph.event_id == event_id)
        .where(RippleGraph.scenario_type == "event")
        # "fallback_template" rows are ripple_service.py's own hand-written
        # placeholder graphs (used when AI ripple generation fails) — not
        # real analysis of this event, so they're excluded here rather than
        # presented as "observed"/"likely" facts about it.
        .where(RippleGraph.source == "ai_generated")
        .order_by(RippleGraph.generated_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if not row or not row.graph_data or not row.graph_data.get("nodes"):
        return []

    effects: list[SecondOrderEffect] = []
    insights = row.insights or {}
    if insights.get("summary"):
        effects.append(SecondOrderEffect(level="immediate", description=insights["summary"], status="observed"))
    for sector in (insights.get("impacted_sectors") or [])[:3]:
        name = sector.get("name") if isinstance(sector, dict) else str(sector)
        if name:
            effects.append(SecondOrderEffect(level="sector", description=f"{name} sector exposure identified", status="likely"))
    for company in (insights.get("beneficiaries") or [])[:2]:
        name = company.get("name") if isinstance(company, dict) else str(company)
        if name:
            effects.append(SecondOrderEffect(level="company", description=f"{name} flagged as a potential beneficiary", status="likely"))
    return effects


async def get_deep_research(db: AsyncSession, event_id: str) -> DeepResearchResponse | None:
    repo = EventRepository(db)
    event = await repo.get_by_id(event_id)
    if event is None:
        event = await repo.get_by_slug(event_id)
    if event is None:
        return None
    resolved_id = event.id

    # Reuses EventService's own cached get_event_detail (Redis, 15 min TTL)
    # rather than re-deriving summary/historical/sector logic — this is
    # the exact same real data the main event response already computed.
    detail = await EventService(db).get_event_detail(resolved_id)
    if detail is None:
        return None

    ev = detail["event"]
    summary = detail["summary"]

    # ── Timeline — real stored EventTimeline rows only. Deliberately NOT
    # detail["timeline"]: EventService.get_event_detail() synthesizes a
    # placeholder timeline (generic steps like "Event Announced" and
    # "Market Outlook: Monitor for developments over the coming weeks.")
    # whenever no real EventTimeline rows exist for this event — useful
    # filler for the legacy Overview tab, but exactly the kind of invented
    # timestamp-free "step" this section is explicitly required never to
    # show. Real rows only; an empty list here is the honest answer when
    # none exist yet.
    real_timeline = await repo.get_timeline(resolved_id)
    timeline = [
        TimelineStep(
            date=t.date or None, title=t.title, description=t.description or "",
            kind="detected" if i == 0 else "update",
        )
        for i, t in enumerate(real_timeline)
    ]

    # ── Historical patterns — real similarity search, already computed ──
    historical_patterns = [
        HistoricalPattern(
            id=h["id"], slug=h.get("slug") or "", title=h["title"], event_date=h.get("event_date"),
            similarity_score=h.get("similarity_score"), impact_score=h.get("impact_score"),
            reason=h.get("reason") or None,
        )
        for h in detail["historicalEvents"]
    ]

    # ── Risks — merged from the ONE real source (summary.risk_factors),
    # never duplicated across a separate checklist/pattern AI call ──────
    risks = [RiskItem(risk=r) for r in (summary.get("risk_factors") or [])[:5]]

    # ── Second-order effects — read-only Ripple reuse ───────────────────
    second_order_effects = await _get_second_order_effects(db, resolved_id)

    # ── Scenarios — the one reused AI call, only when the event actually
    # warrants Bull/Base/Bear framing (see _scenario_worthy) ─────────────
    sector = detail["affectedSectors"][0]["sector"] if detail["affectedSectors"] else ""
    if _scenario_worthy(detail["impactScore"], detail["confidence"]):
        scenarios, scenario_status = await _get_scenarios(
            title=ev["title"], description=summary.get("text") or ev.get("description") or "",
            sector=sector, event_id=resolved_id,
        )
    else:
        scenarios, scenario_status = [], "not_applicable"

    # ── Reasoning / sources — real fields already on the event ──────────
    sources = sorted({n["source"] for n in detail["relatedNews"] if n.get("source")})
    if ev.get("source"):
        sources.insert(0, ev["source"])
    data_used = []
    if detail["impactScore"] is not None:
        data_used.append("Impact score")
    if detail["confidence"] is not None:
        data_used.append("AI confidence")
    if detail["affectedSectors"]:
        data_used.append(f"{len(detail['affectedSectors'])} affected sector(s)")
    if detail["companies"]:
        data_used.append(f"{len(detail['companies'])} company mapping(s)")
    if historical_patterns:
        data_used.append(f"{len(historical_patterns)} historical precedent(s)")

    reasoning = Reasoning(
        data_used=data_used,
        sources=list(dict.fromkeys(sources))[:6],
        analysis_timestamp=ev.get("updated_at"),
        confidence=detail["confidence"],
        summary=summary.get("why_it_matters") or None,
    )

    return DeepResearchResponse(
        event_id=resolved_id,
        timeline=timeline,
        scenarios=scenarios,
        scenario_status=scenario_status,  # type: ignore[arg-type]
        historical_patterns=historical_patterns,
        second_order_effects=second_order_effects,
        risks=risks,
        reasoning=reasoning,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
