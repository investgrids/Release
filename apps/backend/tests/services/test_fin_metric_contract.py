from datetime import date

from app.services.financial_facts import bank_metric_contract as bmc
from app.services.financial_facts import nbfc_metric_contract as fin
from app.services.financial_facts import nse_integrated_filing as nif

TODAY = date(2026, 10, 4)
LENDER = {"RevenueFromOperations": 1000.0, "FinanceCosts": 500.0, "ImpairmentOnFinancialInstruments": 20.0, "Expenses": 800.0, "ProfitBeforeTax": 200.0,
          "ProfitBeforeExceptionalItemsAndTax": 200.0, "ExceptionalItemsBeforeTax": 0.0, "TaxExpense": 50.0, "ProfitLossForPeriod": 150.0,
          "ProfitOrLossAttributableToOwnersOfParent": 150.0, "Assets": 5000.0, "Equity": 1000.0, "EquityAttributableToOwnersOfParent": 1000.0,
          "Loans": 4000.0, "Borrowings": 3000.0, "DebtSecurities": 500.0, "SubordinatedLiabilities": 100.0}


def _bf(facts, scope="Consolidated", pe=date(2026, 3, 31)):
    ref = nif.FilingRef(symbol="F", period_end=pe, scope=scope, audited="Audited", type_sub="Original", seq_id="1", broadcast=None, revised=None,
                        xbrl_url="https://x/INTEGRATED_FILING_NBFC_INDAS_1_2_WEB.xml", filing_file_id="1")
    bf = bmc.BankFiling(ref=ref, sha256="h", annual_status="audited", fullyear_audit="Audited")
    bf.facts = dict(facts)
    return bf


def test_lender_metrics_and_group():
    fm = fin.compute_fin("F", _bf(LENDER), None, 3000.0, today=TODAY)
    m = fm.metrics
    assert fm.group == "LENDERS" and fm.status == "ok"
    assert m["roe"] == 15.0 and m["roa"] == 3.0 and m["nim"] == 10.0          # 150/1000, 150/5000, (1000-500)/5000
    assert m["cost_to_income"] == 56.0                                          # (800-500-20)/(1000-500)
    assert m["credit_cost"] == 0.5 and m["leverage"] == 3.6                     # 20/4000; 3600/1000
    assert fm.valuation["pb"] == 3.0 and fm.valuation["pe"] == 20.0


def test_non_lender_uses_the_smaller_metric_set_and_owners_identity_blocks_bad_profit():
    other = dict(LENDER, Loans=None)
    fm = fin.compute_fin("F", _bf(other), None, 3000.0, today=TODAY)
    assert fm.group == "OTHER" and "nim" not in fm.metrics
    bad = dict(LENDER, ProfitOrLossAttributableToOwnersOfParent=15.0)          # 15 + 0 vs total 150: does not reconcile
    fm2 = fin.compute_fin("F", _bf(bad), None, 3000.0, today=TODAY)
    assert fm2.reasons["roe"] == "OWNERS_PROFIT_SOURCE_GAP" and fm2.valuation["pe"] is None


def test_fin_guard_and_group_scoring_withholds_unlabelled_groups():
    fm = fin.compute_fin("F", _bf(LENDER), None, 3000.0, today=TODAY, reference={"pb": 0.5, "pe": None})
    assert fm.status == "VALUATION_DATA_DISCREPANCY"
    out = fin.score_fin_groups(["F", "G"], {"F": fm.__dict__}, {"F": 50.0, "G": 50.0})
    assert out["F"]["state"] == "withheld" and out["G"]["reason"] == "NO_FILING_RECORD"
