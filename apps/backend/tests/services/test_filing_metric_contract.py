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


def test_disposal_is_detected_by_concept_name_pattern_with_a_nonzero_value():
    ex = _ex(BASE)
    ex.disposal_facts = {"NoncurrentAssetsClassifiedAsHeldForSale": 110.14, "BasicEarningsLossPerShareFromDiscontinuedOperations": 0.0}
    prior = _ex({**BASE, "RevenueFromOperations": 800}, pe=date(2025, 3, 31))
    fm = fmc.compute("T", ex, prior, 3000.0, today=date(2026, 10, 3))
    assert fm.flags["disposal_or_discontinued"] is True and fm.reasons["revenue_growth"] == "COMPARATIVE_MAY_BE_RESTATED"
    ex.disposal_facts = {"NoncurrentAssetsClassifiedAsHeldForSale": 0.0}
    assert fmc.compute("T", ex, prior, 3000.0, today=date(2026, 10, 3)).flags["disposal_or_discontinued"] is False


# ---- income quality outside the exceptional line ----
def _with_reg(ex, debit, credit):
    ex.regulatory = {"debit": debit, "credit": credit}
    return ex


def test_material_regulatory_deferral_gain_fails_closed_with_a_specific_reason():
    cur = _with_reg(_ex({**BASE, "ProfitBeforeExceptionalItemsAndTax": 100, "ProfitBeforeTax": 100, "OtherIncome": 5}), 8666.0, 0.0)
    prior = _with_reg(_ex({**BASE, "RevenueFromOperations": 800}, pe=date(2025, 3, 31)), 7744.0, 2.0)
    fm = fmc.compute("T", cur, prior, 3000.0, today=date(2026, 10, 3))
    assert fm.flags["regulatory_movement_cr"] == 924.0 + 2.0 - 2.0  # (8666-7744) - (0-2) - 2 would be 924 only if credit rose; here (8666-7744) - (0-2) = 924
    assert fm.status == "REGULATORY_DEFERRAL_REVIEW"
    assert fm.metrics["roce"] is None and fm.reasons["roce"] == "REGULATORY_DEFERRAL_UNVERIFIED" and fm.metrics["debt_to_equity"] is not None


def test_regulatory_balances_without_a_prior_year_filing_cannot_be_isolated():
    cur = _with_reg(_ex(BASE), 50.0, 0.0)
    assert fmc.compute("T", cur, None, 3000.0, today=date(2026, 10, 3)).status == "REGULATORY_MOVEMENT_UNKNOWN"


def test_immaterial_or_negative_regulatory_movement_does_not_fail_closed():
    cur = _with_reg(_ex(BASE), 1000.0, 0.0)
    prior = _with_reg(_ex(BASE, pe=date(2025, 3, 31)), 995.0, 0.0)          # +5 on a pre-tax profit of 100: 5% < 10%
    assert fmc.compute("T", cur, prior, 3000.0, today=date(2026, 10, 3)).status == "ok"
    prior2 = _with_reg(_ex(BASE, pe=date(2025, 3, 31)), 1200.0, 0.0)        # -200: a material reversal
    fm = fmc.compute("T", cur, prior2, 3000.0, today=date(2026, 10, 3))
    assert fm.status == "ok" and fm.valuation["pe"] is None
    assert all(fm.reasons[m] in ("REGULATORY_DEFERRAL_MATERIAL", "REGULATORY_DEFERRAL_UNVERIFIED") for m in ("roe",)) and fm.metrics["roce"] is None
    assert fm.reasons["roce"] == "REGULATORY_DEFERRAL_UNVERIFIED" and fm.metrics["debt_to_equity"] is not None


