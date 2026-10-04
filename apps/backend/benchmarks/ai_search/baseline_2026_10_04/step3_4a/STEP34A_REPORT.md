# Step 3.4A report: evidence sufficiency and fail-closed answer authorization

Status: implemented and tested locally, model-free. Not pushed, not deployed. No live provider call was made. Live behavior is **UNVERIFIED** until the CR2 / EI1 / CC1 live gate.

## What changed
- **Gate A, before the model** (`evidence_sufficiency.py`). Sufficiency is defined by what the question needs, not by a count: a company assessment needs current company evidence that is not routine administration; an event-impact question needs the premise established; a comparison needs evidence for each company; a sector assessment needs sector-wide evidence or the live sector row; macro transmission needs the stated condition plus sector exposure; a sector scan needs live sector rows. Failure means no specialist call and a deterministic response stating what cannot be established (`degraded_reason=insufficient_evidence`), with required / satisfied / missing / reason and `premise_check.status=not_established` preserved.
- **Gate B, after the model** (`answer_authorization.py`, `figures.py`). Claim-source validation now blocks publication: missing, unknown or ineligible sources, uncovered factual sentences, claims restating an unestablished premise, and dates or figures anywhere in the public text (timeline, scenarios, insights) that are in neither the evidence nor the question. Failure means the generation is withheld (`degraded_reason=claims_not_authorized`), kept in `REJECTED_GENERATIONS` and an internal field the finalizer strips. No LLM repair, no sentence stripping, no invented citations.
- **Prompts, defense in depth only.** "Use real NSE symbols, actual rupee amounts…" and "Name real numbers… basis to estimate them" are gone; a `GROUNDING_RULES` block is in all specialist prompts. The gates do not depend on the model obeying it.
- Also: `_FACT_RE` now recognizes filed / disclosed / informed / declared / completed / entered into as factual verbs; `premise_check` vocabulary is `not_applicable | supported | not_established`; `insufficient_evidence` stage is never treated as cached.
- Not touched: retrieval, entity resolution, evidence age limits, provider routing/models/timeouts, CD3 semantics, MP2/MP3 routing.

## Tests
- New `tests/services/test_ai_search_fail_closed.py`: **39 passed**. Includes the real CR2 Gemini generation from Step 3.3b as a fixture: `claim_sources=[]`, invented dates 2026-11-10 / 2027-02-12, "18%" and "200 bps" are all rejected, and nothing from it (zero-debt, Honeywell/Siemens, bullish/constructive, dates, figures) reaches the public response. Empty evidence gives zero specialist calls. BEL unsupported premise gives zero specialist calls. Comparison with one side missing, administrative-only filings, single-filing-for-sector, macro and sector-scan requirements, unknown/ineligible sources, uncovered sentences, availability mapping, and not-cached behavior are covered.
- AI Search test files (`tests/services/test_ai_search*.py` and related): **322 passed, 2 xfailed, 6 failed**. The 6 failures are all `test_ai_search_engines_live.py` `*_live` tests (pre-existing; they need live providers), not caused by this step.

## Frozen 18-question deterministic recheck (no model call)
Re-run with the gate neutralised in the frozen harness (so route / entity / evidence rules are unchanged) and with the gate ON (`sufficiency_recheck.py`, `per_question_table.md`).

**Important caveat: the evidence environment drifted and I could not reproduce the committed Step 4 evidence numbers.** This session's yfinance calls fail with SSL errors, so live sector rows, valuation and VIX come back empty, and live RSS news has moved on. As a result the frozen evidence rule now shows FAIL for SR1-3, CC1-3 and EI3 where the committed run showed PASS. Route and entity checks are unchanged (MP2 and MP3 remain the known routing debt). I restored the committed Step 4 result files and did not overwrite them with the drifted run. The gate-ON table below is therefore a statement about *this* environment, not a replacement baseline.

Gate-ON decisions in this environment:
| Decision | Questions |
|---|---|
| Insufficient, specialist NOT called | CR2, EI1, EI2, SR3, CC2 |
| Sufficient, specialist reached | CR1, CR3, EI3, SR1, SR2, MP1-MP3, CC1, CC3, GE1-GE3 |

- CR2 and EI1 are the intended honest-insufficient cases and behave as designed.
- EI2 now fails the premise check because current news no longer confirms its premise (live drift).
- SR3 (needs live sector rows) and CC2 (HDFCBANK has no usable evidence or valuation) are insufficient **because yfinance data was unavailable here**. With market data present they may pass Gate A. This must be re-checked in an environment with market data before relying on those two.

## Limitations
- Sufficiency uses titles/summaries only; the administrative-filing taxonomy is heuristic and will need tuning from real cases.
- Explanation questions (GE*) are deliberately not gated; they still get investment verdicts, an existing known debt (educational contract).
- Gate B may reject often, especially via the figures check on generations that restate numbers in new forms; the fail-closed direction is intended, but the live rejection rate is unmeasured.
- Date/figure matching is textual; unusual formats could slip through or be over-flagged.
- Live behavior with a real provider is unverified.

## Next (not started)
3.4B fixture/regression qualification, then benchmark capacity isolation (dedicated OpenAI benchmark project/key with a hard spend limit, benchmark-only; todo added this session), provider requalification, CR2 -> EI1 -> CC1 live gate, frozen 18 live benchmark.
