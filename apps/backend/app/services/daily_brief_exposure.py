"""Investor implications that do not depend on event-triage sector tags.

Three separate things, never blended:
  1. VERIFIED SECTOR PERFORMANCE: what the sector indices actually did in the session (from the sector index quotes the brief already holds).
  2. EVIDENCE-BACKED EXPOSURE: (a) sectors of companies that the day's developments name, taken from the company master (only where a
     sector is recorded there); (b) general economic exposure to a market variable that verifiably or reportedly moved (rupee, crude, yields),
     from the short documented rule table below. This is background economics, not an observation about the session.
  3. OVERLAP: where an exposed sector's verified move agreed or disagreed with the typical exposure. Stated as an observation only; a sector
     that moved against its typical exposure is reported as such, and nothing here says that a development caused a move.

Pure functions: no network, no DB, no LLM.
"""
from __future__ import annotations

import re

from app.services.daily_brief_composer import FLAT_PCT, NEAR_FLAT_PCT, parse_pct

SOURCE_RULES = "General economic exposure (documented rule table), not derived from this session's data"
SOURCE_SECTOR_INDEX = "Sector index quotes from the market data provider"

# Sector index rows -> the exposure sector they speak for. Only real equivalences.
_INDEX_KEYS = {
    "IT": ("IT",), "Pharma": ("Pharma",), "Auto": ("Auto",), "Realty": ("Realty",), "FMCG": ("FMCG",), "Metal": ("Metal",),
    "Banking": ("Banking", "Private Bank", "PSU Bank"),
}

# variable -> {label, pressured: [...], helped: [...], why}. Typical, widely understood exposures. Conservative on purpose.
RULES: dict[str, dict] = {
    "rupee_stronger": {
        "label": "Stronger rupee (USD/INR lower)",
        "pressured": ["IT", "Pharma", "Textiles"], "helped": ["Aviation", "Paints & chemicals", "Oil marketing companies"],
        "why": "Export earners translate foreign revenue into fewer rupees; import-heavy businesses pay less in rupees for inputs and fuel.",
    },
    "rupee_weaker": {
        "label": "Weaker rupee (USD/INR higher)",
        "pressured": ["Aviation", "Paints & chemicals", "Oil marketing companies"], "helped": ["IT", "Pharma", "Textiles"],
        "why": "Import-heavy businesses pay more in rupees for inputs and fuel; export earners translate foreign revenue into more rupees.",
    },
    "crude_rising": {
        "label": "Rising Brent crude",
        "pressured": ["Aviation", "Paints & chemicals", "Logistics", "Oil marketing companies"], "helped": ["Upstream oil & gas"],
        "why": "Fuel and petro-derived inputs are major costs for these businesses; upstream producers realise higher prices.",
    },
    "crude_falling": {
        "label": "Falling Brent crude",
        "pressured": ["Upstream oil & gas"], "helped": ["Aviation", "Paints & chemicals", "Logistics", "Oil marketing companies"],
        "why": "Lower fuel and petro-derived input costs help these businesses; upstream producers realise lower prices.",
    },
    "yields_rising": {
        "label": "Rising bond yields (reported)",
        "pressured": ["Banking", "NBFCs", "Realty", "Auto"], "helped": [],
        "why": "Banks mark down bond holdings; rate-sensitive borrowers (property, vehicles) face higher financing costs.",
    },
    "yields_falling": {
        "label": "Falling bond yields (reported)",
        "pressured": [], "helped": ["Banking", "NBFCs", "Realty", "Auto"],
        "why": "Banks gain on bond holdings; rate-sensitive borrowers (property, vehicles) face lower financing costs.",
    },
}

_YIELD_UP = re.compile(r"(yields?\s+(rise|rises|rose|jump|jumps|surge|surges|spike|spikes|climb|climbs|harden|hardens)|bonds?\b.*\b(worst day|fall|falls|fell|slump|slumps|sell-?off|weigh|weighs|tumble|slide|slides)|weigh\w*\s+on\s+(govt|government)?\s*bonds?)", re.I)
_YIELD_DOWN = re.compile(r"(yields?\s+(fall|falls|fell|ease|eases|eased|drop|drops|dropped|slide|slides|cool|cools)|bonds?\b.*\b(rally|rallies|gain|gains|best day|surge|surges))", re.I)


def _canon_index_pct(smoves: dict[str, tuple[str, float]], sector: str) -> list[tuple[str, float]]:
    names = _INDEX_KEYS.get(sector) or ()
    return [(n, p) for n, p in smoves.values() if n in names]


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
                   as_of_label: str, company_sectors: dict[str, str] | None = None) -> dict:
    """The three parts of the implications (sector performance, exposure, overlap) plus company links by sector."""
    perf = sector_performance(sectors, as_of_label=as_of_label)
    headlines = [(it["headline"], it.get("source")) for it in drivers.get("items", []) if it.get("evidence_label") != "commentary"]
    variables = _variables(facts, headlines)

    exposure, overlap = [], []
    for v in variables:
        rule = RULES[v["key"]]
        row = {"variable": v["key"], "label": rule["label"], "evidence": v["evidence"], "observed": v["observed"], "source": v.get("source"),
               "observed_at": v.get("observed_at"), "pressured": rule["pressured"], "helped": rule["helped"], "why": rule["why"],
               "basis": SOURCE_RULES}
        exposure.append(row)
        for kind, names in (("pressured", rule["pressured"]), ("helped", rule["helped"])):
            for sector in names:
                for idx_name, pct in _canon_index_pct(smoves, sector):
                    if abs(pct) < NEAR_FLAT_PCT:
                        continue
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

    notes = []
    if not exposure:
        notes.append("No market variable (rupee, crude, yields) moved enough to describe general exposure.")
    if not company_links:
        notes.append("No development names a company with a recorded sector.")
    return {"sector_performance": perf, "exposure": exposure, "overlap": overlap, "company_links": company_links, "exposure_notes": notes}
