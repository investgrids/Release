"""
Fact Registry API — read-only surface over app/services/fact_registry.py.
Backend/data-architecture only (Phase 2 of the Daily Brief restructure) —
no frontend consumes this yet; UI work is Phase 6.

GET /api/facts/today -> today's real market + event facts, each already
                        carrying its own claim/evidence/source/confidence
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import fact_registry

router = APIRouter()


def _iso(dt):
    if not dt:
        return None
    return dt.replace(tzinfo=None).isoformat() + "Z"


def _serialize(f) -> dict:
    return {
        "fact_key": f.fact_key,
        "entity_type": f.entity_type,
        "entity_key": f.entity_key,
        "name": f.name,
        "claim": f.claim,
        "value": f.value,
        "numeric_value": f.numeric_value,
        "unit": f.unit,
        "direction": f.direction,
        "change_pct": f.change_pct,
        "confidence": f.confidence,
        "source": f.source,
        "evidence": f.evidence,
        "affected_sectors": f.affected_sectors,
        "affected_companies": f.affected_companies,
        "observed_at": _iso(f.observed_at),
        "generated_at": _iso(f.generated_at),
    }


@router.get("/today")
async def get_today_facts(db: AsyncSession = Depends(get_db)):
    facts = await fact_registry.get_facts_for_today(db)
    return {
        "valid_date": fact_registry._today_ist(),
        "count": len(facts),
        "facts": [_serialize(f) for f in facts],
    }
