# Step 5: Final Answer Contract

Provider calls: 0. No change to retrieval ranking, Gate A sufficiency, Gate B authorization logic, Step 4A routing, Step 4B curated content, latency settings, providers or the Company Score. Local commits only; nothing pushed or deployed.

## 1. Before-contract audit
`step5/contract_audit.py` runs all 13 final-response classes through the real pipeline and finalizer (provider function set to raise; classes 01 and 02 are saved authorized live responses) and inventories every public key. Full output: `contract_audit_before.json`, `key_inventory_before.json` (after: `*_after.json`).
**13 classes, 58 distinct top-level keys.** Consumers were mapped before anything was removed: the frontend (all non-test web sources), the backend in-process consumers (AEV2, the canonical core, page intelligence, comparison publisher) and the tests.
| Class | A canonical, user-facing | B compatibility only (kept, shape preserved) | C internal diagnostics, exposed by accident | D misleading or unsupported |
|---|---|---|---|---|
| Fields | query, response_id, schema_version, specialist, intent, ui_mode, answer, answer_availability, key_drivers, companies, sectors, related_events, news, policies, citations, claim_sources, evidence_index (authorized answers only), conclusion_scope, education, public_title, follow_up_*, graph, market_chart, timeline, context_used, watch_subject, evidence_score {stars, checklist, source_count}, investment_verdict (authorized fields only) | ai_conclusion, decision_engine_v2, timeline_intelligence, opportunity_risk_matrix, scenarios, decision_intelligence, market_impact_horizons, ai_reasoning_methods, insights, what_to_monitor, monitoring, ripple_chain, historical_comparison (all empty in V2), synthesis_incomplete, degraded_reason, validation, source_attribution, switch_holding/target, company_suggestions, and the confidence_* shapes (now always unscored) | answer_authorization, claim_validation, structured_authorization, timing, evidence_sufficiency, premise_check; evidence_score.development_count and corroborating_source_count | answer.confidence / confidence_level, investment_verdict.confidence, confidence_data score/level/reasons/breakdown, confidence_breakdown.*, confidence.*, verdict horizon and opportunity score without an authorized verdict, the market-wide engine verdict, "neutral" direction and sentiment (fixed in 4C) |
Gate and timing records were read by no client code; `claim_validation` and `structured_authorization` were never read by anything but tests.

## 2. Canonical public contract
Everything a consumer needs to know about *what it received* lives in **one object, `answer_availability`** (no parallel state):
| Field | Meaning |
|---|---|
| `state` | available, limited_evidence, no_verified_evidence, temporarily_unavailable (Step 4C, unchanged) |
| `kind` | research, partial_research, education, product_information, unavailable, temporarily_unavailable |
| `basis` | retrieved_evidence, market_data, education, none |
| `conclusion_authorized` | true only when an authorized structured investment conclusion (a real rating) is present |
| `evidence_count` | evidence items (events, news, policy items) **listed in the response**; 0 for education and for refusals that list nothing |
| `reason` | null when available; otherwise a short public code (evidence_insufficient, retrieval_failed, retrieval_timeout, provider_capacity, generation_failed, time_budget_exhausted, claims_not_authorized, unsupported_subject, education_not_covered, limited_evidence) |
| `scope` | full, partial or none: what was actually answered |
Applied in one module, `ai_search/public_contract.py`, called by the finalizer on every research or educational response (fresh, cached, any route).

