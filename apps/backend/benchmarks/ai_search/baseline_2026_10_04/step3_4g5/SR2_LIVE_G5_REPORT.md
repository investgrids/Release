# SR2 single live call under the composition contract (3.4G.5)

Artifact: `../step3_4c/openai_sr2_g5.json`. `gpt-6-luna`, 1 request, HTTP 200, no retries, no change to prompts or gates for the run. No key in the artifact. Nothing pushed or deployed.

## Outcome: content now useful; withheld by Gate B for one listed-but-unwritten claim
| Measure | Value |
|---|---|
| Gate A | sufficient |
| Gate B | rejected: `claim_not_in_answer` only (6 factual sentences, 0 unsupported figures, 0 uncovered sentences) |
| Tokens | 2,778 prompt + 4,726 completion (3,486 reasoning) = 7,504 |
| Latency | **57.3 s** (3.4F run: 44.3 s; production timeout 30 s) |
| OpenAI window left | about 40,870 of 100,000 |

## What the model wrote (rejected generation)
- **Observations (`what_happened`)**, all sourced and drawn from visible items: the Nifty IT index fell 11% in September with TCS, Infosys and Wipro among the top losers while the cited report asked whether Q2 earnings could spark a rebound (E3); Accenture's strong earnings forecast lifted sentiment around Indian IT and Infosys and Wipro ADRs rose up to 8% (E4); the weekly market wrap reported IT indices down 4% with Infosys leading losses (N4); IT was flat over one day, between FMCG and Pharma (C2, the live sector row).
- **Synthesis:** "Taken together, the reported September decline and Accenture-linked ADR gains, alongside a flat one-day IT reading, leave the market evidence mixed and do not establish Indian IT operating performance." Bottom line: the evidence "does not establish a fuller IT services outlook beyond mixed market signals."
- Distinct visible items cited: E3, E4, N1, N4, C2.

## Against your closing list
| Criterion | Result |
|---|---|
| passes Gate B | **no**: one claim listed but never written |
| uses several high-information visible facts | **yes** (four observations from four distinct items) |
| captures the mixed IT picture rather than only "cannot be established" | **yes** (September fall vs Accenture-led gains vs a flat day; hedged synthesis). The "Street divided" headline was not in today's feed window, so it could not be used |
| invents nothing from hidden summaries | **yes**; no year-less (or full) date, no Q2 results date, in any field (checked) |
| lists no claim absent from the answer | **no**: "The supplied preview frames revenue and margin outlook as key Q2 questions." (N1) is in `claim_sources` but not in the text |
| stays uncertain about the overall direction | **yes** |

The failure is exactly one of the model's ten listed claims. The other nine are present in the answer (three of them, "TCS/Infosys/Wipro is named among the top losers...", are accepted only because the claim-in-answer check is still fuzzy: they restate part of the E3 observation rather than appearing verbatim; flagged for the next gate review, unchanged here).

## Interpretation
- Evidence utilization is fixed: the model used the visible high-information evidence and produced the mixed picture. The 3.4G.5 contract worked on the demonstrated problem.
- The remaining blocker is bookkeeping, not understanding: rule (3) of the contract ("never list a claim you did not write") was violated once, and Gate B correctly withheld the answer. Deleting the stray claim after generation is not allowed, and a longer instruction is a weak lever against a model that already had the rule.
- Latency worsened (57 s, 3,486 reasoning tokens for a 4-item synthesis), so the speed issue is not a one-off.

## Options (not started)
- **A. Make prose and observation claims consistent by construction:** the model emits the observation claims (sentence plus ids) and the synthesis; the code builds `what_happened` from the claim list in order. Nothing can be listed but unwritten, nothing observed can be unlisted, output tokens shrink (no duplicate sentences), and Gate B still checks everything else (synthesis, drivers, risks, limitation sentences). It is a small output-schema change, not a gate change.
- **B. Accept the near-pass and move to latency/model-configuration benchmarking.** The content bar is met; the gate result is a single bookkeeping slip, but publishing it requires a pass.
- Either way, latency is a release blocker and the year-less-date gap in Gate B and the fuzzy claim-in-answer match remain tracked.
