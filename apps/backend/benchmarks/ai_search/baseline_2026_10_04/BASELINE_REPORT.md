# AI Search & Answer: Step 1 baseline (2026-10-04)

Code under test: `release/ai-answer-v2` @ 4022524 in `D:\IG` (`run_ai_search_v3` + `finalize_v3_response`, AEV2 mode off). This is **not** `origin/main`: the AI Search track (response_finalize, answer_availability, safety gate, ui_mode, AEV2) lives only on this branch, 35 commits ahead of the merge base. Local dev DB (data current to 2026-10-04). Nothing deployed, nothing written to production, no production search was run.

Files in this folder: `questions.json` (frozen set and expectations), `stage1_deterministic.py`, `stage2_live.py`, `build_report.py` (rules), `stage1_results.json`, `stage2_results.json`, `results_matrix.csv/json`.

## What was and was not run
- **Stage 1 (real pipeline, specialist model call stubbed):** all 18 ran. Intent, entities, routing, ui_mode and evidence retrieval are the production code. Not fully model-free: the pipeline's own market-pulse classifier makes one model call per non-regex query. Those attempts all failed (429/exhausted).
- **Stage 2 (real pipeline + finalizer, capped at 30 model calls, circuit breaker after 3 consecutive capacity failures):** 18 ran, 6 model calls were made (classifier + specialist for CR1-CR3), **all 6 failed**, the breaker opened, the rest were skipped. **No synthesized answer exists for any question.** Local provider chain is exhausted (`all_providers_failed exhausted_count=9`). Zero paid calls, zero successful calls. All answer-level checks are therefore UNVERIFIED, not passed.
- Existing assets reused: 496 AI Search tests pass on this branch (1 skipped, 2 xfailed, both documented gaps); the 200-question golden run from Aug 2026 (older code, used only as supporting trace); a 20-minute production log sample (providers working there: Gemini 86 successes vs 9 total failures; not search-specific).

## Results by question type (P/F/U out of 3)
| Type | Route | Entities | Evidence | Addresses question | Numbers / citations / score consistency | Degraded honesty | Degraded copy vs evidence |
|---|---|---|---|---|---|---|---|
| Company research | 3/0/0 | 1/2/0 | 1/2/0 | 0/0/3 | 0/0/3 | 3/0/0 | 1/2/0 |
| Event impact | 3/0/0 | 3/0/0 | 3/0/0 | 0/0/3 | 0/0/3 | 3/0/0 | 2/1/0 |
| Sector research | 2/1/0 | 3/0/0 | 2/1/0 | 0/0/3 | 0/0/3 | 3/0/0 | 0/3/0 |
| Macro / policy | 0/3/0 | 0/3/0 | 1/2/0 | 0/2/1 | 0/0/3 | 3/0/0 | 0/1/2 |
| Company comparison | 3/0/0 | 3/0/0 | 0/3/0 | 0/0/3 | 0/0/3 | 3/0/0 | 3/0/0 |
| General explanation | 1/2/0 | 0/3/0 | 1/2/0 | 0/2/1 | 0/0/3 | 3/0/0 | 0/1/2 |
| **Total (18)** | 12/6/0 | 10/8/0 | 8/10/0 | 0/4/14 | 0/0/18 | 18/0/0 | 6/8/4 |

PASS on Evidence means the minimum bar was met, not that the evidence is good: SR1 and SR2 have only 1 of 10 events on topic; EI1, EI2, CR3 rest on a single company event that is 85-88 days old. Degraded honesty is the one strong result: all 18 degraded responses carry no fabricated verdict, confidence, companies or picks. Per-question detail: `results_matrix.csv`.

Per question (route / entities / evidence): CR1 P/F/F, CR2 P/F/F, CR3 P/P/P, EI1-EI3 P/P/P (EI3 uses the sector specialist; ui_mode is correct), SR1 P/P/P, SR2 P/P/P, SR3 F/P/F, MP1 F/F/F, MP2 F/F/P, MP3 F/F/F, CC1-CC3 P/P/F, GE1 P/F/P, GE2 F/F/F, GE3 F/F/F.

Latency, state and calls: failing a query costs 13.3 s (CR1) and 19.4 s (CR2) with 2 model calls each (classifier then specialist, both walking the whole provider chain); once providers were marked exhausted, degraded answers returned in 0.2-2.6 s. In stage 1 (specialist stubbed) retrieval took 0.02-2.7 s per question once the cooldown skipped the classifier; the first two questions took 10.5 s and 22.7 s because the failing classifier call alone walked the provider chain. Minimum model calls per fresh answer is 2 for any query the market-pulse regex does not catch.

