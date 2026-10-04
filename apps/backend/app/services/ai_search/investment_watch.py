"""
Investment Watch (Phase 2B) — the ChatGPT-endorsed merge of "Monitoring
Dashboard" and "Verdict Change Explainer" into one panel (see this
session's prioritization thread). Two real, already-existing data sources
do all the work — nothing here is fabricated:

  - AISearchVerdictSnapshot (new model, this phase) — one row per
    (subject, day), written by pipeline.py after every non-degraded V3
    response that resolves to exactly one subject. Powers "Current
    Verdict" and "Last Change".
  - calendar_events (real, DB-backed, admin-curated — RBI meetings,
    earnings dates, budget sessions; already used by
    GET /api/market/calendar) plus live Brent crude + FII/DII data
    (app.api.market's own cached helpers, reused directly rather than
    re-fetched). Powers "Watching" and "Next Possible Trigger".

Never invents a trigger, a date, or a verdict — every item traces to a
real DB row or a real live market fetch. When a subject can't be resolved
(a query names 0 or 2+ companies, or a sector alongside companies), the
whole panel is simply omitted rather than guessing what to watch.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_search_verdict_snapshot import AISearchVerdictSnapshot

_CALENDAR_KEYWORD_CATEGORIES = {"RBI", "Results", "Government", "Macro", "Global"}


def subject_for(entities: dict, companies_enriched: list[dict]) -> dict | None:
    """Resolves this response to exactly one watchable subject, or None.
    Deliberately reads `entities` — the companies/sectors resolved from the
    QUERY TEXT ITSELF (entities.py's extract_entities, same source
    session_context.py trusts) — not response["companies"], which is the
    specialist's own output and routinely includes same-sector peers even
    for a single-company query (verified live: "outlook for HAL stock"
    still returned HAL/BEL/TATAMOTORS in companies[]). A comparison query
    ("HAL vs BEL") names two companies in the query text and gets no watch
    panel at all, rather than picking one arbitrarily (same "never guess"
    principle as session_context.py's ambiguous-group check)."""
    q_companies = entities.get("companies") or []
    q_sectors = entities.get("sectors") or []
    if len(q_companies) == 1:
        symbol = q_companies[0]
        enriched = next((c for c in companies_enriched if c.get("symbol") == symbol), None)
        return {
            "subject_key": f"company:{symbol}",
            "subject_type": "company",
            "subject_label": symbol,
            "company_name": (enriched or {}).get("name") or symbol,
        }
    if not q_companies and len(q_sectors) == 1:
        name = q_sectors[0]
        return {
            "subject_key": f"sector:{name.lower()}",
            "subject_type": "sector",
            "subject_label": name,
            "company_name": None,
        }
    return None


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def record_snapshot(
    db: AsyncSession, subject: dict, query: str, response_id: str,
    verdict_scale: str | None, rating: str | None, confidence: int, why: str | None,
) -> None:
    """Upserts today's snapshot for this subject. Fire-and-forget from the
    caller's perspective — any failure here must never affect the actual
    search response, so the caller wraps this in try/except."""
    today = _today()
    existing = (await db.execute(
        select(AISearchVerdictSnapshot).where(
            AISearchVerdictSnapshot.subject_key == subject["subject_key"],
            AISearchVerdictSnapshot.snapshot_date == today,
        )
    )).scalar_one_or_none()

    if existing:
        existing.query = query
        existing.response_id = response_id
        existing.verdict_scale = verdict_scale
        existing.rating = rating
        existing.confidence = confidence
        existing.why = why
    else:
        db.add(AISearchVerdictSnapshot(
            subject_key=subject["subject_key"], subject_type=subject["subject_type"],
            subject_label=subject["subject_label"], query=query, response_id=response_id,
            verdict_scale=verdict_scale, rating=rating, confidence=confidence, why=why,
            snapshot_date=today,
        ))
    await db.commit()


def _age_days(snapshot_date: str | None) -> int | None:
    """Whole days since the verdict snapshot (None if the date does not parse); drives the page's "this view may be out of date" note."""
    try:
        return max((datetime.now(timezone.utc).date() - datetime.strptime(str(snapshot_date)[:10], "%Y-%m-%d").date()).days, 0)
    except (ValueError, TypeError):
        return None


def _parse_calendar_date(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw.strip(), "%b %d, %Y").replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


async def _relevant_calendar_rows(db: AsyncSession) -> list[dict]:
    """Every real, future calendar_events row (see api/market.py's own
    /calendar route — same DB table, same data), parsed and date-sorted."""
    from app.db import models_legacy as legacy_models

    rows = (await db.execute(select(legacy_models.CalendarEvent))).scalars().all()
    today = datetime.now(timezone.utc)
    out = []
    for r in rows:
        dt = _parse_calendar_date(r.date)
        if dt is None or dt < today:
            continue
        out.append({
            "category": r.category, "title": r.title, "date": r.date,
            "description": r.description, "_dt": dt,
            "days_until": (dt.date() - today.date()).days,
        })
    out.sort(key=lambda e: e["_dt"])
    return out


def _keyword_match(row: dict, subject: dict) -> bool:
    label = subject["subject_label"].lower()
    name = (subject.get("company_name") or "").lower()
    text = (row["title"] + " " + row["description"]).lower()
    if subject["subject_type"] == "company":
        first_word = name.split()[0] if name else ""
        return label.lower() in text or (len(first_word) > 3 and first_word in text)
    return label in text


# What is watched for a company depends on its sector: crude oil is an input cost for an airline or a paint maker and irrelevant to an IT services firm, while the
# rupee and US tech spending matter to IT exporters. Each indicator is a live Yahoo quote (cached 15 minutes) shown only when the quote is real; "why" is the
# standard economic link, stated in one plain sentence. FII flows are market-wide and always shown when available.
_CRUDE = ("Crude oil (Brent)", "BZ=F", "usd", "an input cost: higher crude tends to squeeze margins")
_USDINR = ("US dollar / rupee", "INR=X", "inr", "export earnings are in dollars: a weaker rupee tends to lift margins")
_NIFTY = ("Nifty 50", "^NSEI", "index", "the broad market the stock trades against")
_SECTOR_WATCH: dict[str, list[tuple]] = {
    "technology": [_USDINR, ("Nasdaq", "^IXIC", "index", "US tech spending and sentiment drive IT services demand"), ("Nifty IT", "^CNXIT", "index", "the sector index this stock is part of")],
    "pharmaceuticals": [_USDINR, ("Nifty Pharma", "^CNXPHARMA", "index", "the sector index this stock is part of")],
    "healthcare": [("Nifty Pharma", "^CNXPHARMA", "index", "the healthcare and pharma index"), _NIFTY],
    "banking": [("Nifty Bank", "^NSEBANK", "index", "the sector index this stock is part of"), _NIFTY],
    "finance": [("Nifty Bank", "^NSEBANK", "index", "the lending sector's index"), _NIFTY],
    "automotive": [_CRUDE, ("Nifty Auto", "^CNXAUTO", "index", "the sector index this stock is part of")],
    "fmcg": [_CRUDE, ("Nifty FMCG", "^CNXFMCG", "index", "the sector index this stock is part of")],
    "consumer": [_CRUDE, _NIFTY],
    "metals": [("Nifty Metal", "^CNXMETAL", "index", "the sector index this stock is part of"), _USDINR],
    "energy": [_CRUDE, ("Nifty Energy", "^CNXENERGY", "index", "the sector index this stock is part of")],
    "chemicals": [_CRUDE, _USDINR],
    "power": [("Nifty Energy", "^CNXENERGY", "index", "the sector index this stock is part of"), _NIFTY],
}
_DEFAULT_WATCH = [_NIFTY, _CRUDE]


def watch_specs(sector: str | None) -> list[tuple]:
    """The indicators to watch for a sector (case-insensitive); the broad market and crude when the sector has no specific list."""
    return list(_SECTOR_WATCH.get((sector or "").strip().lower(), _DEFAULT_WATCH))


def quote_trigger(spec: tuple, quote: dict | None) -> dict | None:
    """One watch row from a live quote, or None when there is no real quote. Flat means a move under 0.05%."""
    if not quote:
        return None
    label, _ticker, kind, why = spec
    pct = quote["pct"]
    status = "flat" if abs(pct) < 0.05 else ("rising" if pct > 0 else "falling")
    value = {"usd": f"${quote['price']:.2f}/bbl", "inr": f"₹{quote['price']:.2f} per US$", "index": f"{quote['price']:,.0f}"}.get(kind, f"{quote['price']:.2f}")
    move = "0.0%" if status == "flat" else f"{pct:+.1f}%"   # never "-0.0%"
    return {"label": label, "status": status, "detail": f"{value} ({move})", "why": why[0].upper() + why[1:] + ".", "scope": "sector"}


async def _macro_triggers(sector: str | None = None) -> list[dict]:
    """Sector-relevant live indicators plus FII/DII flow, reusing api/market.py's cached fetchers (same cache they already use, so this costs little)."""
    import asyncio
    from app.api.market import _yf_quote, _fetch_fii_dii, _cached_sync

    loop = asyncio.get_running_loop()
    specs = watch_specs(sector)

    async def one(spec):
        try:
            return quote_trigger(spec, await loop.run_in_executor(None, lambda: _cached_sync(f"iw_{spec[1]}", 900, lambda: _yf_quote(spec[1]))))
        except Exception:
            return None

    async def flows():
        try:
            return await loop.run_in_executor(None, lambda: _cached_sync("fii_dii", 21600, _fetch_fii_dii))
        except Exception:
            return {"available": False}

    results = await asyncio.gather(*[one(sp) for sp in specs], flows())
    triggers = [t for t in results[:-1] if t]
    fii_dii = results[-1]
    if fii_dii.get("available") and fii_dii.get("fii_net") is not None:
        selling = fii_dii["fii_net"] < 0
        triggers.append({
            "label": "Foreign investor (FII) flows",
            "status": "selling" if selling else "buying",
            "detail": f"{'-' if selling else '+'}₹{abs(fii_dii['fii_net']):,.0f} Cr, previous session",
            "why": "Heavy foreign selling tends to weigh on large, widely held stocks.", "scope": "market",
        })
    return triggers


def pick_next_trigger(subject_rows: list[dict], calendar_rows: list[dict]) -> dict | None:
    """The next dated event for THIS subject if there is one; otherwise the next market-wide event (RBI, macro, government, global). Another company's
    results date is never offered as this company's trigger."""
    if subject_rows:
        n, scope = subject_rows[0], "company"
    else:
        market = [r for r in calendar_rows if r.get("category") != "Results"]
        if not market:
            return None
        n, scope = market[0], "market"
    return {"label": n["title"], "category": n["category"], "date": n["date"], "days_until": n["days_until"], "description": n["description"], "scope": scope}


async def get_watch(db: AsyncSession, subject_key: str, subject_label_hint: str | None = None) -> dict | None:
    """Assembles the full Investment Watch panel for a subject_key
    (e.g. "company:HAL" or "sector:defence"). Returns None only when
    there's no snapshot history at all for this subject yet (first-ever
    search for it) — the "Watching"/"Next Trigger" sections still need a
    Current Verdict to anchor to."""
    snapshots = (await db.execute(
        select(AISearchVerdictSnapshot)
        .where(AISearchVerdictSnapshot.subject_key == subject_key)
        .order_by(AISearchVerdictSnapshot.snapshot_date.desc())
        .limit(2)
    )).scalars().all()
    if not snapshots:
        return None

    current = snapshots[0]
    last_change = None
    if len(snapshots) == 2 and snapshots[1].verdict_scale != current.verdict_scale:
        last_change = {
            "from": snapshots[1].verdict_scale, "to": current.verdict_scale,
            "from_date": snapshots[1].snapshot_date, "to_date": current.snapshot_date,
            "why": current.why,
        }

    subject_type = "company" if subject_key.startswith("company:") else "sector"
    company_name = None
    if subject_type == "company":
        from app.api.companies import _NSE_UNIVERSE
        symbol = subject_key.split(":", 1)[-1]
        company_name = next((co["name"] for co in _NSE_UNIVERSE if co["symbol"] == symbol), None)

    subject = {
        "subject_key": subject_key,
        "subject_type": subject_type,
        "subject_label": current.subject_label or subject_label_hint or subject_key.split(":", 1)[-1],
        "company_name": company_name,
    }

    calendar_rows = await _relevant_calendar_rows(db)
    subject_rows = [r for r in calendar_rows if _keyword_match(r, subject)]

    if subject_type == "company":
        from app.api.companies import _NSE_UNIVERSE
        sector_name = next((co.get("sector") for co in _NSE_UNIVERSE if co["symbol"] == subject_key.split(":", 1)[-1]), None)
    else:
        sector_name = subject["subject_label"]
    watching = await _macro_triggers(sector_name)
    if subject_rows:
        nearest = subject_rows[0]
        watching.insert(0, {
            "label": nearest["category"],
            "status": f"in {nearest['days_until']}d" if nearest["days_until"] > 0 else "today",
            "detail": nearest["title"], "why": nearest["description"] or "", "scope": "company",
        })

    next_trigger = pick_next_trigger(subject_rows, calendar_rows)

    return {
        "subject_key": subject_key,
        "subject_label": subject["subject_label"],
        "current_verdict": {
            "verdict_scale": current.verdict_scale, "confidence": current.confidence,
            "as_of": current.snapshot_date, "age_days": _age_days(current.snapshot_date),
        },
        "last_change": last_change,
        "watching": watching,
        "next_trigger": next_trigger,
    }
