# Step 3.4G.1 report: validator fixes and the EI3 / CC2 live rerun

Code: `7bdd65f` (signed-number grounding, `sectors[].explanation` scanned, period labels exempt from the digit test; 32 regression tests including the exact saved EI3 and CC2 failures and adversarial cases). Live artifact: `../step3_4c/openai_3_4g1.json`. `gpt-6-luna`, 2 requests, both HTTP 200, no retries, no change to prompts, retrieval, routing or gates for the run. No key in the artifact. Nothing pushed or deployed.

## Result: 1 of 2 closed
| Q | Gate B | Class |
|---|---|---|
| **CC2** HDFC vs ICICI | **authorized** (6 factual sentences, 0 unsupported figures, scope valuation-only, no winner, nothing withheld) | **Useful** |
| **EI3** banking credit growth | **rejected: `uncovered_factual_sentences`** | Refused by Gate B, content correct (a **new, different** false positive, below) |

Cost: EI3 2,064 + 1,327 tokens (12.3 s); CC2 2,042 + 2,901 (22.6 s); 8,334 total. About 57,280 of the 100,000 project tokens remain.

## CC2 (closed)
Same grounded shape as the earlier specimen, on live data that moved (HDFC P/E 15.6 and P/B 1.81, ICICI 17.0 and 2.48; the answer matches this run's evidence). Valuation comparison and 52-week ranges, plus a grounded news sentence (HDFC shares up 2% after the Anup Bagchi CEO appointment and Q2 update, headline N2, checked against the evidence). It states operating growth, margins and earnings trends are not available, names no winner, and carries the valuation-only caveat. Verdict, direction and engine view are null; nothing withheld. The limitation sentence with "52-week" and the sector-explanation claim, both of which blocked it before, now pass. The sector explanation is filler ("The query compares HDFC Bank and ICICI Bank..."), which is a quality nit, not an integrity one.

## EI3 (not closed): why it was rejected
The model answered correctly: the supplied evidence has no credit-growth data, so the reported strengthening and its impact cannot be assessed. It claimed one sentence, the live sector move ("Banking rose 0.6% on the day, versus 1.1% for PSU Bank and 0.1% for Private Bank", source C2, status ok, figures grounded). The signed-number and sector-explanation fixes worked (that claim passes). The rejection is one sentence:

> "The supplied evidence does not include credit-growth data, so the reported strengthening and its impact cannot be assessed."

It is flagged factual because it contains the event verb **"reported"** (as in "the reported strengthening"), which is in the detector's event-verb list. It is a limitation, not an assertion. This is the same kind of false positive as the "52-week" digit case but triggered by a verb, which my 3.4G.1 fix (period labels only) deliberately did not touch.

## Recommended next change (not implemented): 3.4G.2, event verbs inside an absence clause
Keep exact matching and add no bypass. Treat a sentence as not factual on the verb test only when the clause containing the verb is an absence/limitation clause (it contains a negation frame such as "does not", "do not", "no ... data", "cannot be", "not available", "not established") **and** has no digit, %, rupee or other figure. Split on clause boundaries first (";", ", but", ", and", " but ") so a disguised assertion in its own clause stays factual, for example "...data is not available, and TCS reported record profit" (the second clause has no negation, so it remains factual). Adversarial tests to require: those disguised-assertion forms stay factual; "has not reported results" and "the reported strengthening cannot be assessed" are not factual; a clause with a figure is factual regardless of negation. Then rerun only EI3 (about 3,400 tokens).

## Status
- Signed-number and sector-explanation defects: closed and confirmed live (EI3's claim passes, CC2 authorizes).
- Limitation-sentence defect: closed for digits, **open for event verbs** (one more narrow rule).
- 3.4F safety/authorization qualification cannot be declared closed until EI3 authorizes; it is one small step away. Nothing misleading was published and nothing leaked in this run either.
- Still separate and untouched: 3.4G evidence usefulness (CR1/SR2/MP1), GE educational contract, MP2/MP3 routing, confidence-versus-evidence-count semantics.
