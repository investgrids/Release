"""
Fact Registry — computes a fact once per IST trading day and reuses it
everywhere the Daily Brief needs it, instead of the LLM re-deriving or
re-wording the same real number in several sections independently (the
audit's finding: crude oil worded five different ways across Hero/
Overnight/Wrap/Risk/WatchNext for what is one real number).

Two families, both built entirely from Phase 1's already-connected
engines — no new data source:
  - Market facts: real Nifty/BankNifty/Sensex/VIX from market_overview,
    real Brent crude/USD-INR/verdict from opening_prediction_service.
  - Event facts: the day's real Critical/High EventTriage rows, via the
    same Intelligence Priority Queue (compute_priority) already wired
    into /api/daily-brief/intelligence.

Each Fact row already IS its own evidence packet (claim + value + source
+ timestamp + confidence + affected entities) — there's no separate
Evidence table bolted on top of it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.fact import Fact

log = structlog.get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))
_TRACKED_INDICES = ("NIFTY 50", "BANK NIFTY", "SENSEX", "INDIA VIX")


def _today_ist() -> str:
    return datetime.now(_IST).strftime("%Y-%m-%d")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _upsert(db: AsyncSession, fact_key: str, **fields: Any) -> Fact:
    existing = (await db.execute(
        select(Fact).where(Fact.fact_key == fact_key)
    )).scalar_one_or_none()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        existing.generated_at = _now()
        await db.commit()
        return existing
    row = Fact(id=str(uuid.uuid4()), fact_key=fact_key, generated_at=_now(), **fields)
    db.add(row)
    await db.commit()
    return row


async def refresh_market_facts(db: AsyncSession) -> list[Fact]:
    from app.api.market import market_overview
    from app.services.opening_prediction_service import build_opening_prediction
    from app.db.session import AsyncSessionLocal

    today = _today_ist()
    facts: list[Fact] = []

    try:
        overview = await market_overview()
        for idx in overview.get("indices", []):
            name = idx.get("name")
            if name not in _TRACKED_INDICES:
                continue
            entity_key = name.replace(" ", "_")
            pct = idx.get("pct")
            fact = await _upsert(
                db, f"market:{entity_key}:{today}",
                valid_date=today, entity_type="market_index", entity_key=entity_key,
                name=name,
                claim=f"{name} is at {idx.get('value')}, {idx.get('change')} today.",
                value=idx.get("value"), numeric_value=pct, unit="%",
                direction="up" if idx.get("positive") else "down",
                change_pct=pct, confidence=None,
                source="NSE (via market data provider)",
                evidence={"high": idx.get("high"), "low": idx.get("low")},
                affected_sectors=[], affected_companies=[], observed_at=_now(),
            )
            facts.append(fact)
    except Exception as exc:
        log.warning("fact_registry.market_overview_failed", error=str(exc))

    try:
        async with AsyncSessionLocal() as db2:
            raw = await build_opening_prediction(db2)
        signals = raw.get("signals", {}) or {}
        prediction = raw.get("prediction", {}) or {}

        crude = signals.get("brent_crude") or {}
        if crude.get("value") and crude.get("value") != "—":
            facts.append(await _upsert(
                db, f"market:BRENT_CRUDE:{today}",
                valid_date=today, entity_type="commodity", entity_key="BRENT_CRUDE",
                name="Brent Crude Oil",
                claim=f"Brent crude is {crude.get('direction', 'trading')} at {crude.get('value')} ({crude.get('change', '—')}).",
                value=crude.get("value"), numeric_value=None, unit="$",
                direction=crude.get("direction"), change_pct=None, confidence=None,
                source="Global futures market data",
                evidence={"change": crude.get("change")},
                affected_sectors=["Aviation", "Paints", "Chemicals", "Oil & Gas", "Logistics"],
                affected_companies=[], observed_at=_now(),
            ))

        usd_inr = signals.get("usd_inr") or {}
        if usd_inr.get("value") and usd_inr.get("value") != "—":
            positive = usd_inr.get("positive")
            facts.append(await _upsert(
                db, f"market:USD_INR:{today}",
                valid_date=today, entity_type="forex", entity_key="USD_INR",
                name="USD/INR",
                claim=f"The rupee is trading at {usd_inr.get('value')} against the US dollar.",
                value=usd_inr.get("value"), numeric_value=None, unit="₹",
                direction="up" if positive else "down" if positive is False else None,
                change_pct=None, confidence=None,
                source="Forex market data",
                evidence={}, affected_sectors=["IT", "Pharma", "Textiles"],
                affected_companies=[], observed_at=_now(),
            ))

        if prediction.get("direction"):
            conf = prediction.get("confidence")
            ai_generated = prediction.get("ai_generated", False)
            facts.append(await _upsert(
                db, f"market:VERDICT:{today}",
                valid_date=today, entity_type="macro", entity_key="MARKET_VERDICT",
                name="Market Verdict",
                claim=prediction.get("reasoning") or f"Today's market outlook is {prediction.get('direction')}.",
                value=prediction.get("direction"),
                numeric_value=float(conf) if conf is not None else None, unit="%",
                direction=None, change_pct=None,
                confidence=(float(conf) / 100.0) if conf is not None else None,
                source="MarketRipple Opening Prediction Engine" + ("" if ai_generated else " (deterministic fallback — AI layer unavailable)"),
                evidence={"drivers": prediction.get("primary_drivers", []), "risks": prediction.get("risks", [])},
                affected_sectors=[], affected_companies=[], observed_at=_now(),
            ))
    except Exception as exc:
        log.warning("fact_registry.opening_prediction_failed", error=str(exc))

    return facts


async def refresh_event_facts(db: AsyncSession, limit: int = 10) -> list[Fact]:
    from app.services.intelligence.engine import read_top_events

    today = _today_ist()
    facts: list[Fact] = []
    try:
        events = await read_top_events(limit=50, min_urgency=0, hours=24)
    except Exception as exc:
        log.warning("fact_registry.events_failed", error=str(exc))
        return facts

    important = [e for e in events if e.get("priority_tier") in ("Critical", "High")][:limit]
    for e in important:
        event_id = e.get("id")
        if not event_id:
            continue
        confidence_raw = e.get("confidence")  # EventTriage.confidence is 0-10
        source_label = e.get("origin") or _SOURCE_CATEGORY_LABELS.get(e.get("source") or "", "MarketRipple Event Triage")
        facts.append(await _upsert(
            db, f"event:{event_id}",
            valid_date=today, entity_type="event", entity_key=event_id,
            name=(e.get("headline") or "")[:160],
            claim=e.get("one_liner") or e.get("headline") or "",
            value=e.get("priority_tier"), numeric_value=e.get("priority_score"), unit=None,
            direction=e.get("direction"), change_pct=None,
            confidence=(float(confidence_raw) / 10.0) if confidence_raw is not None else None,
            source=source_label,
            evidence={"sentiment": e.get("sentiment"), "market_impact": e.get("market_impact")},
            affected_sectors=e.get("sectors") or [], affected_companies=e.get("tickers") or [],
            observed_at=_now(),
        ))
    return facts


_SOURCE_CATEGORY_LABELS = {
    "news": "Financial news wire",
    "policy": "Government/regulatory source",
    "price": "Live market price feed",
    "synthetic": "MarketRipple market monitor",
}


async def get_facts_for_today(db: AsyncSession, refresh: bool = True) -> list[Fact]:
    if refresh:
        await refresh_market_facts(db)
        await refresh_event_facts(db)
    today = _today_ist()
    return (await db.execute(
        select(Fact).where(Fact.valid_date == today).order_by(Fact.entity_type, Fact.name)
    )).scalars().all()
