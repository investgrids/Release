"""
Today's example questions for the AI Search landing page (Step 6).

The "Try" questions should follow the live market instead of being the same four every day. Built deterministically from two live sources and NO model call:
  * the sector moves of the day (market_data.get_sector_changes)
  * the live news snapshot (news_fetcher.get_live_news): company-tagged headlines and rupee / crude headlines

Every live suggestion is checked against the real entity resolver, so a chip only ever offers a question the pipeline recognises (a sector the resolver knows, a company in the registry, a macro driver the router
handles). Each carries a short `note` stating the live fact it came from (for example "Banking -1.2% today" or the headline), so nothing is implied that the data does not say. When live data is thin the list is
topped up with evergreen questions, marked `kind: "evergreen"` and with no note. Cached for a few minutes; a failure of either source degrades to the other, never to an error.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

LIVE_TTL_S = 600
_CACHE: dict = {"at": 0.0, "value": None}

EVERGREEN = [
    "Compare HDFC Bank and ICICI Bank",
    "What does FII selling mean for the Indian market?",
    "How does the MarketRipple Score work?",
    "What is a P/E ratio and how should I read it?",
]

_RUPEE_WEAK = re.compile(r"\b(?:rupee|usd/?inr)\b.*\b(?:weak\w*|fall\w*|slip\w*|slump\w*|record low|pressure|depreciat\w*|intervene\w*|dollar)\b|\b(?:weak\w*|fall\w*|slip\w*|depreciat\w*)\b.*\brupee\b", re.IGNORECASE)
_CRUDE_UP = re.compile(r"\b(?:crude|brent|oil prices?)\b.*\b(?:rise\w*|rall\w*|surg\w*|jump\w*|spik\w*|higher|climb\w*|gain\w*)\b|\b(?:rise\w*|surg\w*|jump\w*|spik\w*|climb\w*)\b.*\b(?:crude|brent|oil prices?)\b", re.IGNORECASE)


def _clean(text: str | None) -> str:
    """Some feeds arrive double-encoded (for example a curly apostrophe read as latin-1); repair it, and collapse whitespace. Anything that does not round-trip is left as it was."""
    t = text or ""
    for enc in ("cp1252", "latin-1"):
        try:
            t = t.encode(enc).decode("utf-8")
            break
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return re.sub(r"\s+", " ", t).strip()


def _pct(value: str | None) -> float | None:
    m = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", value or "")
    return float(m.group(1)) if m else None


def _resolves(query: str, *, company: bool = False, sector: bool = False) -> bool:
    """The question must resolve to the entity it names, using the same extractor the pipeline uses."""
    from app.services.ai_search import entities as entities_mod
    ents = entities_mod.extract_entities(query)
    if company:
        return bool(ents.get("companies"))
    if sector:
        return bool(ents.get("sectors")) and not ents.get("companies")
    return True


def build_suggestions(sector_rows: list[dict] | None, live_news: list[dict] | None, *, now: datetime | None = None, limit: int = 6) -> dict:
    now = now or datetime.now(timezone.utc)
    items: list[dict] = []
    seen: set[str] = set()

    def add(query: str, kind: str, note: str | None) -> None:
        if query not in seen and len(items) < limit:
            seen.add(query)
            items.append({"query": query, "kind": kind, "note": note})

    # 1. The day's strongest sector move in each direction.
    moves = [(r, _pct(r.get("value"))) for r in (sector_rows or []) if r.get("name")]
    moves = [(r, p) for r, p in moves if p is not None and abs(p) >= 0.3]
    for r, p in sorted([m for m in moves if m[1] > 0], key=lambda m: -m[1])[:1] + sorted([m for m in moves if m[1] < 0], key=lambda m: m[1])[:1]:
        q = f"What is driving the {r['name']} sector today?"
        if _resolves(q, sector=True):
            add(q, "sector", f"{r['name']} {p:+.1f}% today")

    # 2. Companies in today's headlines (one headline each, distinct companies).
    used: set[str] = set()
    for n in live_news or []:
        for name in n.get("companies") or []:
            if name in used:
                continue
            q = f"What is happening with {name}?"
            if _resolves(q, company=True):
                used.add(name)
                add(q, "company", "In the news: " + _clean(n.get("headline"))[:90])
                break
        if len(used) >= 2:
            break

    # 3. Macro drivers that today's headlines are actually about.
    for n in live_news or []:
        h = _clean(n.get("headline"))
        if _RUPEE_WEAK.search(h):
            add("How would a weaker rupee affect Indian IT exporters?", "macro", "In the news: " + h[:90])
            break
    for n in live_news or []:
        h = _clean(n.get("headline"))
        if _CRUDE_UP.search(h):
            add("How would higher crude oil prices affect Indian markets?", "macro", "In the news: " + h[:90])
            break

    # 4. Top up with evergreen questions (no live claim attached).
    for q in EVERGREEN:
        add(q, "evergreen", None)
    return {"as_of": now.isoformat(), "live_count": sum(1 for i in items if i["kind"] != "evergreen"), "items": items}


async def get_suggestions(*, force: bool = False) -> dict:
    """Cached for LIVE_TTL_S. Either source failing leaves the other (and the evergreen top-up) in place."""
    now = time.time()
    if not force and _CACHE["value"] is not None and now - _CACHE["at"] < LIVE_TTL_S:
        return _CACHE["value"]
    rows, news = [], []
    try:
        from app.services.market_data import get_sector_changes
        rows = await get_sector_changes() or []
    except Exception:
        rows = []
    try:
        from app.services.news_fetcher import get_live_news
        news = await get_live_news(limit=40) or []
    except Exception:
        news = []
    value = build_suggestions(rows, news)
    _CACHE["at"], _CACHE["value"] = now, value
    return value
