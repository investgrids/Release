# Step 2 notes (read with STEP2_COMPARISON.md)

Branch `release/ai-answer-v2`. Nothing deployed, nothing pushed, not release ready. Answer quality is UNVERIFIED: every model provider was exhausted locally, so no live answer exists for any of the 18 questions.

## What changed
1. **Entity grounding** (`entities.py`, `session_context.py`): suffix-free company aliases ("Kotak Mahindra Bank", "3M India") used for matching and stripping; common-word aliases ("oil") need the capitalised ticker; "it" is the IT sector only as "IT" or before a sector noun; "banks" tags the banking sector; "MarketRipple" is product vocabulary; fuzzy n-grams may not start or end with a function word; "Indian" is treated as an adjective only before a market/sector noun; pronoun questions that already name their subject ("...how should I read it?") are no longer "follow-ups".
2. **Retrieval by question type** (`evidence_filter.py`, `evidence.py`, `retrieval.py`): comparison, company, explanation, topic plans. Comparisons fetch events per company, announcements and valuation for each. Explanations fetch no company/event/news/policy data. Topic questions search by the named sector's / policy's / macro vocabulary, not raw words. Age windows and relevance checks run before evidence reaches the prompt or response; a filter can only remove items.
3. **Degraded copy** (`pipeline.py`, `specialists/base.py`): the summary describes only the events actually displayed.
4. `regexes.py`: the sector trigger accepts "sectors"/"industries" (SR3 "Which sectors...").

## Honest limitations (confirmed in the rerun data)
- Relevance is still lexical. SR2 keeps a "Tera Software" filing because "software" is a sector term; MP1 keeps an RBI crypto item and a "Credit Risk-o-Meter" item because "rbi"/"credit" are topic terms. CR1's single news item is a Kotak Institutional Equities research note matched on the alias "kotak", not news about the bank.
- Event.sectors tags are not used: they are model-assigned and unreliable (an RBI crypto article carries "IT"; a newspaper-publication notice carries Banking, IT, Pharma, Auto, FMCG).
- Evidence PASS still means the minimum bar was met, not that the evidence is good. EI1 (BEL) and CR2 (3M India) now have NO evidence inside the age window: honest, but it means an empty evidence set for those questions.
- Route: MP2 (crude oil) and MP3 (rupee) still resolve to `direct_company_research`, not `policy_macro_impact`: the ui_mode classifier only assigns that mode when a named policy is present, and the product's `policy_macro_impact` layout is a not-yet-supported mode. Left alone on purpose (out of scope).
- Degraded answers display events only. Announcements and valuation are retrieved for comparisons but the degraded shape does not show them, so the copy says nothing about them. That is accurate, not complete.
- Cost: comparisons retrieve about 1 s longer (valuation for each company plus announcements); MP1 about 3 s (macro indices) now that it is no longer short-circuited.
- `addresses_question` moved from 4F/14U to 0F/18U only because the four short-circuit responses (clarification / unsupported) are now capacity-degraded responses. That is not an improvement or a regression in answer quality.

## Scoring-rule changes (applied identically to both runs)
`build_report.py` gained data-driven rules for CR2, SR3, MP1, MP3, per-company coverage by events or announcements for comparisons, and a policies check. The baseline data was re-scored with them and no status changed (checked check by check); the committed baseline `results_matrix.*` is untouched. The scripts gained a `BASELINE_OUT_DIR` option so a rerun cannot overwrite the baseline.

## Tests
- Same 496-test selection: 496 passed, 1 skipped, 2 xfailed (identical to baseline).
- New: 69 tests (`test_ai_search_entity_grounding.py`, `test_ai_search_evidence_routing.py`), each failure case individually plus positive controls (Indian Hotels, Indian Bank, Indian Oil, Oil India, Tech Mahindra with M&M, Kotak with M&M, "Compare with Indian" still asks, bare "Tata" still asks, misspellings still match, IT written as a sector still matches).
- 23 related files outside the 496: 196 passed, 12 failed. The same 12 fail with this patch set aside (live-provider and network tests: `*_live`), so they are pre-existing.
