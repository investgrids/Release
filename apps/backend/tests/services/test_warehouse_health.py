"""
Phase 1B — warehouse-health measurement (owner instruction, 2026-08-23:
"Warehouse health now reports Raw Evidence totals and daily growth").
Real DB-backed, no mocks — checks the report's real shape and internal
consistency against whatever data actually exists.

Originally asserted `total_sources >= 20`, implicitly assuming
source_registry_seed.py had already been run against whatever DB this
test executes against — true of the shared local dev DB, false of a
genuinely isolated test DB (tests/conftest.py's session-scoped scratch
DB). Fixed by calling the real seed function directly, making this test
self-contained (seed_source_registry() is upsert-based, so this is safe
to call even when real rows already exist).
"""
from __future__ import annotations

from app.db.session import AsyncSessionLocal
from app.services.warehouse.health import warehouse_health_report
from app.services.warehouse.source_registry_seed import seed_source_registry

import pytest


@pytest.mark.asyncio
async def test_warehouse_health_report_shape_and_consistency():
    async with AsyncSessionLocal() as db:
        await seed_source_registry(db)
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
    assert sr["total_sources"] >= 20, "seed_source_registry() must have populated its own real rows"
