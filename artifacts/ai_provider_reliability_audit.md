# AI Provider Reliability Audit

**Date:** 2026-08-30
**Scope:** read-only audit of the production AI-provider fallback chain, triggered by two real errors (Mistral 401, OpenRouter 404) observed live during the P0 disk-full incident investigation. No code or configuration changed.
**Method:** real code read (`app/services/ai_service.py`, `fallback_chain_provider.py`, `config.py`, `triage_worker.py`, `event_pipeline.py`, `article_generator.py`, `publisher.py`, `coverage_engine.py`) + real `railway variables`/`railway logs` against production. Two log windows: pre-restart (`05ab21ee`, 2026-08-30 04:53–07:48 UTC, ~3h11m — the deployment's entire retrievable log history, since it had been running unchanged since 08-24) and post-restart (`2e0a520e`, 07:48–07:56 UTC, ~8min, current deployment).

**Note on the audit process itself**: an early redaction command briefly leaked 4-character prefixes of several API keys into the auditing agent's own tool output before being caught and corrected. No full secret was exposed and nothing was written to a persistent file; all subsequent checks used key presence/length only, never values.

## 1. Provider matrix

| Provider (tier order) | Model(s) | Config source | Consumers | Production status | Failure reason | Fallback | Action required |
|---|---|---|---|---|---|---|---|
| 1. Groq HQ | `openai/gpt-oss-120b`, `openai/gpt-oss-20b` | `GROQ_API_KEY` (set) | every `_call_with_fallback` caller | 429, every attempt | Real rate/quota limit, self-healing | → Cerebras | None — working as designed |
| 2. Cerebras | `gpt-oss-120b` | `CEREBRAS_API_KEY` | same | **Not configured** — key absent in Railway, tier never attempted | Not configured | → Groq fast | Provision the key or remove the dead tier |
| 3. Groq fast | `qwen/qwen3.6-27b`, `groq/compound-mini`, `groq/compound`, `openai/gpt-oss-safeguard-20b` | `GROQ_API_KEY` | same | 429, all 4 models | Same account-wide Groq quota as tier 1 | → OpenRouter HQ | None |
| 4. OpenRouter HQ | 3 real models + `openai/gpt-oss-20b:free` | `OPENROUTER_API_KEY` (set) | same | 3 models: 429 (quota). `openai/gpt-oss-20b:free`: **404, 24/24 attempts** | The 3 quota-limited ones are genuine; `openai/gpt-oss-20b:free` is a stale/renamed/removed slug — not a key or account problem, since sibling models on the identical call path succeed or 429 normally | → Mistral | **Remove `openai/gpt-oss-20b:free`** (`ai_service.py` line 430) |
| 5. Mistral | `mistral-small-latest`, `open-mistral-nemo` | `MISTRAL_API_KEY` (set, plausible length/format) | same | **401, both models, 100% of attempts** (48 hits in the 8-min post-restart window alone) | Code is correct — standard Bearer-token auth against the real Mistral endpoint (line 641). The key itself is rejected every time → invalid/expired/rotated at Mistral's end. The code's own 2026-08-22 comment had already diagnosed this and marked it not fixable from code. | → Gemini | **Rotate `MISTRAL_API_KEY`** in Mistral's console + Railway |
| 6. Gemini | `gemini-3.6-flash`, `gemini-3.5-flash-lite` | `GEMINI_API_KEY` (set) | same | **Working** — the real workhorse: 62 successes pre-restart + 22 post-restart | N/A | → OpenRouter small | None |
| 7. OpenRouter small | 3 real models + 3 stale `nvidia/nemotron-*` slugs | `OPENROUTER_API_KEY` | same | The 3 stale slugs: **404, every time reached**. The 3 real ones: 429 (quota) | Same pattern as tier 4 | → Cloudflare | **Remove the 3 stale `nvidia/nemotron-*` slugs** |
| 8. Cloudflare Workers AI | `@cf/zai-org/glm-4.7-flash` | `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` | same | **Not configured** — neither var set, tier never attempted despite the code saying it was added 2026-08-05 | Not configured | → chain exhausted | Provision both vars or remove the dead tier |
| NVIDIA (separate) | `nvidia/nemotron-3-ultra-550b-a55b` | `NVIDIA_API_KEY` (set) | Decision Intelligence explanations only — not part of the main fallback chain | Not exercised in the pulled windows | — | Falls through to the main chain on any failure, never blocks | None |

**On the OpenRouter 404s specifically**: only 4 of ~10 configured free-tier slugs ever 404 — and each one 404s on 100% of attempts, while every sibling slug on the identical account/key/endpoint instead gets 429 or succeeds. This rules out an account/auth/endpoint-level problem; it's 4 specific stale slugs. This directly contradicts the code's own 2026-08-22 comment asserting "OpenRouter's remaining free models are fine, just genuinely exhausted" — that comment is 8 days stale for these 4 slugs.

## 2. Candidate-lifecycle consequence (the key question)

- **`triage_worker.py` — never drops a candidate.** Every failure path returns a real rule-based fallback dict, and `_store_triage()` unconditionally persists an `EventTriage` row regardless. 33 real `triage.fallback_to_rule_based` events fired in the pre-restart window — every one still produced a row.
- **`event_pipeline.py` — degrades, doesn't vanish.** An AI-unavailable classification raises, gets caught, and calls `mark_enrichment_failed(reason="provider_unavailable")` with exponential-backoff retry (up to 5 attempts). The underlying `Event` row is never deleted. This path was **not observed firing** in the pulled logs (the 98 real pipeline failures in that window were all the separate disk-full error) — confirmed non-destructive by code inspection, but not by live observation this time.
- **AIPE article generation — a real, newly-found asymmetry.** Regular triage-driven candidates correctly call `coverage_engine.mark_failed(...)` on generation failure, preserving a trace. But **scheduled/synthetic candidates — `morning_intelligence` and `market_wrap`** — use a synthesized event ID that was never triaged, so no `EventCoverage` row exists for them at all. On generation failure, the code path (`publisher.py` ~line 870) has **no `else` branch**: no coverage update, no `IntelligenceArticle` row, nothing beyond a log line. **Real, measured**: 22 occurrences of `publisher.generation_failed type="morning_intelligence"` in the single 3h11m window pulled — 22 real candidates, zero database trace for any of them. The same code shape exists for evergreen `historical_intelligence` topics (0 real occurrences in this window, but same silent-drop class).

**On the 994 missing candidates**: no evidence was found directly tying provider exhaustion to that specific figure, and none is being asserted here. What's now real and separately established: the scheduled-article path alone silently dropped 22 real candidates with zero trace in one 3-hour window, purely from AI-chain exhaustion — a genuine, previously-unknown bug in its own right, worth its own investigation into how it interacts with the earlier funnel numbers, not assumed to explain them.

## 3. Real frequency data

| Window | Duration | `ai.success` | `ai.all_providers_failed` | Failure rate |
|---|---|---|---|---|
| Pre-restart (`05ab21ee`) | 04:53–07:48 UTC (~3h11m) | 68 (62 gemini, 4 openrouter-hq, 1 groq-hq, 1 groq-fast) | 59 | **46.5%** of fallback-chain invocations exhausted every tier |
| Post-restart (`2e0a520e`) | 07:48–07:56 UTC (~8min) | 24 (22 gemini, 2 groq-hq) | 2 | 7.7% |

The pre-restart window is the full retrievable history for that deployment (it had run unchanged since 08-24; Railway only serves logs per deployment ID) — not extrapolated further. Of the 59 pre-restart exhaustions: 33 triage (soft-degraded, record preserved), 22 scheduled-article (zero trace), ~4 other callers not individually traced in this pass.

## Smallest safe remediation plan (provider/key/model-list only)

1. **Rotate `MISTRAL_API_KEY`** — code is correct, the key is rejected on every call.
2. **Remove 4 dead OpenRouter slugs**: `openai/gpt-oss-20b:free` (`ai_service.py` line 430), `nvidia/nemotron-3-nano-30b-a3b:free`, `nvidia/nemotron-nano-12b-v2-vl:free`, `nvidia/nemotron-nano-9b-v2:free` (lines 549-551) — each 404s on 100% of real attempts, wasting a round-trip on every fallback invocation that reaches them.
3. **Decide on Cerebras and Cloudflare** — both fully coded but zero credentials configured; either provision them or remove the dead tiers.
4. **Not remediated here (out of scope for this pass)**: the scheduled-article zero-trace silent-drop is a real bug but is architectural (a missing `else` branch / a coverage-row model mismatch for untri­aged synthetic events), not a provider/key/model-list fix — flagged for separate follow-up.

## Explicitly not done

- No code or config changes.
- No scheduler, candidate-window, prompt, Article V2, Score, Warehouse, or RSS-linkage changes.
- No claim that this explains the 994 missing candidates — that connection is unproven and not asserted.