## 3. Answer type and state taxonomy (all 13 classes, measured)
| Class | state | kind | scope | reason | basis |
|---|---|---|---|---|---|
| 01 full authorized, evidence-backed | available | research | full | null | retrieved_evidence |
| 02 authorized, narrowed | available | partial_research | partial | null | retrieved_evidence |
| 03 limited evidence, withheld | limited_evidence | unavailable | none | limited_evidence | none |
| 04 genuine evidence insufficiency | no_verified_evidence | unavailable | none | evidence_insufficient | none |
| 05 retrieval failure | temporarily_unavailable | temporarily_unavailable | none | retrieval_failed | none |
| 06 retrieval timeout | temporarily_unavailable | temporarily_unavailable | none | retrieval_timeout | none |
| 07 provider capacity | temporarily_unavailable | temporarily_unavailable | none | provider_capacity | none |
| 08 generation failure | temporarily_unavailable | temporarily_unavailable | none | generation_failed | none |
| 09 time-budget exhaustion | temporarily_unavailable | temporarily_unavailable | none | time_budget_exhausted | none |
| 10 Gate B, claims not authorized | no_verified_evidence | unavailable | none | claims_not_authorized | none |
| 11 general education | available | education | full | null | education |
| 12 product knowledge | available | product_information | full | null | education |
| 13 unsupported subject | no_verified_evidence | unavailable | none | unsupported_subject | none |
A product question asking for detail the methodology does not publish is `product_information` with `scope: partial`. For Step 6: render research, partial research, education or product information, or unavailable/temporary failure from `kind`; `scope` and `reason` refine it.

## 4. Confidence decision: no public answer confidence
Every input to the old figure (for example 42.5 / "Medium") was audited:
- `reasoning_confidence`: the model self-rating is no longer requested and silently defaulted to 5 of 10, i.e. a constant 50.
- `market_confirmation` and `historical_similarity`: 0 both when nothing confirms and when nothing was retrieved.
- A calibration line ("Calibrated from 102 verified predictions (57% historical accuracy)") quoting the accuracy of past stored predictions, which says nothing about this answer. Those predictions were themselves defaulted to "sideways" (see section 5).
- A source term built from a development count.
Nothing here is a fully evidence-derived, defined answer-confidence measure, so **none is published and no replacement formula was invented**. `compute_confidence_breakdown` returns the unscored shape at the source (so AEV2, page intelligence and the routes all see it), and the finalizer enforces it again for cached or saved responses. `answer.confidence`, `answer.confidence_level` ("unscored"), `investment_verdict.confidence`, `confidence_data`, `confidence_breakdown` and `confidence` are null/unscored in all 13 classes.
Evidence quality stays separate and named for what it is: `evidence_score` {stars, checklist, source_count} says how much of the expected evidence was retrieved. It is not answer confidence, a prediction probability or recommendation conviction, and none of those exists in the response. `development_count` and `corroborating_source_count` (counts in a universe the user cannot see, including unlisted filings) left the public contract.

## 5. Verdict semantics, and what depended on the old confidence
- A verdict is public only when its rating is authorized (rating other than "Not Applicable"). Otherwise rating "Not Applicable", direction null, confidence null, **and no horizon or opportunity score** (a horizon such as "1-3 months" implied a verdict that was not made). All 13 classes today. An LLM verdict in a generation never becomes public (tested with a "Strong Buy").
- **The market-wide engine verdict is no longer produced.** It was public for macro questions (MP1 to MP3) and rated from `confidence_breakdown.final_confidence`, while inside the engine a missing direction, confidence, opportunity score and VIX each fall back to a constant ("sideways", 0, 50, 15). Without a measured confidence the only thing it could output is a rating manufactured from defaults, so none is published. The pairwise decision engine had the same dependency and is guarded the same way. Routing and ui_mode for MP1 to MP3 are unchanged.
- **Prediction recording** now happens only for an authorized direction. The recorder defaulted a missing direction to "sideways", so every clean answer with a company was stored as a neutral prediction; those stored predictions fed the "historical accuracy" claim above. Since LLM directions have been withheld since Step 3.4D, this recorder stores nothing until a direction is authorized.
- Forecast and recommendation stay governed by the existing CD3 rules; the verdict field does not reopen them.

