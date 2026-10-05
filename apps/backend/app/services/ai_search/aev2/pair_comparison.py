"""
Shared, deterministic pair-comparison building blocks for AEV2
(2026-09-22) — the ONE place recent_developments/price_reaction/
evidence_freshness are computed from CoreAnswer, reused identically by
switch_analysis.py (current holding vs proposed alternative) and
comparison.py (left vs right, no holding relationship). Neither caller
duplicates this logic (approved spec, 2026-09-22: "Do not copy
switch_analysis.py — extract the common deterministic work").

Zero new retrieval, zero LLM calls, zero regeneration — a direct,
honest reformatting of company/event/announcement rows already sitting
on `core`.

Phase-one scope: only these 3 dimensions, because they're the only ones
CoreAnswer can back with real, per-company, structured data today:
  - recent_developments / evidence_freshness: company_matching.py's one
    real event<->company and announcement<->company relationship,
    filtered separately per company.
  - price_reaction: the same live Yahoo Finance price/change/
    price_fetched_at fields price_movement.py already reads, compared
    for both companies from the SAME response (so both were fetched in
    the same enrichment pass — the "identical measurement window" the
    spec requires).

business_exposure and risk_evidence are deliberately NOT implemented —
CoreAnswer's company dicts carry no verified sector/exposure field, and
CoreAnswer.risks has no per-company attribution at all. Both would need
a new, real per-company data source before they could be added.

Generic left_company/right_company field names — deliberately NOT
current_company/alternative_company, since that framing is
switch_analysis-specific. Callers relabel as needed:
  - switch_analysis.py: left -> current_company, right -> alternative_company
  - comparison.py: left -> left_company, right -> right_company (unchanged)
A `comparable: false` dimension never implies the missing side is worse
— `unavailable_reason` names which side lacks data, nothing more.
"""
from __future__ import annotations

from app.services.ai_search import company_matching
from app.services.ai_search.core_answer import CoreAnswer

DIMENSION_LABELS = {
    "recent_developments": "Recent developments",
    "price_reaction": "Price reaction",
    "evidence_freshness": "Evidence freshness",
}


def company_ref(company: dict) -> dict:
    return {"symbol": company.get("symbol"), "name": company.get("name") or company.get("symbol")}


def _attributed_items(core: CoreAnswer, symbol: str) -> list[tuple[dict, str]]:
    """Every real, company_matching.py-linked event/announcement for
    exactly one symbol — the same deterministic relationship citation_
    validator.py uses, just filtered to a single company instead of the
    whole resolved set. Each item is paired with its own evidence-catalog
    id (never guessed from the item's shape) so callers never need to
    re-derive which source list it came from."""
    wanted = {symbol.upper()}
    events = company_matching.filter_events_to_companies(list(core.related_events), wanted)
    announcements = company_matching.filter_announcements_to_companies(list(core.announcements), wanted)
    tagged = [(e, f"event:{e['id']}") for e in events if e.get("id") is not None]
    tagged += [(a, f"announcement:{a['id']}") for a in announcements if a.get("id") is not None]
    return tagged


def _item_date(item: dict) -> str | None:
    return item.get("date") or item.get("event_date") or item.get("announcement_date") or None


def _item_title(item: dict) -> str:
    return item.get("title") or item.get("subject") or ""


def _recent_developments_dimension(core: CoreAnswer, left: dict, right: dict) -> dict:
    left_items = _attributed_items(core, left["symbol"])
    right_items = _attributed_items(core, right["symbol"])

    def _value(items: list[tuple[dict, str]]) -> dict | None:
        if not items:
            return None
        # company_matching preserves retrieval order; the caller's own
        # evidence.collect() already orders by recency, so [0] is the
        # most recent — no new sort/heuristic introduced here.
        top, _ = items[0]
        refs = [ref for _, ref in items]
        return {"display": f"{len(items)} company-attributed development(s); most recent: {_item_title(top)}", "evidence_refs": refs}

    left_value = _value(left_items)
    right_value = _value(right_items)
    comparable = left_value is not None and right_value is not None
    result = {
        "key": "recent_developments", "label": DIMENSION_LABELS["recent_developments"],
        "left_company": left_value, "right_company": right_value,
        "evidence_refs": sorted({*(left_value or {}).get("evidence_refs", []), *(right_value or {}).get("evidence_refs", [])}),
        "comparable": comparable,
    }
    if not comparable:
        missing = left["symbol"] if left_value is None else right["symbol"]
        result["unavailable_reason"] = f"No company-attributed development found for {missing}"
    return result


def _price_reaction_dimension(left: dict, right: dict) -> dict:
    def _value(c: dict) -> dict | None:
        if not c.get("price_fetched_at") or c.get("price") in (None, "—"):
            return None
        return {"display": f"{c.get('price')} ({c.get('change')})", "evidence_refs": []}

    left_value = _value(left)
    right_value = _value(right)
    comparable = left_value is not None and right_value is not None
    result = {
        "key": "price_reaction", "label": DIMENSION_LABELS["price_reaction"],
        "left_company": left_value, "right_company": right_value,
        "evidence_refs": [],
        "comparable": comparable,
    }
    if not comparable:
        missing = left["symbol"] if left_value is None else right["symbol"]
        result["unavailable_reason"] = f"Live price data unavailable for {missing}"
    return result


def _evidence_freshness_dimension(core: CoreAnswer, left: dict, right: dict) -> dict:
    def _value(symbol: str) -> dict | None:
        items = _attributed_items(core, symbol)
        dates = [_item_date(it) for it, _ in items if _item_date(it)]
        if not dates:
            return None
        most_recent = max(dates)
        return {"display": most_recent, "evidence_refs": []}

    left_value = _value(left["symbol"])
    right_value = _value(right["symbol"])
    comparable = left_value is not None and right_value is not None
    result = {
        "key": "evidence_freshness", "label": DIMENSION_LABELS["evidence_freshness"],
        "left_company": left_value, "right_company": right_value,
        "evidence_refs": [],
        "comparable": comparable,
    }
    if not comparable:
        missing = left["symbol"] if left_value is None else right["symbol"]
        result["unavailable_reason"] = f"No dated evidence found for {missing}"
    return result


def build_pair_comparison_dimensions(core: CoreAnswer, left_company: dict, right_company: dict) -> list[dict]:
    """The one entry point both switch_analysis.py and comparison.py
    call — order of `left_company`/`right_company` is the caller's own
    (switch: current/alternative; comparison: the user's own entity
    order, never resorted), preserved verbatim into each dimension's
    left_company/right_company fields."""
    return [
        _recent_developments_dimension(core, left_company, right_company),
        _price_reaction_dimension(left_company, right_company),
        _evidence_freshness_dimension(core, left_company, right_company),
    ]
