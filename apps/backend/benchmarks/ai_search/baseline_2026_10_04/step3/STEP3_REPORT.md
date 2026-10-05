# Step 3: live-answer validation gate, result: PROVIDER-CAPACITY BLOCKER

Code under test: `release/ai-answer-v2` at 4abf77f (Step 2) with the Step 3 gate at 0152817. Nothing deployed, nothing pushed. Answer quality is **neither passed nor failed**: 0 of 18 real answers exist.

## Run reconciliation
| | Run 1 | Run 2 |
|---|---|---|
| Questions attempted | 18 | 18 |
| Cap / pipeline-level model calls made | 40 / 6 | 34 / 6 |
| Successful model calls | 1 (CR1 market-pulse classifier, 5-token request) | 1 (same) |
| Successful answers | 0 | 0 |
| Capacity-degraded questions | 18 | 18 |
| Skipped by the circuit breaker (after 3 consecutive capacity failures) | 15 | 15 |
| Unused call budget | 34 | 28 |

Combined: 12 of 40 harness calls used, 28 unused. A separate 5-token probe before run 1 also succeeded; it says nothing about full-answer capacity. Every specialist call failed within about 3 s; the classifier succeeded only for the tiny request. Groq answered with 12-18 minute cooldowns even right after run 2's 14-minute wait, and OpenRouter's free models were capped for the day. Cause is not established (daily/token quota vs. request size is a hypothesis). A failing question cost 35-36 s and 2 calls (CR1) before the circuit opened. Run 2 was not rerun and no provider was added.

## Answer-level matrix (per question type, P/F/U out of 3)
Every check, every type: 0 / 0 / 3 (directness, factual claims, numbers, citations, source freshness, score/rank, insufficient-evidence honesty). Totals 0P / 0F / 18U per check. Per-question reasons: `manual_review.json`; matrix: `step3_matrix.csv`.

## Lexical traps and honest-insufficiency cases (retrieval side only, from the saved evidence snapshots)
- **Tera Software (SR2):** two Tera Software filings (11 Aug, 54 days old) are still in the bundle the model would receive, beside legitimate sector items. Whether an answer uses them for a sector claim is UNVERIFIED. The gate's checker flags exactly that (fixture-proven).
- **Kotak research note (CR1):** not in this run's bundle (live news changed); CR1 holds four Kotak Mahindra Bank announcements under its registered name. The trap was not exercised in this run, so it is UNVERIFIED, not cleared.
- **3M India (CR2):** bundle empty, nothing invented by retrieval. Whether the answer says "insufficient recent evidence" is UNVERIFIED.
- **BEL (EI1):** NOT empty. Its only item is a "Top 3 stocks to buy: HDFC Bank, Infosys, BEL" article that mentions BEL and says nothing about an order. Nothing in the bundle supports "just won a new defence order". The gate's honesty check applies only to an empty bundle (`evidence_total == 0`), so it would not run for this case. A gap in the gate's definition, noted and not changed in this baseline.

## Three highest-priority confirmed defects
1. **No answer can currently be produced by the configured chain** (0 of 36 question attempts; specialist calls failing in ~3 s); a failing query burns 2 model calls and up to 36 s. Production capacity is not established by this run.
2. **Retrieval still hands the model evidence that cannot support the claims it will be asked to make:** Tera Software filings for a sector question (SR2) and a stock-tips article as the only BEL evidence (EI1). Confirmed in saved bundles; the age filter was not loosened.
3. **The response contract has no claim-level attribution.** `source_attribution` is the whole bundle, `citations` are news source names, so no citation can be tied to a claim. The gate approximates support lexically; per-claim citation correctness cannot be verified by design (`claim_level_attribution_available: False`).

## Deferred
OpenAI integration (a harness could test answer design, not the production provider chain), Step 4, any release decision. The pasted key was not used. Rotate it.
