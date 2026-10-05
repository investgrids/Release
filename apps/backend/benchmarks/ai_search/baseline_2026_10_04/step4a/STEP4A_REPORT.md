# Step 4A report: MP2/MP3 macro routing

Zero provider calls. No Gate A/B, retrieval, latency, prompt or provider change. Local commit only; nothing pushed or deployed.

## Before
Frozen-18 routing (real entity extraction, intent, `_route_specialist`, `classify_ui_mode`): 14 of 18 matched. Mismatches: MP1, MP2, MP3, EI3.
| Q | Expected (specialist, ui_mode) | Got before |
|---|---|---|
| MP2 "How would higher crude oil prices affect Indian markets?" | company, policy_macro_impact | company, **direct_company_research** |
| MP3 "How would a weaker rupee affect Indian IT exporters?" | sector, policy_macro_impact | **company, direct_company_research** (sector `it` was resolved) |
| MP1 "...if the RBI cuts the repo rate?" | sector, policy_macro_impact | **company**, policy_macro_impact |

## Earliest deterministic causes
1. `classify_ui_mode` reached `policy_macro_impact` only through a resolved **policy entity** (RBI, repo rate). A macro driver such as crude oil or the rupee produced no entity, so MP2 and MP3 fell through to the default.
2. `_route_specialist` sent a question to the sector specialist only if it contained the **literal word** "sector" or "industry". MP3 and MP1 resolve a sector (`it`, `banking`) but never say the word, so they went to the company specialist.
Gate A is keyed on the evidence plan and its own macro vocabulary, not on the specialist or ui_mode, so neither cause was in Gate A and its decisions did not change.

## Fix (three small pieces)
- New `macro_drivers.py`: deterministic detector. A question is a macro-driver question only if it names a driver (crude oil / Brent / oil prices; the rupee / USDINR / a stronger dollar) **and** asks for an effect (an impact verb or "what happens to/if"). Educational or mention-only questions do not match. Sector-discovery questions ("Which sectors benefit from lower crude prices?") are excluded, because they are sector-theme research.
- `classify_ui_mode`: a macro driver with **no resolved company** is `policy_macro_impact`. The no-company condition matters: that mode also unlocks the market-wide engine verdict, which must never appear next to a company answer.
- `_route_specialist`: with no company, a resolved sector plus a policy or macro driver routes to the sector specialist, as the literal word "sector" already did.

## After
Frozen-18 routing: **17 of 18 match**. MP1, MP2 and MP3 now match; EI3 is the only mismatch and is unchanged (its recorded expectation says company, the code has always routed it to sector; pinned in the tests, not part of this step).
Frozen-18 deterministic qualification through the real pipeline (specialists stubbed, **provider calls made: 0**), compared with the Step 3 matrix: no Gate A decision or outcome changed for any question. Only live evidence counts (the feeds moved), timings and the MP routing fields differ. MP1/MP2/MP3: Gate A `SUFFICIENT / macro_transmission`, as before.

## Tests (`test_ai_search_macro_routing.py`, 60 tests)
Frozen-18 route for every question; MP1 to MP3 entities unchanged; the two target questions; a resolved company (Reliance, Infosys and TCS, "buy TCS if the rupee weakens") keeps the question a company question, including when a sector word or a sector plus driver is present; comparisons stay comparisons; educational and mention-only questions ("What is crude oil?", "What is the rupee?", "Crude oil price today", the GE questions, FII) are untouched; a resolved sector with no trigger or driver ("Why are banking stocks down today?") routes as before; driver detection and word boundaries; sector-discovery questions; the comparison and news-reaction priorities; routing never rewrites the entities.
Mutation checks: dropping the no-company guard in ui_mode (2 fail), dropping the sector-plus-driver route (5), dropping the impact-verb requirement (5), letting the sector route ignore a resolved company (2).

## A regression I introduced and fixed
The first version made "Which sectors benefit from lower crude prices?" a macro question, and the existing `test_ui_mode.py::test_sector_theme_research` failed. Discovery questions are now excluded in the detector and pinned by new tests; that test passes.

## Results
AI Search, deadline, news, macro-wait and ui_mode selection: **831 passed, 3 xfailed, 12 deselected** (the live-engine file). Routing/intent/entities selection across the repository: 277 passed, 1 failed, the failure being `test_p5_stage2_v3_live.py::test_multi_compare_3plus_entities_v3`, a live test that fails identically at d7c0d9f. Other known pre-existing failures are unchanged and listed in the Step 3 report.

## Observations, not fixed (outside 4A)
- MP3 now uses the sector specialist, but evidence collection still fetches live sector rows only when the literal word "sector" is present, so MP3's sector prompt has no sector-row block. That is retrieval, which is frozen; Gate A for MP3 is unchanged.
- `policy_macro_impact` makes the market-wide engine verdict public (the 3.4D-2.1 rule). MP1 already had this with a sector entity; MP3 now shares it. It is the frozen expectation, but it is a product question whether a sector-scoped macro answer should show a market-wide verdict.
- Drivers not in the table (inflation, interest rates, FII flows) are unchanged: "How would inflation affect Indian markets?" still routes to direct_company_research. Add a row to `macro_drivers._DRIVERS` when wanted.
- "Crude oil spiked 5% - what is the impact on markets?" now routes as a macro question; its premise handling is the existing, separate premise check.
- MP1's evidence (transmission) remains unresolved as before; only its routing changed.

## Next
Step 4B: GE1/GE2/GE3 educational and product contract.
