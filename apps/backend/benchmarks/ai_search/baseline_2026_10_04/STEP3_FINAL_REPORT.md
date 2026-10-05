# AI Search & Answer V2, Step 3 final report: Evidence + Answer Reliability

## 1. Executive verdict
**STEP 3 CLOSED / GREEN.**
All ten completion invariants hold on the evidence below. H.4 found one genuine defect against invariant 1 (company-question retrieval timing out on every attempt because the deadline discarded a slow optional fetch each time). It was fixed with the smallest safe change (56b5469), proven model-free and with a real-network retrieval check, and re-evaluated. No other release-blocking defect was found. Everything else is listed in section 8 as work outside Step 3.

## 2. H.4 timing table (measured before the closure fix; budgets 24 / 2 / 3 / 8 / 14 s)
Artifact: `step3_4h/h4_production_chain.json`. Providers present in the chain: Groq and OpenRouter (no Mistral or Gemini key), so at most 9 specialist attempts.
| Request | Classifier | Retrieval | News (state, ms) | Specialist chain | Gate B + assembly | Wall | Deadline left | Outcome |
|---|---:|---:|---|---:|---:|---:|---:|---|
| SR2 | 1.03 s, 3 attempts (2 empty) | 6.06 s | cold, 1,531 | 1.28 s, 9 attempts, all 429 | 0.11 s | 8.63 s | 15.39 s | `capacity` |
| CC2 | 0 s, all models exhausted | 1.11 s | fresh, 0 | 0 s, 9 skipped as exhausted | 0.08 s | 1.19 s | 22.81 s | `capacity` |
| CR1 | 0 s, skipped | cut off at 14.0 s | fresh, 0 | not reached | n/a | 14.02 s | 9.99 s | `retrieval_deadline_exceeded` |
| SR2, first specialist attempt replaced by a hang | 1.95 s, 3 attempts (2 empty) | 0.56 s | fresh, 0 | 14.02 s then stop | 0.11 s | 16.64 s | 7.36 s | `deadline_exceeded` |
Retrieval failures recorded: none except CR1's deadline cut-off. The longest request ended at 16.6 s of a 24 s deadline. After the closure fix, CR1's retrieval (real feeds and database, no provider) completes in about 6 s on a cold process and about 2.4 s on later requests (section 5).

## 3. Provider and fallback observations
- **Capacity:** all 9 specialist attempts on SR2 returned 429 (Groq gpt-oss-120b, gpt-oss-20b, qwen; OpenRouter nemotron-ultra, nemotron-super, gemma-31b, gemma-26b, north-mini, nemotron-nano). Logged cooldowns: OpenRouter free models about 38,400 s (daily quota gone), Groq 866 to 1,150 s. The first sweep marked every model exhausted, so CC2 and CR1 degraded instantly with zero attempts (a quota outage became a 1.2 s answer, not a wait). No specialist duration was obtained and no call was spent replacing the failed ones.
- **Classifier:** answered by qwen in 0.19 to 0.22 s, but only after two Groq gpt-oss calls that returned empty content (the 5-token cap is consumed by reasoning), adding 0.8 to 1.7 s and 2 Groq calls per request. Moved to section 8.
- **yfinance / background news:** the refresh ran after the first cold request and finished without failures; 0 of 60 snapshot items came from sources outside the RSS feeds. One sample only.
- **Cancelled retrieval did not poison later requests:** the fourth request ran cleanly on a new session after CR1's retrieval had been cancelled (local SQLite only; the production network database is unverified).

## 4. Synthetic slow-provider result
The first specialist attempt was replaced by a hang (no real quota spent waiting); the classifier and everything else used the real chain.
- Attempt 1 ran for exactly its 14 s cap and was charged as a provider timeout (`full_cap_timeout`), as designed.
- The request budget shrank: 24 s deadline, 2.52 s spent before the specialist, 7.47 s remaining at the end of attempt 1, 5.47 s usable after the 2 s reserve.
- Attempt 2 was **not started**: 5.47 s usable is below the 8 s minimum attempt. The request failed closed as `deadline_exceeded` at 16.64 s, 7.36 s inside the deadline.
- **Proven:** a slow provider consumes only its allowed window, the remaining budget shrinks, the whole request stays inside the single absolute deadline, and the chain cannot extend it.
- **Not proven live, only model-free:** that provider 2 *receives* the remaining allowance. At production values the arithmetic never lets a second attempt follow a full-cap timeout (22 s usable minus 14 s cap leaves 8 s, and the classifier and retrieval always use some of it). The model-free tests (`test_request_deadline_latency_contract.py`, "provider one hangs, provider two gets only the remaining budget") prove the allowance mechanism with smaller numbers. The live consequence is fail-closed, not unsafe; see section 7.

