# Step 2 (entity grounding + retrieval planning) vs the frozen baseline

Same 18 questions, same scoring rules (`build_report.py`), same 496-test selection. Baseline = `885282e`; Step 2 = this patch on `release/ai-answer-v2`. Answer-level checks stay UNVERIFIED: no model provider could produce a live answer (6 capped calls, all failed, circuit breaker opened). This is not release ready.

## Totals (18 questions)

| Check | Baseline | Step 2 |
|---|---|---|
| route | 12P / 6F / 0U | 16P / 2F / 0U |
| entities | 10P / 8F / 0U | 18P / 0F / 0U |
| evidence | 8P / 10F / 0U | 16P / 2F / 0U |
| addresses_question | 0P / 4F / 14U | 0P / 0F / 18U |
| numbers_supported | 0P / 0F / 18U | 0P / 0F / 18U |
| citations | 0P / 0F / 18U | 0P / 0F / 18U |
| score_consistency | 0P / 0F / 18U | 0P / 0F / 18U |
| degraded_honesty | 18P / 0F / 0U | 18P / 0F / 0U |
| degraded_copy_vs_evidence | 6P / 8F / 4U | 18P / 0F / 0U |

## Per question: route / entities / evidence (baseline -> Step 2)

| Q | Type | Route | Entities | Evidence |
|---|---|---|---|---|
| CR1 | company_research | PASS -> PASS | FAIL -> PASS | FAIL -> PASS |
| CR2 | company_research | PASS -> PASS | FAIL -> PASS | FAIL -> FAIL |
| CR3 | company_research | PASS -> PASS | PASS -> PASS | PASS -> PASS |
| EI1 | event_impact | PASS -> PASS | PASS -> PASS | PASS -> FAIL |
| EI2 | event_impact | PASS -> PASS | PASS -> PASS | PASS -> PASS |
| EI3 | event_impact | PASS -> PASS | PASS -> PASS | PASS -> PASS |
| SR1 | sector_research | PASS -> PASS | PASS -> PASS | PASS -> PASS |
| SR2 | sector_research | PASS -> PASS | PASS -> PASS | PASS -> PASS |
| SR3 | sector_research | FAIL -> PASS | PASS -> PASS | FAIL -> PASS |
| MP1 | macro_policy | FAIL -> PASS | FAIL -> PASS | FAIL -> PASS |
| MP2 | macro_policy | FAIL -> FAIL | FAIL -> PASS | PASS -> PASS |
| MP3 | macro_policy | FAIL -> FAIL | FAIL -> PASS | FAIL -> PASS |
| CC1 | company_comparison | PASS -> PASS | PASS -> PASS | FAIL -> PASS |
| CC2 | company_comparison | PASS -> PASS | PASS -> PASS | FAIL -> PASS |
| CC3 | company_comparison | PASS -> PASS | PASS -> PASS | FAIL -> PASS |
| GE1 | general_explanation | PASS -> PASS | FAIL -> PASS | PASS -> PASS |
| GE2 | general_explanation | FAIL -> PASS | FAIL -> PASS | FAIL -> PASS |
| GE3 | general_explanation | FAIL -> PASS | FAIL -> PASS | FAIL -> PASS |

## What evidence each question actually has (baseline -> Step 2)

- **CR1** What is the outlook for Kotak Mahindra Bank?
  - before: events 10, news 8, policies 0, announcements 0, valuation 0, sector rows 0
  - after: events 0, news 1, policies 0, announcements 4, valuation 0, sector rows 0
- **CR2** How is 3M India doing as a business?
  - before: events 10, news 8, policies 2, announcements 3, valuation 0, sector rows 0
  - after: events 0, news 0, policies 0, announcements 0, valuation 0, sector rows 0
- **CR3** What is happening with TCS lately?
  - before: events 1, news 8, policies 0, announcements 2, valuation 0, sector rows 0
  - after: events 1, news 0, policies 0, announcements 2, valuation 0, sector rows 0
- **EI1** BEL just won a new defence order, what does this mean for the stock?
  - before: events 1, news 8, policies 0, announcements 0, valuation 0, sector rows 0
  - after: events 0, news 0, policies 0, announcements 0, valuation 0, sector rows 0
- **EI2** TCS just announced a new AI research center, what does this mean?
  - before: events 1, news 8, policies 0, announcements 0, valuation 0, sector rows 0
  - after: events 0, news 0, policies 0, announcements 2, valuation 0, sector rows 0
- **EI3** Banking sector just reported stronger credit growth, what is the impact?
  - before: events 10, news 8, policies 0, announcements 0, valuation 0, sector rows 11
  - after: events 10, news 9, policies 0, announcements 0, valuation 0, sector rows 11
- **SR1** How is the banking sector doing right now?
  - before: events 10, news 8, policies 0, announcements 0, valuation 0, sector rows 11
  - after: events 10, news 9, policies 0, announcements 0, valuation 0, sector rows 11
- **SR2** What is the outlook for the IT services sector?
  - before: events 10, news 8, policies 4, announcements 0, valuation 0, sector rows 11
  - after: events 10, news 1, policies 0, announcements 0, valuation 0, sector rows 11
- **SR3** Which sectors look weak in the market at the moment?
  - before: events 10, news 8, policies 5, announcements 0, valuation 0, sector rows 0
  - after: events 0, news 0, policies 0, announcements 0, valuation 0, sector rows 11
- **MP1** What happens to Indian banks if the RBI cuts the repo rate?
  - before: short-circuit, nothing retrieved
  - after: events 10, news 10, policies 0, announcements 0, valuation 0, sector rows 0
- **MP2** How would higher crude oil prices affect Indian markets?
  - before: events 10, news 8, policies 0, announcements 0, valuation 0, sector rows 0
  - after: events 10, news 5, policies 0, announcements 0, valuation 0, sector rows 0
- **MP3** How would a weaker rupee affect Indian IT exporters?
  - before: short-circuit, nothing retrieved
  - after: events 10, news 4, policies 0, announcements 0, valuation 0, sector rows 0
- **CC1** TCS vs Infosys, which is stronger?
  - before: events 1, news 8, policies 0, announcements 0, valuation 0, sector rows 0
  - after: events 1, news 0, policies 0, announcements 6, valuation 2, sector rows 0
- **CC2** Compare HDFC Bank and ICICI Bank.
  - before: events 1, news 8, policies 0, announcements 0, valuation 0, sector rows 0
  - after: events 0, news 0, policies 0, announcements 6, valuation 2, sector rows 0
- **CC3** I hold BEL. Should I switch to HAL?
  - before: events 1, news 8, policies 1, announcements 0, valuation 0, sector rows 0
  - after: events 1, news 0, policies 0, announcements 2, valuation 2, sector rows 0
- **GE1** What is a P/E ratio and how should I read it?
  - before: events 10, news 8, policies 4, announcements 0, valuation 0, sector rows 0
  - after: events 0, news 0, policies 0, announcements 0, valuation 0, sector rows 0
- **GE2** What does FII selling mean for the Indian market?
  - before: short-circuit, nothing retrieved
  - after: events 0, news 0, policies 0, announcements 0, valuation 0, sector rows 0
- **GE3** How does the MarketRipple Score work?
  - before: short-circuit, nothing retrieved
  - after: events 0, news 0, policies 0, announcements 0, valuation 0, sector rows 0
