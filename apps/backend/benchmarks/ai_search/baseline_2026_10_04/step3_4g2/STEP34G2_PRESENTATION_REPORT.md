# Step 3.4G.2 report: presentation alignment (sector news visible; authorization corpus = model-visible evidence)

Scope as approved: two changes only. No ranking, budget, summary, Gate A, Gate B logic, routing or composition change; no per-company news balancing; MP1 left as it is. Zero provider calls. Nothing pushed or deployed.

## Invariant now enforced
**retrieved ⊃ selected ⊃ model-visible = claim-authorizable.** Internal traces (`rank_trace`, `filter_report`) keep everything; public authorization does not.

## What changed
1. **The sector specialist now shows the selected news** (`Related market news headlines (real, retrieved)`), the same bounded set and format the company specialist uses (first 5 of the ranked news, ids `N1..N5`). Budgets and ranking are unchanged.
2. **One source of truth for visibility:** `PROMPT_VISIBLE` in `evidence.py` (company: 5 events, 5 news, 3 policies; sector: 6, 5, 4; comparison, pairwise and multi: 4, 4, 0). The prompt builders slice with it, and so do:
   - `EvidenceBundle.index()`: only items the prompt renders get an `E/N/P` id (announcements stay `A1..A8` and context lines `C*`, which the prompt already rendered in full);
   - **Gate B's figure/date corpus** (`answer_authorization.evidence_corpus` -> `EvidenceBundle.visible_text()`): only what the prompt shows: titles and headlines, the event category and score, the announcement block with its dates, every context line, and the live sector rows for the sector prompt. **Summaries and item dates the prompt omits no longer ground anything**, nor do hidden ranked items, the full valuation JSON, macro-index highs, lows and charts, or VIX.
3. The pipeline sets `evidence.prompt_kind = specialist_kind` right after routing. A bundle with no `prompt_kind` (tests, offline tools) keeps the legacy internal corpus; production always sets it (tested).

## Frozen-18 model-free (same snapshot), compared with 3.4G.1
`selection_after_g2.json`. **Unchanged for all 18:** UI mode, specialist, entities, Gate A decision and model-call population. **Alignment holds for all 18 real prompts:** the set of ids in the evidence index equals the set of `[E#]/[N#]/[P#]/[A#]/[C#]` markers in the prompt, in both directions (0 index-only, 0 prompt-only ids).
- **SR2:** selected news is now in the actual sector prompt: all 5 selected headlines visible, ids N1-N5 (before: 0 visible; the index listed N1-N3 that the model never saw). Events: 6 visible, ids E1-E6 (E7+ are no longer citable).
- Sector prompts grew by about 590 characters (SR2 8,264 to 8,854); no other prompt changed in structure.
- Index id counts now equal what is shown, for example SR2 E6/N5/C2, MP1 E5/N5/C3, CC2 N4/A6/C3.

## Tests
New `test_ai_search_prompt_alignment.py`, 17 tests:
- for company, sector, pairwise comparison and multi-comparison prompts built from a bundle larger than every cap, the ids the index offers equal the markers in the real prompt, both directions;
- caps are the single source for prompt and index; the sixth news item is neither shown nor citable in the sector prompt;
- `visible_text` contains the shown evidence and none of the hidden (rank-7 event, summary-only fact, rank-8 news); sector rows only for the sector prompt;
- **adversarial regressions:** a fact present only in hidden evidence cannot be cited (`unknown_source`: the hidden id does not exist); the same fact cited against a visible id is rejected (`unsupported_figures`); a figure that lives only in a summary is rejected; a stated item date the prompt never showed is rejected; a visible title figure and a visible announcement date still authorize; the same fact authorizes when it sits inside the visible slice;
- the pipeline sets `prompt_kind`.
AI Search / AEV2 / core-answer / page-intelligence selection (before this file was added): 804 passed, 1 skipped, 2 xfailed, 2 failed, the 2 being the existing live-engine tests; the new tests add 17 passing.

## SR2 prompt inspection (model-free): does the model now have enough?
What the sector specialist sees for "What is the outlook for the IT services sector?", from the harness data:
- **Events E1-E6:** "TCS, Infosys, Wipro shares ahead of Q2 results... What Accenture's strong earnings mean for Indian IT stocks"; "IT Q2 Results Dates: When TCS, Infosys, Wipro, HCLTech, Tech Mahindra Will Report FY27 Earnings"; **"Nifty IT crashes 11% in September..."**; "Infosys, Wipro ADRs soar up to 8% as strong Accenture earnings forecast lifts mood"; "Nifty IT jumps 2%; Mphasis, Coforge, Infosys, TCS among top gainers..."; "Accenture Shares Jump Record 22% On Earnings Boost".
- **News N1-N5:** "TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook beat estimates"; a market-outlook wrap; "Weekly Market Wrap... IT indices fall 4%; Infosys leads losses"; a Wipro live-price page; **"Indian IT's Q2 earnings dilemma deepens: More deals but weaker growth..."**.
- Plus the live sector rows and the sector-performance context line.
That is enough for a balanced, sourced answer (September fall of 11%, the Accenture read-through rally, the weak-growth caution, the live sector move). Limits: **titles only**: the Q2 results start date (8 Oct) lives in a summary, and the "weaker growth" detail is truncated in the headline, so the model cannot state them. That is the titles-versus-summaries question for the next step. One SR2 live call is now justified if you want to measure it; CR1 and MP1 are not (substantive company evidence and transmission evidence do not exist).

## New finding (pre-existing, outside this scope, not fixed): a cold process silently drops DB-backed news
While inspecting SR2 I saw `collect` return zero news. Cause: `collect` runs the events, news and policies lookups concurrently on **one** database session; on the very first use of a cold connection pool SQLAlchemy raises "This session is provisioning a new connection; concurrent operations are not permitted", `gather(..., return_exceptions=True)` swallows it, and that source becomes an empty list with no log line. Measured: fresh session, cold process: news counts over five runs `[0, 5, 5, 5, 5]`; with the session pre-warmed `[5, 5, 5, 5, 5]`. It only hits the first request(s) after a process start, but it is silent evidence loss. It is also **a confound for earlier diagnoses**: CR1 was the first collect in the 3.4F live run, so its zero news may have been this race rather than the 20-versus-60 news window (the window defect and its fix stand: reproduced and tested separately). Recommend a small separate fix (do not gather on a shared session; use per-task sessions or serialise the first use) and a log line when a source raises.

## Known limitations
- Gate B is stricter by design: claims that depended on summary text, item dates or hidden items will now be rejected. Real answers may lose some figures; that is the intended trade, and the way to restore them is to show summaries or snippets deliberately (next decision), not to widen the corpus.
- `prompt_kind` defaults to None for offline callers (legacy corpus); a new caller that skips the pipeline must set it.
- Context lines (including the development-memory and historical blocks) are fully visible and remain fully authorizable.
- No change to retrieval ranking, so MP1's missing transmission evidence and CR1's missing results evidence are unchanged.

## Verdict
**GREEN for presentation and authorization alignment:** every prompt-visible id is citable and every citable id is prompt-visible, across all four specialist prompts and the frozen 18; hidden evidence can no longer authorize a claim; SR2 now sees its selected news; routing, entities and Gate A are unchanged.

## Next
- Decide titles versus grounded summaries or snippets (its own measurement).
- Fix the cold-start silent-drop race separately.
- Optionally one SR2 live call (about 4-5K tokens; about 52K remain) once you approve.
