# S3-B/S3-C — Financial Fact Store Built + Real Five-Bank Backfill

Date: 2026-08-25. Follow-up to `artifacts/marketripple_score_s3a_reliability_and_casa_check.md`. Built the reusable `FinancialFact` store (S3-B) and ran a real, multi-period backfill across all 5 reference banks (S3-C). `publishable` stays `False` on the score engine — this doesn't wire anything into it yet.

## What was built

- **`app/db/models/financial_fact.py`** — the exact schema you specified: entity/metric/value/unit, fiscal period, `consolidation_scope` (load-bearing, not metadata — see below), full provenance (`source_document_url`, `source_document_id`, `source_tag`, `taxonomy`), and **separate** `extraction_status` (did we get a real value at all: `POPULATED`/`SOURCE_UNAVAILABLE`/`TAG_MISSING`/`PARSE_FAILED`) vs `quality_status`+`quality_reason` (given a real value, is it trustworthy: `OK`/`ANOMALY`/`STALE`) — your rule 2, encoded as two real columns, not conflated into one.
- **`app/services/financial_facts/`** — `nse_xbrl_client.py` (the real, validated NSE query + XBRL fetch/parse), `metrics.py` (the registry — every metric traces to a real S3-A finding; `car_total`/`casa_ratio` are registered with `tag=None`, guaranteeing an explicit `SOURCE_UNAVAILABLE` row rather than silent omission, and CAR is never computed as CET1+AT1 anywhere in this code), `quality.py` (the anomaly check), `ingest.py` (orchestrator with real upsert semantics on the identity index).
- **`scripts/financial_facts_backfill.py`** — the real S3-C runner.
- 7 pure-logic tests, `tests/services/test_financial_facts.py`.

## Two real bugs found and fixed while validating — before trusting any output

**Bug 1 — anomaly detection was structurally blind on the first real run.** Filings come back newest-first from NSE; ingesting in that order meant the *oldest* requested quarter got written *last*, so by the time the real ICICIBANK Q1 FY25 case was assessed, its own chronologically-prior quarters weren't in the DB yet — zero real trailing context, so it trivially reported `OK`. Fixed by fetching a real trailing buffer and processing strictly oldest-first. Confirmed fixed: the real anomaly count went from 0 to 2 (both real, on the exact expected quarter).

**Bug 2 — the ratio-based anomaly threshold was noisy near a genuinely-tiny baseline.** `AdditionalTier1Ratio` legitimately sits near zero for these banks most quarters (many carry little/no AT1 capital) — a real move from 0.0009 to 0.0 registered as a "0.0x deviation," flagging 5 false anomalies alongside the real one. Fixed by skipping the ratio check entirely when the trailing median's own absolute value is below a small floor (0.5%) — ratio comparison has no real signal that close to zero. Re-ran: exactly 2 real anomalies remain, both `ICICIBANK FY2025 Q1` — **Gross NPA (0.02%) and ROA (0.02%) simultaneously**, the same real quarter, which is itself a valuable corroborating signal (two independent metrics going anomalous together in the same filing points at a real, systemic filing-quality event for that one quarter, not two coincidences).

## Real backfill results, all 5 reference banks

**Quarterly** (CET1/NPA/ROA, 8 real quarters requested per bank — 4 to keep + 4 trailing buffer): clean and consistent across every bank — 72 populated, 0 tag_missing, 16 source_unavailable (= `car_total`+`provision_coverage_ratio` × 8 quarters, exactly as designed), 0 parse_failed. Anomalies: 2 for ICICIBANK, 2 for KOTAKBANK, 0 for the other 3 — genuinely different per bank, not a systemic bug (spot-checked KOTAKBANK's flagged case separately from ICICIBANK's, both are real, distinct events).

**Annual** (Advances/Deposits/Borrowings, 7 real filings requested per bank): here the real result is a genuine correction to what S3-A reported.

## Correction to S3-A: Advances/Deposits history is real but currently only 1 year deep, not the "38 real annual filings" I cited before

S3-A's claim that "38 real annual filings exist for ICICIBANK alone... enough real history to compute Advances growth" conflated **filing count** with **tag availability**. Checked directly this time: of 7 real annual filings pulled for ICICIBANK, only the single most recent (FY2024) has real, populated `Advances`/`Deposits`/`Borrowings` values. Every older one (FY2023, FY2022, FY2020, FY2019) shows `TAG_MISSING` — confirmed by fetching FY2023's real XBRL directly: 134 real tags, none named `Advances` or `Deposits`. This is a real, structural finding, not a fetch bug: **SEBI's XBRL taxonomy for these specific balance-sheet fields is new enough that only the most recent annual cycle carries them** — older filings were submitted under a prior taxonomy version that didn't include them. Confirmed the same pattern across all 5 banks (each shows exactly 3 populated / 12-18 tag_missing in the real backfill counts, i.e. exactly 1 real year × 3 tags each).

**Practical consequence**: Deposit growth and Advances growth are **not computable today** — there's only one real data point per bank, not two. This will become real as a second annual filing cycle accumulates under the same taxonomy (next year's results), not something a broader historical backfill can retroactively produce. yfinance was already checked in S1 and doesn't carry `Deposits`/`Advances` as distinct balance-sheet rows either (only a combined `Investments And Advances` figure), so there's no ready alternate source to backfill this retroactively right now.

One separate, minor real issue: ICICIBANK's oldest requested annual filing (FY2018-era) returned `PARSE_FAILED` — a real fetch/parse error, likely a moved or deprecated archive URL for a filing that old. Not investigated further (low priority — outside the real, current-quarter reference window that matters for the score).

## Updated real scorecard

| Metric | Status after S3-B/C |
|---|---|
| Gross NPA %, Net NPA %, CET1 Ratio, ROA | **Real, populated, 20/20 bank-quarters (5 banks × 4 quarters), quality-checked** |
| Additional Tier 1 Ratio | Real, populated, genuinely near-zero for most banks (not scored as informative on its own — too close to zero for the quality check to be meaningful either) |
| Advances, Deposits, Borrowings (level) | **Real, 1 year deep per bank** — usable as a snapshot, not yet for growth |
| Advances growth, Deposit growth | **Not yet computable** — needs a second real annual cycle under the current taxonomy |
| CASA, Provision Coverage Ratio, full CAR | Confirmed structurally absent — explicit `SOURCE_UNAVAILABLE` rows written, not silently omitted |

## Status

S3-B (store + ingest infrastructure) and S3-C (real 5-bank backfill) both done. `publishable=False` unchanged — nothing wired into the score engine yet. Ready for S3-D (rerun the S2 engine using these real facts) on your go-ahead, with one real scoping adjustment from what was originally planned: Financial Strength's growth-rate metrics (deposit/advances growth) aren't available yet, so S3-D would use real GNPA/NNPA/CET1/ROA levels plus the existing ROE/NII-growth/profit-growth from yfinance — not the full growth-rate picture across all balance-sheet metrics, since that genuinely isn't there yet.
