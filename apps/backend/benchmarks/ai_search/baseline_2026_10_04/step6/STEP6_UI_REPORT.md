# Step 6 — Final UI (AI Search & Answer V2)

Scope: redesign the AI Search page around the Step 5 final answer contract. Frontend only, plus one read-only landing endpoint and one Page Intelligence fallback removal. No retrieval, Gate A/B, routing, prompt, provider or Company Score change.

## 1. Before audit
- Production runs the legacy renderer (flags unset); local ran the AEV2 shell. Two render paths, 2,872-line `AISearchClient.tsx`, ~25 panels, right sidebar, fixed follow-up bar.
- Fabricated client fallbacks: `horizon || "6-12 months"`, `opportunity_score ?? 50`, risk derived from missing confidence / default 50, `evidence_score.stars ?? 3`, plus confidence gauges, bars and Medium/High/Low labels, a giant "Not Applicable" verdict card, and empty scenario / decision-engine / matrix / timeline blocks.
- Grey/tinted panels (`bg-text-primary/[0.03]`) unlike the white `bg-surface-card` surfaces on /companies. Fixed 4 example questions.
- Page Intelligence invented `Medium / 60` (and `Low / 20`, per-company 65, sector 60).
- "Before" screenshots: `screenshots/before_*`.

## 2. Component disposition
| Disposition | Components |
|---|---|
| Keep | AIDisclaimer, AISearchFeedback, AITransparencyPanel family, ConfidenceBadge (unscored state), InvestmentWatchPanel, ContextChips, ClarificationPicker, AISearchHistory, SearchProgressStages, Market Pulse block (verbatim) |
| New | `components/ai/v2/contract.ts`, `components/ai/v2/AnswerV2.tsx`, `services/ai_search/suggestions.py` + `GET /api/ai/search/suggestions` |
| Removed | AIAnswerShell chain, IntentLayout, layouts/*, aev2Shared/aev2Types, answerTypes*, ConfidenceBreakdownPanel, DecisionIntelligencePanel, DecisionTimelinePanel, InvestmentVerdictHero, ResearchWorkspace, RefineAnalysisPanel, AISearchFindingsRecap, AISearchGraphReveal, FollowUpIntelligence, RightSidebar, DegradedSearchAnswer, legacy SearchResults, their fixtures/tests, the old e2e shell spec |

## 3. Final information architecture
Question box → answer (lead sentence, "In short") → verdict (only if authorized) → What the evidence shows (claims with source labels) → What it means → Known limits → Where to look next. Side column (desktop): What this involves, Evidence reviewed (5 shown, rest behind "Show N more"; items used by the answer first), Evidence strength. One column on mobile. White surfaces throughout.

## 4. Rendering by kind (from `answer_availability.kind`)
research · partial_research ("Answered in part" note with scope and missing items) · education (no verdict/stars/confidence/opportunity/horizon/failure language; basis note: general explanation, not live evidence) · product_information (documentation-like; methodology vs live data stated) · unavailable (title + short explanation + related evidence if any + "Try instead") · temporarily_unavailable (own wording per reason; Retry; never says evidence is absent). Kind is derived from legacy fields only for pre-Step-5 cached payloads.

## 5. Removed fabricated fallbacks
All five mandatory ones and equivalents, enforced by a source-scan test. Page Intelligence: confidence fallback is `unscored / null`, per-company/opportunity confidence and sector score are null (`page_intelligence_service.py`); the existing test that pinned the invented `Low / 20` was updated.

## 6. Verdict behavior
Rendered only when `conclusion_authorized === true` AND a real rating is supplied. Otherwise absent (no "Not Applicable" card). Session memory stores a verdict only when authorized.

## 7. Evidence presentation
Evidence listed with type, source, date; "Used in this answer" marks cited items; claim source chips come from `claim_sources` + `evidence_index` (labels, never raw ids). Evidence strength is plain language ("which kinds of evidence were found ... not how likely the answer is to be right"), never called confidence; omitted when `evidence_score` is absent.

## 8. Education / product
Deterministic, calm, single column; next-step questions per topic; internal glossary/methodology link only (no external links).

## 9. Failure presentation
Five distinct titles/bodies for retrieval_failed, retrieval_timeout, provider_capacity, generation_failed, time_budget_exhausted; no provider or technical names (tested). Gate B / `claims_not_authorized` renders only the safe public wording; rejected generated content is not rendered (tested).

## 10. Responsive / browser verification (Playwright, mocked deterministic fixtures)
Landing, research, partial, insufficiency, retrieval failure, Gate B, education, product at 1440 and 390: **390 — no horizontal overflow on any**; **1440 — scrollWidth 1480 on every page including /companies and /**, a pre-existing site-wide header overflow, not from this page**. Zero console errors in the final run. Screenshots: `screenshots/{landing,research,partial,insufficient,temp_retrieval,gateb,education,product}_{1440,390}.png`.
Bug found and fixed during verification: an intermittent "Maximum update depth exceeded" (~1 in 20 loads) when a streamed answer arrived — the stream-result effect re-ran with a changing `meta` identity. The effect now handles each distinct result once and no longer depends on `meta`; 50 consecutive loads clean. Root cause of the identity flip was not isolated beyond that; flagged as release debt.
Daily "Try" questions: backend builds them from live sector moves and live headlines (validated through the real entity resolver, no model call, 10-minute cache, evergreen top-up, mojibake repair). Verified against real data (e.g. "FMCG +1.1% today", "Pharma -1.6% today", Wipro / Kotak headlines).

## 11. Performance impact
`AISearchClient.tsx` 2,872 → ~775 lines; ~25 panels and the sidebar removed; no new dependency; no animation system. Not Lighthouse-measured.

## 12. Tests
Frontend: 409 tests across 36 files pass incl. new `AnswerV2.test.tsx` (33), `AISearchClient.landing.test.tsx` (4); `tsc --noEmit` 0 errors. Backend: `test_ai_search_final_contract.py` (112), response semantics, education, new `test_ai_search_suggestions.py` (5), `test_page_intelligence_unscored.py` (2), page-intelligence integrity — all pass. Covered: no fake horizon / opportunity / default stars / answer confidence; verdict gating; evidence strength wording; every kind; insufficiency vs retrieval-failure copy; empty legacy blocks hidden; Gate B content absent; internal diagnostics don't leak; follow-ups; null fields.

## 13. Screenshots
`apps/backend/benchmarks/ai_search/baseline_2026_10_04/step6/screenshots/`

## 14. Remaining release debt
- Pre-existing site-wide 1440 header overflow (1480px).
- Stream-effect identity flip root cause not isolated (guarded).
- Feedback/disclaimer strips (shared components) keep a slightly tinted background.
- Loading state is a plain "Researching…" text (stage list when streaming); no screenshot of it.
- Page Intelligence `IntelligenceBlock` still shows a fixed "medium" horizon label for opportunities (outside this step).
- Suggestions endpoint is new backend surface: needs deploy with the frontend (frontend falls back to static examples if absent).

## 15. Commits
Local commit "feat(ai-search): Step 6 final UI" (see git log). Unrelated user WIP not staged.

## 16. Constraints
Provider calls: **0**. Push: **none**. Deploy: **none**. Secrets in artifacts: **none**.
