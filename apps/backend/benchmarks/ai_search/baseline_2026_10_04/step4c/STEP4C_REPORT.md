# Step 4C report: response semantics cleanup

Zero provider calls. No change to retrieval ranking, Gate A logic, Gate B authorization, prompts, providers, latency settings, Step 4A routing or Step 4B content. Local commit only; nothing pushed or deployed.

## 1. Audit: public field matrix before changing code
`step4c/field_matrix.py` runs representative cases through the real pipeline and finalizer (fixtures, provider function set to raise); A and B are saved authorized live responses. Full output: `field_matrix_before.json` and `field_matrix_after.json`.
| Case | availability state / reason (before) | sentiment, direction (before) | counts (before) |
|---|---|---|---|
| A authorized, evidence-backed | available | null, null | evidence_count 12, sources_count **27**, source_count 27, text "26 independent developments, corroborated by 27 sources" |
| B authorized, partial scope (CC2) | available (`conclusion_scope.partial: true`) | null, null | evidence_count 3, sources_count 3, text **"9 trusted sources"** |
| C Gate A insufficient (search succeeded) | no_verified_evidence | **"neutral", "neutral"** | 0 |
| C2 same, but a source failed | no_verified_evidence (**same as C**) | "neutral", "neutral" | 0 |
| D retrieval cut off by the deadline | temporarily_unavailable | "neutral", "neutral" | 0 |
| E provider capacity | temporarily_unavailable | "neutral", "neutral" | 0 |
| F Gate B rejection | no_verified_evidence | "neutral", "neutral" | 0 |
| G educational (GE1) | available | "neutral", "neutral" | 0 |
| H product knowledge (GE3) | available | "neutral", "neutral" | 0 |

## 2. Defects found
1. **A no-conclusion answer was serialized as a neutral conclusion.** The shared degraded builder, the pre-retrieval shell and the internal specialist stub all wrote `sentiment: "neutral"` and `direction: "neutral"` (the stub also wrote rating "Neutral" and confidence 40). The frontend was already typed for null and never draws a neutral stand-in, but the API itself encoded a conclusion nobody authorized.
2. **Four different numbers were all called a count of sources:** the items listed in the response (`answer_availability.evidence_count`), the retrieved bundle size (`answer.sources_count`, `evidence_score.source_count`), and the confidence copy, which labelled a count of independent *developments* (clusters over events, news and exchange filings, where filings are never listed publicly) as "9 trusted sources". In case B that said 9 next to 3.
3. **A failed search read as an absence.** Gate A refusals looked identical whether retrieval succeeded and found nothing (C) or a source failed during retrieval (C2): same state, same "not enough recent evidence" wording, same stage.
4. **No machine-readable reason.** Capacity, deadline, retrieval timeout, retrieval failure, Gate B rejection and genuine insufficiency could only be told apart by the internal `degraded_reason`.
5. **Educational answers** inherited the neutral values and an availability with no statement of what the answer rests on.

