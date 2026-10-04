# PRC-1: Provider Capacity Reality Audit (diagnostic only)

2026-10-04 (probes about 18:35 IST). No provider, prompt, retry-policy, model, retrieval or production change; nothing pushed or deployed; no production AI Search run. Keys were never printed or logged (presence booleans and a truncated SHA-256 fingerprint only; response metadata is sanitized). Probe cost: 18 small requests in total.

## Headline
**Every model in the locally configured chain returned an explicit, provider-stated DAILY quota refusal.** None was AVAILABLE, none was provably REQUEST_LIMITED, none was UNKNOWN_429. **The real specialist-sized request was never reached for any model**, so "are our specialist prompts too large?" is still unanswered, but the one concrete test of the hypothesis ran against it (below). And the **local environment is not the production topology**, while **local and production share the same Groq and OpenRouter accounts**.

## 1. Local vs production
| | Local (this machine) | Production (booleans via `railway run`) |
|---|---|---|
| Groq key | configured, fingerprint `656d487b` | configured, **same fingerprint** |
| OpenRouter key | configured, fingerprint `94792ba8` | configured, **same fingerprint** |
| Gemini key | **not configured** (tier never attempted) | configured (fingerprint `2a026e39`) |
| Mistral key | not configured | not configured |
| Chain actually exercised | Groq (3 models) then OpenRouter (6 models) | Groq, OpenRouter, **then Gemini** (`gemini-3.6-flash`, `gemini-3.5-flash-lite`) |
| Groq-fast tier code | 1 model (`qwen3.8-27b`) on `release/ai-answer-v2` | 4 models on the deployed `main` code (adds `groq/compound-mini`, `groq/compound`, `openai/gpt-oss-safeguard-20b`) |

Consequences: (a) the Step 3.3 qualification exercised a chain with **no Gemini**, which production logs show succeeding on 4 Oct; (b) **local test traffic draws on production's Groq and OpenRouter quota** (same accounts), and production traffic draws on the same quota local runs see; (c) the AI Search answer-v2 code under test is on `release/ai-answer-v2` and is not what production runs (`main`).

## 2. Per-model classification (every state backed by provider text)
| State | Provider / model | Evidence from the response |
|---|---|---|
| QUOTA_EXHAUSTED | Groq `openai/gpt-oss-120b` | daily tokens (TPD): limit 200,000, used 199,941, remaining 59; `retry-after` 496 s (rolling window) |
| QUOTA_EXHAUSTED | Groq `openai/gpt-oss-20b` | TPD: limit 200,000, used 199,993, remaining 7; `retry-after` 587 s |
| QUOTA_EXHAUSTED | Groq `qwen/qwen3.8-27b` | TPD: limit 200,000, used 199,586, remaining 414; `retry-after` 103 s |
| QUOTA_EXHAUSTED | OpenRouter, all 6 free models | "Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000 free model requests per day"; `X-RateLimit-Limit` 50, remaining 0, reset 2026-10-05 00:00 UTC (05:30 IST). Account-wide, identical for every model |
| NOT_TESTED | Gemini | no key locally; needs the production key, outside this local diagnostic |
| NOT_TESTED | Mistral | no key anywhere |

Smaller requests did succeed while quota remained: Groq 21-token (qwen) and 613-token (both gpt-oss) requests returned 200; the first refusal came at the next size up because the remaining daily tokens were fewer than the request.

## 3. The hypothesis "our large `MAX_TOKENS` is the cause"
- **Tested for the daily-token check, evidence against.** For a 1,000-token request with a 768-token output allowance, Groq reported `Requested 1205`. Calibrating from a successful request (3.6 characters per token) the input alone is about 1,169 tokens; input plus the output allowance would be about 1,937. So Groq's TPD "Requested" counts the **input, not `max_tokens`**.
- **Not tested: the per-minute check.** Headers show a per-minute limit of **8,000 tokens** per model. A CR2 specialist call is about 2,570 real input tokens plus up to 6,500 output, which could touch 8,000/minute if output counts there. Quota blocked every model before any request that large, so this stays a hypothesis.
- Limits seen: 1,000 requests/day, 8,000 tokens/minute, 200,000 tokens/day per Groq model (tier `on_demand`); OpenRouter free: 50 requests/day account-wide.
- Probe-design flaw, found and fixed: reasoning models (`gpt-oss`) return empty content at `max_tokens=5` (finish reason `length`; the budget goes to hidden reasoning). That is a request-budget property, not a capacity signal; the re-run used a realistic budget ladder for them. It also means the pipeline's 5-token market-pulse classifier gets an empty answer from the gpt-oss models and silently falls through to the next model.

