# Step 3.4G report: evidence-usefulness diagnosis for CR1, SR2 and MP1

Zero provider calls (the model call was replaced by a recorder; it stayed at 0). Gate A/B, prompts, retrieval and ranking are unchanged: this step only observes. Script and data: `evidence_trace.py`, `evidence_trace.json` (every item that exists upstream, with its full journey). Nothing pushed or deployed.

Method: for each question the real `evidence.collect` ran, the real specialist prompt was built and searched, and every candidate in the retrieval universe was pushed through the **real** `filter_bundle` one item at a time. Each item records: exists upstream, retrieval rank and whether it fell inside the retrieval limit, filter verdict with reason, bundle rank, index id, **whether it is visible in the prompt and where**, semantic tags (administrative / operating-result / outlook-demand / rate-policy / tips), and whether the previous live answer used it. Caveat: the universe is today's live data; item sets differ slightly from the earlier live runs, and "previous answer used" is matched by title.

## Mechanisms found (apply to all three, so the fixes generalise)
1. **Event retrieval ranks by a stored `impact_score` and cuts at SQL `LIMIT 30` BEFORE filtering and before any question-aware ranking.** In topic questions most of the 30 slots go to single-company filings that the filter then drops (SR2: 21 of 30; MP1: 6 filings, 12 irrelevant and 4 stale among the top 30, leaving 8). Items that would survive the filter and are on-topic sit beyond rank 30 and are never considered (MP1: 48 kept items beyond rank 30, 18 of them topical).
2. **News is scanned from the newest 20 items of the live feed (when the feed cache is warm), sorted by recency only, before relevance matching.** On a cold cache `get_live_news` returns all 60 cached items and ignores its `limit`, so the candidate window itself is 20 or 60 depending on cache state. On-topic items sit beyond the 20 window (SR2: the Accenture/IT-outlook article at live rank 49; MP1: 11 kept bank and rate items beyond the window).
3. **Announcements are fetched by recency only, newest 5 (single-company general questions) or 8, with no category ranking.** Kotak has only 4 announcement rows in the database at all, none a results/financials filing.
4. **The index is larger than what the model sees.** The prompt lists `events[:5]` and `news[:5]` (company specialist), `events[:6]` and **no news block at all** (sector specialist), `events[:4]`/`news[:4]` (comparison). The evidence index, and the corpus Gate B uses to check figures, include items the model never saw (SR2: E7, E8, N1-N3; MP1: E6-E8, N6-N11). Prompts also show only titles/headlines, never summaries.
5. **Gate A "sufficient" means "company-specific and not matched by the administrative regex", not "substantive".**

## CR1 (Kotak outlook): grounded but thin
| Item | Upstream | Retrieved | Filter | Bundle / index | In prompt | Used before | Tags |
|---|---|---|---|---|---|---|---|
| Announcement "General Updates" (24 Aug) | yes | rank 1 of 4 | kept | A1 | yes | **yes** | administrative |
| Announcement "General Updates" (18 Aug) | yes | rank 2 | kept | (deduped) | yes | yes | administrative |
| Announcement "Investor Presentation" (17 Aug, content-free title) | yes | rank 3 | kept | A2 | yes | no | none (looks substantive to Gate A) |
| Announcement "...about Investor Presentation" (17 Aug) | yes | rank 4 | kept | A3 | yes | yes | none |
| Events tagged to Kotak | **0 in the database** | n/a | n/a | n/a | n/a | n/a | n/a |
| Operating-results / financial filing | **not in the universe** | n/a | n/a | n/a | n/a | n/a | n/a |
| Live news "Kotak Mahindra Bank Primed For Next Leg Of Growth..." | yes (today), live-feed rank 37 | only on a cold cache (60 window) | kept | N2 today | yes | n/a (the live run had 0 news) | outlook |
- **What Gate A saw:** the saved run's only company evidence was the two Investor Presentation titles (plus admin filings and a "no_signal" development-memory line). `is_administrative` does not match "Investor Presentation", and a title carrying no content cannot be judged substantive, so it counted. That is the semantic mismatch: Gate A tests exclusion of known-administrative patterns, not presence of substance. It originates in `_company_items` (evidence_sufficiency), fed by `get_recent_announcements` recency order.
- **Why the answer was thin:** the retrieval universe at the time held nothing substantive (no tagged events, no news in the window, no results filing). The model then cited the first-listed filing and the "no_signal" memory line. Classification: **Retrieval/universe (primary), Gate A substance test (secondary), Composition (minor: it cited the weakest items)**. Today's live feed does hold a Kotak growth article, but it is only reachable when the live-feed cache is cold: consistent with, not proof of, the earlier miss.

