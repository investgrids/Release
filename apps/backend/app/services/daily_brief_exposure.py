"""Investor implications that do not depend on event-triage sector tags, wired to the app's own data.

Three separate things, never blended:
  1. VERIFIED SECTOR PERFORMANCE: what the sector indices actually did in the session (from the sector index quotes the brief already holds).
  2. EVIDENCE-BACKED EXPOSURE: (a) sectors of companies that the day's developments name, from the company master (only where a sector is
     recorded there); (b) typical exposure to a market variable that verifiably or reportedly moved (rupee, crude, yields), read from the
     knowledge graph (see daily_brief_graph.py): each sector comes with the graph edge's weight, confidence, lag and written rationale.
  3. OVERLAP: where an exposed sector's verified move agreed or disagreed with the typical exposure. An observation only; a sector that moved
     against its typical exposure is reported as such, and nothing here says that a development caused a move.

Pure functions: no network, no DB, no LLM. The graph context is passed in; with no graph there is simply no exposure row.
"""
from __future__ import annotations

import re

from app.services.daily_brief_composer import FLAT_PCT, parse_pct
from app.services.daily_brief_drivers import _SECTOR_ALIASES, _canon_sector

SOURCE_SECTOR_INDEX = "Sector index quotes from the market data provider"

# Display wording for the tracked variables (interface copy; the sectors and rationales come from the graph).
VARIABLE_LABELS = {
    "rupee_stronger": "Rupee strengthens", "rupee_weaker": "Rupee weakens",
    "crude_rising": "Higher crude oil prices", "crude_falling": "Lower crude oil prices",
    "yields_rising": "Bond yields rise", "yields_falling": "Bond yields fall",
}

_YIELD_UP = re.compile(r"(yields?\s+(rise|rises|rose|jump|jumps|surge|surges|spike|spikes|climb|climbs|harden|hardens)|bonds?\b.*\b(worst day|fall|falls|fell|slump|slumps|sell-?off|weigh|weighs|tumble|slide|slides)|weigh\w*\s+on\s+(govt|government)?\s*bonds?)", re.I)
_YIELD_DOWN = re.compile(r"(yields?\s+(fall|falls|fell|ease|eases|eased|drop|drops|dropped|slide|slides|cool|cools)|bonds?\b.*\b(rally|rallies|gain|gains|best day|surge|surges))", re.I)


def sector_performance(sectors: list[dict] | None, *, as_of_label: str, top: int = 3) -> dict:
    """Leaders and laggards by the sector indices' own moves. Always available when the sector quotes are."""
    rows = []
    for s in sectors or []:
        pct = parse_pct(s.get("value"))
        if s.get("name") and pct is not None:
            rows.append((s["name"], pct))
    if not rows:
        return {"available": False, "leaders": [], "laggards": [], "as_of": as_of_label, "source": SOURCE_SECTOR_INDEX,
                "note": "Sector index quotes are unavailable right now."}
    ordered = sorted(rows, key=lambda r: r[1])
    laggards = [{"name": n, "pct": p} for n, p in ordered[:top] if p < 0]
    leaders = [{"name": n, "pct": p} for n, p in reversed(ordered[-top:]) if p > 0]
    return {"available": True, "leaders": leaders, "laggards": laggards, "as_of": as_of_label, "source": SOURCE_SECTOR_INDEX,
            "tracked": len(rows), "note": None}


def _variables(facts: list[dict], driver_headlines: list[tuple[str, str | None]]) -> list[dict]:
    """The market variables that moved, each with how we know. Rupee and crude are verified from the market data; yields are only ever
    'reported' (taken from a source headline) because the brief holds no yield feed."""
    found: list[dict] = []
    for f in facts:
        d = (f.get("direction") or "").lower()
        if f.get("entity_key") == "USD_INR" and d in ("up", "down"):
            found.append({"key": "rupee_weaker" if d == "up" else "rupee_stronger", "evidence": "verified",
                          "observed": f"USD/INR {'higher' if d == 'up' else 'lower'} at {f.get('value')}", "source": f.get("source"),
                          "observed_at": f.get("observed_at")})
        elif f.get("entity_key") == "BRENT_CRUDE" and d in ("rising", "falling", "up", "down"):
            up = d in ("rising", "up")
            found.append({"key": "crude_rising" if up else "crude_falling", "evidence": "verified",
                          "observed": f"Brent crude {'rising' if up else 'falling'} at {f.get('value')}", "source": f.get("source"),
                          "observed_at": f.get("observed_at")})
    for headline, source in driver_headlines:
        if _YIELD_UP.search(headline):
            found.append({"key": "yields_rising", "evidence": "reported", "observed": f"Reported: {headline}", "source": source, "observed_at": None})
            break
        if _YIELD_DOWN.search(headline):
            found.append({"key": "yields_falling", "evidence": "reported", "observed": f"Reported: {headline}", "source": source, "observed_at": None})
            break
    return found


