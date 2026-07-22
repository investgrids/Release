"""
AI Recommendation Engine — Phase 2.

Replaces the LLM inventing a "top N stocks" list from its own knowledge
for the list_picks intent. Real, deterministic candidate generation:

  1. Real sector/theme-matched opportunities from the Opportunity Engine
     (opportunity_service — same real engine market_pulse and the
     Opportunities intent already reuse).
  2. Each opportunity's real `sectors` field is cross-referenced against
     the real 202-company NSE universe (app.api.companies._NSE_UNIVERSE)
     to resolve actual, tradeable NSE symbols — never an invented ticker.
  3. Ranked by each candidate's real opportunity_score.

No LLM call happens here. This can only surface a symbol that both (a)
really exists in the NSE universe and (b) is really tied to a scored,
stored opportunity — it cannot invent a pick the way free LLM generation
could.
"""
from __future__ import annotations


def _companies_in_sectors(sectors: list[str], terms: set[str]) -> list[dict]:
    """
    Restrict to sectors that actually overlap with the search terms — an
    opportunity matched via `list_by_sector_or_theme` can legitimately span
    several sectors (e.g. an Energy story that also touches Technology,
    Automotive, Banking), and pulling companies from all of them would flood
    a narrow "energy stocks" search with irrelevant Technology/Banking
    names. Only the sector(s) that overlap the query's own terms qualify.
    """
    from app.api.companies import _NSE_UNIVERSE
    relevant = [s for s in sectors if s and any(t in s.lower() or s.lower() in t for t in terms)]
    wanted = {s.lower() for s in relevant}
    if not wanted:
        return []
    return [co for co in _NSE_UNIVERSE if (co.get("sector") or "").lower() in wanted]


async def compute_recommendations(db, terms: list[str], pick_count: int) -> list[dict]:
    from app.services.opportunity_service import OpportunityService

    opps = await OpportunityService(db).list_by_sector_or_theme(terms[:6], limit=10) if terms else []
    if not opps:
        return []

    term_set = {t.lower() for t in terms if t}
    candidates: dict[str, dict] = {}
    for opp in sorted(opps, key=lambda o: o.get("opportunity_score") or 0, reverse=True):
        for co in _companies_in_sectors(opp.get("sectors") or [], term_set):
            sym = co["symbol"]
            if sym in candidates:
                continue
            candidates[sym] = {
                "symbol":            sym,
                "name":              co["name"],
                "sector":            co.get("sector"),
                "opportunity_score": opp.get("opportunity_score"),
                "confidence":        opp.get("confidence"),
                "trend":             opp.get("trend"),
                "risk_level":        opp.get("risk_level"),
                "reason":            opp.get("title"),
                "basis":             "computed",
            }

    ranked = sorted(candidates.values(), key=lambda c: c["opportunity_score"] or 0, reverse=True)
    return ranked[:pick_count]