## Five most consequential failures (all confirmed unless marked)
1. **Entity resolution picks the wrong company or refuses valid questions (8 of 18 fail).** "How is 3M India doing" resolves to BANKINDIA and is grounded in Bank of India announcements (CR2). "Outlook for Kotak Mahindra Bank" also resolves M&M (CR1). "Crude oil" resolves to Oil India (MP2). "...how should I read **it**" resolves the IT sector (GE1). Any query containing the word "Indian" is short-circuited to a company-picker ("Indian Railway Finance Corporation, Indian Renewable Energy...") including the required RBI rate-cut question (MP1), the rupee question (MP3) and FII selling (GE2). "How does the MarketRipple Score work?" is rejected as an unlisted company (GE3). Corroborated by the Aug golden run: wrong company detection 21.1%, sector detection accuracy 19.6% (older code).
2. **Retrieval returns little relevant or fresh evidence.** Events are ordered by impact score, not date. TCS vs Infosys gets 1 event (85.6 days old) and no valuation; the valuation fetch never fired for any of the 14 questions that reached retrieval, including both comparisons. Comparisons skip announcements and company context by code (`intent == general and one company`), although 2 TCS announcements dated 2026-10-01 exist (CR3 retrieved them). Kotak gets zero Kotak-linked events or news; its evidence is other banks' filings (an ICICI Bank filing, RBI items). SR3 retrieves no sector rows at all.
3. **Stale specific numbers sit in the evidence with no recency control.** CC2's only event is "RBI holds repo rate at 6.5% for seventh consecutive meeting", 107.6 days old, while current news in the same bundle discusses a possible hike. EI1 ("BEL just won a new order") is grounded only in "Defence capital expenditure raised by Rs. 45,000 Cr", 87.6 days old. Whether answers then repeat these numbers is **hypothesis** (no live answer to inspect).
4. **Degraded answers promise evidence they do not show.** The copy says "the underlying event and news data is available below", but in 8 of the 14 capacity-degraded answers nothing is shown and `answer_availability.evidence_count` is 0 although 18-23 events, news and policy items were retrieved (news is always empty in the degraded shape; events are shown only if tagged to a resolved company). With wrong entities (failure 1) the tagged-only filter also hides everything.
5. **AI Search is disconnected from the MarketRipple Score and gives every question a verdict.** No file in the AI Search package references the score (confirmed by search), so it cannot agree or disagree with the bank scores released today (Kotak 47.7, HDFC 46.2). Educational and macro questions go through the company specialist with an investment verdict: in the Aug golden run "Explain repo rate in simple terms" returned a "Cautious" rating at 51.2% confidence, and three different macro questions returned the identical 51.2% and identical freshness (older code, **hypothesis** for the current branch).

## Three smallest fixes to make next (not started)
1. **Entity guard** in `entities.py` / `session_context._group_prefixes`: add a stoplist for generic words ("Indian", "India" as a bare prefix), match "it" only when uppercase "IT", require a legal-name or symbol match for short names (OIL, "3M India" vs Bank of India), exempt "MarketRipple" as a product term. Test with the 8 failing questions above.
2. **Evidence recency and coverage** in `retrieval.py` / `evidence.collect`: order company-tagged events by date within the tagged set, drop or flag items older than a set age for "latest/just/outlook" questions, and fetch announcements and valuation for every resolved company (comparisons included).
3. **Degraded response surface** in `_build_degraded_response` / `specialists/base.py`: show the retrieved news and policies (or change the "available below" copy when none are shown) and derive `evidence_count` from what was retrieved; also skip the market-pulse classifier call when the company or sector route is already certain.

## Confirmed vs hypotheses
- Confirmed (code plus run): routes and entities for all 18; evidence counts, dates and relevance for the 14 that retrieved; degraded-shape behavior; classifier call per query; absence of score references; retrieval ordering.
- Hypotheses (need live answers): whether answers repeat stale numbers, whether answers address the question, unsupported numbers, citation correctness, rating vs score disagreement, verdicts on educational questions in current code.
- Limits: the local DB is a dev copy, so evidence counts can differ in production; the model chain was exhausted locally, so no answer-level check could be run; the 8 failing-entity cases are deterministic and do not depend on the model.
