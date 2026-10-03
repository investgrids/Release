from datetime import date, datetime

from app.services.financial_facts import filing_metric_contract as fmc
from app.services.financial_facts import nse_integrated_filing as nif

CR = 1e7


def _ex(facts: dict, scope="Consolidated", audited="Audited", pe=date(2026, 3, 31)):
    ref = nif.FilingRef(symbol="T", period_end=pe, scope=scope, audited=audited, type_sub="Original", seq_id="1",
                        broadcast=datetime(2026, 5, 30), revised=None, xbrl_url="https://x/INDAS_1_2_3.xml", filing_file_id="1")
    ex = nif.FilingExtract(ref=ref, retrieved_at="t", sha256="h", nbytes=1, currency="INR", level_of_rounding="Lakhs",
                           annual_status="audited" if audited == "Audited" else "unverified_unaudited")
    for k, v in facts.items():
        ex.facts[k] = nif.ExtractedFact(k, v * CR, "p", None, str(v * CR))
    return ex


BASE = {"RevenueFromOperations": 1000, "ProfitBeforeExceptionalItemsAndTax": 100, "ExceptionalItemsBeforeTax": 0, "ProfitBeforeTax": 100,
        "FinanceCosts": 20, "Assets": 800, "CurrentLiabilities": 200, "Equity": 500, "EquityAttributableToOwnersOfParent": 500,
        "ProfitLossForPeriod": 75, "ProfitOrLossAttributableToOwnersOfParent": 75, "BorrowingsCurrent": 40, "BorrowingsNoncurrent": 60}


def test_clean_company_has_all_metrics_and_provenance():
    prior = _ex({**BASE, "RevenueFromOperations": 800, "ProfitBeforeExceptionalItemsAndTax": 80}, pe=date(2025, 3, 31))
    fm = fmc.compute("T", _ex(BASE), prior, 3000.0, today=date(2026, 10, 3))
    assert fm.status == "ok" and fm.metrics["revenue_growth"] == 25.0 and fm.metrics["profit_growth"] == 25.0
    assert fm.metrics["roe"] == 15.0 and fm.metrics["roce"] == 20.0 and fm.metrics["interest_coverage"] == 6.0 and fm.metrics["debt_to_equity"] == 0.2
    assert fm.valuation["pe"] == 40.0 and fm.valuation["pb"] == 6.0
    assert fm.provenance["sha256"] == "h" and fm.provenance["growth_basis"]["prior_sha256"] == "h" and fm.contract_version == fmc.CONTRACT_VERSION


def test_material_exceptional_gain_fails_closed_and_blocks_roe_and_pe():
    fm = fmc.compute("T", _ex({**BASE, "ExceptionalItemsBeforeTax": 5000, "ProfitBeforeTax": 5100}), None, 3000.0, today=date(2026, 10, 3))
    assert fm.status == "EXCEPTIONAL_GAIN_REVIEW" and fm.reasons["roe"] == "EXCEPTIONAL_MATERIAL"
    assert fm.valuation["pe"] is None and fm.valuation["pe_reason"] == "EXCEPTIONAL_MATERIAL"


def test_negative_equity_ranks_worst_and_pb_unavailable():
    fm = fmc.compute("T", _ex({**BASE, "Equity": -90, "EquityAttributableToOwnersOfParent": -90}), None, 100.0, today=date(2026, 10, 3))
    assert fm.metrics["roe"] == fmc.WORST["roe"] and fm.metrics["debt_to_equity"] == fmc.WORST["debt_to_equity"]
    assert fm.valuation["pb"] is None and fm.valuation["pb_reason"] == "NEGATIVE_EQUITY"


def test_unaudited_stale_disposal_and_unresolved_fail_closed():
    assert fmc.compute("T", _ex(BASE, audited="Un-Audited"), None, 1.0, today=date(2026, 10, 3)).status == "UNVERIFIED_UNAUDITED"
    assert fmc.compute("T", _ex(BASE, pe=date(2025, 3, 31)), None, 1.0, today=date(2026, 10, 3)).status == "NO_FILING"  # older than FRESH_DAYS
    fm = fmc.compute("T", _ex({**BASE, "AssetsClassifiedAsHeldForSale": 50}), _ex(BASE, pe=date(2025, 3, 31)), 1.0, today=date(2026, 10, 3))
    assert fm.reasons["revenue_growth"] == "COMPARATIVE_MAY_BE_RESTATED" and fm.metrics["revenue_growth"] is None
    assert fmc.compute("VEDL", _ex(BASE), None, 1.0).status == "UNRESOLVED_REVIEW"
    assert fmc.compute("T", None, None, 1.0).status == "NO_FILING"


def test_growth_needs_same_scope_audited_prior_one_year_earlier():
    cur = _ex(BASE)
    assert fmc.compute("T", cur, _ex(BASE, scope="Standalone", pe=date(2025, 3, 31)), 1.0, today=date(2026, 10, 3)).reasons["revenue_growth"] == "NO_COMPARABLE_PRIOR"
    assert fmc.compute("T", cur, _ex(BASE, audited="Un-Audited", pe=date(2025, 3, 31)), 1.0, today=date(2026, 10, 3)).reasons["profit_growth"] == "NO_COMPARABLE_PRIOR"


