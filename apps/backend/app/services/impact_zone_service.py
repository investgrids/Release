"""
Sector Setup + Companies In Focus (2026-08 Pre-Market rebuild, Part A4).

Replaces market.py's old synthetic `stocks_to_watch` (a score derived from
mere gainer/loser list membership, with a hardcoded 5-stock fallback) with
intelligence-driven output:

- sector_setup: theme momentum data, relabeled HONESTLY (a momentum
  reading, not a forward-looking "Expected Outperform" claim the
  calculation doesn't support), optionally enriched with a qualitative
  Intelligence Graph tag when a genuine propagation path exists from an
  active development.
- companies_in_focus: derived SOLELY from Development.companies (the
  canonical source per the plan's explicit refinement — Intelligence
  Graph company-node coverage is confirmed too sparse to trust, even as
  enrichment, for company-level output).

Per the plan's third refinement: ripple_from_node()'s accumulated_weight
is used only as an internal ranking/tie-break signal, NEVER rendered as a
raw decimal — the UI gets a qualitative "Direct impact"/"Secondary
impact" tag or plain ordering instead, the same principle that fixed the
earlier unexplained-0.8-score class of bug elsewhere on this page.
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

_MOMENTUM_LABEL = {
    "rising":  "Strong momentum",
    "falling": "Weak momentum",
    "stable":  "Neutral momentum",
}

# How many of the top (already importance-ranked) developments to try
# graph enrichment for, and how many of each development's own sectors
# to try as ripple sources — kept small since this is best-effort
# enrichment, not the primary signal (sector_setup stands on theme
# momentum data alone regardless of whether any of this matches).
_MAX_DEVELOPMENTS_FOR_ENRICHMENT = 2
_MAX_SECTORS_PER_DEVELOPMENT = 2


async def build_sector_setup(themes: list[dict], developments: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for t in themes:
        momentum = t.get("momentum")
        rows.append({
            "sector":      t.get("theme"),
            "label":       _MOMENTUM_LABEL.get(momentum, "Neutral momentum"),
            "momentum":    momentum,
            "score":       t.get("score"),
            "impact_tag":  None,
            "impact_source": None,
        })

    try:
        from app.services.intelligence_graph_service import make_node_id, ripple_from_node
    except Exception as exc:
        log.warning("impact_zone.graph_import_error", error=str(exc)[:200])
        return rows

    by_sector = {r["sector"]: r for r in rows if r["sector"]}
    for dev in developments[:_MAX_DEVELOPMENTS_FOR_ENRICHMENT]:
        change = "rise" if dev.get("direction") == "positive" else "fall"
        for sector_name in (dev.get("sectors") or [])[:_MAX_SECTORS_PER_DEVELOPMENT]:
            try:
                node_id = make_node_id("sector", sector_name)
                result = await ripple_from_node(node_id, change=change)
            except Exception as exc:
                log.warning("impact_zone.ripple_error", sector=sector_name, error=str(exc)[:200])
                continue
            for impact in result.get("impacts", []):
                node = impact.get("node") or {}
                if node.get("type") != "sector":
                    continue
                row = by_sector.get(node.get("label"))
                # First (highest-ranked) match wins per sector — don't
                # overwrite an already-tagged row with a weaker one.
                if row and not row["impact_tag"]:
                    row["impact_tag"] = "Direct impact" if impact.get("depth", 99) <= 1 else "Secondary impact"
                    row["impact_source"] = dev.get("title")
    return rows


def build_companies_in_focus(developments: list[dict], limit: int = 8) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for dev in developments:
        for symbol in (dev.get("companies") or []):
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            rows.append({
                "symbol":    symbol,
                "reason":    dev.get("title"),
                "direction": dev.get("direction"),
            })
            if len(rows) >= limit:
                return rows
    return rows