## 6. Evidence semantics
`evidence_count` = items listed (Step 4C); `answer.sources_count` and `evidence_score.source_count` always equal it, in every class (tested for all 13). Claims-as-observations is preserved: `claim_sources` and `evidence_index` appear **only on authorized answers** (classes 01 and 02), every claim has sources, every source id exists in the index, and a Gate B rejection exposes none of the rejected generated text, claims, key drivers or timeline.

## 7. Failure and availability semantics
Retrieval failure is not insufficiency (different state, `evidence_retrieval_completed`, wording, reason); capacity is not a retrieval timeout; the time budget running out is its own reason; Gate B rejection stays fail-closed. These are asserted across the real pipeline for all classes. Public wording carries no exception text or internals.

## 8. Educational contract: generic fallback resolved (option B)
Options were a lightweight educational authorization (A) or an honest "not covered" answer (B). **B** was chosen: A would need a new claim-checking authorization for free prose (what counts as a "current-market claim" in an explanation of EBITDA?), which is a new gate to design and to test with live models; B is smaller, deterministic and safe. Any definitional question without a curated, reviewed explanation (for example "What is EBITDA?", "Explain how a SIP works", "How does MarketRipple rank companies?") now returns `degraded_reason: education_not_covered`, kind `unavailable`, scope `none`, reason `education_not_covered`, with no model call, no retrieval, no claims and no numbers: "MarketRipple answers general-knowledge questions only from explanations it has reviewed, and it doesn't have one for this question yet..." That removes the last path where a model could state current market facts, recommendations, forecasts, MarketRipple product facts or invented numbers with no authorization. Current-data wording cannot reach it (it takes the evidence-gated topic plan; tested with seven phrasings including "What is the Nifty today?" and "What does FII selling mean today?"). **Cost:** definitions that used to get a generated explanation now get "not covered yet" until curated; widening the curated set is a content decision (Step 4B), deliberately not done here. GE1 and GE2 are unchanged.

## 9. Product-knowledge contract and the branch/main dependency
Unchanged from Step 4B: MarketRipple product facts come only from an authoritative owner-published source, and nothing generates them (the product topic never reaches a model; an uncurated MarketRipple question gets "not covered"). **Integration dependency:** GE3's text is grounded in the *deployed* methodology page (`origin/main`, three pillars 8/15, 4/15, 3/15). This branch's copy of that page and its score engine are the older four-pillar Banking V1 version and were deliberately not used. When the branch is merged with main, the page and engine must come from main, and the drift test (`test_ge3_facts_match_the_deployed_methodology_page`) must keep passing; the contract bakes in no branch-side methodology.

## 10. Deprecated and internal fields
Internal, removed from the public serialization (still on the pipeline result and in logs): `answer_authorization`, `claim_validation`, `structured_authorization`, `timing`, `evidence_sufficiency`, `premise_check`, and the two `evidence_score` counters. Already internal: `announcements`, `_rejected_generation`, `_engine_verdict_internal`, `_retrieval_failures`.
Compatibility only (shape kept, not for new UI): the empty LLM-structured blocks (scenarios, decision_engine_v2, ai_conclusion, timeline_intelligence, opportunity_risk_matrix, decision_intelligence, market_impact_horizons, ai_reasoning_methods, insights, monitoring, what_to_monitor, ripple_chain, historical_comparison), the confidence_* shapes (always unscored), `synthesis_incomplete`, `degraded_reason`, `validation`, `source_attribution`, `switch_holding/target`.

