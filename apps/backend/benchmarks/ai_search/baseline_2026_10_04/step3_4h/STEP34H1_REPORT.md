# Step 3.4H.1 report: zero-call inspection of reasoning/output controls and the real timeout path

Zero OpenAI calls made. Two harness dry runs (no key, `--dry`) and one local profile of `evidence.collect` (database and RSS reads only). Nothing pushed or deployed.

## 1. What the benchmark request sends to gpt-6-luna
`qualify_openai.py` posts exactly `{model, messages, max_completion_tokens}` (6,500 for company/sector, 7,000 for full comparison). Nothing else: no `reasoning_effort`, no verbosity control, no temperature. So Luna runs at its **unspecified default reasoning effort**, and the cap (max seen 4,726 completion tokens, which includes hidden reasoning) never binds.

Not verifiable offline: whether `gpt-6-luna` accepts `reasoning_effort`, and which values. I have no model documentation here and will not guess. The first request that carries the parameter will tell us (an unsupported parameter or value returns a 400 that the harness already classifies and stops on, with no generation tokens spent).

## 2. The benchmark is not what production runs
Production never calls OpenAI. `ai_service._call_with_fallback` walks Groq `openai/gpt-oss-120b`, `gpt-oss-20b` (both already sent `reasoning_effort: "low"`), Groq `qwen3.8-27b` (`"none"`), OpenRouter, Mistral, Gemini, OpenRouter small. Payload there: `max_tokens` (6,500 / 7,000), `temperature 0.4`. The Luna harness replaces that chain with a single call.

Consequence: Luna latency numbers measure the benchmark provider, not production. Tuning Luna's reasoning effort only helps production if Luna becomes a production provider (your OpenAI-as-benchmark-only todo says it is not today). Production latency depends on the Groq tier, currently capacity-limited.

## 3. Per-call breakdown (from saved artifacts; provider call only)
| Specimen | LLM s | Prompt | Completion | Hidden reasoning | Visible output | tok/s |
|---|---:|---:|---:|---:|---:|---:|
| EI3 run2 | 16.5 | 2,064 | 2,167 | 1,744 | 423 | 131 |
| EI3 3.4G.1 | 12.3 | 2,064 | 1,327 | 876 | 451 | 108 |
| EI3 3.4G.2 | 19.2 | 2,064 | 2,246 | 1,676 | 570 | 117 |
| CC2 3.4G.1 | 22.6 | 2,042 | 2,901 | 1,849 | 1,052 | 128 |
| MP1 | 21.0 | 2,490 | 2,771 | 2,273 | 498 | 132 |
| SR2 run2 | 27.4 | 2,130 | 3,424 | 2,455 | 969 | 125 |
| SR2 3.4G.4 | 44.3 | 2,312 | 4,014 | 3,335 | 679 | 91 |
| SR2 3.4G.5 | 57.3 | 2,778 | 4,726 | 3,486 | 1,240 | 82 |

- Latency tracks completion tokens at roughly 80 to 130 tokens/s. Hidden reasoning is 40% to 83% of completion; visible answer text is only 0.4K to 1.2K tokens.
- SR2's reasoning grew 2,455 → 3,335 → 3,486 as the prompt gained rules (+about 520 prompt tokens from the composition contract in 3.4G.5). Throughput also fell to 82 tok/s on the slowest call, so provider-side variance adds to it.
- The "CC1 D-4, 25.2 s" row is not in any saved artifact I can find: `openai_qualification.json` holds an earlier 55.2 s CC1 run (verbose schema, 4.8K visible tokens). I did not re-derive that row.

## 4. The 30-second timeout covers neither the request nor the total
- Production's 30 s is `httpx` **read timeout per provider attempt** (`_HTTP_READ_TIMEOUT_S = 30.0`, connect 5 s). It is not a deadline for the AI Search request.
- No `asyncio.wait_for`, `asyncio.timeout` or deadline exists in `pipeline.py`, the specialists or `api/ai_search.py`. The chain can try several models in sequence, so a degraded provider state can stack 30 s per attempt. The interactive tier-slot wait is 1.5 s per tier.
- The web client has no AI Search timeout (only a comment mentioning one).
- The harness's `would_exceed_30s` looks at the provider call only. Measured totals are larger: SR2 3.4G.5 was 71.2 s wall = 57.3 s model + 13.8 s evidence collection.

## 5. New finding: cold news fetch costs about 13 s inside the request
Profile of `evidence.collect` for SR2 (`step3_4h/profile_collect.py`, fresh process): total 16.1 s; `_search_news` 13.1 s; events 0.14 s; VIX 0.19 s; clustering about 0. Two consecutive dry runs gave 13.9 s evidence collection each time.
Cause: `_search_news` calls `get_live_news`, whose in-process cache has `CACHE_TTL = 900` s. A cold cache fetches all RSS/yfinance sources inline (10 s per-feed timeout). The harness starts a fresh process per run, so every measured question pays it; earlier runs that were warm inside one process show 0.3 to 2 s.
Production likely pays it on the first AI Search request after each 15-minute expiry, with no stale-while-revalidate that I found. Not verified: whether anything else warms that cache in production (the news endpoints also call it). This predates 3.4G; I have not changed it.

## 6. Where the time goes (target view)
| Stage | Warm | Cold / worst seen |
|---|---:|---:|
| Retrieval and gates | 0.3 to 2 s | 13 to 14 s (cold live-news cache) |
| LLM (Luna, default effort) | 12 to 27 s | 44 to 57 s on SR2 |
| Validation and assembly | under 0.1 s | under 0.1 s |
A total under 20 s needs the LLM at about 10 to 15 s and a warm news cache.

## 7. Recommended 3.4H.2 (not run)
- **Specimen:** SR2 on the current prompt. The default-effort baseline is already measured (3.4G.5: 57.3 s, 4,726 completion, 3,486 reasoning), so it is not re-run.
- **Config A:** the lowest reasoning effort Luna accepts. **Config B:** the next one up (low, if A is minimal/none). Test B only if A fails quality or integrity. A rejected parameter is learned from the first response at no generation cost.
- **Accept only if all hold:** Gate B authorized; at least three distinct visible observations from distinct items plus the mixed synthesis; model latency under 20 s (hard ceiling well below 30 s); reasoning/completion tokens materially below 3,486 / 4,726.
- **Budget:** about 3 to 4K tokens per call at low effort, so two calls are roughly 8K of the ~40.9K remaining; the default-effort rerun is avoided.
- **Needs a harness change before it can run:** an env var (for example `OPENAI_BENCH_REASONING_EFFORT`) added to the payload. That is not done yet because you asked for the report first.

## 8. Decisions for you
1. Is Luna meant to become a production provider, or is it only a quality probe? If only a probe, 3.4H.2 results will not change production latency; the production lever is the reasoning/tokens setting per provider and an end-to-end deadline.
2. Add an end-to-end deadline and a stale-while-revalidate for the live-news cache as separate, small items (3.4H.3, model-free)? Neither is started.