## 4. Cooldown behavior (`already_exhausted`), from the code, confirmed against the responses
- **Triggers:** HTTP 429 (cooldown from `Retry-After`, else `x-ratelimit-reset-requests`, else `x-ratelimit-reset`, else 120 s), 402 (45 min), 401/403 (6 h), 404 (24 h), 5xx or any exception/timeout (30 s). Provider-supplied values are capped at 24 h.
- **Scope:** `(provider, model)`, held **in process memory** only. No account-level grouping and no sharing between workers or restarts. An account-wide quota therefore produces one refusal per model per worker (OpenRouter: six).
- **Retry-After is respected and parsed correctly:** Groq `retry-after` 103-587 s matched the rolling-window waits; OpenRouter's reset arrives as an epoch in milliseconds, converted correctly, matching the earlier 14.7 h cooldown (14:44 IST to 05:30 IST).
- **EI1 and CC1 skipping in Step 3.3 was correct, not over-broad:** every model was genuinely quota-exhausted.
- **Gaps (confirmed in code, no behavior changed):** (1) the 429 **body is never read**, so the service logs "rate_limit" for daily-token exhaustion, per-minute throttling and per-day request caps alike; telemetry cannot tell quota from rate, which is why PRC-1 had to call providers directly. (2) A model with a little quota left (qwen: 414 tokens) is marked exhausted as a whole for the cooldown, so even tiny calls skip it. (3) After each cooldown the next large request is refused again, one wasted round trip per model per window. (4) The app's 30 s read timeout converts a slow but successful long generation into an exception and a 30 s cooldown (gpt-oss-120b produced 417 tokens in 1.4 s, about 300 tokens/s, so 6,500 tokens is roughly 20 s there; slower providers were not measured).

## 5. What this means
- The "provider-capacity blocker" in Steps 3 to 3.3 is **daily quota exhaustion on shared free-tier accounts**, stated by the providers themselves, in a local environment that also lacks production's Gemini tier.
- Quota arithmetic (estimates, not measurements): Groq 3 models x 200,000 tokens/day, at roughly 7,000-9,000 tokens per specialist answer, is about 65-85 answers/day at best, before the market-pulse classifier (about 700 tokens per call was measured once) and every other AI job on the same accounts. OpenRouter free tops out at 50 requests/day account-wide. Production's usage of the same accounts is not visible from here.
- Production capacity is **not established** by this audit: its Gemini tier was not tested, and production shares the exhausted Groq and OpenRouter quotas right now.

## 6. Gate decision (no action taken)
Outcome sits between the plan's branches: not "only the local environment" (the shared accounts are also production's) and not "requests exceed limits" (never reached). Not UNKNOWN_429. Options for the next, explicitly approved step, none started:
1. **Qualify the production-representative path:** run the 3-question Step 3.3 gate through Gemini using the production key via `railway run`, capped at the three specialist calls (consumes a little of production's Gemini quota).
2. **Give benchmarks their own capacity:** separate benchmark keys so evaluation does not compete with production (OpenRouter credits, a Groq paid tier, or another provider), a decision outside this diagnostic.
3. **Wait for resets:** OpenRouter at 05:30 IST; Groq's rolling window frees tokens gradually, but production traffic refills it.

Files: `config_presence.py`, `key_fingerprint.py`, `probe.py`, `finalize.py`, `probe_results.json`, `probe_results_gptoss.json`, `probe_results_final.json`.
