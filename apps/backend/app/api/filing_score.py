"""
Read API for the filing-backed MarketRipple Score. Off by default (settings.filing_score_public): every request answers 404 until a release decision turns it on.
Reads only the ACTIVE run; never computes anything and never touches the live scorer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services.filing_score import store
from app.services.filing_score.pipeline import METHOD_VERSION

router = APIRouter()


def _public_view(snap) -> dict:
    scored = snap.state == "scored"
    return {
        "symbol": snap.symbol, "method_version": METHOD_VERSION, "segment": snap.segment, "peer_group": snap.peer_group, "state": snap.state,
        "score": snap.score if scored else None, "rating": snap.rating if scored else None,
        "pillars": {"financial_strength": snap.financial_strength, "valuation": snap.valuation, "market_behaviour": snap.market_behaviour} if scored else None,
        "coverage_pct": snap.coverage_pct, "metrics_used": snap.metrics_used,
        "metrics": snap.metrics, "valuation_detail": snap.valuation_detail,
        "labels": snap.metadata_flags or [], "rule_tags": snap.rule_tags or [],
        "unavailable": None if scored else {"reason": snap.withheld_reason, "label": snap.na_label},
        "source": {"filing": (snap.provenance or {}).get("url"), "filing_sha256": (snap.provenance or {}).get("sha256"), "period_end": (snap.provenance or {}).get("period_end"),
                   "scope": (snap.provenance or {}).get("scope"), "market_cap_source": (snap.valuation_detail or {}).get("market_cap_source") or "Yahoo Finance (interim)"},
    }


@router.get("/{symbol}")
async def get_filing_score(symbol: str, db: AsyncSession = Depends(get_db)):
    if not settings.filing_score_public:
        raise HTTPException(status_code=404, detail="Not found")
    snap = await store.get_active_snapshot(db, METHOD_VERSION, symbol)
    if snap is None:
        raise HTTPException(status_code=404, detail="No filing-backed score for this symbol")
    return _public_view(snap)
