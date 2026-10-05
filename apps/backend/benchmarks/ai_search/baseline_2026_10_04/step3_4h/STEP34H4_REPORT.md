# Step 3.4H.4 report: production-chain latency measurement

Measurement only. No setting, prompt, provider order or reasoning parameter was changed; no OpenAI/Luna call; each request ran once, no retries. Budgets during the probe: 24 total / 2 reserve / 3 classifier / 8 min attempt / 14 attempt cap. Artifact: `h4_production_chain.json` (no keys or headers). Harness: `h4_production_chain.py`. Providers configured locally (and so in the chain): Groq and OpenRouter; Mistral and Gemini have no key. The chain therefore has 9 specialist attempts, not 13.

## Result in one line
**The real chain had no capacity: all 9 specialist attempts returned 429, so no specialist timing was obtained.** The deadline envelope held in every run (longest 16.6 s). Two other latency problems were found: the classifier wastes calls, and the first company request after a process start spends about 20 s in historical retrieval.

## Timing table (seconds)
| Request | Classifier | Retrieval | News snapshot (state, ms) | Specialist chain | Gate B + assembly | Wall | Deadline left at end | Outcome |
|---|---:|---:|---|---:|---:|---:|---:|---|
| SR2 | 1.03 (3 attempts, 2 empty) | 6.06 | cold, 1,531 | 1.28 (9 attempts, all 429) | 0.11 | 8.63 | 15.39 | degraded `capacity` |
| CC2 | 0.00 (all models exhausted, skipped) | 1.11 | fresh, 0 | 0.00 (9 skipped as exhausted) | 0.08 | 1.19 | 22.81 | degraded `capacity` |
| CR1 | 0.00 (skipped) | **cut off at 14.0** | fresh, 0 | not reached | n/a | 14.02 | 9.99 | `retrieval_deadline_exceeded` |
| SR2, first specialist attempt replaced by a hang | 1.95 (3 attempts, 2 empty) | 0.56 | fresh, 0 | 14.02 + gate stop | 0.11 | 16.64 | 7.36 | `deadline_exceeded` |
Gate A was SUFFICIENT for SR2 and CC2 (CR1 never reached it). Retrieval failures recorded: none except CR1's deadline cut-off.

## The five questions
1. **Does retrieval stay cheap?** Not on cold paths. Warm: CC2 1.1 s, SR2 0.56 s, news 0 ms. Cold: news about 1.5 s (as designed), SR2's first retrieval 6.1 s (replay: 4.7 s), and **CR1's first company retrieval about 20 s**. The cause, found by a model-free replay (`profile_collect_sequence.py`): `development_memory.find_similar_developments_context` takes **20.2 s on its first call in a process and 0.00 s on the second** (historical-event load and similarity build), and only the company path calls it. Every company question after a restart or deploy hits it. An isolated profile with a stubbed intent missed it because it skipped that branch.
2. **How much of the request does the classifier consume?** 1.0 to 2.0 s when providers answer (limit 3 s), 0 s when every model is already marked exhausted. About 1 s of that is waste: the two Groq gpt-oss models return **empty content** for the 5-token classifier (reasoning tokens use the cap), so each non-regex request spends 2 failed Groq calls and 0.8 to 1.7 s before qwen answers in about 0.2 s. These are also 2 of the limited daily Groq calls per query.
3. **Does the first specialist provider usually succeed?** Not measurable today: 0 of 9 attempts succeeded, all 429. The logged cooldowns say why: OpenRouter free models report a retry-after of about 38,400 s (10.7 h, daily quota gone), Groq models 866 to 1,150 s. Qwen answered the classifier moments before its specialist 429, so a size-based or token-rate limit may be involved on Groq; the artifact cannot separate that from a daily limit. The first sweep marked all 9 models exhausted, so CC2 and CR1 degraded instantly (the exhaustion cache turned an outage into a 1.2 s answer, which is good for latency). No retry was spent, as instructed.
4. **Can fallback happen within 24 s?** **No, not with the current numbers.** In the slow-first-provider run the hung attempt used its full 14 s cap (charged as a provider timeout, as designed). Pre-specialist work had already used 2.5 s (classifier 1.95 s, entity and retrieval 0.6 s), leaving 7.47 s remaining, 5.47 s usable after the 2 s reserve, which is below the 8 s minimum. The chain stopped and failed closed at 16.6 s, with 7.4 s of the deadline unspent. The H.2b coupling rule I proposed (cap at most total - reserve - min attempt = 14) ignored the time the classifier and retrieval spend first. The intended demonstration (real provider 2 receiving the remaining allowance) did not occur; the bound held, the fallback did not.
5. **Does the whole request stay bounded?** Yes in all four: 8.6 s, 1.2 s, 14.0 s (retrieval cap), 16.6 s, all inside 24 s, with failures reported as `temporarily_unavailable`.

## yfinance and background refresh
The background refresh ran after the first cold request and completed without failures; no snapshot items came from sources outside the RSS feeds (0 of 60). One sample, not a judgement of long-term value.

## Recommended values for the five provisional settings (not applied)
| Setting | Now | Recommendation | Basis |
|---|---:|---:|---|
| total budget | 24 | **24** | Held in every run; matches the 20 to 25 s target. |
| finalization reserve | 2 | **2 (keep until measured)** | Gate B + assembly was 0.08 to 0.11 s, but only in degraded responses. A normal assembly (company enrichment, chart) was never measured because no specialist succeeded. |
| classifier budget | 3 | **3 now, about 1.5 after the classifier fix** | Observed 1.0 to 2.0 s with two wasted attempts; with the waste removed qwen answers in about 0.2 s. |
| min provider attempt | 8 | **6** | Coupling: the second attempt must fit after the first. |
| attempt cap | 14 | **8** | Worst realistic pre-specialist time is about 8 s (cold SR2): 24 - 2 - 8 = 14 = cap + min, so a slow first attempt still leaves a usable second one. |
Caveat on cap and min: **no successful specialist duration exists to validate them.** A cap of 8 s suits fast Groq generation but would cut slower free OpenRouter models and charge them as provider timeouts. Treat these two as provisional until one real specialist call per specialist type is timed after quota recovers.

## Does 3.4H close? Not yet: three targeted items
1. **Historical-retrieval cold start (about 20 s on the first company request per process).** Release blocker: first-after-deploy company questions fail closed. Needs warm-up at startup or in the scheduler, or a bounded optional context that never blocks retrieval.
2. **Classifier waste:** 2 empty Groq calls per request plus 0.8 to 1.7 s. A fix may be as small as skipping reasoning models for the 5-token call, or going deterministic-first (not designed here).
3. **Re-couple the attempt cap and minimum attempt** (config only) and re-time one real specialist call per type once quota recovers.
Separate, already tracked: provider capacity (OpenRouter free daily quota exhausted for about 10.7 h; Groq in cooldown for 14 to 19 min). A real specialist measurement needs that to recover; I will not spend calls until you say so.

## Files
`h4_production_chain.py`, `h4_production_chain.json`, `profile_collect_company.py` (the stubbed-intent profile that missed the cause, kept for the record), `profile_collect_sequence.py` (the replay that found it).
