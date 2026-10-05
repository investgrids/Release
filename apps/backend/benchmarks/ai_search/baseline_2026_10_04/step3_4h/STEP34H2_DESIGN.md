# Step 3.4H.2 design: production latency contract (end-to-end deadline and remaining-budget propagation)

Inspection and design only. Zero provider calls; nothing in `app/` changed. Evidence: code read of `ai_service.py`, `pipeline.py`, `evidence.py`, `api/ai_search.py`, `Dockerfile`, plus `cancellation_probe.py` (a local stub HTTP server driving the real `_call_provider` and `_tier_slot`; output reproduced below). Not changed or decided here: Gate A/B, retrieval ranking, provider order, reasoning settings (Groq gpt-oss `low`, qwen `none` stay frozen).

## 1. What bounds a request today
| Layer | Bound | Source |
|---|---|---|
| One provider attempt | httpx `connect 5 s`, `read 30 s`, `write 10 s`, `pool 5 s` | `_HTTP_TIMEOUT` |
| One chain traversal | none. 13 model attempts in sequence (Groq 2+1, OpenRouter 3, Mistral 2, Gemini 2, OpenRouter small 3) | `_call_with_fallback` |
| Pipeline / routes | none: no `wait_for`, `asyncio.timeout` or deadline in `pipeline.py`, specialists, `evidence.py` or `api/ai_search.py` | grep |
| Process | gunicorn `--timeout 120`, `--graceful-timeout 30` (Dockerfile); Railway/Vercel proxy limits not verified | Dockerfile |

Nominal worst case for one traversal is 13 x 35 s. Exhaustion cooldowns (30 s after a timeout or 5xx, 120 s after a 429) shorten later traversals but not the first.

**The 30 s read timeout is not even a per-attempt total.** Probe 4: a server sending one byte every 0.4 s never triggered a 1 s read timeout; the call ran until the outer 4 s wait_for cancelled it. `read=` bounds the gap between bytes, so a provider that trickles keep-alive bytes can hold an attempt open far past 30 s.

## 2. Two request-path costs the Luna benchmark never showed
1. **A second LLM chain traversal before the specialist.** `_detect_market_pulse_async` runs a regex, and when it does not match (the code comment says about 86% of queries) it calls `_classify_market_pulse_llm` (`max_tokens=5`) through the **full fallback chain**, serially, before retrieval. The Luna harness refuses classifier-sized requests, so its numbers exclude it. Its production latency is unmeasured here; with a degraded chain it can burn a whole traversal for a yes/no.
2. **Sync work in the default executor.** Valuation, VIX, company enrichment and chart fetches run via `run_in_executor` (`evidence.py:452,467`, `pipeline.py:632,651`).

## 3. Cancellation semantics (measured with the real functions, local stub server)
| Question | Result |
|---|---|
| Does a deadline cancel the in-flight provider call and close the connection? | PASS. `wait_for` cancels the task; the stub server saw EOF 0.03 s after the cancel. `CancelledError` is a `BaseException`, so the `except Exception` in `_call_provider` does not swallow it. |
| Is the tier slot released on cancel? | PASS. `in_flight` 1 during the call, 0 after (`_tier_slot` releases in `finally`). |
| Is the model marked exhausted when cancelled? | No (PASS for "does not charge"): a cancelled call returns nothing and leaves the model untouched. |
| What if the budget is delivered as a shortened httpx timeout instead? | The timeout lands in the `except Exception` branch: the model is marked exhausted for 30 s and logged `reason: timeout`. A budget cut-off would be charged to the provider. |
| Does cancelling `await run_in_executor(...)` stop the thread? | No. The thread ran to completion after the awaiter was cancelled; it holds a default-executor worker until it returns. |

So the right primitive is `asyncio.timeout`/`wait_for` around the attempt (clean cancellation), not a shorter httpx timeout (charges the provider, and does not bound trickling responses). Executor work cannot be cancelled; it can only be abandoned.