## SR2 (IT sector outlook): grounded but thin, leaning useful
| Item | Retrieved (rank by impact) | Filter | Bundle / index | In prompt | Used before | Tags |
|---|---|---|---|---|---|---|
| "TCS, Infosys, Wipro shares ahead of Q2 results... Accenture..." | 5 | kept | E1 | yes | yes | operating, outlook |
| "IT Q2 Results Dates: ... Report FY27 Earnings" | 7 | kept | E2 | yes | no | operating |
| "Accenture Shares Jump Record 22%..." | 9 | kept | E3 | yes | no | operating, outlook |
| "Infosys, Wipro ADRs jump up to 10% after Accenture Q4..." | 10 | kept | E4 | yes | **yes** | operating, outlook |
| "Infosys, Wipro ADRs Spike Over 8%..." | 11 | kept | E5 | yes | no | operating, outlook |
| "**Nifty IT crashes 11% in September**..." | 12 | kept | **E6, last visible slot** | yes | **no** | operating, outlook |
| ADRs soar / Nifty IT jumps 2% | 13, 15 | kept | E7, E8 | **no (cut by events[:6])** | no | operating, outlook |
| News "IT firms' Q2 reality check: growth recovery still out of sight" | live feed | kept | N-slot | **no: sector prompt has no news block** | no | outlook |
| News "Indian IT's Q2 earnings dilemma deepens: more deals but weaker growth..." | 20 | kept | N2 | **no** | no | operating, outlook |
| News "TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook..." | live rank 49 | would be kept | not retrieved (beyond the window) | no | no | operating, outlook |
| 21 single-company filings (Tera, Wipro, HCL, ...) | ranks 1-30 | dropped | n/a | no | no | none |
- The evidence the user would want (the September 11% fall, weak-growth news) **was retrieved or visible in part, but** the weak-growth articles were retrieved and then **never shown**: the sector prompt contains no news block. Only events[:6] reached the model, and those are dominated by one Accenture read-through cluster (E1-E5), because events are ranked by `impact_score`, not by recency, diversity or question usefulness. The 11% fall was visible at the last slot and not used.
- Classification: **Representation/selection (primary: news invisible to the sector specialist; events[:6] by impact, one-cluster dominance), Retrieval (secondary: news window, LIMIT 30 before filter), Composition (the model did not use the visible 11% title)**.

## MP1 (repo-rate cut and banks): grounded but thin
- **Strong evidence exists but was not retrieved.** The universe holds 22 rate-policy items, all passing the filter, including "RBI MPC Meeting October 2026: Repo rate hike soon?" (rank 97), "RBI MPC may hike repo rate next week" (98), "Global bond rout ... before RBI policy" (162), "RBI rate hike expected in October? What it means for Sensex, Nifty" (211). The 30 retrieved were ranked 1-30 by `impact_score`: crypto remarks, Sebi credit-risk meter, FCNR swaps, a Reg-30 filing, rupee articles, a Fed task-force item. None is about the repo rate or bank transmission.
- **What does not exist:** the universe has essentially no item on how a cut transmits to banks (net interest margin, deposit and lending rates, treasury gains). Repo-related bank items are single-company MCLR filings (dropped). The only transmission-type content is the five **historical precedents** (context line C2), all at about 33% similarity with no titles recorded.
- **Composition:** the model chose the emergency (COVID, Mar 2020) cut over the more analogous "surprise cut between meetings (2015)" and "begins cut cycle (2019)" in the same list; the five precedents are near-tied (33.6, 33.1 x4), so selection among them is arbitrary. The current evidence also says markets are pricing a **hike**, which the model did not reconcile with a cut hypothetical.
- Routing: MP1 goes to the company specialist (expected sector); known, not touched.
- Classification: **Retrieval/ranking (primary: impact_score ordering with LIMIT 30 before relevance), Universe gap (transmission evidence absent), Composition (arbitrary precedent among near-ties), Routing (known debt)**.

## Evidence-budget pressure (summary)
| Stage | Cap | Effect observed |
|---|---|---|
| Event retrieval | SQL `LIMIT 30`, ordered by `impact_score`, before filtering | SR2: 21/30 slots are filings dropped later; MP1: 8/30 survive and the on-topic items rank 84-483 |
| Event bundle | 10 | not binding here |
| News candidate window | newest 20 of 60 (warm) or 60 (cold) | on-topic items beyond rank 20 are invisible (SR2 rank 49; MP1 11 items) |
| Announcements | newest 5 or 8, no category ranking | CR1 gets 4 admin/presentation rows |
| Prompt events / news | 5/5 company, 6/**0** sector, 4/4 comparison | index ids exist for items the model never saw |
| Prompt content | titles only, no summaries | the model reasons from headlines |

## Decision (diagnosis only, nothing implemented)
Earliest demonstrated layer is **candidate selection before the cut**: all three questions lose their strongest or most diverse evidence to `impact_score` ordering with a hard `LIMIT` ahead of any question-aware ranking, plus a news window that depends on cache state. Recommended fix order, each generalising beyond these questions:
1. **Retrieval ranking (earliest):** widen the candidate pool, then rank deterministically with generic semantic signals before cutting: filter first (so filings/tips/stale items do not consume slots), then score by title/summary term coverage, recency within the age window, administrative-versus-substantive tag, and source diversity (avoid one cluster filling every slot). Use the same scoring for events and for the news window (stop slicing the live feed to 20 before matching; make the window independent of cache state).
2. **Presentation:** make the prompt show what the index claims: add the news block to the sector specialist, and make index ids exist only for prompt-visible items so the model and Gate B see the same evidence.
3. **Gate A substance (after retrieval):** require an affirmative substantive signal rather than only non-administrative, for example a results/earnings/outlook signal in the title or description. Content-free titles ("Investor Presentation") need the description or must not count. This changes sufficiency semantics, so decide after (1), when more real evidence may make it unnecessary.
4. **Composition (last):** only if strong, visible, well-ranked evidence is still ignored after 1-3. Not warranted by this diagnosis for CR1 or MP1; SR2's single un-used visible item (the 11% fall) is a weak signal.
5. **Universe gaps (data, not code):** no Kotak results filings or tagged events; no bank-transmission evidence for rate moves; historical precedents lack titles. These are ingestion/memory work, separate.

Then: implement only (1), model-free, test across the frozen 18 (Gate A/B frozen), and only then decide whether a small live qualification is warranted. The remaining OpenAI quota (about 52K tokens) was not touched.
