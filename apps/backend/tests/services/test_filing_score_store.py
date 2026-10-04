import pytest

from app.db.session import AsyncSessionLocal
from app.services.filing_score import store

MV = "TEST_FILING_SCORE_MV"


def _row(sym, state="scored", score=60.0):
    return {"symbol": sym, "segment": "industrial", "peer_group": "Test|", "state": state, "score": score if state == "scored" else None,
            "rating": "Positive" if state == "scored" else None, "withheld_reason": None if state == "scored" else "NO_FILING", "metrics": {"roe": 12.5},
            "provenance": {"sha256": "abc", "seq_Id": "1"}, "inputs": {"facts_cr": {"Assets": 100.0}}, "contract_version": "T"}


async def _complete(db, symbols, score=60.0):
    run = await store.start_run(db, MV, trigger="manual", contracts={"industrial": "T"})
    await store.write_snapshots(db, run, [_row(s, score=score) for s in symbols])
    await store.complete_run(db, run, {"scored": len(symbols)})
    return run


async def test_run_is_invisible_until_activated_and_then_readable():
    async with AsyncSessionLocal() as db:
        run = await _complete(db, ["AAA", "BBB"])
        assert await store.get_active_snapshot(db, MV, "AAA") is None            # complete but not active: no reader sees it
        await store.activate_run(db, run.id)
        snap = await store.get_active_snapshot(db, MV, "aaa")
        assert snap is not None and snap.score == 60.0 and snap.provenance["sha256"] == "abc" and snap.metrics["roe"] == 12.5
        await db.rollback()


async def test_completed_run_is_immutable_and_failed_run_cannot_activate():
    async with AsyncSessionLocal() as db:
        run = await _complete(db, ["AAA"])
        with pytest.raises(ValueError):
            await store.write_snapshots(db, run, [_row("ZZZ")])
        bad = await store.start_run(db, MV)
        await store.fail_run(db, bad, "boom")
        with pytest.raises(ValueError):
            await store.activate_run(db, bad.id)
        await db.rollback()


async def test_activation_keeps_one_active_run_and_rollback_restores_previous():
    async with AsyncSessionLocal() as db:
        r1 = await _complete(db, ["AAA"], score=50.0)
        await store.activate_run(db, r1.id)
        r2 = await _complete(db, ["AAA"], score=70.0)
        await store.activate_run(db, r2.id)
        assert (await store.active_run(db, MV)).id == r2.id
        assert (await store.get_active_snapshot(db, MV, "AAA")).score == 70.0
        prev = await store.rollback_active(db, MV)
        assert prev is not None and prev.id == r1.id and (await store.get_active_snapshot(db, MV, "AAA")).score == 50.0
        assert await store.rollback_active(db, MV) is None                         # nothing earlier: readers then see no filing score
        assert await store.get_active_snapshot(db, MV, "AAA") is None
        await db.rollback()


async def test_duplicate_symbol_in_one_run_is_rejected():
    async with AsyncSessionLocal() as db:
        run = await store.start_run(db, MV)
        with pytest.raises(ValueError):
            await store.write_snapshots(db, run, [_row("AAA"), _row("AAA")])
        await db.rollback()
