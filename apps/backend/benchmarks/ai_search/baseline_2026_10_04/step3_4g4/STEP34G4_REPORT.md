# Step 3.4G.4 report: factual-sentence detector closure (zero provider calls)

Fixes only the two false-positive classes demonstrated by the saved SR2 live rejection. `claim_not_in_answer` and the rest of Gate B are unchanged. No prompt, retrieval, ranking, routing or Gate A change. Nothing pushed or deployed; no API call; about 47,750 OpenAI tokens remain.

## Changes (`claim_sources.is_factual`, `figures`)
1. **Fiscal/period labels.** One shared definition, `figures.FISCAL_LABEL_PATTERN`, now covers FY26, FY2026, FY26-27, FY26/27, Q1-Q4 (Q2, Q2 FY27, Q2FY27, Q2'27), 1Q-4Q (1Q26) and H1/H2 (with or without FY). The figure validator and the factual-sentence detector use the same pattern. In the detector the labels are stripped **only inside an evidence-limitation clause** (an absence frame, an inability statement that names the evidence, or a pronoun continuation of one), so "Infosys Q2 profit beat estimates" stays factual exactly as before.
2. **Pronoun continuation.** "...cannot be established from the available evidence; it does not include reported operating results." The pronoun clause is part of the limitation only when the previous clause was an evidence limitation AND the verb is present-tense negated (does/do not ...). "it reported record profit", "it did not report a profit", "it announced a buyback" stay factual, as do pronoun clauses with no limitation before them and any clause with a figure. "cannot establish/assess/determine/verify/confirm/show/support" now counts as an inability statement, alongside "cannot be established".

## Tests (`test_ai_search_detector_closure.py`, 48)
- **Exact saved SR2 failure:** live reasons were `claim_not_in_answer` + `uncovered_factual_sentences`; after the fix the same generation yields exactly `['claim_not_in_answer']`, flagged for the one claim the model listed but never wrote ("IT was flat at +0.0%..."). With that single contract violation removed, Gate B **authorizes** the same answer, proving the two detector fixes were the only other blockers.
- 16 fiscal-label forms accepted inside a limitation (and the label pattern is the figure validator's); look-alikes (Q5, SQ2, Q2x, FY2, H3, 5Q) are not exempted.
- Adversarial: a real figure or an event in a separate clause, a bare "TCS reported Q2 results", "Infosys Q2 profit beat estimates", "Q2 revenue was Rs 500 crore", a limitation followed by "it reported record profit" / "it did not report a profit" / "it announced a buyback", "The company cannot establish a profit; it reported record profit", and a limitation-style answer carrying an invented 14% growth claim (still rejected for missing claims and unsupported figures) all stay factual or rejected.
- Selection (AI Search, AEV2, core-answer, page-intelligence, follow-up files): 830 passed, 1 skipped, 2 xfailed, 2 failed (the existing live-engine tests) before this file; the new file adds 48 passing.

## Known limits
- Detection stays lexical. A limitation phrased outside the known frames still reads as factual (fail-closed). Outside limitation clauses a fiscal label keeps its digit and counts as a figure.
- The SR2 generation is still not publishable as written, by design: the model has to state the claims it lists.

## Next
3.4G.5 composition contract (zero calls: inspect first), then one SR2 call, then latency qualification. Not started.
