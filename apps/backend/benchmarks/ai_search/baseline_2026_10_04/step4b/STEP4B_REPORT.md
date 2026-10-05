# Step 4B report: educational / product-information contract (GE1, GE2, GE3)

Zero provider calls. Gate A, Gate B, retrieval ranking, macro routing (4A), prompts, latency and providers are unchanged. Local commit only; nothing pushed or deployed.

## 1. Inspection: why GE1/GE2/GE3 reached an ungated generic path
Traced with the real code (all three: no company, sector or policy entity; specialist `company`; ui_mode `direct_company_research`):
- `evidence_filter.plan_for` gives any "what is / what does / how does / explain ..." question with no entities the **`explanation` plan**: no events, no news, no policies.
- Gate A: `explanation` is `not_gated` (SUFFICIENT with nothing required). Gate B: `answer_authorization.authorize` returns `applicable: False, authorized: True` for that plan. Both are documented in the code as "an educational contract is a separate step".
- The company specialist then answered from the model's memory, with no evidence and no authorization. For P/E that is harmless; for "How does the MarketRipple Score work?" the model was free to invent pillars, weights and bands.
- **A second hole on the same path:** the explanation plan keyed only on the question's first words, so a current-data question phrased as a definition ("What is the Nifty today?", "What is the price of gold today?", "What is the current repo rate?") also took it: no evidence, no gate, free generation.
- Frontend: the answer renders through the normal answer layout; it needed no change (it displays whatever stage label and fields the backend sends).

## 2. Is there an authoritative MarketRipple definition? Yes, with one important catch
| Topic | Authoritative source found |
|---|---|
| P/E | MarketRipple glossary, `apps/web/lib/glossary-data.ts` slug `pe-ratio` ("single source of truth for /learn/glossary") |
| FII selling | same glossary, slugs `fii` and `dii` |
| MarketRipple Score | the public methodology page `apps/web/app/(knowledge)/methodology/marketripple-score/page.tsx` |
**Catch:** the copy of the methodology page in this branch (`release/ai-answer-v2`) is the **older "Banking V1" version** (four pillars 40/20/15/25, banks only). The **deployed** page on `origin/main` (rewritten in aee9f41 and 7eb263d, verified by its author against the backend on 2026-09-27) defines the score as **three weighted pillars, 8/15 Financial Strength, 4/15 Valuation, 3/15 Market Behaviour**, Current Intelligence shown separately and never in the number, Banking plus 19 non-bank sectors, and different publication thresholds (5 of 7 Banking metrics or 4 of 6 non-bank, 65% overall coverage). This branch's backend `engine.py` still has the old four-pillar weights, so the branch alone would have produced a **wrong** product answer. GE3 is therefore grounded in the **deployed** page (origin/main 8bbe68b), not the branch copy, and the contract is tested against it. The score is not redefined or redesigned anywhere.

## 3. The contract (new `ai_search/education.py`, no model call)
- **General education (P/E, FII flows):** a fixed answer copied from the glossary, labelled educational. It contains no company, figure or "today", makes no forecast and gives no recommendation, and says what it does not do ("does not describe any company's current P/E", "does not report how much FIIs bought or sold on any day"). If the question asks for advice or a forecast ("Should I buy when FII selling is high?"), it still gets the explanation plus an explicit notice that it does not forecast or recommend.
- **Product knowledge (MarketRipple Score):** a fixed answer built only from the deployed methodology: pillars and fixed fractions, Current Intelligence separate, sector-specific inputs, supported sectors, peer-relative percentile, rating bands, publication requirements, coverage is not confidence, and "not a prediction of future share-price returns and not a recommendation about any stock". A request for detail the methodology does not publish (exact formula, metric-level weights, back-tests, predictive accuracy, "secret algorithm") gets the same answer plus a notice that those are not part of the published methodology, and no new number. Prediction or advice questions in any interrogative form ("Is it a buy signal?") get the published not-a-prediction statement.
- **What never uses the contract (it continues through the evidence-gated pipeline unchanged):** any question naming a company, sector or policy; any question with a current-data or numeric marker (today, current, latest, this week, how much, price, level, any digit); any question covering more than one topic. So "What is TCS's current P/E?", "How much did FIIs sell today?" and "What is TCS's MarketRipple Score?" still need evidence (shown end to end: Gate A refuses them when no evidence exists).
- **Closing the data-question hole:** `plan_for` now refuses the evidence-free explanation plan to current-data wording, so "What is the Nifty today?" takes the topic plan and is held to Gate A and Gate B. This is a plan classification guard, not a retrieval or ranking change.
- Response: complete, non-degraded, `specialist: "education"`, `education` metadata, `answer_availability` = available with no retrieved evidence, a new `education` stage (so these are not reported as cache hits), source attribution as plain internal text, no external link.
- **Safety gate not bypassed:** the unmodified advisory-language gate rejects the bare words "buy" and "sell" anywhere. Three sentences were reworded with the same meaning ("not a recommendation about any stock" instead of "not a buy/sell recommendation"; "trade Indian securities"; "DIIs absorb FII selling by investing"). The owner's original sentences remain in the sources and are checked by the tests.

