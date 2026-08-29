# MarketRipple Score — S5-D: Methodology Page

**Date:** 2026-08-29
**Scope:** Fourth S5 sub-phase. `/methodology/marketripple-score`, modeled on the real, existing `/ai-methodology` page's structure and design system. Local/shadow only — not deployed, not linked from primary nav.
**Branch:** `company-identity/c1-reconciliation`

## Real-fact verification, per owner instruction

Before writing any copy, verified directly against the real backend code (not memory, not the frontend):

- **Pillar weights** — `engine.py::CANDIDATE_WEIGHTS`: Financial Strength 40%, Valuation 20%, Market Behaviour 15%, Current Intelligence 25%.
- **Rating boundaries** — `engine.py::_label_for()`: Strong ≥75, Positive ≥60, Neutral ≥45, Cautious <45. Confirmed **test-covered** (`tests/services/test_marketripple_score.py:80-91`, including exact boundary cases 75/60/45/44.9) — not just implemented, genuinely locked by a real test.
- **Banking V1's 7 real metrics** — `financial_strength.py::_FACT_METRICS` (Gross NPA %, Net NPA %, CET1 Ratio, ROA) + the 3 yfinance-sourced ones (ROE, NII Growth, Profit Growth).
- **5 disclosed known-unavailable metrics** — `financial_strength.py::_KNOWN_UNAVAILABLE` (CASA Ratio, Provision Coverage Ratio, Total CAR, Deposit Growth, Advances Growth).
- **Publication policy** — `eligibility.py::BANKING_V1_P1`, stated in plain language (≥5/7 metrics, ≥65% overall coverage, Financial Strength required, eligible period required) — the internal identifier `BANKING_V1_P1` is not used as a headline anywhere on the page.

## What was built

Real sections, following the owner's 8-part outline: hero + the "not a prediction" distinction, the four pillars with real weights, Banking V1 (7 real inputs + 5 disclosed gaps, explicit note that future sectors get their own Financial Strength methodology under the same 4-pillar frame), evidence quality (excluded-not-corrected philosophy, no internal jargon like `SOURCE_DOCUMENT_QUARANTINED` exposed), evidence coverage (explicitly distinguished from confidence, matching the owner's exact framing), publication requirements in plain language, a real ratings table, an honest non-"real-time" update-frequency explanation, a Does/Does Not summary, and 3 real FAQ entries with `FAQPage` JSON-LD.

**Explicitly excluded, per instruction**: no company-specific outcomes (YESBANK/INDUSINDBK) — this page documents the methodology only, never an individual company's result.

**Closed the loop from S5-C**: `MarketRippleScoreCard`'s "How this score works →" link (both the eligible-score state and the Unavailable state) now points here instead of nowhere.

## Real live verification

- `tsc --noEmit` clean.
- Real headless-browser check: zero console errors, page title renders (`MarketRipple Score Methodology | Banking V1 | MarketRipple`), full-page screenshot confirms every section renders correctly with the intended design-system styling (matches `/ai-methodology`'s cards, badges, table, FAQ `<details>` pattern).
- Real Company-page → methodology-page link confirmed working from a live ICICIBANK page (`href="/methodology/marketripple-score"`, visible and clickable).

## Status: S5-D DONE

Ready for S5-E (multi-cycle shadow validation) — the last gate before `publishable` can move from `False` to `True` for the 25 individually eligible banks.
