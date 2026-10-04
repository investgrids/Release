from datetime import date

from app.services.financial_facts import bank_metric_contract as bmc
from app.services.financial_facts import nse_integrated_filing as nif


def _bf(scope="Standalone", facts=None, status="audited", pe=date(2026, 3, 31), prior=None):
    ref = nif.FilingRef(symbol="B", period_end=pe, scope=scope, audited="Audited", type_sub="Original", seq_id="1", broadcast=None, revised=None,
                        xbrl_url="https://x/INTEGRATED_FILING_BANKING_1_2_WEB.xml", filing_file_id="1")
    bf = bmc.BankFiling(ref=ref, sha256="h", annual_status=status, fullyear_audit="Audited" if status == "audited" else "Unaudited")
    bf.facts = dict(facts if facts is not None else FACTS)
    if prior:
        bf.prior = dict(prior)
    return bf


FACTS = {"InterestEarned": 1000.0, "InterestExpended": 600.0, "OtherIncome": 100.0, "OperatingExpenses": 250.0, "ProfitLossForThePeriod": 100.0,
         "ProfitLossFromOrdinaryActivitiesBeforeTax": 140.0, "ProfitBeforeExtraordinaryItemsAndTax": 140.0, "ExceptionalItems": 0.0, "TaxExpense": 40.0,
         "Capital": 50.0, "ReservesAndSurplus": 950.0, "CapitalAndLiabilities": 10000.0,
         "PercentageOfGrossNpa": 0.0203, "PercentageOfNpa": 0.0074, "CET1Ratio": 0.1686}
TODAY = date(2026, 10, 4)


def test_bank_metrics_from_filed_figures_and_ratios_as_percent():
    fm = bmc.compute_bank("B", _bf(), None, 2000.0, today=TODAY)
    m = fm.metrics
    assert fm.status == "ok" and m["roe"] == 10.0 and m["roa"] == 1.0 and m["nim"] == 4.0          # 100/1000, 100/10000, (1000-600)/10000
    assert m["cost_to_income"] == 50.0                                                              # 250 / (400 + 100)
    assert (m["gross_npa"], m["net_npa"], m["cet1"]) == (2.03, 0.74, 16.86)
    assert fm.valuation["pb"] == 2.0 and fm.valuation["pe"] == 20.0


def test_consolidated_bank_takes_ratios_from_the_standalone_filing_and_zero_is_not_reported():
    cons = _bf("Consolidated", dict(FACTS, PercentageOfGrossNpa=0.0, PercentageOfNpa=0.0, CET1Ratio=0.0))
    cons.facts["ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates"] = 90.0
    fm = bmc.compute_bank("B", cons, None, 2000.0, today=TODAY)
    assert fm.metrics["gross_npa"] is None and fm.metrics["cet1"] is None and fm.metrics["roe"] == 9.0
    fm2 = bmc.compute_bank("B", cons, None, 2000.0, today=TODAY, ratio_source=_bf("Standalone"))
    assert fm2.metrics["gross_npa"] == 2.03 and fm2.metrics["cet1"] == 16.86


def test_bank_unaudited_year_end_fails_closed_and_growth_needs_same_scope_audited_prior():
    assert bmc.compute_bank("B", _bf(status="unverified"), None, 2000.0, today=TODAY).status == "UNVERIFIED_UNAUDITED"
    prior = _bf(pe=date(2025, 3, 31), facts=dict(FACTS, ProfitBeforeExtraordinaryItemsAndTax=100.0))
    prior.facts["ProfitBeforeExtraordinaryItemsAndTax"] = 100.0
    assert bmc.compute_bank("B", _bf(), prior, 2000.0, today=TODAY).metrics["profit_growth"] == 40.0
    assert bmc.compute_bank("B", _bf(), None, 2000.0, today=TODAY).reasons["profit_growth"] == "NO_COMPARABLE_PRIOR"


def test_bank_plausibility_guard_withholds_a_pb_off_by_more_than_3x():
    fm = bmc.compute_bank("B", _bf(), None, 2000.0, today=TODAY, reference={"pb": 0.2, "pe": None})
    assert fm.status == "VALUATION_DATA_DISCREPANCY" and all(v is None for v in fm.metrics.values())


def test_bank_group_scoring_ranks_and_requires_both_valuation_multiples():
    fms = {}
    for i, sym in enumerate(("A", "B", "C")):
        fms[sym] = bmc.compute_bank(sym, _bf(facts=dict(FACTS, ProfitLossForThePeriod=100.0 + 20 * i)), None, 1500.0 + 100 * i, today=TODAY).__dict__
        fms[sym]["flags"] = fms[sym]["flags"]
    out = bmc.score_bank_group(["A", "B", "C"], fms, {"A": 50.0, "B": 50.0, "C": 50.0})
    assert all(o["state"] in ("scored", "withheld") for o in out.values())
    fms["A"]["valuation"]["pe"] = None
    assert bmc.score_bank_group(["A", "B", "C"], fms, {"A": 50.0, "B": 50.0, "C": 50.0})["A"]["reason"].startswith("VALUATION_NEEDS_TWO_COMPONENTS")