## 5. Gate A and Gate B results
- **Gate A:** SUFFICIENT for SR2 (sector_assessment) and CC2 (comparison) in H.4; CR1 was cut off before Gate A. Earlier live and model-free runs: CR2, EI1, EI2 refuse without any model call; the Gate A suites pass.
- **Gate B:** not exercised live in H.4, because no generation was produced (providers 429). It is covered by the saved live generations (SR2 3.4G.5 was withheld for exactly one listed-but-unwritten claim, then replayed through the 3.4G.6 assembler and authorized with no reasons) and by the model-free suites, including: a generation arriving inside the finalization reserve is still authorized; a generation with no time left to authorize is never published.
- **Closure defect (the only one found):** CR1 retrieval reached the 14 s cap in H.4. A model-free replay found the cause: `_real_interest_rate_trend` (optional dimension of historical retrieval) triggers a cold macro-rate fetch of three external sources that takes 10 to 20 s, and it was cancelled by the deadline **every time** (three consecutive attempts all cut off at 14 s), so its cache was never filled and any company question with a relevant Development failed closed permanently. This violated invariant 1 (reliable retrieval), by interaction with the request deadline. Fix (56b5469, `macro_rates/service.py`, `historical_integration.py`, one setting): the fetch is single-flight and shielded, so cancelling a waiter never discards it and it warms the cache; an interactive request waits at most 2 s (`macro_rate_interactive_wait_seconds`) and leaves the dimension unset (never guessed) if it is not ready; background callers wait as before. Verification: 6 model-free tests; the real-network check now shows CR1 retrieval completing in 5.97 s, then 2.4 s per request until the fetch lands, instead of three 14 s cut-offs; related suites show the same failures before and after. No extra real provider request was needed or made.

## 6. The ten Step 3 invariants
| # | Invariant | Verdict | Evidence |
|---|---|---|---|
| 1 | Relevant evidence retrieved reliably | HOLDS | Deterministic ranking and wide pool (3.4G.1); cold-start race fixed with failures recorded, never silent `[]` (3.4G.3); live-news snapshot (3.4H.3); company-path macro fix (56b5469). H.4 retrieval 0.56 to 6.1 s (warm and cold) |
| 2 | Only model-visible evidence can authorize claims | HOLDS | 3.4G.2 prompt-visible index and Gate B corpus alignment; prompt alignment suites |
| 3 | Gate A fails closed | HOLDS | Fail-closed and Gate A suites; CR2/EI1/EI2 never reach a model |
| 4 | Gate B blocks unsupported public claims | HOLDS | Authorization, figures, scope and detector suites; live SR2 withheld exactly as designed |
| 5 | Useful evidence can appear in the answer | HOLDS | SR2 3.4G.5 live generation used 4 distinct visible items and a hedged mixed picture; replay authorizes |
| 6 | Observations and claim_sources cannot drift | HOLDS | 3.4G.6 by construction; 19 tests; mutation check 14 of 19 fail; saved SR2 replay |
| 7 | Retrieval/provider latency bounded per request | HOLDS | Absolute deadline (3.4H.2b); H.4 longest 16.6 s of 24 s; 20 tests |
| 8 | A slow/failing provider cannot create an unbounded chain | HOLDS | Synthetic H.4 run bounded at 16.6 s; real 429 sweep of 9 attempts in 1.3 s; trickling-provider test |
| 9 | Live-news ~13 s penalty gone | HOLDS | Cold 13 s to 1.97 s; stale and fresh under 1 ms; H.4: SR2 cold news 1.53 s, later 0 ms |
| 10 | No Gate B bypass because the deadline is expiring | HOLDS | Fail-closed checkpoints; tests: late generation still authorized within the reserve, no-time generation never published. Not exercised live (no generation in H.4) |

