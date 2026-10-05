# Step 3.4G.1 report: deterministic retrieval ranking

Scope (as approved): candidate universe and deterministic retrieval, filter and ranking only. Not changed: prompts (no sector news block, no summaries), Gate A, Gate B, routing, composition, and the Gate B evidence-corpus invariant (left for the next step). Zero provider calls. Nothing pushed or deployed.

## What changed
Old order: SQL `LIMIT 30` ordered by stored `impact_score` -> filter -> first 10; news scanned from the newest 20 (warm cache) or 60 (cold cache) of the live feed; announcements newest 5/8 by recency.
New order: **wide recency-bounded pool -> the existing eligibility/age/relevance filter (unchanged) -> deterministic question-aware ranking -> bounded selection.**
- **Events:** pool of the newest 600 term-matching rows (topic) or 200 per company (tagged), bounded by recency, not by impact. After filtering, items are ranked and cut to 10. Comparisons are selected per company (5 each) so one side cannot take every slot.
- **News:** the live-feed window is requested explicitly (60) and no longer depends on cache state; matching and filtering run on the whole window; survivors are ranked and cut to 10.
- **Announcements:** a 60-row recency pool, stale rows dropped and counted, then ranked (substantive and question-relevant before administrative recency) into the same budgets (5 single-company general, 8 per company otherwise).
- **Score** (`evidence_ranking.py`, every component recorded in `bundle.rank_trace`, never on the published items): coverage 0.50 (distinct question terms in the title, half weight in the summary), recency 0.25 (linear over the plan's age window), substance 0.15 (administrative < routine corporate action < neutral < results/orders/rates/outlook/collaboration), impact 0.10 (stored `impact_score` as a signal only). Ties break on recency then input order.
- **Diversity:** near-duplicates (title content-word Jaccard >= 0.5, with exchange-filing boilerplate removed so two different filings by one company are not "duplicates") are suppressed and never used to fill leftover budget. The budget is a ceiling, not a quota.
- Pools: events 600/200, news window 60, announcements 60; retrieval ordering by recency is opt-in (`pool_by_recency`), so other callers of the retrieval functions are unchanged.

## Frozen-18 model-free before/after (same frozen live-news snapshot, back to back)
Files: `selection_before.json`, `selection_after.json`, `live_news_snapshot.json`, `comparison.md` (full tables), `frozen18_selection.py`, `compare.py`.

**Invariants (18 of 18 unchanged):** UI mode and specialist, entities, Gate A decision (same 3 refusals: CR2, EI1, EI2), and which questions would call a model.

**Selected evidence counts (events / news / announcements), before > after:**
| Q | Counts | Notes |
|---|---|---|
| CR1 | 0/0/4 > 0/0/2 | the two repeated "General Updates" filings and the two repeated "Investor Presentation" filings each collapse to one; the Investor Presentation (substantive) now ranks above the General Updates filing |
| CR3, EI2, CC1 | news 0 > 1 | one on-topic live item at feed rank 49 ("TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook...") is now reachable; the old 20 window never saw it |
| EI3, SR1 | 8/11/0 > 10/10/0 | topical-tagged items 5 > 10 and 5 > 9; administrative items 1 > 0 |
| SR2 | 8/2/0 > 10/5/0 | topical-tagged items 16 > 22 |
| MP1 | 8/12/0 > 10/10/0 | topical-tagged items 7 > 17 |
| MP3 | 10/5/0 > 10/8/0 | topical 15 > 20 |
| CC2 | 0/2/6 > 0/7/6 | HDFC-side news now reachable (see risks) |
| others | unchanged | |

Duplicates (boilerplate-normalised pairs at Jaccard >= 0.5): CR1 2>0, CC1 1>0, CC3 1>0, MP2 1>0, no increase anywhere. Freshness: median age of selected evidence improved where fresher on-topic items exist (SR1 0.0>1.8 shows the mix, CC1 34>19, CC2 34>0 days); CC3 median rose 48>68 days because the one remaining item is an older announcement (the repeated annual-meeting notice was dropped).

**Targets**
- **SR2:** the strong IT evidence is now in the selected set. News "Indian IT's Q2 earnings dilemma deepens: more deals but weaker growth..." and "TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook..." are selected (they were outside the window or ranked out); "Nifty IT crashes 11% in September" moved from event slot 6 to 3 and is visible. The two news items are selected but **not visible to the model**, because the sector prompt has no news block: that is the next step, not this one. The "IT firms' Q2 reality check" article from the earlier run is not in today's feed snapshot, so it could not be tested.
- **MP1:** RBI and rate evidence now beats the previous off-topic top-30. Selected and visible events: "RBI MPC Meeting October 2026", "RBI MPC may hike repo rate next week", "RBI rate hike expected in October? What it means for Sensex, Nifty", "WACR tops repo rate for first time in nearly 2 months". 18 topical items that previously sat beyond rank 30 are now in the pool; topical-tagged items in the bundle 7 > 17. **Not solved:** these are about a *hike* (October MPC bets), the question asks about a *cut*, and evidence on how a cut reaches bank margins and deposit rates still does not exist in the data; the historical-precedent context (near-tied, titleless) is unchanged. Retrieval ranking cannot supply that.
- **CR1:** unchanged in substance, as expected. Retrieval cannot create results evidence the database lacks; the answer set is now two distinct filings instead of four with repeats, which makes the weakness plainer.

**Displaced items:** for EI3, SR1, MP1, MP3 the "topical" items displaced were mostly rupee and forex stories replaced by more relevant rate or IT items; for MP3 they were replaced by other rupee items ("Rupee strengthens...", "RBI intervention, dollar flows push rupee to two-month peak") but "India's forex reserves fall $18.3 bn as RBI steps in to defend rupee" left the selection, a relevant item for a weaker-rupee question. Full list at the bottom of `comparison.md`. No previously useful item was lost for SR2, CR1, CC1, CC2, CC3.

**Cost:** warm `evidence.collect` is about 170-310 ms for the three traced questions (earlier artifacts: 484 ms and 1,891 ms); the larger pools did not show up as latency.

## Tests
- New `test_ai_search_evidence_ranking.py`: 21 tests: score components and weights; coverage, recency and substance; near-duplicate suppression (never fills leftover budget); boilerplate-aware duplicate key; deterministic tie-breaks; **filter before limit** (40 high-impact filings do not displace four lower-impact on-topic events); relevance beats stored impact for a rate question; budgets; per-company comparison selection; **warm and cold cache give the same news candidates** (on-topic items beyond the newest 20 are found either way); announcements (substantive over newer administrative, repeats collapse, stale dropped and counted, budget); the event pool is ordered by recency and not by impact; ranking details never appear on published items.
- Two existing retrieval-stub signatures updated to the new keyword arguments (assertions unchanged); `filter_bundle` tolerates the minimal stand-in bundles older tests use.
- AI Search / AEV2 / core-answer / page-intelligence selection: **804 passed, 1 skipped, 2 xfailed, 2 failed**; the 2 are the existing `test_ai_search_engines_live.py` live tests.

## Known limitations and risks (not hidden)
1. **Weights are hand-set** (0.50/0.25/0.15/0.10), explainable but not tuned on outcomes. Stored `impact_score` is 0 on most RSS-derived events, so the impact component barely acts.
2. **Sector vocabulary is broad:** "bank", "credit", "loan" match single-bank stories, so MP1's news slots include "Kotak ... Primed For Next Leg Of Growth" and the HDFC CEO items. They are bank-related but not about the rate-cut transmission.
3. **News is not balanced per company in comparisons** (events and announcements are): CC2's news is HDFC-heavy.
4. Dedup is lexical; templated headlines can collapse more than intended, near-paraphrases with different words will not.
5. The live-news snapshot makes before/after comparable but only covers one moment of the feed.
6. Gate B's evidence corpus still includes items the model never saw (deliberately left for the next step).

## Verdict
**GREEN for the retrieval layer:** selection improved on SR2 and MP1 where evidence existed, nothing regressed in route, entities or Gate A across the frozen 18, duplicates fell, and the news window is state-independent. It did not, and cannot, fix CR1's missing evidence or MP1's missing transmission evidence.

## Next (3.4G.2 presentation alignment, not started)
Add the news block to the sector prompt, make index ids exist only for prompt-visible items (so the model and Gate B see the same evidence), and consider per-company news balance for comparisons. No live calls until then; about 52K OpenAI tokens remain.
