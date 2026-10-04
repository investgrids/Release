# Step 3.4D-2 report: conclusion scope + structured claim authorization

Regression case: the saved live CC1 generation (Step 3.4C artifact, forensic `8f73198`). No provider call, no push, no deploy. Not changed: provider routing, retrieval, evidence ages, MP2/MP3, timeouts, CD3 semantics, Gate A, existing Gate B rules.

## 1. Conclusion scope (`conclusion_scope.py`)
Deterministic. For a comparison it records the conclusion the question REQUESTS (`overall_strength` for broad questions, `valuation` when the question itself is about valuation/P/E/cheaper) and the conclusion the evidence AUTHORIZES, from per-company coverage:
- valuation: P/E or P/B present;
- operating: a non-administrative, non-tips item about THIS company whose **title** carries an operating term (results, earnings, revenue, profit, margins, order book/orders worth, guidance, outcome of board meeting). Titles only, so a sector item that mentions "revenue" in general or a market-wrap summary that mentions "TCS' earnings" as a watch item does not count (this was a real false-positive found by the new tests and fixed).
- `overall_strength` is authorized only when every compared company has operating evidence; valuation-only evidence authorizes `valuation_comparison` and marks the answer `partial`.
- Partial analysis is preserved. A prose sentence that states an overall winner/preference ("stronger", "better", "prefer", "favors", "leads", "winner", "best company/stock/pick"...) with no valuation qualifier and no hedge is `conclusion_scope_exceeded`, which fails Gate B (whole answer withheld, no sentence stripping). The saved CC1 prose, which was correctly qualified ("valuation-led", "supplied valuation measures"), is NOT flagged. ("Best Buy" no longer matches "best"; only "best company/stock/pick/choice/business/option/bet" does.)
- When partial, the response carries `conclusion_scope` {requested, authorized, partial, missing, coverage} and a caveat "This is a valuation comparison only ... doesn't conclude which company is stronger overall", and the pairwise `engine_recommendation` (a winner/preference) is not attached.
- Saved CC1 evidence: requested overall_strength, authorized valuation_comparison, partial, missing operating evidence for TCS and INFY.

## 2. Structured public claims (`structured_authorization.py`)
Default-deny. An analytical claim that is a rating, direction, sentiment, confidence, probability, score, expected range, winner/preference or recommendation is public only if a deterministic producer made it. Nothing authorizes the LLM's own versions yet, so `sanitize()` (run after prose authorization, before assembly) replaces them with an explicit unavailable state and the response lists what was withheld (`structured_authorization`).
- `investment_verdict` -> rating "Not Applicable", direction None, confidence None, no picks/catalysts/risks, no opportunity score (the deterministic Opportunity Radar score, deterministic horizon and engine_verdict still come from code).
- `answer.sentiment`, model `confidence`/`confidence_self_rating` -> None. Public `answer.confidence` remains the deterministic evidence-grounded value from the confidence breakdown.
- `scenarios`, `decision_intelligence`, `decision_engine_v2`, `opportunity_risk_matrix`, `ai_conclusion`, `timeline_intelligence` -> empty.
- `companies[].impact_type/impact_score/confidence`, `sectors[].score/outlook/positive/confidence`, `key_drivers[].confidence` -> None; names, reasons and explanations (prose, already covered by Gate B) are kept; derived sector `status/time_horizon` are removed.
- Not converted into Neutral / Cautious / "No clear edge" (asserted by test).

## Regression (saved CC1 generation)
`tests/services/test_ai_search_structured_authorization.py`: **30 passed**, including a variant of the saved generation whose prose is made to pass Gate B (claim_sources rebuilt verbatim), run through the REAL `_assemble_response` and finalizer (only network enrichment stubbed). Public output contains no "Selectively Constructive", no "bullish", no "current_view": "Positive", no 30/50/20 scenario probabilities, no impact scores 58/50, no key-driver confidences 86/72, public confidence is the deterministic value (not the model's 69), no engine recommendation, and an honest `conclusion_scope` + `structured_authorization` account. Also covered: valuation questions need only valuation evidence, operating evidence for both sides authorizes overall strength, one side only stays partial, administrative/PR items do not count, an overall-winner sentence fails Gate B end to end, degraded shapes carry the new keys as None.

## Test selection
32 AI Search / AEV2 / core-answer / page-intelligence / follow-up test files: **685 passed, 1 skipped, 2 xfailed, 6 failed**. The 6 are the same pre-existing `test_ai_search_engines_live.py` live_e2e failures. Attributable failures: 0.

## Behaviour changes to know about (not silent)
1. **Every authorized generated answer now drops the LLM's scenarios, decision blocks, ai_conclusion, verdict/rating/direction/sentiment, scores and per-item confidences**, for company and sector answers as well as comparisons, because no deterministic authorizer exists for them yet. The UI will show prose, sourced claims, evidence, deterministic confidence and an unavailable state for verdict-type fields. Frontend rendering of `direction: null` / `sentiment: null` / empty blocks was NOT verified here (the client falls back to "neutral" styling when both are null, `AISearchClient.tsx:1311`).
2. The deterministic market-wide `engine_verdict` (MIE direction + confidence + VIX, not company-specific) still appears under `investment_verdict.engine_verdict`; I left it, as it is code-produced, but it is a market-level view next to a company comparison and may deserve a separate look.
3. Operating-evidence detection is a keyword rule over titles. It will miss real operating news whose title lacks those words (false "partial", safe direction) and cannot judge quality.
4. The overreach rule is lexical; a winner claim phrased with none of the listed words would not be caught.

## Not verified
Live model behaviour after these changes (no provider call made); frontend rendering of withheld fields; effect on the frozen-18 live benchmark.