# ---- exceptional-item materiality at zero / negative / near-zero profit (explicit rule) ----
def test_exceptional_rule_zero_negative_and_near_zero_profit():
    m = fmc.exceptional_materiality
    # zero profit base: threshold falls back to 0.5% of revenue (5.0 on revenue 1000)
    assert m(5.0, 0.0, 0.0, 1000.0)[:2] == (False, False)
    assert m(6.0, 0.0, 0.0, 1000.0)[:2] == (True, True)
    # loss-making year judged on the size of the loss: -266 base, +118 gain is material
    assert m(118.0, -148.0, -266.0, 2000.0)[:2] == (True, True)
    # near-zero base: a tiny item is not material just because the base is tiny
    assert m(0.05, 0.2, 0.1, 1000.0)[:2] == (False, False)
    # sign flip is always material even when small versus revenue
    assert m(0.7, 0.2, -0.5, 1000.0)[:2] == (True, True)
    # no profit base and no revenue: cannot be judged, fails closed
    assert m(5.0, 0.0, 0.0, None)[:2] == (True, True)
    # a material loss is material but not a gain; zero/None items are not material
    assert m(-500.0, 100.0, 600.0, 5000.0)[:2] == (True, False)
    assert m(0.0, 100.0, 100.0, 1000.0)[0] is False and m(None, 100.0, 100.0, 1000.0)[0] is False


# ---- selection: audited first, then scope preference ----
def _row(scope, audited, qe="31-MAR-2026", seq="1", rev=None):
    return {"xbrl": f"https://x/corporate/xbrl/INTEGRATED_FILING_INDAS_{seq}_30052026050832_WEB.xml", "qe_Date": qe, "audited": audited,
            "consolidated": scope, "type_Sub": "Original", "seq_Id": seq, "symbol": "T", "broadcast_Date": "30-May-2026 17:08:22", "revised_Date": rev}


def _patch_extract(monkeypatch):
    def fake(ref, session=None, raw_dir=None):
        ex = _ex(BASE, scope=ref.scope, audited=ref.audited or "Un-Audited", pe=ref.period_end)
        ex.ref = ref
        return ex
    monkeypatch.setattr(nif, "extract", fake)


def test_unaudited_consolidated_never_displaces_audited_standalone(monkeypatch):
    _patch_extract(monkeypatch)
    rows = [_row("Consolidated", "Un-Audited", seq="1"), _row("Standalone", "Audited", seq="2")]
    ex, info = nif.select_annual(rows)
    assert ex.ref.scope == "Standalone" and ex.ref.audited == "Audited" and info["fallback_unaudited"] is False


def test_both_audited_prefers_consolidated(monkeypatch):
    _patch_extract(monkeypatch)
    ex, _ = nif.select_annual([_row("Standalone", "Audited", seq="2"), _row("Consolidated", "Audited", seq="1")])
    assert ex.ref.scope == "Consolidated"


def test_newest_year_unaudited_uses_prior_audited_only_while_fresh(monkeypatch):
    _patch_extract(monkeypatch)
    rows = [_row("Consolidated", "Un-Audited", "31-MAR-2026", "1"), _row("Standalone", "Un-Audited", "31-MAR-2026", "2"),
            _row("Consolidated", "Audited", "31-MAR-2025", "3")]
    ex, info = nif.select_annual(rows)
    assert ex.ref.period_end == date(2025, 3, 31) and info["newer_unaudited_year_end"] is True
    # stale audited prior year + newer un-audited year-end => UNVERIFIED_UNAUDITED (not silently "audited")
    assert fmc.compute("T", ex, None, 1.0, today=date(2026, 10, 3), newer_unaudited_year_end=True).status == "UNVERIFIED_UNAUDITED"
    # the same audited prior year is still usable while inside the freshness window
    assert fmc.compute("T", ex, None, 1.0, today=date(2026, 2, 1), newer_unaudited_year_end=True).status == "ok"


def test_no_audited_filing_at_all_falls_back_to_unaudited_and_is_flagged(monkeypatch):
    _patch_extract(monkeypatch)
    ex, info = nif.select_annual([_row("Consolidated", "Un-Audited", seq="1")])
    assert ex is not None and info["fallback_unaudited"] is True
    assert fmc.compute("T", ex, None, 1.0, today=date(2026, 10, 3)).status == "UNVERIFIED_UNAUDITED"


def test_zero_valued_discontinued_concepts_do_not_count_as_a_disposal():
    cur = _ex({**BASE, "ProfitLossFromDiscontinuedOperationsAfterTax": 0, "AssetsClassifiedAsHeldForSale": 0})
    prior = _ex({**BASE, "RevenueFromOperations": 800}, pe=date(2025, 3, 31))
    fm = fmc.compute("T", cur, prior, 3000.0, today=date(2026, 10, 3))
    assert fm.flags["disposal_or_discontinued"] is False and fm.metrics["revenue_growth"] == 25.0
    cur2 = _ex({**BASE, "AssetsClassifiedAsHeldForSale": 12.5})
    assert fmc.compute("T", cur2, prior, 3000.0, today=date(2026, 10, 3)).reasons["revenue_growth"] == "COMPARATIVE_MAY_BE_RESTATED"


def test_owners_profit_uses_equity_evidence_for_no_minority_only():
    no_nci = _ex({**{k: v for k, v in BASE.items() if k != "ProfitOrLossAttributableToOwnersOfParent"}})
    v, basis = nif.owners_profit(no_nci)
    assert v == 75.0 and "no minority" in basis
    minority = _ex({**{k: v for k, v in BASE.items() if k != "ProfitOrLossAttributableToOwnersOfParent"}, "Equity": 560})
    v2, basis2 = nif.owners_profit(minority)
    assert v2 is None and "not populated" in basis2
