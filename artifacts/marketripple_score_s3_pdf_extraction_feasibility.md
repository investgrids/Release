# S3 — Banking Fundamental Data: Real-Source Feasibility Check (read-only)

Date: 2026-08-25. First step of S3 per your instruction: determine whether the metrics S1 found blocked (NPA, CET1/CAR, CASA, deposits, advances) can be reliably extracted from real sources before building any ingestion infrastructure. **No fact store built yet, no code changed** — this is the "can we get it at all, and how reliable is it" question, answered against live data.

## Headline finding: the raw material is real, structured, and much better than PDF

S1 assumed the path to these metrics ran through unparsed PDF attachments on NSE corporate announcements. That's true for the announcements this app currently captures (`corporate-announcements`, `corporate-board-meetings`) — but there is a **separate, real NSE endpoint** already identified but not wired up in an earlier session (`app/providers/nse_provider.py`'s own comments, dated 2026-08-07/09: *"corporates-financial-results was probed live and returned empty in bulk... needs a per-symbol fan-out, not pursued that pass"*). Confirmed live today: a **symbol-scoped, period-scoped query works**, and each real result carries a link to a **real, well-formed XBRL file** — not a PDF at all.

```
GET https://www.nseindia.com/api/corporates-financial-results
    ?index=equities&symbol=ICICIBANK&period=Quarterly
```

Real recent result → `xbrl: "https://nsearchives.nseindia.com/corporate/xbrl/BANKING_117723_1361304_25012025041735.xml"`

That file uses a real, standard, bank-specific taxonomy (`in-bse-fin`, `banking_entry_point_2019-09-30.xsd` — the SEBI/BSE-defined XBRL schema NSE bank filers submit under) with **75 real, labeled fields per filing**, including — directly, by name — the exact metrics S1 found blocked:

- `CET1Ratio` — real value for ICICIBANK: **14.04%**
- `AdditionalTier1Ratio`
- `GrossNonPerformingAssets` / `PercentageOfGrossNpa` — real value for ICICIBANK: **1.96%**
- `NonPerformingAssets` (net) / `PercentageOfNpa` — real value for ICICIBANK: **0.42%**
- `ReturnOnAssets`, `InterestEarned`, `InterestExpended` — corroborate/refine what's already sourced from yfinance

This is a real, structured, machine-readable format — no PDF parsing, no OCR, no table-extraction ambiguity. If this holds up, it closes the two most important categories S1 flagged as blocked (asset quality, capital adequacy) with real, standard, government-mandated disclosure data, not an estimate.

## But: real per-filer data quality varies — checked all 5 reference banks, not just one

Before reporting this as solved, checked the same real tags across all 5 reference banks' most recent real quarterly XBRL filing:

| Symbol | CET1Ratio | Gross NPA % | Net NPA % | Verdict |
|---|---|---|---|---|
| ICICIBANK | 14.04% | 1.96% | 0.42% | **Real, populated** |
| AXISBANK | 14.63% | 1.46% | 0.35% | **Real, populated** |
| KOTAKBANK | 21.71% | 1.50% | 0.41% | **Real, populated** |
| HDFCBANK | 0.00% | 0.00% | 0.00% | **Tags present, values not populated** |
| SBIN | 0.00% (tag absent) | 0.00% | 0.00% | **Tags present, values not populated** |

**3 of 5 real, genuinely usable. 2 of 5 have the real tag structure but the filer left the value as a literal `0.00` placeholder** — confirmed this isn't a wrong-tag problem: pulled SBIN's full real tag list and it has real, correctly-populated *other* fields in the same filing (`PaidUpValueOfEquityShareCapital`, real segment-wise `SegmentAssets` breakdown) — the NPA/CET1-specific tags are simply left at zero in that bank's own submission for that quarter, a real, known category of XBRL filing-quality inconsistency across filers, not something wrong with the query or extraction approach.

## What this means, honestly

- The **source and format are real and correct** — this is the right endpoint, the right file type, the right taxonomy.
- **Coverage is per-filer, per-quarter, not guaranteed** — any real ingestion needs to check a genuine "was this field actually populated" test (e.g., reject an all-zero cluster as unreliable rather than trusting it), and probably needs to check more than one recent quarter per bank before concluding a metric is unavailable, since HDFCBANK/SBIN might have populated these fields correctly in a different real quarter (not checked yet — a real next step, not assumed either way).
- This is **exactly the "never fabricate, honest gaps" pattern already established everywhere else in this codebase** — a fact store built on this source must be able to say "not extracted for HDFCBANK Q3 FY25" rather than silently treating a filer's real `0.00` as a real 0% NPA (which would be a fabrication in the other direction — reporting a suspiciously perfect number as if it were true).

## What wasn't checked yet (real open questions, not resolved by this pass)

- Whether an *older* real quarter for HDFCBANK/SBIN has these fields correctly populated (would tell us whether this is a one-quarter anomaly or a persistent filer-specific gap).
- CASA and deposits/advances — not found as direct tags in this specific filing's 75-tag set. Worth a targeted second pass (a different `resultType` or `format` parameter, or the standalone-vs-consolidated distinction, might surface them) before concluding they're unavailable through this source too.
- Whether NSE's own rate limiting/access patterns (the same `nseindia.com` cookie/session handshake this app's existing NSE provider already handles) would hold up under a real, scheduled per-symbol fan-out across the full company universe, not just 5 manual test calls.

## Recommendation

This is real enough to justify building the structured financial-fact store you described (metric, value, period, unit, source document, entity ID) — the source is genuine, government-mandated disclosure data with the right schema, not a guess. But the store's own design needs a first-class "not reliably extracted" state from day one (not an afterthought), because the real data already proves roughly 40% of even this well-covered 5-bank reference set won't cleanly populate on the first real quarter checked. Suggest checking 1-2 more historical quarters for HDFCBANK/SBIN specifically before finalizing the store's schema, so the "how often does this actually work" question has a real answer wider than a single snapshot.

**Not built yet, per your own sequencing**: the fact store, the backfill, and the S2 rerun. Ready to proceed to those once you've reviewed this — this stops here as instructed.
