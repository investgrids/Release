"""
Pure, deterministic company<->evidence matching rules — the one shared
place both the V3 pipeline (pipeline.py's fail-closed degraded-response
builder) and AEV2 (aev2/citation_validator.py's claim-evidence
attribution) derive "which retrieved evidence is genuinely tied to
these resolved companies" from, so the two can never silently drift
into two different matching rules.

Zero I/O, zero DB access, zero imports beyond the standard library —
pure functions over already-retrieved dicts. This is what makes it safe
for aev2/ to import despite living in the same package as the real
retrieval code: it does no retrieval itself, only matches structured
fields two callers already have in hand.
"""
from __future__ import annotations


def event_company_symbols(event: dict) -> set[str]:
    """An event's own structured `companies` field (set at ingestion,
    ~93% coverage — see retrieval.py's _search_events), uppercased."""
    return {
        (c.get("symbol") or "").upper()
        for c in (event.get("companies") or [])
        if isinstance(c, dict) and c.get("symbol")
    }


def filter_events_to_companies(events: list[dict], symbols: list[str] | set[str]) -> list[dict]:
    """Only events whose own structured `companies` field names one of
    `symbols` — the one real, deterministic company<->event link this
    codebase has, never a text/keyword match. Never applied to news/
    policy rows, which carry no company field at all today."""
    wanted = {s.upper() for s in symbols if s}
    if not wanted:
        return []
    return [e for e in events if event_company_symbols(e) & wanted]


def filter_announcements_to_companies(announcements: list[dict], symbols: list[str] | set[str]) -> list[dict]:
    """CompanyAnnouncement rows carry a direct `symbol` column (set at
    ingestion from the NSE/BSE feed itself) — an even more direct match
    than events' companies list, no ambiguity about which company a row
    belongs to."""
    wanted = {s.upper() for s in symbols if s}
    if not wanted:
        return []
    return [a for a in announcements if (a.get("symbol") or "").upper() in wanted]
