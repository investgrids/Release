import pytest

from app.db.session import AsyncSessionLocal
from app.services.filing_score import pipeline, runner, store
from app.services.filing_score.pipeline import Collected, Company

METRICS = {"revenue_growth": 5.0, "profit_growth": 5.0, "roe": 12.0, "roce": 10.0, "debt_to_equity": 1.0, "interest_coverage": 3.0}


class FakeCollector:
    """Offline collector: deterministic fm dicts shaped like the contracts' output."""
    def __init__(self, fail=(), reroute=None):
        self.fail, self.reroute, self.calls = set(fail), reroute or {}, []

    def collect(self, company, segment):
        self.calls.append(company.symbol)
        if company.symbol in self.fail:
            raise RuntimeError("nse down")
        seg = self.reroute.get(company.symbol, segment)
        i = len(self.calls)
        if seg == "industrial":
            fm = {"status": "ok", "metrics": {k: v + i for k, v in METRICS.items()}, "valuation": {"pe": 10.0 + i, "pb": 1.0 + i / 10}, "flags": {}, "provenance": {"sha256": "x"}}
        else:
            fm = {"status": "ok", "group": "LENDERS", "metrics": {k: float(i) for k in ("roe", "roa", "cost_to_income", "revenue_growth", "profit_growth", "nim", "credit_cost", "leverage")},
                  "valuation": {"pe": 8.0 + i, "pb": 1.0 + i / 10}, "flags": {}, "provenance": {"sha256": "y"}}
            if seg == "bank":
                fm.pop("group"); fm["metrics"] = {k: float(i) for k in ("roe", "roa", "nim", "cost_to_income", "gross_npa", "net_npa", "cet1", "profit_growth")}
        return Collected(company.symbol, seg, fm, 50.0, {"price": 100.0})


def _universe():
    return [Company("I1", "Chemicals"), Company("I2", "Chemicals"), Company("I3", "Chemicals"), Company("B1", "Banking"), Company("B2", "Banking"), Company("B3", "Banking"),
            Company("F1", "Finance"), Company("F2", "Finance"), Company("F3", "Finance"), Company("INS", "Insurance"), Company("NOSEC", None)]


def test_classification_routes_banks_finance_industrial_and_unsupported():
    assert pipeline.classify(Company("X", "Banking")) == "bank" and pipeline.classify(Company("X", "Finance")) == "fin"
    assert pipeline.classify(Company("X", "Finance"), taxonomy="BANKING") == "bank"                 # banking-format filer under Finance
    assert pipeline.classify(Company("X", "Chemicals")) == "industrial"
    assert pipeline.classify(Company("X", "Insurance")) is None and pipeline.classify(Company("X", None)) is None


def test_every_company_gets_a_row_scored_or_with_an_explicit_reason():
    rows, counts = pipeline.score_universe(_universe(), FakeCollector())
    by = {r["symbol"]: r for r in rows}
    assert len(rows) == len(_universe()) and counts["universe"] == 11
    assert by["INS"]["withheld_reason"] == "SEGMENT_NOT_SUPPORTED" and by["INS"]["na_label"].startswith("N/A")
    assert by["NOSEC"]["withheld_reason"] == "NO_SECTOR_ASSIGNED"
    assert by["I1"]["state"] == "scored" and by["I1"]["segment"] == "industrial" and by["B1"]["segment"] == "bank" and by["F1"]["segment"] == "fin_lenders"
    assert counts["scored"] == sum(1 for r in rows if r["state"] == "scored") and counts["by_segment"]["bank"]["total"] == 3


def test_a_failing_company_becomes_a_withheld_row_and_never_stops_the_run():
    rows, _ = pipeline.score_universe(_universe(), FakeCollector(fail={"I2"}))
    by = {r["symbol"]: r for r in rows}
    assert by["I2"]["state"] == "withheld" and by["I2"]["withheld_reason"] == "COLLECTION_ERROR" and by["I1"]["state"] == "scored"


def test_collector_can_reroute_a_banking_format_filer():
    rows, _ = pipeline.score_universe(_universe(), FakeCollector(reroute={"F3": "bank"}))
    assert {r["symbol"]: r["segment"] for r in rows}["F3"] == "bank"


def test_market_cap_check_flags_only_a_wrong_yahoo_share_count():
    # stored 1000 vs filing-share figure 100; live P/B x equity = 105 agrees with the filing shares: flagged
    assert pipeline.market_cap_check(1000.0, 10.0, 1e9, 10.0, 2.1, 50.0)["ratio"] == 10.0
    # stored agrees with live P/B x equity (the filing share count is stale after a split): not flagged
    assert pipeline.market_cap_check(1000.0, 10.0, 1e9, 10.0, 20.0, 50.0) is None
    assert pipeline.market_cap_check(100.0, 10.0, 1e9, 10.0, 2.0, 50.0) is None                     # within 1.5x
    assert pipeline.market_cap_check(1000.0, None, 1e9, 10.0, 2.0, 50.0) is None                    # missing input: not checkable


async def test_refresh_persists_an_immutable_run_and_activation_is_guarded():
    async with AsyncSessionLocal() as db:
        out = await runner.run_refresh(db, FakeCollector(), universe=_universe(), activate=True)
        assert out["status"] == "complete" and out["activated"] is True
        snap = await store.get_active_snapshot(db, pipeline.METHOD_VERSION, "I1")
        assert snap.state == "scored" and snap.segment == "industrial" and snap.contract_version
        # a second run that collapses (every company fails) must be kept but NOT activated over the good one
        bad = await runner.run_refresh(db, FakeCollector(fail={c.symbol for c in _universe()}), universe=_universe(), activate=True)
        assert bad["status"] == "complete" and bad["activated"] is False and "not activated" in bad["activation_note"]
        assert (await store.active_run(db, pipeline.METHOD_VERSION)).id == out["run_id"]
        await db.rollback()


def test_lock_file_blocks_a_second_refresh_and_stale_locks_are_recovered(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(runner, "lock_path", lambda: tmp_path / "running.lock")
    assert runner.acquire_lock() is True
    assert runner.acquire_lock() is False                                    # held by this live process
    runner.release_lock()
    (tmp_path / "running.lock").write_text("not-a-pid")
    assert runner.acquire_lock() is True                                     # unreadable lock is recovered
    runner.release_lock()
    (tmp_path / "running.lock").write_text(str(os.getpid()))
    os.utime(tmp_path / "running.lock", (0, 0))                              # very old lock: recovered even if the pid looks alive
    assert runner.acquire_lock() is True
    runner.release_lock()


async def test_universe_is_the_production_directory_with_sector_blank_meaning_not_assigned(monkeypatch):
    from app.api import companies

    async def fake_directory(db):
        return [{"symbol": "TCS", "name": "Tata", "sector": "Technology"}, {"symbol": "HDFCBANK", "name": "HDFC", "sector": "Banking"},
                {"symbol": "NEWCO", "name": "New Co", "sector": ""}, {"symbol": "TCS", "name": "dup", "sector": "Technology"}]
    monkeypatch.setattr(companies, "get_full_company_directory", fake_directory)
    async with AsyncSessionLocal() as db:
        uni = {c.symbol: c for c in await runner.load_universe(db)}
    assert set(uni) == {"TCS", "HDFCBANK", "NEWCO"} and uni["TCS"].sector == "Technology" and uni["NEWCO"].sector is None
