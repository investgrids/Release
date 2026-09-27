"""
Focused tests for s7_pilot_bank_disclosure_apply.py's transactional safety
guarantees -- the exact four properties the owner's round-2 review required
tests for. Run through the repo's existing test-DB isolation guardrail
(tests/conftest.py), so these hit the isolated scratch sqlite DB, never a
real dev or production database.

Loaded via importlib rather than a normal import, since scripts/ is a
one-off tooling directory, not an installed package.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.financial_fact import EXTRACTION_POPULATED, FinancialFact, QUALITY_OK

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "s7_pilot_bank_disclosure_apply.py"
_spec = importlib.util.spec_from_file_location("s7_pilot_bank_disclosure_apply", _SCRIPT_PATH)
s7 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = s7
_spec.loader.exec_module(s7)


@pytest.fixture(autouse=True)
async def _clean_pilot_period():
    """tests/conftest.py only creates the scratch schema once per session --
    it does not wipe rows between individual tests. Without this, one
    test's leftover rows at (FISCAL_YEAR, FISCAL_QUARTER) would falsely
    collide with the next test's records, masking what each test actually
    means to exercise."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(FinancialFact).where(
                FinancialFact.fiscal_year == s7.FISCAL_YEAR, FinancialFact.fiscal_quarter == s7.FISCAL_QUARTER,
            )
        )).scalars().all()
        for row in rows:
            await db.delete(row)
        await db.commit()
    yield


async def _count_pilot_rows() -> int:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(FinancialFact).where(
                FinancialFact.fiscal_year == s7.FISCAL_YEAR, FinancialFact.fiscal_quarter == s7.FISCAL_QUARTER,
            )
        )).scalars().all()
        return len(rows)


@pytest.mark.asyncio
async def test_collision_aborts_before_any_row_commits():
    """A pre-existing row at one of the 8 exact keys must abort the whole
    batch -- and, crucially, nothing else from the batch should have been
    committed either, since _write_records_transactionally raises before
    the caller ever calls db.commit()."""
    colliding = s7.RECORDS[0]  # ICICIBANK / gross_npa_pct
    async with AsyncSessionLocal() as db:
        db.add(FinancialFact(
            symbol=colliding.symbol, metric_code=colliding.metric_code, metric_name=colliding.metric_name,
            unit=colliding.unit, fiscal_year=s7.FISCAL_YEAR, fiscal_quarter=s7.FISCAL_QUARTER,
            period_type="Quarterly", consolidation_scope="Non-Consolidated", source_provider="PriorTest",
            extraction_status=EXTRACTION_POPULATED, quality_status=QUALITY_OK, value=0.0999,
            observed_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    async with AsyncSessionLocal() as db:
        with pytest.raises(s7.CollisionError):
            await s7._write_records_transactionally(db, s7.RECORDS)
        await db.rollback()

    # Exactly the one pre-existing row should be present -- none of the
    # other 7 records (which come after the colliding one in RECORDS,
    # since it's RECORDS[0]) were committed by the aborted transaction.
    assert await _count_pilot_rows() == 1


@pytest.mark.asyncio
async def test_mid_batch_quality_failure_commits_nothing():
    """A single record that fails the plausibility gate must abort the
    ENTIRE batch, including the records that were already added (but not
    yet committed) before the failing one was reached."""
    bad_cet1 = replace(s7.RECORDS[3], value_pct=95.0)  # ICICIBANK cet1_ratio -> 0.95, outside (0.02, 0.60)
    records = list(s7.RECORDS[:3]) + [bad_cet1] + list(s7.RECORDS[4:])
    assert records[3].metric_code == "cet1_ratio"

    async with AsyncSessionLocal() as db:
        with pytest.raises(s7.QualityGateError):
            await s7._write_records_transactionally(db, records)
        await db.rollback()

    # Nothing committed at all -- not even the 3 good records that were
    # added and flushed before the bad one raised.
    assert await _count_pilot_rows() == 0


@pytest.mark.asyncio
async def test_full_batch_commits_cleanly_when_nothing_blocks_it():
    """Sanity check the other two tests' assumptions: with a real, clean
    database and no injected failure, all 8 records commit successfully."""
    async with AsyncSessionLocal() as db:
        manifest = await s7._write_records_transactionally(db, s7.RECORDS)
        await db.commit()

    assert len(manifest) == 8
    assert await _count_pilot_rows() == 8
    assert all(m["quality_status"] == QUALITY_OK for m in manifest)


@pytest.mark.asyncio
async def test_rollback_refuses_to_delete_a_row_that_changed_since_insert():
    """The rollback path must compare the row's CURRENT state against what
    the manifest recorded, and refuse deletion on any mismatch -- never
    delete by id alone."""
    async with AsyncSessionLocal() as db:
        manifest = await s7._write_records_transactionally(db, s7.RECORDS[:2])
        await db.commit()

    unchanged_id = manifest[0]["id"]
    changed_id = manifest[1]["id"]

    # Simulate an external change to one of the two rows after insert.
    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(FinancialFact).where(FinancialFact.id == changed_id))).scalar_one()
        row.value = 0.999  # no longer matches the manifest's recorded value
        await db.commit()

    async with AsyncSessionLocal() as db:
        results = await s7._rollback_records(db, manifest)

    by_id = {r["id"]: r for r in results}
    assert by_id[unchanged_id]["action"] == "deleted"
    assert by_id[changed_id]["action"] == "refused"

    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(FinancialFact).where(FinancialFact.id == unchanged_id))).scalar_one_or_none() is None
        still_there = (await db.execute(select(FinancialFact).where(FinancialFact.id == changed_id))).scalar_one_or_none()
        assert still_there is not None
        assert still_there.value == pytest.approx(0.999)


@pytest.mark.asyncio
async def test_readonly_verification_fails_when_pragma_was_never_applied():
    """A read-only engine that was never actually put into query_only mode
    must be caught by _verify_readonly_engine, not silently trusted."""
    from sqlalchemy.ext.asyncio import create_async_engine

    # Same style of throwaway file-backed engine the self-test itself uses,
    # deliberately WITHOUT the PRAGMA connect-event listener -- simulating
    # the exact failure mode the round-1 review flagged: enforcement that
    # silently didn't take effect.
    import tempfile
    import os as _os
    fd, path = tempfile.mkstemp(suffix=".db")
    _os.close(fd)
    try:
        unenforced_engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        with pytest.raises(RuntimeError, match="FAILED verification"):
            await s7._verify_readonly_engine(unenforced_engine)
        await unenforced_engine.dispose()
    finally:
        try:
            _os.remove(path)
        except OSError:
            pass


def test_readonly_engine_refuses_a_non_sqlite_url():
    with pytest.raises(RuntimeError, match="sqlite-specific"):
        s7._assert_sqlite_url("postgresql+asyncpg://user:pass@host/db")
