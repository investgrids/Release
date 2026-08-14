"""
Source Health API — read-only observability over ingestion-provider health
(see app/services/source_health.py). Answers the question the 2026-08
audit found had no operational signal at all: is NSE/BSE/RSS/RBI/PIB/SEBI
still actually working, or has it silently gone dark (confirmed live: BSE
had been failing in production for multiple days before this existed,
with zero dashboard signal — an operator had to go read logs to find out).

GET /api/sources/health          -> all known sources
GET /api/sources/health/{source} -> one source by name (URL-encoded,
                                     e.g. "RSS/Economic Times")
"""
from __future__ import annotations

from urllib.parse import unquote

from fastapi import APIRouter, Query

from app.services import source_health

router = APIRouter()


@router.get("/health")
async def get_all_health(stale_after_hours: float = Query(6.0, gt=0, le=48)):
    results = source_health.get_all_source_health(stale_after_hours=stale_after_hours)
    unhealthy = [r for r in results if r["status"] in ("FAILED", "STALE")]
    return {
        "sources": results,
        "total": len(results),
        "unhealthy_count": len(unhealthy),
        "unhealthy": [r["source"] for r in unhealthy],
    }


@router.get("/health/{source}")
async def get_one_health(source: str, stale_after_hours: float = Query(6.0, gt=0, le=48)):
    return source_health.get_source_health(unquote(source), stale_after_hours=stale_after_hours)
