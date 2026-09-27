"""
S6 — Pilot two-bank FinancialFact refresh, DRY RUN ONLY.

Real data source: NSE's `corporates-financial-results` endpoint (the only
source `ingest.py` currently knows how to fetch) has nothing newer than a
Jan-2025-broadcast Q3 FY2024-25 filing for ICICIBANK/KOTAKBANK, confirmed
live 2026-09-27 (see artifacts/marketripple_score_freshness_root_cause_
2026_09_27.md §5-6). NSE likely migrated current-quarter reporting to a
separate "Integrated Filing" section (also confirmed real, same artifact
§6), but its underlying API could not be identified — NSE's own site
blocks automated/headless browser access at the protocol level.

As an interim, manually-verified alternative — NOT a replacement for
resolving the NSE question for a real recurring pipeline — this script
carries the 8 required (bank x metric) values read directly from each
bank's own official, board-approved regulatory disclosure for the quarter
ended June 30, 2026 (Q1 FY2026-27), with full document-level provenance.
Source label is deliberately "BankDisclosure", never "NSE" — these were
not extracted from any XBRL taxonomy tag, so source_tag/taxonomy are left
null rather than mislabeled.

This script NEVER connects to any database and NEVER writes anything. It:
  1. Reuses the real, unmodified `_fiscal_year_from_financial_year` /
     `_QUARTER_MAP` (ingest.py) to derive fiscal_year/fiscal_quarter from
     the same kind of period string ingest_period() would compute from a
     real filing, rather than hand-deriving a period label.
  2. Reuses the real, unmodified `quality.assess_plausibility()` against
     each real value.
  3. Prints a full preview: value, provenance, expected insert/update,
     the real plausibility-check result, and a rollback method.

A separate, explicitly-approved write script would be created only after
this preview is reviewed — this file intentionally has no --apply mode.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

sys.path.insert(0, r"D:\IG-marketripple-score\apps\backend")

from app.services.financial_facts.ingest import _fiscal_year_from_financial_year, _QUARTER_MAP  # noqa: E402
from app.services.financial_facts import quality  # noqa: E402

# Real filing period for both banks: quarter ended June 30, 2026 = Q1 FY2026-27.
# Financial-year string built in the SAME shape ingest.py's real parser expects
# ("01-Apr-YYYY To 31-Mar-YYYY"), not a hand-picked fiscal_year integer.
_FINANCIAL_YEAR_STR = "01-Apr-2026 To 31-Mar-2027"
_RELATING_TO = "First Quarter"
_PERIOD_END = datetime(2026, 6, 30, tzinfo=timezone.utc)
_BOARD_APPROVED_DATE = datetime(2026, 7, 18, tzinfo=timezone.utc)

FISCAL_YEAR = _fiscal_year_from_financial_year(_FINANCIAL_YEAR_STR)
FISCAL_QUARTER = _QUARTER_MAP[_RELATING_TO]


@dataclass(frozen=True)
class SourceDoc:
    label: str
    url: str
    sha256: str
    fetched_bytes: int
    location: str  # page/table within the document


ICICI_STATUTORY_RESULTS = SourceDoc(
    label="ICICI Bank — Standalone Financial Results, Q1-2027 (statutory filing table)",
    url="https://www.icici.bank.in/content/dam/icicibank/india/managed-assets/docs/about-us/2027/financial-results-q1-2027.pdf",
    sha256="b95bef731a963323ad256416cf2cc473c3c2554f6c09e4a83744ee1a6a094e2a",
    fetched_bytes=344867,
    location="Page 1, item 19 (NPA Ratio) and Page 2, item 20 (Return on assets)",
)
ICICI_PERFORMANCE_REVIEW = SourceDoc(
    label="ICICI Bank — Performance Review narrative page, quarter ended June 30, 2026",
    url="https://www.icici.bank.in/about-us/news-room/2026/performance-review-quarter-ended-june-30-2026",
    sha256="abfdb2aca6c219b9c85f93ac8dd98f04014ffbf72d1a60ffd73d2ec45bf5c514",
    fetched_bytes=1052925,
    location='Narrative paragraph: "CET-1 ratio was 16.19%, on a standalone basis, at June 30, 2026"',
)
KOTAK_MEDIA_RELEASE = SourceDoc(
    label="Kotak Mahindra Bank — Media Release, Q1FY27 (standalone results section)",
    url="https://www.kotak.bank.in/content/dam/Kotak/investor-relation/Financial-Result/QuarterlyReport/FY-2027/q1/PressRelease/Q1-FY27_Press-Release.pdf",
    sha256="54adb21b7e357705313de731671f2409e7ad9fc2eade71f243897ce7ddea623c",
    fetched_bytes=439357,
    location='Page 2, "Kotak Mahindra Bank standalone results" section (GNPA/NNPA/ROA/CET1 all in this one section, before the separate "Consolidated results at a glance" section)',
)


@dataclass(frozen=True)
class PilotRecord:
    symbol: str
    metric_code: str
    metric_name: str
    value_pct: float  # as officially disclosed, in percent
    unit: str
    source: SourceDoc
    quote: str
    annualised: bool | None  # None = not applicable / not stated as annualised


RECORDS: list[PilotRecord] = [
    PilotRecord("ICICIBANK", "gross_npa_pct", "Gross NPA %", 1.38, "pct", ICICI_STATUTORY_RESULTS,
                "% of gross non-performing customer assets (net of write-off) to gross customer assets: 1.38%", None),
    PilotRecord("ICICIBANK", "net_npa_pct", "Net NPA %", 0.35, "pct", ICICI_STATUTORY_RESULTS,
                "% of net non-performing customer assets to net customer assets: 0.35%", None),
    PilotRecord("ICICIBANK", "roa", "Return on Assets", 2.49, "pct", ICICI_STATUTORY_RESULTS,
                "Return on assets (annualised): 2.49%", True),
    PilotRecord("ICICIBANK", "cet1_ratio", "CET1 Ratio", 16.19, "pct", ICICI_PERFORMANCE_REVIEW,
                "CET-1 ratio was 16.19%, on a standalone basis, at June 30, 2026", None),
    PilotRecord("KOTAKBANK", "gross_npa_pct", "Gross NPA %", 1.18, "pct", KOTAK_MEDIA_RELEASE,
                "As at June 30, 2026, GNPA was 1.18% & NNPA was 0.27%", None),
    PilotRecord("KOTAKBANK", "net_npa_pct", "Net NPA %", 0.27, "pct", KOTAK_MEDIA_RELEASE,
                "As at June 30, 2026, GNPA was 1.18% & NNPA was 0.27%", None),
    PilotRecord("KOTAKBANK", "roa", "Return on Assets", 2.14, "pct", KOTAK_MEDIA_RELEASE,
                "Standalone Return on Assets (ROA) for Q1FY27 (annualised) was 2.14%", True),
    PilotRecord("KOTAKBANK", "cet1_ratio", "CET1 Ratio", 22.4, "pct", KOTAK_MEDIA_RELEASE,
                "Capital Adequacy Ratio of the Bank, as per Basel III, as at June 30, 2026 was 22.8% and CET1 ratio of 22.4%", None),
]

# Known from the real, owner-executed production diagnostic (2026-09-26/27):
# the newest stored period for ANY bank/metric in FinancialFact is
# fiscal_year=2025, fiscal_quarter=3. A fiscal_year=2027, fiscal_quarter=1
# row therefore cannot already exist for either symbol -- every record below
# is an INSERT, not an UPDATE. This is a fact carried from that real read,
# not assumed.
_KNOWN_MAX_STORED_PERIOD = (2025, 3)


def preview() -> None:
    print(f"Derived period: fiscal_year={FISCAL_YEAR}, fiscal_quarter={FISCAL_QUARTER}, "
          f"period_end={_PERIOD_END.date()}, consolidation_scope=Non-Consolidated\n")
    assert (FISCAL_YEAR, FISCAL_QUARTER) > _KNOWN_MAX_STORED_PERIOD, (
        "Sanity check failed: this period is not newer than the known stored max — "
        "re-verify before treating these as inserts."
    )

    for i, r in enumerate(RECORDS, 1):
        value_fraction = r.value_pct / 100.0  # DB convention: fraction of 1, matching quality.py's own bounds
        q_status, q_reason = quality.assess_plausibility(r.metric_code, value_fraction)

        print(f"[{i}/8] {r.symbol} — {r.metric_name} ({r.metric_code})")
        print(f"  value: {r.value_pct}% (stored as {value_fraction} per fraction-of-1 DB convention)")
        print(f"  unit: {r.unit}   annualised_basis: {r.annualised}")
        print(f"  fiscal_year={FISCAL_YEAR} fiscal_quarter={FISCAL_QUARTER} period_type=Quarterly "
              f"period_end={_PERIOD_END.date()} consolidation_scope=Non-Consolidated")
        print(f"  source_provider=BankDisclosure  source_tag=None  taxonomy=None  "
              f"(not XBRL-sourced — never labeled NSE)")
        print(f"  source_document_url: {r.source.url}")
        print(f"  source_document_sha256: {r.source.sha256}  ({r.source.fetched_bytes} bytes)")
        print(f"  source_document_location: {r.source.location}")
        print(f"  published_at (board approval date): {_BOARD_APPROVED_DATE.date()}")
        print(f"  quoted disclosure: \"{r.quote}\"")
        print(f"  expected DB action: INSERT (no existing row possible — known max stored period is "
              f"FY{_KNOWN_MAX_STORED_PERIOD[0]} Q{_KNOWN_MAX_STORED_PERIOD[1]} for every bank/metric)")
        print(f"  quality.assess_plausibility() [REAL function, executed]: {q_status}"
              + (f" — {q_reason}" if q_reason else ""))
        print(f"  quality.assess() [within-entity anomaly vs trailing]: NOT SIMULATED — requires this "
              f"symbol's real trailing FinancialFact values from production, which this dry run does not "
              f"have. Will run identically to any ingest_period() call at actual write time.")
        print(f"  rollback: DELETE FROM financial_facts WHERE symbol='{r.symbol}' AND "
              f"metric_code='{r.metric_code}' AND fiscal_year={FISCAL_YEAR} AND fiscal_quarter={FISCAL_QUARTER} "
              f"AND period_type='Quarterly' AND consolidation_scope='Non-Consolidated' — safe because this is a "
              f"pure insert of a period identity that does not currently exist; cannot remove or alter any prior row.")
        print()

    print("Summary: 8/8 records previewed, 8/8 expected INSERT, 0/8 expected UPDATE.")
    print("Plausibility check: run for real against all 8 values above (see per-record output).")
    print("Anomaly check: NOT run — needs production trailing data, not fabricated here.")
    print("No database connection was opened. No write occurred. No --apply mode exists in this script.")


if __name__ == "__main__":
    preview()
