"""
Shadow method for NON-BANK FINANCIALS (NSE_FILING_FIN_V1): NBFCs, housing finance, and asset-light financials (brokers, AMCs, exchanges, depositories) that
file on the Ind-AS Division III or standard Ind-AS formats. Not wired into any live scorer.

Those filings have revenue, finance costs, profit and balance sheet but no current-liabilities split, so ROCE and interest coverage are not used. Two peer
groups, by business model measured from the filing itself: LENDERS (loans >= 40% of total assets) and OTHER financials.
  roe             owners' profit / owners' equity                                       (all)
  roa             profit for the period / total assets                                  (all)
  cost_to_income  operating costs / net revenue                                         (all, lower is better)
  revenue_growth, profit_growth  vs the audited prior year, same scope                  (all)
  nim             (revenue - finance costs) / total assets                              (lenders)
  credit_cost     impairment on financial instruments / loans                           (lenders, lower is better)
  leverage        (borrowings + debt securities + subordinated liabilities) / equity    (lenders, lower is better)
Same evidence standard and guards as the industrial contract (audited full-year statement, owners' profit rule, Rule 4A/4C, valuation needs both multiples).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.services.financial_facts import bank_metric_contract as bmc
from app.services.financial_facts.filing_metric_contract import (
    ADJUSTED_LABEL, DISCREPANCY_LABEL, DISCREPANCY_STATUS, EXCEPTIONAL_LOSS_TAX_CAP, FRESH_DAYS, RULE_4A, RULE_4C, exceptional_materiality, plausibility_check,
)

FIN_CONTRACT_VERSION = "NSE_FILING_FIN_V1"
LENDER_LOANS_SHARE = 0.40
LENDER_DIRECTIONS = {"roe": True, "roa": True, "cost_to_income": False, "revenue_growth": True, "profit_growth": True, "nim": True, "credit_cost": False, "leverage": False}
OTHER_DIRECTIONS = {"roe": True, "roa": True, "cost_to_income": False, "revenue_growth": True, "profit_growth": True}
LENDER_MIN, OTHER_MIN = 6, 4
FLOW = ("RevenueFromOperations", "InterestEarned", "FinanceCosts", "ImpairmentOnFinancialInstruments", "Expenses", "Income", "ExceptionalItemsBeforeTax",
        "ProfitBeforeExceptionalItemsAndTax", "ProfitBeforeTax", "TaxExpense", "ProfitLossForPeriod", "ProfitOrLossAttributableToOwnersOfParent",
        "ProfitOrLossAttributableToNonControllingInterests")
INSTANT = ("Assets", "Equity", "EquityAttributableToOwnersOfParent", "Loans", "Borrowings", "DebtSecurities", "SubordinatedLiabilities", "EquityAndLiabilities")
PER_SHARE = ("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",)
MARKER = "INDAS"


def select_fin_annual(rows, session=None, raw_dir=None):
    return bmc.select_bank_annual(rows, session=session, raw_dir=raw_dir, marker=MARKER, core=("RevenueFromOperations", "ProfitBeforeTax", "ProfitLossForPeriod"),
                                  flow=FLOW, instant=INSTANT, ratio=("DebtEquityRatio",), per_share=PER_SHARE)


@dataclass
class FinMetrics:
    symbol: str
    contract_version: str = FIN_CONTRACT_VERSION
    group: str = ""
    provenance: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    reasons: dict = field(default_factory=dict)
    flags: dict = field(default_factory=dict)
    valuation: dict = field(default_factory=dict)
    status: str = "ok"


def compute_fin(symbol: str, bf, prior, market_cap_cr: float | None, today: date | None = None, newer_unaudited_year_end: bool = False,
                reference: dict | None = None) -> FinMetrics:
    today = today or date.today()
    fm = FinMetrics(symbol=symbol)
    if bf is None:
        fm.status = "NO_FILING"; return fm
    ref, f = bf.ref, bf.facts
    fm.provenance = {"seq_Id": ref.seq_id, "file_id": ref.filing_file_id, "url": ref.xbrl_url, "sha256": bf.sha256, "scope": ref.scope, "audited": ref.audited,
                     "fullyear_audit_statement": bf.fullyear_audit, "period_end": str(ref.period_end), "market_cap_source": "Yahoo Finance (interim)"}
    if bf.annual_status != "audited" or (today - ref.period_end).days > FRESH_DAYS:
        fm.status = "UNVERIFIED_UNAUDITED" if (bf.annual_status != "audited" or newer_unaudited_year_end) else "NO_FILING"
        return fm
    assets = f.get("Assets") or f.get("EquityAndLiabilities")
    eq_o, eq_t = f.get("EquityAttributableToOwnersOfParent"), f.get("Equity")
    equity = eq_o if (ref.scope == "Consolidated" and eq_o is not None) else eq_t
    total, ow, nci = f.get("ProfitLossForPeriod"), f.get("ProfitOrLossAttributableToOwnersOfParent"), f.get("ProfitOrLossAttributableToNonControllingInterests")
    if ow is not None and not (ow == 0 and total not in (None, 0)):
        owners = ow if not (total is not None and abs(ow + (nci or 0.0) - total) > max(1.0, 0.05 * abs(total))) else None   # Rule 4D identity
    elif ow is None and (ref.scope == "Standalone" or (eq_t is not None and eq_o is not None and abs(eq_t - eq_o) < 0.01)):
        owners = total
    elif ow is None and nci is not None and total is not None:
        owners = round(total - nci, 4)
    else:
        owners = None
    revenue = f.get("RevenueFromOperations") if f.get("RevenueFromOperations") else f.get("Income")
    fin_costs = f.get("FinanceCosts") if f.get("FinanceCosts") is not None else f.get("InterestExpended")
    loans = f.get("Loans")
    lender = bool(loans and assets and loans / assets >= LENDER_LOANS_SHARE)
    fm.group = "LENDERS" if lender else "OTHER"
    directions = LENDER_DIRECTIONS if lender else OTHER_DIRECTIONS
    pbt, pre_exc, exc = f.get("ProfitBeforeTax"), f.get("ProfitBeforeExceptionalItemsAndTax"), f.get("ExceptionalItemsBeforeTax")
    net_rev = None if revenue is None or fin_costs is None else round(revenue - (fin_costs if lender else 0.0), 4)
    op_cost = None
    if f.get("Expenses") is not None:
        op_cost = round(f["Expenses"] - (fin_costs or 0.0) - (f.get("ImpairmentOnFinancialInstruments") or 0.0), 4) if lender else f["Expenses"]
    debt = None
    if lender:
        parts = [f.get(k) for k in ("Borrowings", "DebtSecurities", "SubordinatedLiabilities")]
        debt = None if all(p is None for p in parts) else round(sum(p or 0.0 for p in parts), 4)
    fm.values = {"group": fm.group, "assets": assets, "owners_equity": equity, "owners_profit": owners, "loans": loans, "net_revenue": net_rev}
    material, gain, rule = exceptional_materiality(exc, pbt, pre_exc, revenue)
    loss_bypass = bool(material and not gain and exc is not None and exc < 0 and owners is not None)
    adj = None
    if loss_bypass:
        tax = f.get("TaxExpense"); t = max(0.0, min(tax / pbt, EXCEPTIONAL_LOSS_TAX_CAP)) if (pbt and pbt > 0 and tax is not None) else 0.0
        adj = round(owners - exc * (1 - t), 4)
    fm.flags = {"exceptional_material": bool(material), "exceptional_gain_material": bool(gain), "scope": ref.scope, "exceptional_rule": rule, "group": fm.group}
    if gain:
        fm.status = "EXCEPTIONAL_GAIN_REVIEW"

    def na(m, why):
        fm.metrics[m] = None; fm.reasons[m] = why
    if equity is None or owners is None:
        na("roe", "OWNERS_PROFIT_SOURCE_GAP" if owners is None and equity is not None else "CONCEPT_MISSING")
    elif equity <= 0:
        fm.metrics["roe"] = -1.0e9; fm.reasons["roe"] = "NEGATIVE_EQUITY"
    elif material and not loss_bypass:
        na("roe", "EXCEPTIONAL_MATERIAL")
    else:
        fm.metrics["roe"] = round((adj if loss_bypass else owners) / equity * 100, 2)
    if total is None or not assets:
        na("roa", "CONCEPT_MISSING")
    else:
        fm.metrics["roa"] = round(total / assets * 100, 3)
    if net_rev is None or op_cost is None or net_rev <= 0:
        na("cost_to_income", "CONCEPT_MISSING")
    else:
        fm.metrics["cost_to_income"] = round(op_cost / net_rev * 100, 2)
    ok_prior = (prior is not None and prior.ref.scope == ref.scope and prior.annual_status == "audited" and ref.period_end.year - prior.ref.period_end.year == 1
                and prior.ref.period_end.month == ref.period_end.month)
    if not ok_prior:
        na("revenue_growth", "NO_COMPARABLE_PRIOR"); na("profit_growth", "NO_COMPARABLE_PRIOR")
    else:
        pr = prior.facts.get("RevenueFromOperations") or prior.facts.get("Income")
        pp = prior.facts.get("ProfitBeforeExceptionalItemsAndTax") if prior.facts.get("ProfitBeforeExceptionalItemsAndTax") is not None else prior.facts.get("ProfitBeforeTax")
        cur_pp = pre_exc if pre_exc is not None else pbt
        if revenue is None or not pr:
            na("revenue_growth", "CONCEPT_MISSING")
        else:
            fm.metrics["revenue_growth"] = round((revenue / pr - 1) * 100, 2)
        if cur_pp is None or pp in (None, 0):
            na("profit_growth", "CONCEPT_MISSING")
        else:
            fm.metrics["profit_growth"] = round((cur_pp - pp) / abs(pp) * 100, 2)
    if lender:
        if net_rev is None or not assets:
            na("nim", "CONCEPT_MISSING")
        else:
            fm.metrics["nim"] = round(net_rev / assets * 100, 3)
        imp = f.get("ImpairmentOnFinancialInstruments")
        if imp is None or not loans:
            na("credit_cost", "CONCEPT_MISSING")
        else:
            fm.metrics["credit_cost"] = round(imp / loans * 100, 3)
        if debt is None or equity is None:
            na("leverage", "CONCEPT_MISSING")
        elif equity <= 0:
            fm.metrics["leverage"] = 1.0e9; fm.reasons["leverage"] = "NEGATIVE_EQUITY"
        else:
            fm.metrics["leverage"] = round(debt / equity, 3)
    if not market_cap_cr or market_cap_cr <= 0:
        fm.valuation = {"pe": None, "pb": None, "reason": "NO_MARKET_CAP"}
    else:
        pb = round(market_cap_cr / equity, 3) if equity and equity > 0 else None
        prof = adj if loss_bypass else owners
        pe, why = None, None
        if owners is None:
            why = "OWNERS_PROFIT_SOURCE_GAP"
        elif material and not loss_bypass:
            why = "EXCEPTIONAL_MATERIAL"
        elif prof is None or prof <= 0:
            why = "PROFIT_NOT_POSITIVE"
        else:
            pe = round(market_cap_cr / prof, 2)
        fm.valuation = {"pe": pe, "pb": pb, "pe_reason": why, "pb_reason": None if pb is not None else "NEGATIVE_EQUITY" if equity is not None else "CONCEPT_MISSING", "market_cap_cr": market_cap_cr}
    used_4a = loss_bypass and (fm.metrics.get("roe") is not None or fm.valuation.get("pe") is not None)
    fm.flags.update({"rule_4a_exceptional_loss_bypass": bool(used_4a), "adjusted_label": ADJUSTED_LABEL if used_4a else None, "rule_tags": ([RULE_4A] if used_4a else [])})
    bad = plausibility_check(fm.valuation, reference, pe_basis_adjusted=bool(used_4a))
    fm.flags["plausibility_checked"] = bool(reference)
    if bad:
        fm.status = DISCREPANCY_STATUS
        fm.metrics = {m: None for m in directions}
        fm.valuation = {"pe": None, "pb": None, "reason": DISCREPANCY_STATUS, "discrepancy": bad, "market_cap_cr": market_cap_cr}
        fm.flags.update({"rule_4c_discrepancy": bad, "rule_tags": [RULE_4C], "na_label": DISCREPANCY_LABEL})
    return fm


def score_fin_groups(members: list[str], fm: dict, mb: dict) -> dict:
    """Scores each peer group separately (LENDERS / OTHER) with the bank scorer's rules and the group's own metric set."""
    out = {}
    for grp, directions, floor in (("LENDERS", LENDER_DIRECTIONS, LENDER_MIN), ("OTHER", OTHER_DIRECTIONS, OTHER_MIN)):
        ms = [s for s in members if (fm.get(s) or {}).get("group") == grp]
        out.update(bmc.score_bank_group(ms, {s: fm[s] for s in ms}, mb, directions=directions, min_metrics=floor))
    for s in members:
        if s not in out:
            out[s] = {"state": "withheld", "reason": (fm.get(s) or {}).get("status", "NO_FILING_RECORD") if fm.get(s) else "NO_FILING_RECORD"}
    return out