## 11. Compatibility impact
- Frontend: types gained optional `kind`, `scope`, `conclusion_authorized` and the new `reason` value. `ConfidenceBreakdownPanel` had no null handling and would have drawn "0%"; it now renders nothing without a measured confidence. The verdict hero and evidence-confidence card already handled null. **Frontend suite: 56 files, 588 tests pass; no non-test type errors.**
- Client fallbacks that now show invented values for what the backend correctly sends as null (**Step 6 must remove these**): `horizon || "6-12 months"`, `opportunity_score ?? 50` and `100 - (confidence ?? 50)` for the risk share, `evidence_score.stars ?? 3`.
- AEV2 reads the core built from the already-projected response, so both presenters agree; page intelligence reads the raw pipeline result, which is now unscored at the source. Its separate fallback `{"level": "Medium", "score": 60}` (used only if `confidence_data` is missing) still exists and should be removed with the same rule.
- Ten-plus existing tests pinned the old dicts or the retired behaviour (diagnostics read from the public response, the engine verdict computed in every scope, a prediction stored for every clean answer, the Step 4C confidence copy). They were updated to the contract, not loosened: diagnostics are read from the raw result and asserted absent publicly; the engine test now asserts none is produced; prediction tests assert none without an authorized direction.

## 12. Frozen-18
Real pipeline, specialists stubbed, **provider calls made: 0**: **0 of 18 rows changed** in outcome, Gate A decision, premise status or route versus the Step 4C run (the harness now reads gate records from the raw result, since they are internal). MP1 to MP3 and GE1 to GE3 as before.

## 13. Tests
- `test_ai_search_final_contract.py`: **112 tests**, all 13 classes built once through the real pipeline and finalizer. Per class: kind, scope, reason, basis and `conclusion_authorized`; no neutral, hold or sideways; no confidence number or label; evidence_count equals every public count; no internal diagnostics; minimum shape (query, schema_version, response_id, answer, answer_availability, synthesis_incomplete, investment_verdict). Plus: failure classes distinguishable by reason; retrieval failure is not insufficiency, capacity is not a timeout; partial stays partial; Gate B exposes none of the rejected claims; authorized claims keep their sources and ids resolve; a structured conclusion survives only when authorized and never carries a confidence number; an LLM verdict never becomes public; no confidence depends on a default, a self-rating or the evidence volume; the old 42.5 / reasoning 50 cannot reach a saved response; prediction recording only for an authorized direction; five uncurated educational questions get the honest not-covered answer; seven current-data questions cannot escape into education; GE1 to GE3 and MP1 to MP3 unchanged.
- Mutation checks (each fails the tests): confidence projection removed (4), verdict horizon not nulled (4), diagnostics left public (12), prediction guard removed (1), uncurated education reaching the old path (6), a confidence number returning (9), the engine rating from defaults (5), partial flattened to full research (2).
- Regression: AI Search, deadline, news, macro, ui_mode, availability, pulse-safety and gate-precedence selection **1,098 passed**, 3 xfailed, 12 deselected (the live-engine file); wide selection 996 passed, 7 failed, **all 7 identical at the previous commit** (live-provider tests and `test_quant_leakage`); no new failure.
- A live test, `test_p5_stage3_v3_live::test_engine_verdict_populated_single_entity`, asserts the retired engine-verdict behaviour. It already fails here without providers; it should be retired or rewritten when live tests next run.

## 14. Remaining debt for Step 6 and release
- Step 6: remove the client fallbacks above; render from `kind`/`scope`/`reason`; stop showing the empty compatibility blocks; show `evidence_score` as evidence strength, never as confidence.
- Page intelligence: its own default confidence and its use of the removed fields should follow the same rule; check that surface renders a null score.
- Curated education coverage (content), the branch/main Company Score merge, and the live tests that encode retired behaviour.
- Market Pulse keeps its own response shape; it carries `answer_availability.kind` ("research", basis market_data) but was not otherwise reworked.
- Carried: executor work not cancellable, cap/minimum tuning, provider capacity, classifier waste (see the Step 3 report); pre-existing failing tests unchanged.

## 15. Commits
- `1b01f44` Step 5 implementation (contract module, confidence and engine changes, finalizer projection, uncurated-education answer, tests, audit artifacts, frontend types and panel guard).
- This document's own commit follows it. Step 4C was `2245bef`; the earlier steps are listed in their reports.

## 16. Statements
Provider calls: **0**. No push. No deploy. No secrets in any artifact.
