# Step 3.4D-2.1 report: UI integrity for withheld verdicts + engine_verdict scope

Base: `6053328`. Model-free; no provider call, no push, no deploy. Not changed: Gate A/B, retrieval, providers, evidence ages, MP2/MP3, CD3, timeouts, the AEV2 layouts.

## 1. A withheld verdict is never drawn as Neutral (`apps/web/app/ai-search/AISearchClient.tsx`)
Backend contract: `direction=null`, `sentiment=null`, rating "Not Applicable" or empty, empty decision blocks mean "no authorized conclusion".
Defects found in the legacy result page (it still defaulted to "neutral"):
- `dir` fell back to `"neutral"` and the label to `"Neutral"` (Research Outlook card);
- the sidebar showed the label `"Neutral"` or `"Not Applicable"` with an amber dot;
- the hero verdict panel was built whenever `decision_engine_v2 && ai_conclusion` were truthy, and the new empty `{}` blocks are truthy, so it would have rendered with a default "Neutral" scale;
- `DirectionIcon` drew a neutral "Minus" icon for any non-bull/bear value.
Fixes (UI only, not the redesign): types now allow `null`; `hasAuthorizedVerdict()` (rating present and not "Not Applicable"); no direction icon for a null direction; the card shows "Verdict: Not available" with a one-line reason; Risk Level and Suitable For are hidden unless a verdict is authorized (Confidence, the deterministic value, and a stated Time Horizon stay); the hero panel needs an authorized verdict AND non-empty `decision_engine_v2`/`ai_conclusion`; the sidebar shows "Not available" and "—" for best-for. Empty scenarios, decision intelligence and timeline panels were already hidden by their own guards (verified by test). The engine-view disclosure is titled "Market-level data engine view" when no verdict is authorized.
Tests: new `AISearchClient.withheldVerdict.test.tsx` (8 tests). Mutation check: against the old client 5 of the 8 fail; with the fix all pass. Existing UI tests unchanged and green. `components/ai` + `app/ai-search`: **24 files, 228 tests passed**.

## 2. Market-wide `engine_verdict` only for market-wide scopes (`pipeline.py`, `response_finalize.py`)
`engine_verdict` (market direction + confidence + VIX + Radar score) is still computed in every scope and kept as internal `_engine_verdict_internal` (stripped by the finalizer, like `_rejected_generation`). It is public in `investment_verdict.engine_verdict` only when `ui_mode` is in `MARKET_WIDE_UI_MODES = {policy_macro_impact, market_pulse}`; otherwise `None`.
Tested independently through the real assembly (`test_ai_search_engine_verdict_scope.py`, 12 tests): company research -> hidden, comparison -> hidden, event impact -> hidden, sector -> hidden, macro -> public; internal copy computed and non-empty in all five; internal copy never reaches the client response; no "bullish" market rating inside a company answer's verdict.
Sector was deliberately left non-public (a market-wide read is not a sector read); say if you want it included.

## Test selection
Backend: 32 AI Search / AEV2 / core-answer / page-intelligence / follow-up test files: **698 passed, 1 skipped, 2 xfailed, 5 failed**, all in `test_ai_search_engines_live.py` (live_e2e, pre-existing; one of the earlier six passed this run, so those are flaky against live data). Attributable failures: 0. Pre-existing TS errors in `AISearchClient.test.tsx` (Scenario fixture type) are unchanged.

## Not done / still unverified
Not checked in a browser (jsdom tests only); the AEV2 layouts already avoided verdict fields and were not touched; market-pulse results go through a separate component. `decision_intelligence: {}` is shown nowhere, but the Decision panel guard (`intent` present) is what keeps it hidden.

## Next
D-3 (model-free): canonical factual claims and removing prohibited structures from the generation contract, then the single CC1 rerun.
