"""
Banking metric registry — every entry traces to a real, live-validated
check (S3/S3-A), not a guess at what the taxonomy might contain. `tag=None`
means confirmed absent from every real taxonomy checked (both the 75-tag
Quarterly and 162-tag Annual `in-bse-fin` schema) — those metrics always
get an explicit SOURCE_UNAVAILABLE FinancialFact row (see FinancialFact's
module docstring, rules 3-4), never silently omitted, and CAR is never
derived from CET1 + AdditionalTier1 (would omit Tier 2 and misrepresent
an estimate as the real disclosed figure).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDef:
    code: str
    name: str
    tag: str | None   # real in-bse-fin XBRL tag name, or None if confirmed unavailable
    unit: str          # "pct" | "inr" | "ratio"
    period_type: str   # "Quarterly" | "Annual" — which real taxonomy carries it


QUARTERLY_METRICS: list[MetricDef] = [
    MetricDef("gross_npa_pct", "Gross NPA %", "PercentageOfGrossNpa", "pct", "Quarterly"),
    MetricDef("net_npa_pct", "Net NPA %", "PercentageOfNpa", "pct", "Quarterly"),
    MetricDef("gross_npa_amount", "Gross NPA (absolute)", "GrossNonPerformingAssets", "inr", "Quarterly"),
    MetricDef("net_npa_amount", "Net NPA (absolute)", "NonPerformingAssets", "inr", "Quarterly"),
    MetricDef("cet1_ratio", "CET1 Ratio", "CET1Ratio", "pct", "Quarterly"),
    MetricDef("additional_tier1_ratio", "Additional Tier 1 Ratio", "AdditionalTier1Ratio", "pct", "Quarterly"),
    MetricDef("roa", "Return on Assets", "ReturnOnAssets", "pct", "Quarterly"),
    MetricDef("interest_earned", "Interest Earned", "InterestEarned", "inr", "Quarterly"),
    MetricDef("interest_expended", "Interest Expended", "InterestExpended", "inr", "Quarterly"),
    # Confirmed absent from the real 75-tag Quarterly taxonomy (S3-A) —
    # explicit known gaps, not silently omitted.
    MetricDef("car_total", "Total Capital Adequacy Ratio (CET1+AT1+Tier2)", None, "pct", "Quarterly"),
    MetricDef("provision_coverage_ratio", "Provision Coverage Ratio", None, "pct", "Quarterly"),
]

ANNUAL_METRICS: list[MetricDef] = [
    MetricDef("advances", "Advances (loan book)", "Advances", "inr", "Annual"),
    MetricDef("deposits", "Deposits", "Deposits", "inr", "Annual"),
    MetricDef("borrowings", "Borrowings", "Borrowings", "inr", "Annual"),
    # Confirmed absent from the real 162-tag Annual taxonomy (S3-A).
    MetricDef("casa_ratio", "CASA Ratio", None, "pct", "Annual"),
]

ALL_METRICS: list[MetricDef] = QUARTERLY_METRICS + ANNUAL_METRICS
METRICS_BY_CODE: dict[str, MetricDef] = {m.code: m for m in ALL_METRICS}
