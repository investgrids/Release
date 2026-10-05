# Step 3.4D-3 report: canonical claim contract + generation schema reduction

Base `73617b2`. Model-free: no provider call, no push, no deploy. Preserved unchanged: Gate A, Gate B exact claim matching (no fuzzy/semantic matching added), conclusion scope, structured authorization/sanitization (kept as defense in depth), retrieval, evidence ages, provider routing, MP2/MP3, CD3, timeouts, token caps.
Note: the D-3 prompt text was cut off mid-sentence ("Keep deterministic structured authorization/s"); I read it as "keep structured authorization/sanitization as defense in depth", which is what is kept.

## 1. Canonical claim contract (`CLAIM_SOURCES_RULES`, in every specialist prompt)
- Every sentence anywhere in the answer text that states a fact, number, date, order, announcement, result or comparison of figures gets ONE `claim_sources` entry, copied character for character, with admissible evidence IDs.
- **State each fact once. If it is needed in more than one field, repeat the IDENTICAL sentence word for word; never restate it in different words; never combine claims or add a clause to a claimed sentence.** Other fields may point back without new numbers or dates ("the valuation gap noted above").
- A limitation ("recent operating results are not in the current evidence") is not a fact: write it plainly, without announced/disclosed/filed (the words that made the factual-sentence detector flag caveats in the CC1 forensic).
- Scope rule: conclude only what the evidence covers; with valuation-only evidence compare valuation and say operating results are not in the evidence; do not say which company is stronger, better or preferred.
- This works with the exact matcher: an identical sentence repeated in several fields is covered by one entry (tested); a paraphrase is still rejected (tested). Nothing fuzzy was added.

## 2. Generation schema reduction
Removed from the model output contract and prompts (company, pairwise comparison, multi-compare, multi-compare compact retry, sector): rating, direction, sentiment, confidence and self-rating, verdict scale and "why", horizon, the whole `decision` group (current view, action note, view-changers, explain-why-not), scenarios and probabilities, insights, `top_picks`, impact_type/impact_score/confidence on companies, score/outlook/positive/confidence on sectors, key-driver confidence, the timeline horizon narratives, opportunity and risk matrices, the comparison `decision_intelligence` block (winner, best investor type, holding/target analyses, tradeoff, framework, entity analyses), the compact retry's `best_for` and `confidence`, sector `sector_score`, `money_flow`, leaders and laggards. Also removed: the instructions that demanded those fields (rating label list, "probabilities sum to 100", "verdict_scale must agree with direction", etc.).

Kept (nuance respected): `summary`, `bottom_line` (shorter, no verdict), `what_happened`, `why_it_happened`, `key_drivers` (icon/title/explanation, no confidence), `risks` and `opportunities` as grounded prose or evidence-limitation statements, `milestones` only for dated events in the evidence, `monitoring` (at most 3 items), `follow_up_questions`, `claim_sources`, `companies` (symbol, name, reason), `sectors` (name, explanation). The compact retry keeps its per-entity prose view.
Also removed from the contract: `immediate_impact`, `medium_term`, `long_term`, `what_priced_in` (forecast-style prose with no evidence authority).

Honest absence: `flatten_nested` no longer defaults missing fields into neutral values (confidence, sentiment, rating, direction, verdict scale are `None`; empty decision/timeline/matrix/conclusion blocks are `{}` rather than shells of empty strings), so structured authorization reports only what the model genuinely generated. `validation.py` is None-safe: nothing to reconcile or downgrade when there is no model verdict, and a missing direction is treated like neutral on the grounding-collapse path (no new degradation).

## Size
Company prompt: **9,072 -> 5,838 characters (-36%)**, about 800 fewer input tokens. Output: the saved CC1 generation spent 4,818 visible tokens, about 90% on structures this contract no longer asks for (decision_intelligence alone about 1,700). I expect the visible output to fall to roughly a third of that; this is an **estimate, not a measurement** (no model call was made). Token caps and timeouts were not changed, per the instruction not to shorten aggressively before measuring.

## Tests
- New `test_ai_search_generation_contract.py`: **27 passed**. No prompt (company, pairwise, multi, compact, sector) contains any of 48 prohibited output keys; the grounded prose keys are still requested; canonical-claim, scope and grounding rules are in every prompt; a contract-conformant generation (hand-written to the new nested shape on the saved CC1 evidence) parses without degrading, validates quietly, **passes Gate B**, is `partial` with no overreach, and `sanitize` withholds nothing (`state: none_generated`); end to end through the real assembly its public response has no withheld structure, a null verdict, a null engine verdict and the valuation-only caveat; verbatim repetition passes, paraphrase fails, an overall-winner sentence still fails scope.
- Two existing parity tests changed on purpose: the multi and pairwise prompts previously had to contain `entity_analyses` / `holding_analysis`; they now must not.
- Selection (32 AI Search / AEV2 / core-answer / page-intelligence / follow-up files): **724 passed, 1 skipped, 2 xfailed, 6 failed**; the 6 are the pre-existing `test_ai_search_engines_live.py` live tests. Attributable failures: 0.

## Not verified / risks
- No model has seen the new prompts. Whether OpenAI follows the canonical-claim rule is exactly what the single CC1 rerun measures; the conformant fixture proves the gates accept such an answer, not that a model produces it.
- The multi-compare path no longer returns per-entity analyses; the UI already dropped them after D-2, but confirm nothing else wants `entity_analyses` when you test a 3-company question.
- The compact multi-compare retry still maps `confidence` to a default internally (`_compact_to_flat`); those values are sanitized away downstream and never public.

## Next
D-4: exactly one OpenAI CC1 call with the committed harness (about 96K tokens remain in the project window; a call should now be far smaller than the previous 9,740). Success bar: partial valuation-only conclusion, every factual sentence claim-sourced, Gate B authorized, no overall winner, no verdict, no model confidence/probabilities/scores, useful public valuation comparison, materially fewer than 6,379 completion tokens.
