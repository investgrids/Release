# AI Search Benchmark Suite

The permanent regression suite for AI Search — quality, speed, consistency,
and honesty, not just "did it respond." Every future AI Search change
should be run against this before deploying. See **Recommended workflow**
at the bottom for baselining V2 before building V3.

## Files

- **`data.py`** — reference data: 150+ real NSE-listed companies (with
  sector), events, macro/policy/theme/commodity/global-market topics,
  persona/difficulty/time-horizon taxonomies.
- **`generate_dataset.py`** — regenerates the dataset from `data.py`. Run
  `python generate_dataset.py` to reproduce `dataset.json`,
  `golden_questions.json`, and `evaluation_sheet.csv` from scratch (fixed
  random seed, so output is deterministic run to run unless `data.py`
  changes).
- **`dataset.json`** — 2,400 unique questions across 17 categories (Company
  Analysis, Comparison, Sector, Event Impact, Macro, Policy, Earnings, IPO,
  Strategy, Historical, Theme, Commodities, Global Markets, Risk,
  Beginner, Advanced, Edge Cases). Each record: `id, category, difficulty,
  intent, persona, time_horizon, question`.
- **`golden_questions.json`** — 200-question curated subset (proportional
  across all categories) — the mandatory pre-deploy regression set.
- **`expected_answers.json`** — 180 ground-truth regression checks: real
  verifiable facts, hallucination-trap questions (fake company names), and
  comparison/analysis questions checked for correct company/sector
  detection and topic coverage. See **Honesty boundary** below — this file
  deliberately does *not* assert "correct investment winner" calls.
- **`evaluation_sheet.csv`** — one row per dataset question with the full
  scoring rubric: the original automatable columns (Answered Correctly?,
  Company/Event Detection, Response Time, Hallucination, etc.) *plus* 7
  UI/UX star-rating columns (AI Verdict Visible, Executive Summary Quality,
  Ripple Graph Quality, Comparison Quality, Sources Relevance,
  Recommendation Usefulness, Overall UX — all 1-5) — because AI Search is a
  product, not just an API. All scoring columns are blank, for
  manual/human scoring — a screen-reading judgment call can't be automated
  honestly.
- **`runner.py`** — automated benchmark runner. Hits a real running backend,
  captures structured output + latency + the backend's own stage-timing
  breakdown, scores against `expected_answers.json` when a question
  matches, computes freshness/hallucination/consistency signals, and
  prints/writes the exact KPI dashboard format below. Subjective judgment
  still needs a human against `evaluation_sheet.csv` — merge it in with
  `--ux-sheet` once scored.

## Running the benchmark

```bash
# Fast iteration: a slice of the golden set
python runner.py --dataset golden --limit 50

# Full golden set (200 questions, ~22 min at the default 6.5s/request pace —
# that pace is deliberate, it matches /api/ai/search's real 10/min production
# rate limit, not a runner inefficiency)
python runner.py --dataset golden

# Full 2,400-question dataset (~4.3 hours at the same safe pace)
python runner.py --dataset full

# Include the Average UX Score in the KPI dashboard, once you've had a
# human fill in the star-rating columns for at least a sample
python runner.py --dataset golden --ux-sheet evaluation_sheet.csv

# Consistency test — ask the same question N times, check the answer
# doesn't flip. Genuinely independent calls, not cache replays (see below).
python runner.py --consistency 5 --question "HAL vs BEL"

# Point at a different backend (e.g. prod, once the deploy lands)
python runner.py --dataset golden --base-url https://backend-production-78042.up.railway.app

# Compare two runs for regressions before/after an AI Search change
python runner.py --compare results/run_A.json results/run_B.json
```

Each run writes three files to `results/` (gitignored — point-in-time
artifacts, not source): a full `.json` (summary + every per-question row,
feeds `--compare`), a `.csv` (same data, spreadsheet-friendly, includes
per-question `timing.*`, `freshness.*`, and `expected.*` columns), and a
self-contained `.html` dashboard — open it directly in a browser.

## The KPI dashboard

Every run prints (and the `.html` shows) the release-over-release scorecard:

```
Questions Tested          2400
Passed                    2328
Pass Rate                 97.0%
Average Response          3.2 sec
Average Confidence        74%
Hallucinations            0.8%
Wrong Company Detection   0.5%
Wrong Sector Detection    0.2%
Source Relevance          96%
Average UX Score          9.3/10   (needs --ux-sheet; shows "—" otherwise)
Consistency               98%      (needs a separate --consistency run)
Avg Speed Breakdown:
  intent_detection_ms     ...
  db_search_ms            ...
  llm_ms                  ...
  graph_generation_ms     ...
  assembly_ms             ...
  total_ms                ...
Overall Grade             A        (composite of the above, weighted toward
                                     correctness/honesty over raw speed)
```

Fields that need a separate input (UX score, consistency) print an honest
"— (not measured this run)" rather than a fabricated number — don't let a
grade look more complete than it is.