## 4. Verification
- `test_ai_search_education.py`: **62 tests**. Frozen GE1/GE2/GE3 recognised; company, current, numeric and multi-topic variants rejected; the explanation plan versus data questions; Gate A refusing those data questions with no evidence; no currency, "today", company name, forecast or advice language in the education text; coverage of definition, reading, limits; advice and forecast requests; the superseded 40/20/15/25 definition absent; detail requests add only the notice and no number; copied sentences verified against the glossary; **GE3 facts verified against the deployed page from `origin/main`** (skipped only if that ref is missing); end to end through the real pipeline with the provider function set to raise: no model call, safety gate passes, honest availability; company and data questions still insufficient-evidence refusals.
- Mutation checks (each fails the tests): dropping the entity guard (5), the current-data guard in the matcher (3), the guard in the retrieval plan (5), changing a published weight (2), restoring a stale weight (3), dropping the not-published notice (4).
- Frozen-18 qualification through the real pipeline (specialists stubbed, **provider calls made: 0**): GE1, GE2 and GE3 are answered by the contract with no specialist and no model call, ui_mode unchanged; the other 15 rows have identical Gate A decisions and outcomes to the 4A run.
- Regression: AI Search, deadline, news, macro, ui_mode selection **893 passed**, 3 xfailed, 12 deselected (live-engine file); wider selection (evidence filter, explanation, entities, ui_mode, routing, intent, safety, availability, finalize) 482 passed, 1 failed: `test_p5_stage2_v3_live.py::test_multi_compare_3plus_entities_v3`, a live test that fails identically before this step. Other known failures are unchanged.

## 5. Review items and debt (outside 4B)
- **Owner review:** one P/E sentence was written for the contract, not copied (earnings can include one-off items such as exceptional gains or losses). It is declared in `TOPICS["pe_ratio"].authored_for_contract` and in the response metadata. The glossary has no such sentence; the frozen question asks for "one-offs", so it was added rather than left out.
- **Branch versus main divergence:** this branch's methodology page and score engine are older than the deployed ones. Merging or rebasing with main should bring the page and engine together; GE3 already matches the deployed page.
- Definitions not in the curated set ("What is EBITDA?") still take the existing evidence-free explanation path with a model answer and no gate. They can no longer be current-data questions, but they remain unvetted prose; widening the curated set, or a light educational authorization for that path, is a separate decision.
- "Is a low P/E good?" and similar non-definitional phrasings of the education topics are not curated and stay on the evidence-gated pipeline (a refusal when no evidence applies).
- The educational answer still shows the generic investment-verdict area as "Not Applicable"; presentation of verdict, confidence and availability for educational answers belongs to Step 4C.
- FII selling's glossary example with a rupee figure was deliberately not used (it would read as a current figure).

## 6. Statements
No push, no deploy. Provider calls: 0. No secrets in any artifact.

NEXT: Step 4C, response semantics cleanup.
