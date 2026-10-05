# Step 7 — Release Qualification & Deployment

**Verdict: AI SEARCH V2: BLOCKED — the push to `origin/main` was denied by the local auto-mode safety classifier (no reason given). Nothing was pushed or deployed. The release candidate itself is qualified GREEN.**

## 1. Production / main baseline
- `origin/main` = `8bbe68b` (unchanged through the whole step; re-fetched immediately before the push attempt).
- V2 branch `release/ai-answer-v2` @ `f08ed46`: 84 commits ahead, 129 behind main; merge-base `c84c28a`. All 84 commits are AI Search work (AEV2 foundation through Step 6); none is on main.
- Production backend does not have the new endpoint (`GET /api/ai/search/suggestions` returned 404 on production when checked). Production commit hashes beyond that were not determinable without a deploy and are not claimed.
- User WIP in `D:\IG` and the three stashes were not touched (3 stashes before and after; the release was built only in separate worktrees).

## 2. Integration strategy
Clean worktree `D:\IG-ai-v2-release` from `origin/main`, then a normal merge (`--no-ff`) of `release/ai-answer-v2`. A merge, not a copy, so main's newer code is kept wherever the branch did not change it. Only 6 files were changed on both sides.

## 3. Integrated commit list
86 commits ahead of main: the 84 reviewed V2 commits, merge commit `808193c`, and `8ac35cb` (Step 7 integration fixes). Branch `release/ai-v2-integration`. `git log origin/main..HEAD` is the authoritative list.

## 4. Conflict resolutions
- `apps/web/.gitignore`: union of both sides.
- `apps/web/playwright.config.ts`: main's one-score config kept (the branch's AEV2-shell harness was retired in Step 6).
- `config.py`, `scheduler.py`, `package.json`, `package-lock.json` merged without conflict.

## 5. Company Score divergence
The branch never changed score code. `git diff origin/main..HEAD` over `marketripple_score/`, `filing_score/` and the methodology page is empty: the integrated tree uses main's three-pillar methodology. GE3 was written against main's page (education.py cites `8bbe68b`); the education drift/contract tests pass on the integrated tree.

## 6. Pre-deploy test results (integrated tree)
- Backend, targeted AI Search gate (Step 5 contract, 4A macro, 4B education/product, 4C semantics, deadline, retrieval/news, suggestions, Page Intelligence, GE3): **278 passed**.
- Backend full suite (excluding the live end-to-end tier): 3,730 passed; the failures are accounted for in §9.
- Frontend: **52 files / 490 tests pass**, `tsc` 0 errors, `next build` succeeds.
- Four tests that pinned behaviour Steps 3–6 changed on purpose were updated (confidence removed from public JSON, generation schema reduced, Page Intelligence unscored, new degraded reason); each was confirmed obsolete before editing.

## 7. Browser qualification (production-style build, plain POST transport; and again on the stream-enabled build)
Landing, research, partial, education, product information, insufficient evidence, retrieval failure, capacity failure, Gate B, at 1440 and 390, plus suggestions-unavailable fallback and a loading capture: **0 failed checks on both transports**. Verified: correct presentation per kind, white page background, no confidence/6-12 months/opportunity/risk/"Medium / 60"/"Not Applicable" text, verdict absent, retry only on temporary failure, evidence disclosure expands, follow-ups present, no AI Search horizontal overflow at 390, no console errors (the one tolerated line is the request the fallback check aborts on purpose).
Screenshots: `step7/screenshots/`.
UI changes made this step at the user's request: white page background; comparison layout aligned to the supplied mockup using only contract fields (breadcrumb, title, side-by-side table, entity snapshot). **Not built, by decision:** the mockup's "Evidence Confidence 64%" panel (contradicts the Step 5/6 rule: no public answer confidence), market cap / analyst coverage / source-integrity grades (not in the contract), and a policy "transmission chain" (the available `ripple_chain` is an engine graph with weights, not contract-grade evidence).

## 8. Streamed-meta stress
125 consecutive fixture loads on the stream transport (mixed desktop/mobile): **0** "Maximum update depth" errors, 0 other console errors (pre-guard rate was about 1 in 20). Root cause of the identity change still not isolated; recorded as monitored debt.

## 9. Known / pre-existing failures
Reproduced on a pristine `origin/main` worktree: **60 failures on main itself** (admin-endpoint and canary tests, `*_v3_live` and other live-provider tests, ingestion, etc.). The integrated tree has the same 60. Twelve additional failures seen in the first full run were investigated: 4 live-news and 3 seed-guard tests pass in isolation (load flakes while building/serving in parallel); 4 migration tests failed only because a fresh worktree lacks `.venv` (7/7 pass once linked); `test_us_treasury_live` needs the network. `test_ai_search_engines_live.py` (live end-to-end tier, needs the dev DB and live providers) was not run.

## 10. Provider state / call count
**Provider calls in Step 7: 0.** The AI Search answers in browser tests are fixtures; the only live calls were the suggestions endpoint (market data and RSS, no model). Provider quota was last observed exhausted (Groq and OpenRouter 429 with long cooldowns).

## 11. Push result
**DENIED.** `git push origin release/ai-v2-integration:main` (a fast-forward of 86 commits) was rejected by the local auto-mode classifier: "The server-side auto mode classifier judged this action dangerous (it gave no explanation)". Not retried, not split, no alternative route used.

## 12–15. Backend deploy, frontend deploy, production verification, production log check
**Not performed** (blocked at the push gate; the release order backend-first, then frontend, with exact-commit verification is unchanged and ready).

## 16. Remaining non-blocking debt
Global 1440px header overflow (pre-existing); streamed `meta` identity root cause; feedback/disclaimer strips slightly tinted; 60 pre-existing failures on main; `lightweight-charts` missing from the shared dev `node_modules` (main declares it; the worktree used a clean `npm ci`); `package.json` unchanged by this release.

## 17. Final release verdict
**AI SEARCH V2: BLOCKED — push to `origin/main` denied by the local auto-mode classifier.** Candidate commit `8ac35cb` on local branch `release/ai-v2-integration` (worktree `D:\IG-ai-v2-release`) is GREEN and ready.
To proceed, the owner can either push that branch themselves, or add a permission rule that allows the push, then ask for Step 7 to resume at the push gate.