## 3. Public definitions chosen
- **`evidence_count` = the number of evidence items (events, news, policy items) listed in this response.** It is 0 for an educational answer and for any refusal that lists nothing. `answer.sources_count` and `evidence_score.source_count` now always equal it (applied once, in the finalizer, so cached responses are covered too). Real responses always carry those keys; a response without them is not given new ones.
- **Developments are named as developments.** In AI Search the confidence copy now reads "N independent developments in MarketRipple's records (events, news and exchange filings)" and never says "trusted sources" or "news & event sources". The scoring is unchanged. The shared `confidence_service` copy, which other surfaces and tests rely on, is untouched; the rewrite lives in AI Search's `postprocess`.
- **`answer_availability.reason`** (additive; null when the answer is available): `evidence_insufficient`, `retrieval_failed`, `retrieval_timeout`, `provider_capacity`, `generation_failed`, `time_budget_exhausted`, `claims_not_authorized`, `unsupported_subject`, `limited_evidence`. No exception text or internals.
- **`answer_availability.basis`** (additive): `retrieved_evidence`, `market_data`, `education`, `none`.
- **Absence of a conclusion is null, never "neutral":** `sentiment` and `verdict.direction` are null on every no-conclusion shape; `rating` stays "Not Applicable" (the frontend's existing signal); confidence stays null/"unscored", not 0.
- **Partial stays partial.** The four public states are unchanged: AVAILABLE is `available`; PARTIAL is `limited_evidence` (evidence exists, answer withheld) or `available` with `conclusion_scope.partial: true` (authorized for a narrowed scope, as in case B); UNAVAILABLE is `no_verified_evidence`; TEMPORARILY_UNAVAILABLE is `temporarily_unavailable`. Nothing was merged or relabelled.
- **Retrieval failure is not absence.** When a source failed during retrieval, a Gate A refusal is now `degraded_reason: retrieval_failed`, state `temporarily_unavailable`, `evidence_retrieval_completed: false`, title "The evidence search did not complete" and body "MarketRipple couldn't finish searching its evidence for this question just now, so it can't tell whether supporting evidence exists. No conclusion was drawn. Please try again in a moment.", with no "insufficient" verdict published and a distinct `retrieval_incomplete` stage. **Gate A's own decision is unchanged** (a test proves the same status, kind and missing items with and without a failed source); only the public response differs.

## 4. After (field_matrix_after.json)
C: `evidence_insufficient`; C2: `retrieval_failed`; D: `retrieval_timeout`; E: `provider_capacity`; F: `claims_not_authorized`; G and H: available, basis `education`, reason null, evidence_count 0, sentiment/direction/confidence null, rating "Not Applicable". A: evidence_count = sources_count = evidence_score.source_count = 12 = listed items, no "N sources" text. B: the same, 3, and the copy now names developments.

## 5. Frontend compatibility
- Only a type change: `AnswerAvailability` gained optional `reason` and `basis`. Null sentiment and direction were already supported by the client's types and rendering.
- Frontend AI Search tests: 35 of 35 pass. `tsc --noEmit` reports no error in non-test code (existing errors are in `AISearchClient.test.tsx`, a `Scenario` fixture type, unrelated to this step).

## 6. Tests and results
- `test_ai_search_response_semantics.py`: **31 tests**: no neutral on any no-conclusion shape (builders, shell, stub, and the real pipeline for insufficient, retrieval failure, capacity, Gate B, deadline); authorized answers still withhold structured claims as null; retrieval failure versus genuine absence (same Gate A verdict, different public answer, no internals leaked, distinct stages, not reported as a cache hit); capacity versus deadline versus retrieval failure versus Gate B reasons; Gate B rejection stays fail-closed and the rejected text never appears; educational answers expose no verdict, direction, confidence or evidence count; evidence_count equals every public count on saved authorized responses; the normalization is idempotent and changes nothing else; the confidence copy never calls developments sources, including through a real confidence run; human-readable counts agree with evidence_count (the "9 trusted sources" case); partial stays partial; all four states reachable; market pulse unchanged.
- Mutation checks (each fails the tests): neutral sentiment returning (8 fail), neutral direction returning (8), retrieval failure reported as absence (2), count normalization removed (1), confidence-copy rewrite removed (1), capacity mislabelled as retrieval failure (1), education basis dropped (2).
- Existing tests: 10 tests pinned the exact old availability dict; they now compare the three original fields (`_core`) and the new keys explicitly, so they still guard the original contract. No other test changed.
- Frozen-18 deterministic qualification (**provider calls made: 0**): no decision, outcome or route changed in any of the 18 rows versus the Step 4B run.
- Regression: AI Search, deadline, news, macro, ui_mode and availability selection **943 passed**, 3 xfailed, 12 deselected (the live-engine file); wider selection (evidence filter, entities, ui_mode, routing, education, intent, safety, availability, finalize, confidence, degraded, refine, session) 690 passed with **2 failures, both pre-existing live tests that fail identically at the previous commit** (`test_p5_stage2_v3_live::test_multi_compare_3plus_entities_v3`, `test_p5_stage4_v3_live::test_exact_key_cache_collision_across_sessions`). Other known failures from earlier steps are unchanged.

## 7. Findings left for Step 5 and later (not changed here)
- **Confidence on authorized answers.** Case A and B show `answer.confidence` 42.5 / "Medium" while the verdict is "Not Applicable". Part of that number is a constant: `reasoning_confidence` is 50.0 because the model is no longer asked for a self-rating and the code defaults it to 5/10. That is a fabricated input to a public score; whether authorized answers should show a confidence figure at all is a Step 5 decision.
- `evidence_score.corroborating_source_count` (a raw count that includes unlisted filings) and `development_count` are still public and named differently from `evidence_count`; they do not contradict it, but they are internal diagnostics in a public object.
- The internal specialist degraded stub still holds generic filler prose and a "Neutral" `verdict_scale`; it is discarded before anything becomes public.
- The client defaults a missing evidence-star value to 3 (`evidence_score?.stars ?? 3`), which draws stars for responses with none, including educational ones. A UI item for Step 6.
- The curated-education fallback (uncurated "What is EBITDA?") is unchanged, as agreed.
- Branch versus main Company Score divergence is not touched here.

## 8. Process note
During verification I ran a `git stash` of `apps/` to compare against the previous commit, which also swept up the uncommitted work in progress in the working tree (stocks, market data, score files, company pages). I restored it at once with `git stash pop`: all 23 modified files came back, the stash entry was dropped, and the older stashes were not touched. I then redid the baseline comparison with a separate worktree, which is the right tool, and nothing outside this step's files is in the commit.

## 9. Statements
No push, no deploy. Provider calls: 0. No secrets in any artifact.

NEXT: Step 5, Final Answer Contract.