## Speed breakdown — what's actually measured

The backend (`app/services/ai_search_service.py`) now returns a `timing`
field on every response: `intent_detection_ms, db_search_ms, llm_ms,
graph_generation_ms, assembly_ms, total_ms`. These are checkpoint-based
(time since the previous checkpoint), not independently profiled spans, so
treat them as *which stage dominates*, not a strict profiler — good enough
to know the LLM call is your bottleneck without instrumenting every
function. `total_ms` is the true end-to-end time from function entry; it
runs slightly ahead of the sum of named stages because the market-pulse
pre-check (a separate query family, checked before any named stage starts)
isn't individually attributed.

**"Rendering" time is intentionally not reported** — it's a frontend
concern (paint/hydration time in the browser), and this runner only talks
to the API. Measuring it for real would need a browser-based run
(Playwright), not just an HTTP client — flagged here rather than faked.

## Consistency testing and the cache

`--consistency` appends invisible zero-width-space characters to the
question on each repeat (`question + "​" * i`) — same text an LLM or
human reads, different string, so it bypasses the backend's response cache
(keyed on `md5(query.lower().strip())`, several-minute TTL). Without this,
repeating the *exact* same string just replays run 1's cached answer and
reports a meaningless 100% every time. Pass `--no-cache-bypass` only if you
specifically want to test the cache-hit path itself.

## Honesty boundary: what `expected_answers.json` will and won't assert

Verified live against the real backend while building this: a genuinely
low-scoring real pipeline event and a purely factual question can both
legitimately produce a lowish confidence score (confidence measures
investment-thesis conviction, not factual certainty) — so `confidence_min`
is *not* set on factual entries, only on comparison/analysis entries where
it's actually the right signal.

Comparison entries (`"HAL vs BEL"`-style) check what's objectively
checkable — did the response correctly identify both named companies, did
it engage with the right analytical themes for that sector — and set
`"winner": null, "winner_needs_review": true`. This suite will never
assert a fabricated "correct" investment winner for a forward-looking
comparison; that needs a domain expert's real judgment or backtested data.
Filling in real `winner` values for the 80 flagged comparison entries is
the one piece of this suite that has to be done by a human, on purpose.

Hallucination-trap entries (fake company names) check for two things: no
fabricated `companies` in the response, and a clear rejection phrase in the
actual narrative text (not just anywhere in the JSON — see next section).
Verified live: the backend currently does the safe thing for a fake
company (returns `companies: []`, doesn't invent financials) but falls
back to a generic template rather than an explicit "no verified company
found" — a real, legitimate product gap this benchmark surfaced on its
first real run, not a scorer bug.

## Why `must_mention`/`must_not_mention` only reads the narrative text

Checking the *entire* response (including the structured peer-companies
list) against `must_not_mention` produces false failures — e.g. asking
about HAL/Tejas legitimately returns BEL as a related defence-sector peer
company, which isn't the AI claiming BEL manufactures Tejas. Verified this
exact false-positive live and fixed it: `must_mention`/`must_not_mention`
now only scan the AI's actual prose (`answer.summary`, `bottom_line`,
`key_drivers[].explanation`, etc.), matching what a human reader would
judge as "what did it actually say," not "what data was attached."

## What "hallucination-risk flag" and "wrong sector detection" actually mean

Cheap, honest heuristics — not a real hallucination detector, which needs
ground truth most questions don't have:

- **Hallucination-risk flag**: high confidence (≥85) with zero cited
  sources, OR a company named directly in the question that never appears
  in the response's `companies` list. Worth a human look, not "confirmed
  wrong."
- **Wrong sector detection**: only computed for questions with an
  `expected_answers.json` match — compares the sector of the companies
  named in the question against the sector of the companies actually
  returned.
- **Source relevance**: a coverage proxy (did *any* real sources come back
  at all), not semantic relevance grading — that needs human judgment or
  embedding similarity, out of scope here.

## Extending the dataset

Add entities to `data.py` (more companies, events, themes, etc.) and/or
templates in `generate_dataset.py`, then re-run `python generate_dataset.py`.
The generator asserts zero duplicate question text before writing output —
if a category generator can't reach its target count uniquely (all
template×entity combinations exhausted), it will silently stop short rather
than duplicate; check the printed per-category counts against the targets
after regenerating. Re-run `python generate_expected_answers.py` afterward
if you added companies/facts relevant to `expected_answers.json`.

## Recommended workflow

Don't jump straight to an AI Search V3 redesign. Run this suite against the
current version first for a real baseline (`python runner.py --dataset
golden`, plus a sample of `evaluation_sheet.csv` scored by hand and merged
with `--ux-sheet`). Build V3, run the identical command, and use
`--compare` plus the two KPI dashboards side by side. That's the difference
between "we changed the interface" and "we can prove this is measurably
better" — pass rate, hallucination rate, comparison accuracy, and source
relevance are the ones that actually matter; don't ship a redesign that
regresses any of them even if the UI looks nicer.
