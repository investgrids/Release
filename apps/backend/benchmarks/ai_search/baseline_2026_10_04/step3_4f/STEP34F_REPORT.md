# Step 3.4F report: five live specimens (gpt-6-luna, one clean measurement)

Artifact: `../step3_4c/openai_3_4f_run2.json` (the third attempt; the first two stopped on a rejected key and on a key with a trailing newline, 0 tokens used). Model `gpt-6-luna`, no retries, no prompt/model/gate changes during or after the run. 5 requests, all HTTP 200, `finish_reason` stop. Nothing pushed or deployed. The key never appears in the artifact (the single "sk-" regex hit is a URL slug, `credit-risk-o-meter`).

## Result in one line
**3 of 5 authorized (all three grounded but thin), 2 of 5 withheld by Gate B with correct content.** By your rule (2-3 of 5): fix the demonstrated failure classes only. Nothing misleading was published and nothing leaked.

## Cost and latency
| Q | Prompt | Completion (reasoning) | Latency | Gate B |
|---|---|---|---|---|
| CR1 | 1,681 | 1,788 (1,330) | 18.2 s | authorized (2 factual sentences) |
| EI3 | 2,064 | 2,167 (1,744) | 16.5 s | rejected: claim_not_in_answer, unsupported_figures |
| SR2 | 2,130 | 3,424 (2,455) | 27.4 s | authorized (4) |
| MP1 | 2,490 | 2,771 (2,273) | 21.0 s | authorized (0 factual by the detector) |
| CC2 | 1,986 | 2,241 (1,348) | 18.1 s | rejected: claim_not_in_answer, uncovered_factual_sentences |

Total 22,742 tokens (about 4,550 per call); 12,391 completion tokens, of which about 9,150 (74%) were hidden reasoning. All under 30 s, SR2 closest (27.4 s). Project window after the run: about 64,900 of 100,000 tokens.

## Grades (does the public answer answer the user's question?)
| Q | Class | Why |
|---|---|---|
| **CR1** Kotak outlook | **Grounded but thin** | Says the evidence "does not establish operating outlook". Everything stated is sourced, but it leads with "informed the Exchange about General Updates" (an administrative filing) and a 28%-confidence no-signal memory line. Gate A passed on an "Investor Presentation" title; the user learns almost nothing. |
| **EI3** banking credit growth | **Refused by Gate B; content correct** | The model said, correctly, that the evidence does not substantiate a stronger credit-growth report or its size. That is the right answer to an unverified premise. Withheld because of a validator false rejection (below). |
| **SR2** IT outlook | **Grounded but thin, leaning useful** | Gives IT +1.7% (1-day) and the Accenture read-through, and states the forward trajectory cannot be established. It ignored richer evidence that was in the bundle: Nifty IT down 11% in September, Q2 results dates from 8 Oct, "growth recovery still out of sight". Not misleading, but an outlook answer without them is thin. The same Accenture sentence is also repeated under "opportunities". |
| **MP1** repo-rate cut and banks | **Grounded but thin** | Uses the only matching precedent the model chose, an emergency (COVID) cut with "sharp relief rallies in banking", and says the evidence does not establish how banks respond to a future cut. Labelled "emergency", disclaimed, not wrong, but it skipped the regular cut-cycle precedents in the same bundle and does not really answer the question. The market-level engine view ("Cautious", tier 5, sideways) is shown, as designed for macro scope. |
| **CC2** HDFC vs ICICI | **Refused by Gate B; content correct** | Would have been a useful valuation comparison (HDFC P/E 15.8, P/B 1.83 vs ICICI 16.9, 2.47; 52-week ranges; operating data not available) with no winner. Withheld by claim and sentence handling (below). |

Specimen quality to date: CC1 (D-4) useful-but-thin, CR1 thin, SR2 thin, MP1 thin. The system is honest and safe. It is not yet reliably helpful.

## Failure classes demonstrated (from the unchanged validators run on the saved generations)
1. **Regression I introduced in Step 3.4B.1: negative numbers are always rejected.** Evidence tokens are extracted without their minus sign, answer tokens keep it, so "Banking -0.4%" never matches evidence that says "Banking -0.4%". Confirmed in isolation: `-0.4%` and `-0.7%` flagged, `+1.3%` passes. This is what produced EI3's `unsupported_figures` (2). It would hit every falling-sector or falling-price answer. Class B: false rejection, my bug.
2. **Claim-in-answer check does not scan `sectors[].explanation`.** The model claimed a sentence that lives only in a sector explanation (EI3: the live 1-day data sentence; CC2: "Both companies are banks compared here..."). The claim-in-answer check does not read that field, though the figure check does, so a correctly sourced claim is reported `claim_not_in_answer`. Class D (contract/validator mismatch): either scan the field or tell the model not to put claims there.
3. **A limitation sentence containing a digit is treated as a factual sentence.** CC2's "The available evidence supports comparison of the stated valuation multiples and 52-week ranges only; operating results... are not available" is flagged uncovered because of "52-week". Class B (narrow false positive of the digit/verb detector on a limitation statement); the model followed the "write limitations plainly" rule.
4. **Retrieval/ranking quality, not gates:** CR1 sufficiency counts "Investor Presentation"; SR2 and MP1 ignored the most relevant items in their bundles (the prompt/evidence ordering and the model's choice of what to cite). Not demonstrated by a gate failure, observed by reading the answers.
5. **Tracked, not blocking:** confidence "N trusted sources" vs evidence count; GE educational contract; MP2/MP3 routing.

Not observed: any invented number, date, verdict, scenario or winner in any answer or rejected generation; any leak of a rejected generation (CC2/EI3 public responses are the deterministic withheld shape).

## Decision against your rule
2-3 of 5 authorized, all thin: **fix the demonstrated classes only**, in this order of value and risk:
1. Fix the negative-number token handling (a regression of mine, small, testable).
2. Resolve the `sectors[].explanation` mismatch (scan the field for claim-in-answer, or forbid claims there in the contract).
3. Do not treat a limitation sentence as a factual sentence merely because it contains a digit like "52-week" (keep exact matching; narrow the detector, do not add fuzzy matching).
4. Then re-run only the two withheld questions (EI3, CC2) to confirm they become authorized with the same content, about 8.5K tokens.
Separately, the answer-usefulness gap (CR1/SR2/MP1) is a retrieval/prompt-ordering question, not a gate defect; do not tune gates for it.

None of this was changed in this step.
