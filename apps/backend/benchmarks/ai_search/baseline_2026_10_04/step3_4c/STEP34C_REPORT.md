# Step 3.4C report: OpenAI benchmark isolation (harness wired; live run waiting on the owner's key)

Frozen at `00facc7`. No rule, retrieval, provider-chain, production or app/ change. Nothing pushed or deployed. **No OpenAI request has been made.**

## What exists
`qualify_openai.py` runs CR2 -> EI1 -> CC1 through the real pipeline with the model call replaced by a wrapper that talks only to the dedicated benchmark project:
- Key from `OPENAI_BENCH_API_KEY` (shell only, never a committed file, never Railway), removed from the environment after import, never printed or written. Every other environment variable is deleted before the app loads.
- Model id from `OPENAI_BENCH_MODEL` (default `gpt-6-luna`, as named by the owner; **I could not verify this id, a `model_not_found` result will be classified as such**). The exact id and the model id OpenAI returns are recorded in the artifact.
- Call cap `OPENAI_BENCH_MAX_CALLS` (default 2), no retries, stop on the first non-200, no fallback to any production provider, not added to the production chain.
- Errors are classified from the actual OpenAI code/type: AUTH_INVALID_KEY, MODEL_NOT_FOUND_OR_NOT_ENABLED_FOR_PROJECT, CREDITS_OR_PROJECT_SPEND_LIMIT_EXHAUSTED, PROJECT_SPEND_LIMIT_REACHED, RATE_LIMITED, BAD_REQUEST, NETWORK_OR_TIMEOUT.
- Per question it captures: Gate A decision, premise check, model call count vs expected, tokens, reasoning tokens, latency, finish reason, structured-parse outcome, claim_sources, claim_validation, Gate B decision, final public response, and the rejected generation when authorization fails.
- Success criterion: **CR2 0 calls, EI1 0 calls, CC1 exactly 1 call** (2 correct deterministic refusals + 1 grounded answer), not 3/3 model successes.

## Preflight (dry run, no key, no request; `openai_preflight.json`)
| Q | Gate A | Premise | Model calls |
|---|---|---|---|
| CR2 | INSUFFICIENT / company_assessment (missing current_company_evidence) | not_applicable | 0 |
| EI1 | INSUFFICIENT / event_impact (missing event_verification) | not_established | 0 |
| CC1 | SUFFICIENT / comparison | n/a | 1 (would be made) |

CC1 passes Gate A in this environment, so it will not be forced. Caveat: valuation data is empty here (yfinance SSL failure), so CC1's bundle is filings and one event only (6 announcements, 1 event, no valuation). Gate A is satisfied, but a thin comparison is likely, and live evidence in the owner's environment may differ from this snapshot. Gate A was not weakened.

## Owner actions needed (I cannot do these)
1. Create OpenAI project `MarketRipple AI Search Benchmark` with a new project-scoped key. Enable only the benchmark model. Set a small spend limit ($5-10) and **explicitly configure it as an enforced hard limit** (a plain budget/alert does not stop requests).
2. Do not reuse any key previously pasted in chat. Do not paste the new key into chat or commit it.
3. Run in your own shell (or authorize me to run it with the variable already set):
   `$env:OPENAI_BENCH_API_KEY="..."; $env:OPENAI_BENCH_MODEL="gpt-6-luna"; python benchmarks/ai_search/baseline_2026_10_04/step3_4c/qualify_openai.py`
4. Confirm the exact model id your project exposes if `gpt-6-luna` returns model_not_found.

## Next
Step 3.4D (the live CR2/EI1/CC1 run) once the key exists. If CC1 returns `claims_not_authorized`, Gate B is NOT loosened: the artifact is inspected to see whether the model ignored claim_sources, the validator rejected a legitimate transformation, or (the serious case) Gate B authorized an unsupported statement. Only a CC1 pass leads to the frozen-18 run (3.4E).
