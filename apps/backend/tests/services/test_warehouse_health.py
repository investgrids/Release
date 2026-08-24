"""
Phase 1B — warehouse-health measurement (owner instruction, 2026-08-23:
"Warehouse health now reports Raw Evidence totals and daily growth").
Real DB-backed, no mocks — checks the report's real shape and internal
consistency against whatever data actually exists.
"""
from __future__ import annotations

from app.db.session import AsyncSessionLocal
from app.services.warehouse.health import warehouse_health_report

import pytest


@pytest.mark.asyncio
async def test_warehouse_health_report_shape_and_consistency():
    async with AsyncSessionLocal() as db:
        report = await warehouse_health_report(db)

    assert set(report.keys()) == {"generated_at", "raw_evidence", "market_observations", "source_registry"}

    re = report["raw_evidence"]
    assert re["total"] == sum(re["by_source_type"].values()), "per-source-type breakdown must sum to the real total"
    assert re["total"] == sum(re["by_quality"].values()), "per-quality breakdown must sum to the real total"

    mo = report["market_observations"]
    assert mo["total"] == sum(mo["by_metric"].values())
    assert mo["total"] == sum(mo["by_quality"].values())

    sr = report["source_registry"]
    assert sr["total_sources"] == sum(sr["by_rights_basis"].values())
    assert sr["total_sources"] >= 20, "the 20 real seeded sources must still be present"
