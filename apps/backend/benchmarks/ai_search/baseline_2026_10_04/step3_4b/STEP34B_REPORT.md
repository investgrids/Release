# Step 3.4B report: fail-closed gate qualification

Frozen: Step 3.4A at `697946d`. No rule, retrieval, provider, age-limit, CD3 or MP2/MP3 change in this step; only tests and this report were added. Model-free, no live provider call, nothing pushed or deployed. The committed frozen-18 baseline was not replaced; the drifted yfinance/RSS rerun is not used here.

## Result
`tests/services/test_ai_search_gate_qualification.py`: **89 passed** (128 with the 39 Step 3.4A tests). Honest refusal is scored PASS. No rule was tuned.

## Boundaries proven on both sides
| Boundary | Fails closed | Stays authorized |
|---|---|---|
| Company assessment (CR2) | zero evidence; 15 unrelated market items; tips article only; administrative filings only (even 30 of them) | one substantive filing; administrative + one substantive; company-specific news event |
| Event impact (EI1) | premise not established, even with other company filings or another company's strong evidence | premise supported |
| Comparison | neither side; TCS only; INFY only; one side administrative only | filing on one side + valuation on the other; valuation both; filings both |
| Sector assessment | nothing; single-company filing; tips article; row for a different sector | sector-wide item; live sector row |
| Macro transmission | nothing; condition without exposure; exposure without condition | condition + exposure |
| Sector scan | no live rows | live rows |
| Education | not gated by either gate (3 questions) | |
| Gate A is not a count | 30 administrative notices still insufficient | 1 substantive filing sufficient |
| End to end | CR2 and EI1: zero specialist calls, rating Not Applicable, no confidence/timeline/scenarios/drivers/companies, no directional wording, passes the recommendation-language gate, `premise_check=not_established` | sufficient evidence reaches the specialist |
| Claim sources | missing, None, unknown ID, malformed ID, empty list, claim not in answer, uncovered factual sentence, tips source, single-company filing for a sector claim, claim restating an unestablished premise | valid ID (either case), sector-wide source for a sector claim, supported premise, a sentence with no factual content |
| Figures/dates | invented ISO date, invented figure, invented rupee amount, invented values in timeline / scenarios / drivers / risks / prose fields | figure or date present in evidence or question; today's date |
| Leakage | the real CR2 generation is rejected; no leak words, no verbatim public string of the generation, internal field stripped, only reason codes/counts in the public summary, generation retained internally, generation not mutated, deterministic across runs | a fully sourced generation with supported figures publishes end to end |

## Representation variants (deterministic, no fuzzy authorization added)
Correctly handled: ISO vs "Oct 1, 2026" vs "1st October 2026" vs "1 Oct 2026" vs ISO timestamps; comma vs no comma; Rs vs ₹; "11%" vs "11 per cent" (both directions); 12% vs 12.0%; 1200.5 vs 1,200.50; 2500MW vs 2,500 MW; year, fiscal-label, horizon and single-digit exemptions.

## Known limitations (pinned as tests, listed here, not fixed)
| Case | Direction | Effect |
|---|---|---|
| Legitimate `01/10/2026` date supported by evidence | **false rejection** | numeric dates are not parsed, so "01" and "10" are flagged as bare numbers; an honest answer using this form is withheld |
| `1.2 lakh crore` in the answer vs `120,000 crore` in evidence | **false rejection** | no unit conversion |
| Number written in words ("eighteen percent") | **false acceptance** | not checked at all |
| `18%` when evidence only has `2,180` | **false acceptance** | the match is a substring of the digit string |

Two of my predicted limitations were wrong when run (`1200.5` vs `1,200.50` is accepted; invented `12/11/2026` is rejected, though only incidentally via bare numbers). The table above reflects measured behavior. The two false acceptances weaken Gate B in the permissive direction and deserve a decision on a stricter number-boundary match; the two false rejections only cost throughput. I did not change them here, as instructed.

Also recorded: an administrative filing cited as a source for a claim is not blocked by Gate B (only excluded from Gate A sufficiency).

## Regression selection
AI Search test files (`tests/services/test_ai_search*.py` and related): **411 passed, 2 xfailed, 6 failed**.
- Attributable to Step 3.4A/3.4B: **0**.
- Existing: 6 `test_ai_search_engines_live.py` live_e2e failures (`test_decision_engine_live` x4, `test_recommendation_engine_live` x2). They fail identically on the parent commit `697946d~1` (checked in a temporary worktree, since removed). Caveat: the worktree had no `ig_dev.db` copy, so this proves they are not caused by the new gates in code, not that they would pass with the dev database.

## Frozen 18 / SR3 / CC2
The committed Step 4 results are unchanged. In the drifted local environment (yfinance SSL failures, empty sector rows/valuation/VIX, moved RSS), Gate A stops SR3 (no live sector rows) and CC2 (HDFCBANK has no usable evidence or valuation), and EI2 (premise no longer confirmed by current news). SR3 and CC2 are market-data unavailability, not gate defects, and must be re-checked where market data exists. See `step3_4a/STEP34A_REPORT.md`.

## Not done / still unverified
Live behavior with a real provider, Gate B's real rejection rate, and the frozen-18 gate decisions with market data present.