## 7. Latency settings (provisional, unchanged)
| Setting | Value | Recommendation |
|---|---:|---|
| total budget | 24 s | KEEP |
| finalization reserve | 2 s | KEEP (normal-path assembly never measured; Gate B + assembly was 0.08 to 0.11 s in degraded responses) |
| classifier budget | 3 s | TUNE LATER (about 1.5 s once the classifier waste is removed; observed 1.0 to 2.0 s) |
| minimum provider attempt | 8 s | TUNE LATER (suggest 6) |
| per-attempt cap | 14 s | TUNE LATER (suggest 8) |
Not CHANGE NOW: the cap/minimum pairing means a slow first provider fails the request closed instead of falling back (section 4). That is a safe failure; fast failures such as 429 fall back normally (9 attempts in 1.3 s), and a hung provider is charged a 30 s cooldown so the next request skips it. The suggested 8 / 6 values cannot be validated because no successful specialist duration exists, and a too-small cap would charge healthy slower providers as timed out, which is the worse failure. Revisit with one timed specialist call per type once quota recovers.

## 8. Technical debt moved outside Step 3 (no further Step 3 work)
- Classifier waste (2 empty Groq calls and 0.8 to 1.7 s per non-regex request); deterministic-first or skipping reasoning models.
- Provider capacity (OpenRouter free quota exhausted about 10.7 h, Groq cooldowns 14 to 19 min); tune cap, minimum and classifier budget after a real specialist timing.
- First company request after a restart still waits up to 2 s for the macro fetch; warming it at boot is optional.
- Cancelled-retrieval database behaviour on the production network database (local SQLite only observed).
- `run_in_executor` work is not cancellable (not shown to break the request contract in H.4).
- yfinance source value, persisted `news_articles` vs live feed, RSS-system consolidation, dead `news_worker`, article-age eligibility.
- Year-less-date Gate B xfail, snippets, retrieval-weight tuning, comparison-news balancing, Luna reasoning-effort benchmarking, wording and UI polish, broad provider redesign.
- Pre-existing test failures (below), including the stale Weekend Intelligence job-count assertion.

## 9. Test results
- AI Search + deadline + live-news + macro-wait selection: **739 passed, 3 xfailed, 12 deselected** (the existing live-engine test file `test_ai_search_engines_live.py`, which has 2 pre-existing live failures). New tests in this finish: `test_macro_rate_interactive_wait.py` 6; earlier in 3.4G.6 to 3.4H.3: claims-as-observations 19, request deadline 20, live-news snapshot 23. Mutation checks recorded in each step report.
- Pre-existing failures, unchanged by this work (documented, not fixed):
  - `test_ingest_news_shared_fetch.py` (2 tests): fail at commit 6319bd7, before 3.4H.
  - `test_weekend_intelligence_scheduler.py::test_recurring_job_count_increased_by_exactly_two`: asserts 30; the registry already had 32 before this work.
  - `test_macro_rates.py::test_rbi_wss_live`, `::test_macro_rate_state_live_end_to_end`, `test_development_historical_retrieval.py` (2 tests): identical failure set before (cf8363d) and after (56b5469).
  - `test_source_document.py`: needs `pypdf`, which is not installed in this environment.
- The full repository suite was not run; the selections above were.

## 10. Commits created in this autonomous finish
- `56b5469` fix(ai-search): macro-rate fetch single-flight and shielded, 2 s interactive wait.
- This report's own commit follows it.
Step 3 arc verified as ancestors of HEAD: ae9c285 (detector closure), 6319bd7 (claims-as-observations), e65784a (latency inspection), e4b0c9a (deadline design), 8e0c3ff (live-news snapshot), plus 73a60be (deadline implementation), 1a7e637, cf8363d (H.4).

## 11. Statements
- **No push performed. No deployment performed.**
- **Provider-call count in this finish:** 15 real HTTP requests to Groq and OpenRouter during H.4 (9 Groq: 3 classifier attempts for SR2, 3 for the slow run, 3 specialist; 6 OpenRouter specialist, all 429) from 3 real requests plus 1 synthetic request; 0 OpenAI/Luna; 0 retries; no call spent replacing a capacity failure. The synthetic hang was a local stub, not a real call.
- **Secrets:** none entered artifacts. The artifact records only the presence flags of provider keys (for example `"mistral_api_key": false`); no key values, headers or prompts. A pattern scan of `h4_production_chain.json` found no key material.
