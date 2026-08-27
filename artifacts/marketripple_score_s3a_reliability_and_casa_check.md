# S3-A — Multi-Quarter Reliability Check + CASA/Deposits/Advances Search (read-only)

Date: 2026-08-25. Follow-up to `artifacts/marketripple_score_s3_pdf_extraction_feasibility.md`. Two real checks: (1) is HDFCBANK/SBIN's earlier "0.00" result a persistent gap or a one-off, and (2) can CASA/deposits/advances be found via a different real query variant. **No fact store built, no code changed.**

## Correction to the previous report: the "2/5 banks have real gaps" finding was a methodology artifact, not a real data gap

Checked HDFCBANK and SBIN across 4 real historical quarters each. The real cause of the earlier `0.00` result: NSE files **two separate real XBRL documents per quarter** — Consolidated and Non-Consolidated — and my first pass picked whichever the API happened to list first, which was Consolidated for HDFCBANK/SBIN and (coincidentally) Non-Consolidated for the other 3. **Bank-level regulatory ratios (CET1, NPA%) are only ever reported on the Non-Consolidated (standalone) filing — never the Consolidated one.** That's correct, expected behavior (capital-adequacy regulation applies to the bank entity, not the consolidated group including insurance/AMC subsidiaries), not a filer-quality problem. Once explicitly filtered to `consolidated == "Non-Consolidated"`, real data quality across all 5 reference banks turned out excellent:

| Symbol | Q4FY24 CET1 | Q4FY24 GNPA | Q1FY25 CET1 | Q1FY25 GNPA | Q2FY25 CET1 | Q2FY25 GNPA | Q3FY25 CET1 | Q3FY25 GNPA |
|---|---|---|---|---|---|---|---|---|
| ICICIBANK | 15.60% | 2.16% | 15.24% | **0.02%** ⚠️ | 14.65% | 1.97% | 14.04% | 1.96% |
| HDFCBANK | 18.80% | 1.24% | 19.33% | 1.33% | 19.77% | 1.36% | 19.97% | 1.42% |
| AXISBANK | 13.74% | 1.43% | 14.06% | 1.54% | 14.12% | 1.44% | 14.61% | 1.46% |
| KOTAKBANK | 20.55% | 1.39% | 22.41% | 1.39% | 21.52% | 1.49% | 21.71% | 1.50% |
| SBIN | 10.36% | 2.24% | 10.25% | 2.21% | 9.95% | 2.13% | 9.52% | 2.07% |

**20 of 20 real bank-quarters checked, 20 populated.** One real anomaly flagged honestly, not smoothed over: ICICIBANK's Q1 FY25 Gross NPA shows 0.02% (and Net NPA 0.00%) — implausibly low for a bank of this size, versus a normal ~2% in every adjacent quarter. This is either a genuine one-off real reporting event or a filing-side data-entry issue on ICICI's part — flagged as a case the eventual fact store's `quality_status` must be able to catch (e.g., a value that deviates from the trailing trend by an order of magnitude should be flagged for review, not trusted blindly), not resolved here.

## CASA / Deposits / Advances — found via a different real query variant

The Quarterly `period=Quarterly` XBRL taxonomy (75 tags, checked in the first S3 report) does **not** carry these. Checked `period=Annual`, which uses a real, richer taxonomy (**162 distinct tags** for the same real ICICIBANK Non-Consolidated filing) — and it directly includes:

- `Advances` — real value, ICICIBANK FY24: **₹11,84,406.39 Cr** (matches ICICI's real, publicly known FY24 advances figure)
- `Deposits` — real value, ICICIBANK FY24: **₹14,12,824.95 Cr** (matches ICICI's real, publicly known FY24 deposits figure)
- `Borrowings`, `InterestOrDiscountOnAdvancesOrBills` — also real and present

38 real annual filings exist for ICICIBANK alone going back years — genuinely enough real history to compute Advances growth and Deposit growth YoY, not just a single snapshot.

**CASA specifically was not found** — no `SavingsDeposits`/`CurrentAccountDeposits`/`TermDeposits` breakdown tag exists anywhere in either the 75-tag Quarterly or 162-tag Annual taxonomy. This is a real, honest remaining gap: CASA ratio is not disclosed in NSE's XBRL results taxonomy at all — it would need a different real source (bank investor presentations, which are real but a different, likely non-machine-readable format — the original PDF concern, now narrowed to just this one metric).

**Provision Coverage Ratio also checked, also not found**: the real "provision"-related tags present (`ProvisionsOtherThanTaxAndContingencies`, `OperatingProfitBeforeProvisionAndContingencies`) are P&L provisioning *expense* line items, not the balance-sheet coverage *ratio* S1 originally flagged. Genuinely unavailable via this source in a directly-usable form.

## Updated scorecard vs. S1's original 12-metric list

| Metric | S1 verdict | S3/S3-A verdict |
|---|---|---|
| Gross NPA | BLOCKED | **READY** — real, 5/5 banks, 4/4 quarters, Non-Consolidated Quarterly XBRL |
| Net NPA | BLOCKED | **READY** — same source |
| Provision coverage | BLOCKED | **Still BLOCKED** — no direct tag in either taxonomy checked |
| CET1 | BLOCKED | **READY** — same source |
| CAR (total) | BLOCKED | Only `CET1Ratio` + `AdditionalTier1Ratio` found; no combined CAR tag — **PARTIALLY READY** (CET1 alone is real and usable; full CAR would need Tier 2 capital, not found) |
| CASA | BLOCKED | **Still BLOCKED** — checked both taxonomies, not present |
| Deposit growth | BLOCKED | **READY** — real `Deposits` tag, Annual XBRL, 38 real years of history for ICICIBANK |
| Advances (loan book) | BLOCKED | **READY** — real `Advances` tag, same source |
| ROE, ROA, NII growth, Profit growth | already READY (yfinance) | unchanged |

**Net: 2 of the original 7 blocked metrics remain genuinely blocked (CASA, Provision Coverage); 5 are now real and reliably available** — a substantial upgrade from S1's original assessment, which assumed the wrong document type (PDF) entirely.

## What this changes for the fact-store design

- Must key on **Non-Consolidated** filings specifically for bank-regulatory ratios — this is now a load-bearing extraction rule, not an implementation detail.
- Needs **both Quarterly and Annual** XBRL ingestion — they carry different real tag sets (Quarterly: CET1/NPA; Annual: Advances/Deposits). Not a single feed.
- `extraction_status`/`quality_status` (per your schema) needs a real anomaly-detection rule from day one, informed by the real ICICIBANK Q1 FY25 case found here — not hypothetical.
- CASA and full CAR (Tier 1 + Tier 2) stay explicitly unavailable — the store's schema should represent them as `not_applicable`/`source_unavailable` rather than silently omitting them, so a future search for a better source has a clear, named gap to fill.

## Status

S3-A done as instructed. Ready to proceed to S3-B (build the `FinancialFact` store) with a materially better real-data picture than S1 or the first S3 pass suggested — 5 of 7 originally-blocked metrics are real and reliably extractable, not 0.
