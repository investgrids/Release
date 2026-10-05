# Step 3.4G.3 report: cold-start evidence reliability

Isolated patch. No ranking, prompt, Gate A, Gate B or routing change. Zero provider calls, no network. Nothing pushed or deployed. The 52K OpenAI tokens are untouched.

## The defect (reproduced, not mocked)
`evidence.collect` ran its events, news and policies lookups concurrently on **one** `AsyncSession`. A session cannot run two operations at once. On the first use of a cold connection pool SQLAlchemy raised "This session is provisioning a new connection; concurrent operations are not permitted", `gather(..., return_exceptions=True)` swallowed it, and a whole evidence source silently became `[]` with no log line. The same pattern existed in the pairwise decision engine (`asyncio.gather(_opp_for(a), _opp_for(b))` on the pipeline's one session).

## The fix
- **No concurrent operations on one session:** the three `collect` lookups run one after another on the existing session (one connection; I chose serial over per-task sessions so the request does not take two extra pool connections, since pool contention after deploys is already a tracked debt). The two `_opp_for` lookups are sequential too.
- **A failing source is never silently `[]`:** each lookup is guarded. On failure: (a) logged as `ai_search_v3.evidence_source_failed` with `source` and `error_class` only (no query text, no exception message); (b) recorded in `bundle.retrieval_failures` and copied into `filter_report["retrieval_failures"]` (internal diagnostics), so "the source failed" is distinguishable from "nothing matched"; (c) the other sources' evidence is kept.
- A source that genuinely returns nothing records no failure. The Gate A log line for an insufficient-evidence refusal now carries `retrieval_failures` for diagnosis. Gate A itself is untouched: a failed source leaves less evidence and Gate A judges what exists exactly as before (tested).

## Tests (`test_ai_search_cold_start_retrieval.py`, 9)
- **Root cause reproduced:** two concurrent operations on one session of a cold pool (real temp SQLite, fresh engine) raise `InvalidRequestError`.
- **Cold-pool first use equals later use:** three fresh engines with a disposed seeding connection (a genuine cold pool each time); events AND news found on the first call, identical across runs, no source failed.
- **No overlap:** an instrumented run shows at most one lookup in flight, in the order events, news, policies.
- **Partial-failure contract:** events succeed + news fails + policies succeed -> events/policies kept, news `[]`, `retrieval_failures == {"news": "RuntimeError"}` and the same in the filter report; a genuinely empty news result reports no failure; all three failing are all recorded; the log carries only source name and exception class (the "secret" in the exception message and the query text never appear); the failure flag does not change the Gate A decision; the pairwise decision engine lookups are sequential.
- **Mutation check:** with the old concurrent `gather` restored, 5 of the 9 tests fail (including the cold-pool first-use test); with the fix restored, 9 pass. So the tests detect the defect, they do not just pass.
- Selection (AI Search / AEV2 / core-answer / page-intelligence / follow-up files): 821 passed, 1 skipped, 2 xfailed, 2 failed (existing live-engine tests) before this file; the new file adds 9 passing.

## Frozen-18 model-free sanity (new process, so the first question hits a cold pool)
Compared with the 3.4G.2 snapshot (same frozen news snapshot): **17 of 18 questions have identical selected evidence; routing, entities, Gate A and model-call population are identical for all 18; index ids equal prompt markers for all 18; no retrieval failure was recorded for any question.**
The one difference is the proof: **CR1**, the first question in every snapshot process, previously returned **zero news**, now returns **two** ("Kotak Mahindra Bank Primed For Next Leg Of Growth As Street Cheers Anup Saha's Elevation" and a bank-stocks wrap), both visible in the prompt with ids N1-N2. The race had been silently dropping CR1's news in every earlier cold run.
Latency: warm collect stays about 170-470 ms (SR2 234-328, MP1 296-469, CR1 172-203); cold first calls are dominated by network (valuation, feeds), not by the serial lookups.

## Correction to earlier conclusions (important)
1. **CR1 was not purely a data gap.** The 3.4F live CR1 run was the first collect in its process and probably lost its news to this race; the 3.4G diagnosis and the 3.4G.1 report said CR1 "cannot improve because the database lacks substantive evidence". The database still has no Kotak results filing or tagged events, but a Kotak growth/outlook article **is** retrievable and now arrives on a cold first call. CR1 should be re-assessed with this fixed before anyone concludes it needs new data.
2. The news-window defect (newest 20 versus 60, fixed in 3.4G.1) is real and separately tested; it is not explained by this race.
3. Any earlier snapshot where the first question showed missing news or events (the 3.4G traces, the 3.4G.1 before/after) carries this confound for that one question.

## Known limits
- Serial execution adds the lookup times together (milliseconds locally). If these ever move to a remote database, per-task sessions would be the better design.
- A failed source is recorded and logged but the answer path does not change: Gate A may still refuse for "insufficient evidence" when the real cause is a retrieval failure. The cause is now visible in the log and the bundle; surfacing it in the public refusal wording is a separate product decision.
- Other concurrent paths using their own sessions (`get_symbol_context`, `get_recent_announcements`) were not changed.

## Verdict
**GREEN.** Cold-process retrieval behaves like warm retrieval; source failures are explicit; partial evidence is preserved; Gate A and the rest of the pipeline are unchanged.

## Next
Per the agreed sequence: one SR2 live call with the current titles-only contract (about 4-5K tokens), after you confirm. CR1 is worth a model-free re-look first, now that its news arrives.