def test_profit_resting_on_other_income_makes_earnings_metrics_unavailable_but_is_not_a_company_gate():
    ex = _ex({**BASE, "ProfitBeforeExceptionalItemsAndTax": 5.41, "ProfitBeforeTax": 5.41, "OtherIncome": 6.10})
    prior = _ex({**BASE, "RevenueFromOperations": 800}, pe=date(2025, 3, 31))
    fm = fmc.compute("T", ex, prior, 3000.0, today=date(2026, 10, 3))
    assert fm.status == "ok" and fm.flags["non_core_profit"] is True and fm.flags["core_pretax_cr"] == -0.69
    for m in ("profit_growth", "roe", "roce", "interest_coverage"):
        assert fm.metrics[m] is None and fm.reasons[m] == "NON_CORE_INCOME_BASIS"
    assert fm.valuation["pe"] is None and fm.valuation["pe_reason"] == "NON_CORE_INCOME_BASIS"
    assert fm.metrics["revenue_growth"] is not None and fm.metrics["debt_to_equity"] is not None   # metrics not built on that income stay valid
    ok = _ex({**BASE, "OtherIncome": 30})   # core profit 70 > 0
    f2 = fmc.compute("T", ok, prior, 3000.0, today=date(2026, 10, 3))
    assert f2.status == "ok" and f2.flags["non_core_profit"] is False and f2.metrics["roce"] is not None


def test_soft_flags_are_recorded_without_changing_the_status():
    ex = _ex({**BASE, "OtherIncome": 60, "ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod": 50})
    fm = fmc.compute("T", ex, None, 3000.0, today=date(2026, 10, 3))
    assert fm.status == "ok" and fm.flags["other_income_over_half_of_pbet"] is True and fm.flags["associates_over_half_of_owners_profit"] is True


# ---- audit status comes from the filing's own full-year statement, not the listing's Q4 flag ----
def _xbrl(tmp_path, q4, fy, extra_fy=None):
    def ctx(i, s, e):
        return f'<xbrli:context id="{i}"><xbrli:entity><xbrli:identifier scheme="x">T</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>{s}</xbrli:startDate><xbrli:endDate>{e}</xbrli:endDate></xbrli:period></xbrli:context>'
    vals = "".join(f'<in-capmkt:WhetherResultsAreAuditedOrUnaudited contextRef="{c}">{v}</in-capmkt:WhetherResultsAreAuditedOrUnaudited>'
                   for c, v in (("q", q4), ("fy", fy), ("fy", extra_fy)) if v)
    xml = ('<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/in-capmkt">'
           + ctx("q", "2026-01-01", "2026-03-31") + ctx("fy", "2025-04-01", "2026-03-31") + vals
           + '<in-capmkt:RevenueFromOperations contextRef="fy" decimals="0">1000000000</in-capmkt:RevenueFromOperations></xbrli:xbrl>')
    (tmp_path / "T_1_abc.xml").write_text(xml)
    return str(tmp_path)


def _ref(audited):
    return nif.FilingRef(symbol="T", period_end=date(2026, 3, 31), scope="Consolidated", audited=audited, type_sub="Original", seq_id="1",
                         broadcast=None, revised=None, xbrl_url="https://x", filing_file_id="1")


def test_fullyear_audited_overrides_a_quarter_level_unaudited_listing_flag(tmp_path):
    ex = nif.extract(_ref("Un-Audited"), raw_dir=_xbrl(tmp_path, "Unaudited", "Audited"))
    assert ex.annual_status == "audited" and ex.audit_source == "xbrl_fullyear"


def test_fullyear_unaudited_or_ambiguous_is_never_audited_even_if_listing_says_audited(tmp_path):
    assert nif.extract(_ref("Audited"), raw_dir=_xbrl(tmp_path, "Unaudited", "Unaudited")).annual_status == "unverified_unaudited"


def test_conflicting_fullyear_statements_fail_closed(tmp_path):
    ex = nif.extract(_ref("Un-Audited"), raw_dir=_xbrl(tmp_path, "Unaudited", "Audited", "Unaudited"))
    assert ex.annual_status == "unverified_unaudited" and ex.xbrl_fullyear_audit == "AMBIGUOUS"


def test_missing_fullyear_statement_is_unverified_whatever_the_listing_says(tmp_path):
    d = _xbrl(tmp_path, "Unaudited", None)
    for flag in ("Un-Audited", "Audited"):
        ex = nif.extract(_ref(flag), raw_dir=d)
        assert ex.annual_status == "unverified_unaudited" and ex.audit_source == "missing_statement"
