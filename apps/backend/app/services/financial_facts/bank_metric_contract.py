"""
Shadow method for BANKS (NSE_FILING_BANK_V1). Not wired into any live scorer or scheduler.

Banks file on the Integrated Filing "BANKING" taxonomy, which has no revenue-from-operations, current liabilities or EBIT, so the industrial metrics do not
apply. Same evidence standard as the industrial contract: audited full-year context (the filing's own statement), Consolidated preferred, units INR -> crore,
owners' profit never substituted, material exceptional items block ROE / P-E, valuation needs BOTH P/E and P/B, plausibility guard against live reference.

Scored metrics (peer percentile among banks; direction in BANK_HIGHER_IS_BETTER):
  roe            owners' profit / owners' equity
  roa            profit for the period / total assets
  nim            (interest earned - interest expended) / total assets        (net interest margin on assets)
  cost_to_income operating expenses / (net interest income + other income)   (lower is better)
  gross_npa      gross NPA ratio as filed                                    (lower is better)
  net_npa        net NPA ratio as filed                                      (lower is better)
  cet1           CET1 ratio as filed
  profit_growth  growth of pre-exceptional profit before tax vs the audited prior year, same scope
Financial strength = mean of the available metric percentiles (>= BANK_MIN_METRICS of 8).
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date

import requests

from app.services.financial_facts import nse_integrated_filing as nif
from app.services.financial_facts.filing_metric_contract import (
    ADJUSTED_LABEL, DISCREPANCY_LABEL, DISCREPANCY_STATUS, EXCEPTIONAL_LOSS_TAX_CAP, FRESH_DAYS, RULE_4A, RULE_4C, exceptional_materiality, plausibility_check,
)

BANK_CONTRACT_VERSION = "NSE_FILING_BANK_V1"
BANK_HIGHER_IS_BETTER = {"roe": True, "roa": True, "nim": True, "cost_to_income": False, "gross_npa": False, "net_npa": False, "cet1": True, "profit_growth": True}
BANK_MIN_METRICS = 5
_FLOW = ("InterestEarned", "InterestExpended", "OtherIncome", "OperatingExpenses", "OperatingProfitBeforeProvisionAndContingencies",
         "ProvisionsOtherThanTaxAndContingencies", "ProfitLossFromOrdinaryActivitiesBeforeTax", "ProfitBeforeExtraordinaryItemsAndTax", "ExceptionalItems",
         "TaxExpense", "ProfitLossForThePeriod", "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates", "ProfitLossOfMinorityInterest")
_INSTANT = ("Advances", "Deposits", "Borrowings", "Capital", "ReservesAndSurplus", "CapitalAndLiabilities", "Assets")
_RATIO = ("PercentageOfGrossNpa", "PercentageOfNpa", "CET1Ratio", "AdditionalTier1Ratio")  # period-end ratios as filed, any context ending at the period end
_PER_SHARE = ("BasicEarningsPerShareAfterExtraordinaryItems",)
_BANKING_MARKER = "BANKING"


@dataclass
class BankFiling:
    ref: nif.FilingRef
    sha256: str
    facts: dict = field(default_factory=dict)       # concept -> INR crore (flow/instant) or ratio as filed
    prior: dict = field(default_factory=dict)       # prior-year flow facts, crore
    eps: float | None = None
    fullyear_audit: str = ""
    annual_status: str = ""
    level_of_rounding: str | None = None


def _num(text) -> float | None:
    try:
        return float((text or "").strip())
    except ValueError:
        return None


def extract_bank(ref: nif.FilingRef, session: requests.Session | None = None, raw_dir: str | None = None) -> BankFiling:
    import glob
    body = None
    if raw_dir:
        hits = sorted(glob.glob(f"{raw_dir}/{ref.symbol}_{ref.filing_file_id}_*.xml"))
        if hits:
            with open(hits[0], "rb") as fh:
                body = fh.read()
    if body is None:
        resp = (session or nif._session()).get(ref.xbrl_url, headers=nif._HEADERS, timeout=60)
        resp.raise_for_status()
        body = resp.content
        if raw_dir:
            with open(f"{raw_dir}/{ref.symbol}_{ref.filing_file_id}_{hashlib.sha256(body).hexdigest()[:12]}.xml", "wb") as fh:
                fh.write(body)
    root = ET.fromstring(body)
    ctx = nif._contexts(root)
    # banking-format contexts also carry the true period in the DateOfStart/EndOfReportingPeriod facts
    starts, ends = {}, {}
    for el in root.iter():
        n = el.tag.split("}")[-1]
        if n == "DateOfStartOfReportingPeriod" and el.text:
            starts[el.get("contextRef")] = el.text.strip()
        elif n == "DateOfEndOfReportingPeriod" and el.text:
            ends[el.get("contextRef")] = el.text.strip()
    for cid in set(starts) & set(ends):
        try:
            if cid in ctx and ctx[cid][0] == "duration":
                ctx[cid] = ("duration", date.fromisoformat(starts[cid]), date.fromisoformat(ends[cid]), ctx[cid][3])
        except ValueError:
            pass
    bf = BankFiling(ref=ref, sha256=hashlib.sha256(body).hexdigest(), annual_status="unverified_unaudited")
    pe = ref.period_end
    prior_end = date(pe.year - 1, pe.month, min(pe.day, 28)) if pe.month == 2 else date(pe.year - 1, pe.month, pe.day)
    stmts = set()
    for el in root.iter():
        name = el.tag.split("}")[-1]
        if name == "LevelOfRounding" and el.text:
            bf.level_of_rounding = el.text.strip()
        c = ctx.get(el.get("contextRef"))
        if not c or c[3]:
            continue
        kind, start, end, _ = c
        if name == "WhetherResultsAreAuditedOrUnaudited" and el.text and kind == "duration" and nif._is_year(start, end) and end == pe:
            stmts.add(el.text.strip())
            continue
        v = _num(el.text)
        if v is None:
            continue
        if name in _FLOW and kind == "duration" and nif._is_year(start, end):
            if end == pe:
                bf.facts.setdefault(name, round(v / 1e7, 4))
            elif end == prior_end:
                bf.prior.setdefault(name, round(v / 1e7, 4))
        elif name in _INSTANT and kind == "instant":
            if end == pe:
                bf.facts.setdefault(name, round(v / 1e7, 4))
            elif end == prior_end:
                bf.prior.setdefault(name, round(v / 1e7, 4))
        elif name in _RATIO and end == pe:
            bf.facts.setdefault(name, v)
        elif name in _PER_SHARE and kind == "duration" and nif._is_year(start, end) and end == pe:
            bf.eps = v
    bf.fullyear_audit = next(iter(stmts)) if len(stmts) == 1 else ("AMBIGUOUS" if stmts else "")
    bf.annual_status = "audited" if bf.fullyear_audit.lower() == "audited" else "unverified_unaudited"
    return bf


def select_bank_annual(rows: list[dict], scope_preference=("Consolidated", "Standalone"), session: requests.Session | None = None,
                       raw_dir: str | None = None, max_periods: int = 6) -> tuple["BankFiling | None", dict]:
    """Newest year-end banking filing whose own full-year statement says Audited; scope preference applies within a year end."""
    info: dict = {"notes": [], "newer_unaudited_year_end": False}
    brows = [r for r in rows if _BANKING_MARKER in (r.get("xbrl") or "") and nif._parse_qe(r.get("qe_Date"))]
    fy_months = {nif._parse_qe(r["qe_Date"]).month for r in brows if r.get("audited") == "Audited"}
    ends = sorted({nif._parse_qe(r["qe_Date"]) for r in brows if nif._parse_qe(r["qe_Date"]).month in fy_months}, reverse=True)
    unverified: list[date] = []
    for pe in ends[:max_periods]:
        for scope in scope_preference:
            cands = [nif._ref(r) for r in brows if r.get("consolidated") == scope and nif._parse_qe(r["qe_Date"]) == pe]
            cands = [c for c in cands if c]
            if not cands:
                continue
            aud = [c for c in cands if c.audited == "Audited"]
            ref = sorted(aud or cands, key=lambda c: (c.revised or c.broadcast or __import__("datetime").datetime.min))[-1]
            try:
                bf = extract_bank(ref, session, raw_dir)
            except requests.HTTPError:
                info["notes"].append(f"{pe} {scope}: link error")
                continue
            if "InterestEarned" not in bf.facts and "ProfitLossForThePeriod" not in bf.facts:
                info["notes"].append(f"{pe} {scope}: no full-year context")
                continue
            if bf.annual_status != "audited":
                info["notes"].append(f"{pe} {scope}: full-year status {bf.fullyear_audit or 'missing'}")
                unverified.append(pe)
                continue
            info["newer_unaudited_year_end"] = any(u > pe for u in unverified)
            return bf, info
    return None, info


@dataclass
class BankMetrics:
    symbol: str
    contract_version: str = BANK_CONTRACT_VERSION
    provenance: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    reasons: dict = field(default_factory=dict)
    flags: dict = field(default_factory=dict)
    valuation: dict = field(default_factory=dict)
    status: str = "ok"


def compute_bank(symbol: str, bf: "BankFiling | None", prior: "BankFiling | None", market_cap_cr: float | None, today: date | None = None,
                 newer_unaudited_year_end: bool = False, reference: dict | None = None, ratio_source: "BankFiling | None" = None) -> BankMetrics:
    today = today or date.today()
    fm = BankMetrics(symbol=symbol)
    scored = tuple(BANK_HIGHER_IS_BETTER)
    if bf is None:
        fm.status = "NO_FILING"; fm.reasons = {m: "NO_FILING" for m in scored}; return fm
    ref = bf.ref; f = bf.facts
    fm.provenance = {"seq_Id": ref.seq_id, "file_id": ref.filing_file_id, "url": ref.xbrl_url, "sha256": bf.sha256, "scope": ref.scope, "audited": ref.audited,
                     "fullyear_audit_statement": bf.fullyear_audit, "period_end": str(ref.period_end), "level_of_rounding": bf.level_of_rounding,
                     "market_cap_source": "Yahoo Finance (interim)"}
    if bf.annual_status != "audited" or (today - ref.period_end).days > FRESH_DAYS:
        fm.status = "UNVERIFIED_UNAUDITED" if (bf.annual_status != "audited" or newer_unaudited_year_end) else "NO_FILING"
        fm.reasons = {m: fm.status for m in scored}; return fm

    def na(m, why):
        fm.metrics[m] = None; fm.reasons[m] = why
    assets = f.get("CapitalAndLiabilities") if f.get("CapitalAndLiabilities") else f.get("Assets")
    equity = None if f.get("Capital") is None or f.get("ReservesAndSurplus") is None else round(f["Capital"] + f["ReservesAndSurplus"], 4)
    profit = f.get("ProfitLossForThePeriod")
    owners = f.get("ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates") if ref.scope == "Consolidated" else profit
    if ref.scope == "Consolidated" and owners is None:
        owners = None if profit is None else (round(profit - f["ProfitLossOfMinorityInterest"], 4) if f.get("ProfitLossOfMinorityInterest") is not None else None)
    nii = None if f.get("InterestEarned") is None or f.get("InterestExpended") is None else round(f["InterestEarned"] - f["InterestExpended"], 4)
    income = None if nii is None or f.get("OtherIncome") is None else round(nii + f["OtherIncome"], 4)
    pbt = f.get("ProfitLossFromOrdinaryActivitiesBeforeTax")
    pre_exc = f.get("ProfitBeforeExtraordinaryItemsAndTax")
    exc = f.get("ExceptionalItems")
    fm.values = {"net_interest_income": nii, "total_assets": assets, "owners_equity": equity, "owners_profit": owners, "profit": profit, "pbt": pbt}
    material, gain, rule = exceptional_materiality(exc, pbt, pre_exc, income)
    loss_bypass = bool(material and not gain and exc is not None and exc < 0 and owners is not None)
    adj = None
    if loss_bypass:
        tax = f.get("TaxExpense"); t = max(0.0, min(tax / pbt, EXCEPTIONAL_LOSS_TAX_CAP)) if (pbt and pbt > 0 and tax is not None) else 0.0
        adj = round(owners - exc * (1 - t), 4)
    fm.flags = {"exceptional_material": bool(material), "exceptional_gain_material": bool(gain), "scope": ref.scope, "exceptional_rule": rule}
    if gain:
        fm.status = "EXCEPTIONAL_GAIN_REVIEW"
    # ROE
    if equity is None or owners is None:
        na("roe", "CONCEPT_MISSING")
    elif equity <= 0:
        fm.metrics["roe"] = -1.0e9; fm.reasons["roe"] = "NEGATIVE_EQUITY"
    elif material and not loss_bypass:
        na("roe", "EXCEPTIONAL_MATERIAL")
    else:
        fm.metrics["roe"] = round((adj if loss_bypass else owners) / equity * 100, 2)
    if profit is None or not assets:
        na("roa", "CONCEPT_MISSING")
    else:
        fm.metrics["roa"] = round(profit / assets * 100, 3)
    if nii is None or not assets:
        na("nim", "CONCEPT_MISSING")
    else:
        fm.metrics["nim"] = round(nii / assets * 100, 3)
    if income is None or not income or f.get("OperatingExpenses") is None:
        na("cost_to_income", "CONCEPT_MISSING")
    else:
        fm.metrics["cost_to_income"] = round(f["OperatingExpenses"] / income * 100, 2)
    # Asset-quality and capital ratios are filed as fractions (0.0203 = 2.03%) and, in consolidated bank filings, usually as 0 (not reported at group level):
    # they are read from the audited STANDALONE filing of the same year when the primary filing is consolidated. A reported 0 is treated as not reported.
    rsrc = ratio_source.facts if (ratio_source is not None and ratio_source.annual_status == "audited" and ratio_source.ref.period_end == ref.period_end) else {}
    fm.provenance["ratio_source_scope"] = ratio_source.ref.scope if rsrc else ref.scope
    for m, c in (("gross_npa", "PercentageOfGrossNpa"), ("net_npa", "PercentageOfNpa"), ("cet1", "CET1Ratio")):
        v = (rsrc.get(c) if ref.scope == "Consolidated" else f.get(c))
        if v is None or (v == 0 and m != "net_npa") or abs(v) > 1.0:
            na(m, "CONCEPT_MISSING")
        else:
            fm.metrics[m] = round(v * 100, 3)
    # profit growth on pre-exceptional profit before tax, comparable basis only
    pr = prior
    if pr is None or pr.ref.scope != ref.scope or pr.annual_status != "audited" or ref.period_end.year - pr.ref.period_end.year != 1 or pr.ref.period_end.month != ref.period_end.month:
        na("profit_growth", "NO_COMPARABLE_PRIOR")
    else:
        pp = pr.facts.get("ProfitBeforeExtraordinaryItemsAndTax")
        if pre_exc is None or pp in (None, 0):
            na("profit_growth", "CONCEPT_MISSING")
        else:
            fm.metrics["profit_growth"] = round((pre_exc - pp) / abs(pp) * 100, 2)
    # valuation (both components required downstream)
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
    fm.flags.update({"rule_4a_exceptional_loss_bypass": bool(used_4a), "adjusted_label": ADJUSTED_LABEL if used_4a else None,
                     "rule_tags": ([RULE_4A] if used_4a else [])})
    # Rule 4C plausibility guard (same rule as the industrial contract)
    bad = plausibility_check(fm.valuation, reference, pe_basis_adjusted=bool(used_4a))
    fm.flags["plausibility_checked"] = bool(reference)
    if bad:
        fm.status = DISCREPANCY_STATUS
        fm.reasons = {m: DISCREPANCY_STATUS for m in scored}
        fm.metrics = {m: None for m in scored}
        fm.valuation = {"pe": None, "pb": None, "reason": DISCREPANCY_STATUS, "discrepancy": bad, "market_cap_cr": market_cap_cr}
        fm.flags.update({"rule_4c_discrepancy": bad, "rule_tags": [RULE_4C], "na_label": DISCREPANCY_LABEL})
    return fm


def score_bank_group(members: list[str], fm: dict, mb: dict) -> dict:
    """Peer scoring for banks. fm: symbol -> BankMetrics dict; mb: symbol -> stored market-behaviour pillar. Same rules as the industrial scorer:
    mid-rank percentiles per metric, valuation = mean of peer P/E and P/B percentiles (both required), headline 8/15 FS + 4/15 valuation + 3/15 market
    behaviour, coverage >= 65, bands Strong >= 75 / Positive >= 60 / Neutral >= 45 / Cautious."""
    from fractions import Fraction
    from app.services.financial_facts import filing_shadow_score as fss
    usable = {s: f for s, f in fm.items() if s in members and f and f.get("metrics")}
    pct = {}
    for m, hib in BANK_HIGHER_IS_BETTER.items():
        vals = {s: f["metrics"].get(m) for s, f in usable.items() if f["metrics"].get(m) is not None}
        pct[m] = {s: fss.percentile_rank(vals, s, cheaper_is_better=not hib) for s in vals}
    pes = {s: f["valuation"].get("pe") for s, f in usable.items() if f["valuation"].get("pe") is not None}
    pbs = {s: f["valuation"].get("pb") for s, f in usable.items() if f["valuation"].get("pb") is not None}
    out = {}
    for s in members:
        f = fm.get(s)
        if f is None:
            out[s] = {"state": "withheld", "reason": "NO_FILING_RECORD"}; continue
        if f["status"] != "ok":
            out[s] = {"state": "withheld", "reason": f["status"]}
            if (f.get("flags") or {}).get("na_label"):
                out[s]["label"] = f["flags"]["na_label"]
            continue
        used = [m for m in BANK_HIGHER_IS_BETTER if pct[m].get(s) is not None]
        fs = round(sum(pct[m][s] for m in used) / len(used), 1) if used else None
        pe_p = fss.percentile_rank(pes, s, True) if s in pes else None
        pb_p = fss.percentile_rank(pbs, s, True) if s in pbs else None
        val = round((pe_p + pb_p) / 2, 1) if pe_p is not None and pb_p is not None else None
        r = {"fs": fs, "fs_n": len(used), "val": val, "val_parts": [k for k, v in (("pe", pe_p), ("pb", pb_p)) if v is not None], "mb": mb.get(s)}
        if len(used) < BANK_MIN_METRICS:
            r.update(state="withheld", reason="INSUFFICIENT_FINANCIAL_METRICS")
        elif val is None:
            r.update(state="withheld", reason="VALUATION_NEEDS_TWO_COMPONENTS (%s)" % ("PE_ONLY" if pe_p is not None else "PB_ONLY" if pb_p is not None else "NONE"))
        elif mb.get(s) is None:
            r.update(state="withheld", reason="MARKET_BEHAVIOUR_MISSING")
        else:
            cov = (len(used) / len(BANK_HIGHER_IS_BETTER) * 100) * 8 / 15 + 100 * 4 / 15 + 100 * 3 / 15
            if cov < 65:
                r.update(state="withheld", reason="INSUFFICIENT_OVERALL_COVERAGE")
            else:
                score = round(float(Fraction(fs).limit_denominator(10**6) * Fraction(8, 15) + Fraction(val).limit_denominator(10**6) * Fraction(4, 15)
                                    + Fraction(mb[s]).limit_denominator(10**6) * Fraction(3, 15)), 1)
                r.update(state="scored", score=score, rating=fss.band(score), coverage=round(cov, 1))
                if (f.get("flags") or {}).get("adjusted_label"):
                    r["metadata_flags"] = [f["flags"]["adjusted_label"]]
        out[s] = r
    return out
