"""
Deterministic company attribution for AEV2's companies_affected field —
grouped by TODAY'S REAL, LIVE price movement (Yahoo Finance, already
fetched once by V3's own enrichment.py::_enrich_sync), not by the
specialist's generated impact_type ("beneficiary"/"at_risk") judgment.
"currently higher" / "currently lower" is a fact about the market right
now; impact_type is the model's own narrative claim about WHY — AEV2's
Build 1 scope is the former only (see the approved spec's fields).

Zero new retrieval: reads price/positive/price_fetched_at, all already
sitting on CoreAnswer.companies because pipeline.py's _assemble_response
already ran _enrich_sync before this ever runs. A company is grouped as
"omitted_unattributed" — never guessed into higher/lower — whenever
either the price fetch failed (price == "—", enrichment.py's own
existing failure sentinel) or no price_fetched_at timestamp exists,
which is _enrich_sync's honest "no real fetch happened" signal.
"""
from __future__ import annotations


def build_price_movement_groups(companies: tuple[dict, ...]) -> dict:
    higher: list[dict] = []
    lower: list[dict] = []
    omitted: list[dict] = []

    for c in companies:
        symbol = c.get("symbol")
        if not symbol:
            continue
        fetched_at = c.get("price_fetched_at")
        price = c.get("price")
        if not fetched_at or price in (None, "—"):
            omitted.append({"symbol": symbol, "name": c.get("name", symbol)})
            continue
        entry = {
            "symbol": symbol,
            "name": c.get("name", symbol),
            "price": price,
            "change": c.get("change"),
            "fetched_at": fetched_at,
        }
        if c.get("positive"):
            higher.append(entry)
        else:
            lower.append(entry)

    return {"currently_higher": higher, "currently_lower": lower, "omitted_unattributed": omitted}
