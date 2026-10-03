"""
NSE_FILING_METRICS_V1 - the metric contract derived from the two 25-company reconciliation samples (2026-10-03).
Executable, not wired into the scorer or any scheduler. Input: FilingExtract objects from nse_integrated_filing.py.

Canonical source: NSE Integrated Filing - Financials XBRL (as given on the listing row). Yahoo is used only for market cap
(price x shares), labelled as such; its revenue, "unusual items" and "normalized income" are NOT inputs.

FILING SELECTION  newest Ind-AS filing with a ~12-month revenue context; scope Consolidated preferred, else Standalone;
                  Audited preferred; the latest of original/revisions. Period end can be any month.
AUDITED POLICY    an Un-Audited year-end filing is "unverified_unaudited": every filing metric is unavailable
                  (UNVERIFIED_UNAUDITED). The prior audited year is used only if it passes FRESH_DAYS.
UNITS             INR from the raw XBRL value; reported in crore (value / 1e7). Rounding level is recorded, not applied.
REVENUE           RevenueFromOperations as reported on NSE (canonical even where Yahoo defines revenue differently).
PROFIT            three separately named values, never merged:
                    reported_profit            ProfitLossForPeriod (total, after tax, incl. minority)
                    owners_profit              owners_profit() with its basis label (owners / total-less-NCI / standalone total)
                    pre_exceptional_pretax     ProfitBeforeExceptionalItemsAndTax
                  The filing gives no adjusted after-tax figure; none is derived.
EXCEPTIONAL       ExceptionalItemsBeforeTax. Material when |exceptional| > EXCEPTIONAL_MATERIAL_PCT of max(|PBT|,|pre-exceptional|).
                  Material exceptional GAIN: score fails closed (EXCEPTIONAL_GAIN_REVIEW). Material loss: flagged; ROE unavailable.
SCORED METRICS    revenue_growth, profit_growth (pre_exceptional_pretax), roe (owners_profit / owners equity), roce
                  (pre_exceptional_pretax + FinanceCosts) / (Assets - CurrentLiabilities), debt_to_equity, interest_coverage.
                  Negative or zero owners equity: roe and debt_to_equity rank worst (flag negative_equity), never dropped.
GROWTH            only on a comparable basis: prior filing must be the same scope, audited, exactly one year earlier, and the
                  current filing must carry no discontinued-operations / held-for-sale facts. Otherwise growth is unavailable
                  (COMPARATIVE_MAY_BE_RESTATED / NO_COMPARABLE_PRIOR). The integrated XBRL has no income-statement comparatives.
VALUATION         P/B = market cap / owners equity (equity > 0); P/E = market cap / owners_profit when owners_profit > 0,
                  pre_exceptional_pretax > 0 and exceptional is not material. Valuation needs BOTH components (no single-component
                  pillar). Market cap is the labelled Yahoo interim input.
MISSING DATA      every unavailable metric carries one reason code (REASONS below); nothing is inferred or defaulted.
PROVENANCE        per score: contract version, filing seq_Id, file id, URL, retrieved_at, sha256, scope, audited, type_sub,
                  period end, concept names and values (crore), growth basis, market-cap source.
INCOME QUALITY    income that sits OUTSIDE the "exceptional" line can still distort the ratios. Two gates (fail closed, specific reason) and two flags:
                    REGULATORY DEFERRAL  movement = change in (debit - credit) regulatory-deferral balances between this filing and the prior-year filing
                      (filers net the P&L effect into expenses or revenue, so no P&L tag exposes it: CESC +924 Cr on a pre-tax profit of 2,119 Cr).
                      Material (same test as exceptional items) positive movement -> REGULATORY_DEFERRAL_REVIEW; material negative -> ROE and P/E unavailable;
                      balances present but no prior-year filing -> REGULATORY_MOVEMENT_UNKNOWN.
                    NON-CORE PROFIT      core = pre-exceptional profit - other income - positive regulatory movement. A positive pre-exceptional profit with
                      core <= 0 exists only because of non-core income -> NON_CORE_PROFIT_REVIEW.
                    Flags only (recorded, no gate): other income above 50% of pre-exceptional profit; associates' share above 50% of owners' profit.
                  A company that fails an earnings-quality gate is also excluded from peer pools: its ratios are not acceptable score inputs.
UNRESOLVED CASES  KNRCON, VEDL, TRANSWORLD, PRINCEPIPE are forced to UNRESOLVED_REVIEW (no scored values) in shadow runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.services.financial_facts import nse_integrated_filing as nif

CONTRACT_VERSION = "NSE_FILING_METRICS_V1"
CR_UNIT = 1.0e7
EXCEPTIONAL_MATERIAL_PCT = 10.0
EXCEPTIONAL_REVENUE_FLOOR_PCT = 0.5   # a near-zero profit base never makes a tiny item material
FRESH_DAYS = 456
UNRESOLVED_CASES = {"KNRCON", "VEDL", "TRANSWORLD", "PRINCEPIPE"}
REASONS = (
    "UNVERIFIED_UNAUDITED", "NO_FILING", "EXCEPTIONAL_GAIN_REVIEW", "EXCEPTIONAL_MATERIAL", "COMPARATIVE_MAY_BE_RESTATED",
    "NO_COMPARABLE_PRIOR", "CONCEPT_MISSING", "CAPITAL_EMPLOYED_NOT_POSITIVE", "NO_FINANCE_COSTS", "OWNERS_PROFIT_SOURCE_GAP",
    "NEGATIVE_EQUITY", "NO_MARKET_CAP", "PROFIT_NOT_POSITIVE", "UNRESOLVED_REVIEW", "REGULATORY_DEFERRAL_MATERIAL",
)
SCORED = ("revenue_growth", "profit_growth", "roe", "roce", "debt_to_equity", "interest_coverage")
WORST = {"roe": -1.0e9, "debt_to_equity": 1.0e9}  # negative equity ranks worst on these two


@dataclass
class FilingMetrics:
    symbol: str
    contract_version: str = CONTRACT_VERSION
    provenance: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)        # named reported figures (crore)
    metrics: dict = field(default_factory=dict)       # scored metrics: value or None
    reasons: dict = field(default_factory=dict)       # metric -> reason code when None
    flags: dict = field(default_factory=dict)
    valuation: dict = field(default_factory=dict)     # pe / pb or None
    status: str = "ok"                                # ok | UNVERIFIED_UNAUDITED | NO_FILING | EXCEPTIONAL_GAIN_REVIEW | UNRESOLVED_REVIEW


def exceptional_materiality(exc, pbt, pbet, revenue) -> tuple[bool, bool, str]:
    """(material, gain, rule). Explicit for zero, negative and near-zero profit:
      base = max(|PBT|, |pre-exceptional|)   (absolute values, so a loss-making year is judged on its size)
      threshold = max(10% of base, 0.5% of revenue)   (a near-zero base cannot make a tiny item material)
      sign flip: a positive exceptional item that turns a loss (pre-exceptional <= 0) into a profit (PBT > 0) is ALWAYS material
      base == 0 with no revenue to compare: any non-zero item is material (cannot be judged, fails closed)."""
    if exc is None or exc == 0:
        return False, False, "no exceptional item"
    base = max(abs(pbt or 0.0), abs(pbet or 0.0))
    if exc > 0 and pbet is not None and pbt is not None and pbet <= 0 < pbt:
        return True, True, "sign flip: gain turns a loss into a profit"
    threshold = max(EXCEPTIONAL_MATERIAL_PCT / 100 * base, EXCEPTIONAL_REVENUE_FLOOR_PCT / 100 * (revenue or 0.0))
    if threshold == 0:
        return True, exc > 0, "no profit base and no revenue: fails closed"
    material = abs(exc) > threshold
    return material, material and exc > 0, f"|exceptional| {'>' if material else '<='} {threshold:.2f} (max of 10% of base {base:.2f}, 0.5% of revenue)"


def _c(ex: "nif.FilingExtract | None", name: str):
    return nif.crore(ex.facts.get(name)) if ex else None


def compute(symbol: str, ex: "nif.FilingExtract | None", prior: "nif.FilingExtract | None", market_cap_cr: float | None,
            today: date | None = None, newer_unaudited_year_end: bool = False) -> FilingMetrics:
    today = today or date.today()
    fm = FilingMetrics(symbol=symbol)
    if symbol.upper() in UNRESOLVED_CASES:
        fm.status = "UNRESOLVED_REVIEW"
        fm.reasons = {m: "UNRESOLVED_REVIEW" for m in SCORED}
        return fm
    if ex is None:
        fm.status = "NO_FILING"
        fm.reasons = {m: "NO_FILING" for m in SCORED}
        return fm
    ref = ex.ref
    fm.provenance = {"seq_Id": ref.seq_id, "file_id": ref.filing_file_id, "url": ref.xbrl_url, "retrieved_at": ex.retrieved_at, "sha256": ex.sha256,
                     "scope": ref.scope, "audited": ref.audited, "type_sub": ref.type_sub, "period_end": str(ref.period_end),
                     "currency": ex.currency, "level_of_rounding": ex.level_of_rounding, "market_cap_source": "Yahoo Finance (interim)"}
    stale = (today - ref.period_end).days > FRESH_DAYS
    if ex.annual_status != "audited" or stale:
        # an older audited year is usable only while fresh; if a newer un-audited year-end exists and the audited one is stale,
        # the honest status is UNVERIFIED_UNAUDITED, otherwise the filing is simply too old
        why = "UNVERIFIED_UNAUDITED" if (ex.annual_status != "audited" or newer_unaudited_year_end) else "NO_FILING"
        fm.status = why
        fm.reasons = {m: why for m in SCORED}
        return fm
    rev, pbet, exc, pbt = _c(ex, "RevenueFromOperations"), _c(ex, "ProfitBeforeExceptionalItemsAndTax"), _c(ex, "ExceptionalItemsBeforeTax"), _c(ex, "ProfitBeforeTax")
    fin, assets, cl = _c(ex, "FinanceCosts"), _c(ex, "Assets"), _c(ex, "CurrentLiabilities")
    eq = _c(ex, "EquityAttributableToOwnersOfParent") if ref.scope == "Consolidated" and _c(ex, "EquityAttributableToOwnersOfParent") is not None else _c(ex, "Equity")
    owners, basis = nif.owners_profit(ex)
    bc, bn = _c(ex, "BorrowingsCurrent"), _c(ex, "BorrowingsNoncurrent")
    fm.values = {"revenue_from_operations": rev, "reported_profit": _c(ex, "ProfitLossForPeriod"), "owners_profit": owners, "owners_profit_basis": basis,
                 "pre_exceptional_pretax": pbet, "exceptional_items": exc, "profit_before_tax": pbt, "finance_costs": fin, "assets": assets,
                 "current_liabilities": cl, "owners_equity": eq, "borrowings": None if bc is None and bn is None else (bc or 0.0) + (bn or 0.0)}
    material, gain, mat_rule = exceptional_materiality(exc, pbt, pbet, rev)
    # ---- income quality outside the exceptional line
    oi = _c(ex, "OtherIncome") or 0.0
    assoc = _c(ex, "ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod") or 0.0
    reg_cur = ex.regulatory or {}
    reg_present = abs(reg_cur.get("debit", 0.0)) + abs(reg_cur.get("credit", 0.0)) > 0.005
    reg_move, reg_state = 0.0, "none"
    if reg_present:
        reg_prior = (prior.regulatory if prior is not None else None)
        if prior is None or reg_prior is None:
            reg_state = "unknown"
        else:
            reg_move = round((reg_cur.get("debit", 0.0) - reg_prior.get("debit", 0.0)) - (reg_cur.get("credit", 0.0) - reg_prior.get("credit", 0.0)), 2)
            thr = max(EXCEPTIONAL_MATERIAL_PCT / 100 * max(abs(pbt or 0.0), abs(pbet or 0.0)), EXCEPTIONAL_REVENUE_FLOOR_PCT / 100 * (rev or 0.0))
            reg_state = "material_gain" if (reg_move > 0 and (thr == 0 or reg_move > thr)) else "material_loss" if (reg_move < 0 and (thr == 0 or -reg_move > thr)) else "immaterial"
    core_pretax = None if pbet is None else round(pbet - oi - max(reg_move, 0.0), 2)
    non_core_profit = pbet is not None and pbet > 0 and core_pretax is not None and core_pretax <= 0
    # A disposal / discontinued-operations disclosure counts only when its VALUE is non-zero (most filings carry these concepts as 0).
    # Matched by concept-name pattern (HeldForSale | DisposalGroup | DiscontinuedOperations), not a fixed list: e.g. SKYGOLD tags
    # NoncurrentAssetsClassifiedAsHeldForSale, which a fixed list missed.
    dfacts = dict(ex.disposal_facts)
    for k in ("ProfitLossFromDiscontinuedOperationsAfterTax", "AssetsClassifiedAsHeldForSale", "NoncurrentAssetsOrDisposalGroupsClassifiedAsHeldForSale",
              "LiabilitiesDirectlyAssociatedWithAssetsInDisposalGroupClassifiedAsHeldForSale"):
        if ex.facts.get(k) is not None:
            dfacts[k] = ex.facts[k].value_inr / CR_UNIT
    disposal = any(abs(v) > 0.005 for v in dfacts.values())
    fm.flags = {"exceptional_material": bool(material), "exceptional_gain_material": bool(gain), "disposal_or_discontinued": bool(disposal),
                "negative_equity": eq is not None and eq <= 0, "scope": ref.scope, "exceptional_rule": mat_rule}
    fm.flags.update({"regulatory_balances_present": reg_present, "regulatory_movement_cr": reg_move if reg_state not in ("none", "unknown") else None, "regulatory_state": reg_state,
                     "core_pretax_cr": core_pretax, "non_core_profit": bool(non_core_profit),
                     "other_income_over_half_of_pbet": bool(pbet and pbet > 0 and oi / pbet > 0.5),
                     "associates_over_half_of_owners_profit": bool(owners and owners > 0 and assoc / owners > 0.5)})
    if gain:
        fm.status = "EXCEPTIONAL_GAIN_REVIEW"
    elif reg_state == "material_gain":
        fm.status = "REGULATORY_DEFERRAL_REVIEW"
    elif reg_state == "unknown":
        fm.status = "REGULATORY_MOVEMENT_UNKNOWN"
    elif non_core_profit:
        fm.status = "NON_CORE_PROFIT_REVIEW"

    def na(metric, reason):
        fm.metrics[metric] = None
        fm.reasons[metric] = reason

    # growth (comparable basis only)
    if disposal:
        na("revenue_growth", "COMPARATIVE_MAY_BE_RESTATED"); na("profit_growth", "COMPARATIVE_MAY_BE_RESTATED")
    elif prior is None or prior.ref.scope != ref.scope or prior.annual_status != "audited" or (ref.period_end.year - prior.ref.period_end.year) != 1 or prior.ref.period_end.month != ref.period_end.month:
        na("revenue_growth", "NO_COMPARABLE_PRIOR"); na("profit_growth", "NO_COMPARABLE_PRIOR")
    else:
        pr, pp = _c(prior, "RevenueFromOperations"), _c(prior, "ProfitBeforeExceptionalItemsAndTax")
        if rev is None or not pr:
            na("revenue_growth", "CONCEPT_MISSING")
        else:
            fm.metrics["revenue_growth"] = round((rev / pr - 1) * 100, 2)
        if pbet is None or pp in (None, 0):
            na("profit_growth", "CONCEPT_MISSING")
        else:
            fm.metrics["profit_growth"] = round((pbet - pp) / abs(pp) * 100, 2)
        fm.provenance["growth_basis"] = {"prior_seq_Id": prior.ref.seq_id, "prior_file_id": prior.ref.filing_file_id, "prior_url": prior.ref.xbrl_url,
                                         "prior_sha256": prior.sha256, "basis": "as filed one year earlier, same scope, no disposal facts in current filing"}
    # ROE
    if eq is None:
        na("roe", "CONCEPT_MISSING")
    elif eq <= 0:
        fm.metrics["roe"] = WORST["roe"]; fm.reasons["roe"] = "NEGATIVE_EQUITY"
    elif material:
        na("roe", "EXCEPTIONAL_MATERIAL")
    elif reg_state == "material_loss":
        na("roe", "REGULATORY_DEFERRAL_MATERIAL")
    elif owners is None:
        na("roe", "OWNERS_PROFIT_SOURCE_GAP")
    else:
        fm.metrics["roe"] = round(owners / eq * 100, 2)
    # ROCE and interest coverage on EBIT before exceptional items
    ebit = None if pbet is None or fin is None else pbet + fin
    if ebit is None or assets is None or cl is None:
        na("roce", "CONCEPT_MISSING")
    elif assets - cl <= 0:
        na("roce", "CAPITAL_EMPLOYED_NOT_POSITIVE")
    else:
        fm.metrics["roce"] = round(ebit / (assets - cl) * 100, 2)
    if ebit is None or fin is None:
        na("interest_coverage", "CONCEPT_MISSING")
    elif fin <= 0:
        na("interest_coverage", "NO_FINANCE_COSTS")
    else:
        fm.metrics["interest_coverage"] = round(ebit / fin, 2)
    # debt to equity
    debt = fm.values["borrowings"]
    if eq is None or debt is None:
        na("debt_to_equity", "CONCEPT_MISSING")
    elif eq <= 0:
        fm.metrics["debt_to_equity"] = WORST["debt_to_equity"]; fm.reasons["debt_to_equity"] = "NEGATIVE_EQUITY"
    else:
        fm.metrics["debt_to_equity"] = round(debt / eq, 3)
    # valuation (needs both components)
    if market_cap_cr is None or market_cap_cr <= 0:
        fm.valuation = {"pe": None, "pb": None, "reason": "NO_MARKET_CAP"}
    else:
        pb = round(market_cap_cr / eq, 3) if eq and eq > 0 else None
        pe, pe_reason = None, None
        if owners is None:
            pe_reason = "OWNERS_PROFIT_SOURCE_GAP"
        elif material:
            pe_reason = "EXCEPTIONAL_MATERIAL"
        elif reg_state == "material_loss":
            pe_reason = "REGULATORY_DEFERRAL_MATERIAL"
        elif owners <= 0 or pbet is None or pbet <= 0:
            pe_reason = "PROFIT_NOT_POSITIVE"
        else:
            pe = round(market_cap_cr / owners, 2)
        fm.valuation = {"pe": pe, "pb": pb, "pe_reason": pe_reason, "pb_reason": None if pb is not None else "NEGATIVE_EQUITY" if eq is not None else "CONCEPT_MISSING",
                        "market_cap_cr": market_cap_cr}
    return fm