def build_exposure(*, sectors: list[dict] | None, smoves: dict[str, tuple[str, float]], facts: list[dict], drivers: dict,
                   as_of_label: str, company_sectors: dict[str, str] | None = None, graph=None, vocabulary: list[str] | None = None) -> dict:
    """The parts of the implications (sector performance, exposure, overlap, sectors named) plus company links by sector."""
    perf = sector_performance(sectors, as_of_label=as_of_label)
    headlines = [(it["headline"], it.get("source")) for it in drivers.get("items", []) if it.get("evidence_label") != "commentary"]
    variables = _variables(facts, headlines)

    exposure, overlap, notes = [], [], []
    for v in variables:
        graph_row = graph.exposure(v["key"]) if graph is not None else None
        if graph_row is None:
            notes.append(f"The knowledge graph records no sector exposure for '{VARIABLE_LABELS[v['key']].lower()}', so none is shown.")
            continue
        exposure.append({"variable": v["key"], "label": VARIABLE_LABELS[v["key"]], "evidence": v["evidence"], "observed": v["observed"],
                         "source": v.get("source"), "observed_at": v.get("observed_at"), "pressured": graph_row["pressured"], "helped": graph_row["helped"],
                         "basis": graph_row["basis"], "node": graph_row["node_id"]})
        for kind in ("pressured", "helped"):
            for item in graph_row[kind]:
                canon = _canon_sector(item["sector"])
                moved = smoves.get(canon) if canon else None
                if not moved or abs(moved[1]) < FLAT_PCT:
                    continue
                idx_name, pct = moved
                agrees = (pct < 0) == (kind == "pressured")
                overlap.append({
                    "sector": idx_name, "verified_move_pct": pct, "variable": v["key"], "typical": kind, "agrees": agrees,
                    "text": (f"{idx_name} is typically {kind} by this; its index moved {pct:+.2f}% in the session, "
                             f"{'in line with' if agrees else 'against'} that typical exposure. An observation, not an attribution."),
                })

    companies: dict[str, dict] = {}
    for it in drivers.get("items", []):
        for c in it.get("companies", []):
            sector = (company_sectors or {}).get(c["symbol"])
            if not sector:
                continue
            row = companies.setdefault(sector, {"sector": sector, "companies": [], "developments": []})
            if c["symbol"] not in row["companies"]:
                row["companies"].append(c["symbol"])
            if it["headline"] not in row["developments"]:
                row["developments"].append(it["headline"])
    company_links = [{"sector": r["sector"], "companies": r["companies"][:5], "via": r["developments"][:2],
                      "basis": "Named in the development; sector from the company master (not an assessment of impact)"} for r in companies.values()]

    if not variables:
        notes.append("No market variable (rupee, crude, yields) moved enough to describe general exposure.")
    if not company_links:
        notes.append("No development names a company with a recorded sector.")
    return {"sector_performance": perf, "exposure": exposure, "overlap": overlap, "company_links": company_links, "exposure_notes": notes,
            "sectors_mentioned": sectors_mentioned(drivers, company_links, vocabulary=vocabulary, index_names=[n for n, _ in smoves.values()])}


# ── sectors named in the developments themselves ───────────────────────────────────────────────────────────────────

def _term_regex(term: str) -> re.Pattern:
    """Whole-word match, plural-tolerant. Case-sensitive for short or all-caps terms ('IT'), so the pronoun 'it' is never a sector."""
    body = re.escape(term.strip())
    flags = 0 if (len(term) <= 3 or term.isupper()) else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z]){body}(?:s|es)?(?![A-Za-z])", flags)


def _vocabulary_terms(vocabulary: list[str] | None, index_names: list[str] | None) -> dict[str, list[str]]:
    """display name -> search terms. Names come from the graph's own sector labels and the sector index names the brief already holds; the
    alias table only joins different spellings of the same sector (banks/banking, real estate/realty)."""
    names: dict[str, list[str]] = {}
    for label in list(vocabulary or []) + list(index_names or []):
        names.setdefault(label, [label])
    for display in list(names):
        canon = _canon_sector(display)
        if canon:
            for alias in _SECTOR_ALIASES.get(canon, ()):
                if alias not in {t.lower() for t in names[display]}:
                    names[display].append(alias)
    return names


def sectors_mentioned(drivers: dict, company_sectors_links: list[dict] | None = None, *, vocabulary: list[str] | None = None,
                      index_names: list[str] | None = None) -> list[dict]:
    """Sectors that the developments themselves name: in the headline text, in a recorded event sector tag, or as the company-master sector of
    a named company. Shows exposure to the news, not an observed sector move. Each entry says where it was found."""
    terms = _vocabulary_terms(vocabulary, index_names)
    patterns = {name: [_term_regex(t) for t in ts if len(t.strip()) >= 2] for name, ts in terms.items()}
    found: dict[str, dict] = {}
    for it in drivers.get("items", []):
        if it.get("evidence_label") == "commentary":
            continue
        for name, rxs in patterns.items():
            if any(rx.search(it.get("headline") or "") for rx in rxs):
                found.setdefault(name, {"name": name, "via": []})["via"].append({"basis": "headline", "headline": it["headline"]})
        for s in it.get("sectors", []):
            if s.get("name"):
                found.setdefault(s["name"], {"name": s["name"], "via": []})["via"].append({"basis": "event sector tag", "headline": it["headline"]})
    for link in company_sectors_links or []:
        found.setdefault(link["sector"], {"name": link["sector"], "via": []})["via"].append({"basis": "company master", "headline": ", ".join(link["companies"])})
    # one entry per sector even if the vocabulary spelt it two ways (Banking / Banks)
    by_canon: dict[str, dict] = {}
    for entry in found.values():
        canon = _canon_sector(entry["name"]) or entry["name"].lower()
        if canon in by_canon:
            have = {(v["basis"], v["headline"]) for v in by_canon[canon]["via"]}
            by_canon[canon]["via"].extend(v for v in entry["via"] if (v["basis"], v["headline"]) not in have)   # same sector spelt two ways: one entry, every place it was found
        else:
            by_canon[canon] = entry
    return list(by_canon.values())[:8]