Not verified: whether client disconnect on the SSE route cancels `_event_stream` (Starlette normally does; the probe covers the cancel path, not the HTTP layer).

## 4. Design
**Deadline carrier.** A `ContextVar` holding an absolute monotonic deadline, set only by the three HTTP entry points (`/search`, `/search/v3`, `/search/stream`). Reason: about 30 callers use `_call_with_fallback`, and in-process callers such as `comparison_publisher` and `page_intelligence_service` run the same specialists (which hardcode `priority="interactive"`) as background work; an unset var means identical behaviour to today for all of them, so no signature churn and no accidental new limit on batch jobs. Context vars propagate through awaits and tasks created inside the request.

**Budget (starting values, to be set from H.4 measurements).**
| Item | Value |
|---|---|
| Hard backend deadline | 24 s from request start (target typical total under 20 s) |
| Reserve for Gate B, assembly, serialization | 2 s |
| Retrieval | its own cap (about 6 s) after H.3 makes the news path bounded |
| Market-pulse classifier | own sub-budget about 3 s; on timeout treat as "no" (already its failure behaviour) |
| Specialist generation | `remaining - reserve` |
| Minimum useful specialist attempt | parameter (start 8 s); below it no attempt starts |

**`_call_with_fallback`.** Before each model attempt compute `remaining`. If below the minimum useful time for this call class, stop the chain. Run the attempt under `asyncio.timeout(min(read_cap, remaining - reserve))`. The seven tier loops repeat the same code; one `_attempt()` helper keeps the change small. A **cancelled** attempt records `reason: "deadline"` in `failure_log`; it is charged to the provider (a short cooldown) only when it had at least a typical full budget, otherwise it is not charged. Hedged parallel attempts are out: they burn free-tier quota.

**Pipeline checkpoints.** After retrieval and Gate A, and before the specialist call: if `remaining < minimum useful`, return the existing degraded shell with a new internal reason `deadline_exceeded` and the same public wording as other provider-unavailable cases. Never start work that cannot finish.

**Fail closed.** Deadline expiry produces a degraded, unauthorized response, never a partial specialist answer. No Gate A/B change.

**Interaction to carry into H.3.** A retrieval step cancelled by its stage budget must surface as `retrieval_failures`, not as an empty bundle; otherwise Gate A would refuse with "no evidence" wording (the tracked retrieval-failure-versus-absence item).

**Executor work.** Wrap each executor await in a short stage timeout and fall back to empty, as the code already does on error. Threads still run to completion, so the stage budget must be small (about 2 s) and a repeating slow source should be tracked as a separate item.

## 5. Model-free test plan (stub servers, as in the probe)
1. Provider 1 hangs, provider 2 healthy: provider 2 receives only the remaining budget; total is bounded by the deadline.
2. Every provider hangs: total is at most the deadline plus reserve; one degraded `deadline_exceeded` response; no attempt starts below the minimum.
3. Trickling provider (bytes every 0.4 s): cancelled by the attempt timeout (this is the case the read timeout cannot catch).
4. Cancelled attempt: connection closed, tier slot released, model not marked exhausted when under budget; charged when it had a full budget.
5. Classifier sub-budget: hanging classifier does not consume the specialist's budget.
6. Context var unset (background jobs): behaviour byte-identical to today.
7. Retrieval stage cap yields `retrieval_failures`, not silent `[]`.
8. Streaming route: deadline emits the degraded envelope; frontend wording check.

## 6. Open measurements (H.4, not guessable)
- Classifier latency on the real chain.
- Typical specialist attempt time per tier (Groq gpt-oss-120b/20b, qwen, Gemini, Mistral); this sets the minimum useful attempt.
- How often the first tier is exhausted or slow in production.

## 7. Next
Awaiting approval for the implementation step (3.4H.2b): contextvar deadline, `_attempt()` helper, pipeline checkpoints, tests above. Separate from H.3 (live-news cache).
