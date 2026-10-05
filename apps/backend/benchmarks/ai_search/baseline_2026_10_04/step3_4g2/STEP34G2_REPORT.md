# Step 3.4G.2 report: EI3-only live rerun, closing 3.4F

Code: `44d862f` (clause-level factual detection; 23 regression tests including the exact saved EI3 rejection and disguised-assertion adversarials). Live artifact: `../step3_4c/openai_3_4g2.json`. `gpt-6-luna`, 1 request, HTTP 200, no retries, no prompt, retrieval, model or gate change. No key in the artifact (the one "sk-" regex hit is the URL slug `credit-risk-o-meter`). Nothing pushed or deployed.

## EI3: authorized
| Check (your closing bar) | Result |
|---|---|
| Gate B authorized | **yes** (`reasons: []`, 1 factual sentence, 0 unsupported figures) |
| Signed sector moves accepted | **yes**: "Banking was +0.5% for the day; PSU Bank was +1.2%, while Private Bank was -0.1%." matches the evidence (C2 and the sector rows: Banking +0.5%, PSU Bank +1.2%, Private Bank -0.1%), including the negative figure |
| Grounded claim accepted | **yes**: 1 claim, source C2, status ok, 0 uncovered |
| Limitation sentence correctly ignored | **yes**: "The available MarketRipple evidence does not establish the reported stronger credit growth or its sector impact" and the risk line "...does not establish whether the reported credit growth affects earnings or asset quality" both contain the verb "reported" and are not treated as factual claims |
| No unsupported claims or figures | **yes** |
| Withheld structures | none generated; verdict "Not Applicable", direction null, engine view null |

Content: correct and honest. It says the evidence does not establish the reported stronger credit growth or its sector impact, gives the live sector moves, and does not invent a cause or magnitude. Grade: **grounded, appropriately limited, a useful answer to an unverified-premise question** (it does not answer "what is the impact" because the premise cannot be verified from the evidence, which is the correct behaviour).

Cost: 2,064 + 2,246 tokens (1,676 reasoning), 19.2 s. About 52,256 of the 100,000 project tokens remain.

## Status: 3.4F Safety and Authorization is CLOSED/GREEN
Across the live specimens: every generation was grounded; nothing fabricated; no rejected text leaked; all five frozen-set questions that were run (plus the CC1 and CC2 reruns) are now explained. The three mechanical authorization defects found by the live specimens (signed numbers, `sectors[].explanation`, limitation sentences with digits and with event verbs) are fixed and protected by adversarial regression tests; do not mine the frozen five for further hypothetical validator edge cases.

## Still open and separate (unchanged)
- **3.4G evidence usefulness (CR1, SR2, MP1):** model-free: why the right evidence was missing, ranked poorly or ignored; Gate A/B stay frozen.
- MP2/MP3 macro routing; GE1-GE3 educational contract; confidence versus evidence-count semantics; Final Answer Contract; UI.
- The benchmark key has been used many times; rotate it again when benchmarking ends.
- About 52K tokens remain in the OpenAI project window; do not spend them before the model-free evidence work.
