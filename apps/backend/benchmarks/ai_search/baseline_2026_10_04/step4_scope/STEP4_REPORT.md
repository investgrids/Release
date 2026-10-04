# Evidence scope + claim-level source IDs (local, model-free)

Branch `release/ai-answer-v2`. Local only: nothing pushed or deployed. No model call was made for any of this (the re-check disables the market-pulse classifier and stubs the specialists). Live answer review is still blocked on provider capacity; **answer quality remains UNVERIFIED**. OpenAI integration not started.

## 1. What the model is now allowed to see
Shared rules in `evidence_scope.py`, used by retrieval, the prompt, claim validation and the offline gate (one definition, so they cannot drift):
- **Stock-tips articles** ("Top 3 stocks to buy: ...", "target price / stop-loss", "buy or sell") are removed from every bundle and can never confirm an event.
- **Single-company exchange communications** ("X Limited has informed the Exchange", "The Exchange has sought clarification from X Limited", Regulation 30 disclosures) are removed from sector, macro and general bundles. This removes the Tera Software filings, the Oracle Financial Services Software notice, and ICICI/DPSC/Dynacons/Wipro filings that were sitting in sector bundles.
- **Company-scoped news** must use the registered name or symbol. A bare brand ("Kotak") or a brand inside another entity's name ("Kotak Institutional Equities") does not count.
- **Event premises.** A question phrased as news ("BEL just won a new defence order") is a premise. If no eligible evidence about the company mentions that kind of event, the premise is recorded as unsupported, the prompt carries a verification note ("say plainly the event could not be verified; do not state its size, value, timing or effects"), and the response carries `premise_check`.
- **A leak fixed.** Announcement lines were written into the free-text context before the age filter ran, so announcements the filter removed could still reach the prompt. They are now rendered after filtering, with IDs.
- IT-sector vocabulary gained "IT spending", "IT industry", "Nifty IT" etc. after a fixture showed a sector-wide event tagged to TCS/Infosys/Wipro being dropped.

## 2. Gate: irrelevant evidence, not just an empty bundle
`answer_checks.bundle_irrelevance` re-checks every item in a saved bundle against the scope of the question. The insufficient-evidence check now applies when the bundle is empty, holds nothing relevant, **or the question's premise is unsupported**, so a non-empty bundle like BEL's (one tips article) is treated as insufficient evidence and an answer that invents an order fails it.

Run over the **pre-change Step 3 bundles** (real saved data): **10 of 18 questions held irrelevant evidence** (BEL tips article in EI1 and in CC1-CC3; Tera Software and Wipro filings in SR2 and MP3; ICICI, DPSC and Dynacons filings in EI3, SR1, MP1; a tips-style market wrap in MP2). After the change: **0 of 18**. `per_question_table.md` has the per-question detail.

## 3. Claim-level source IDs in the answer contract
- Every evidence item in the prompt is tagged: **E** events, **N** news, **P** policies, **A** announcements, **C** context lines. `EvidenceBundle.index()` returns the same IDs in the same order, so an ID in the prompt and an ID in `claim_sources` always mean the same item (tested for the company, sector and pairwise-comparison prompts).
- The specialist JSON gained `claim_sources: [{claim, sources}]`; rules tell the model to copy each factual sentence exactly, cite only listed IDs, and not state as fact anything no listed item supports.
- `claim_sources.validate_claim_sources` checks, with no model: structure, unknown IDs, claims with no source, claims not present in the answer, claims whose every cited source is ineligible for the claim's scope (tips article; another company's filing for a sector claim; brand-only mention for a company claim), claims asserting an unsupported premise, and factual sentences no claim covers. Status `ok` / `problems` / `not_provided`. Non-blocking: nothing is rewritten or removed.
- The assembled response gains `evidence_index`, `claim_sources` (with per-claim status), `claim_validation` and `premise_check`. Degraded responses are unchanged (they share a tested key skeleton with the safety-gate degraded response); a missing field means "not applicable".
- The gate re-validates `claim_sources` independently from the saved index and reports any disagreement with the pipeline.

All of this is proven on **fixtures only** (unknown ID, no source, claim not in answer, Tera/tips/Kotak ineligible sources, partly-eligible sources, unsupported premise, uncovered sentence, not provided, malformed). Whether a real model fills `claim_sources` correctly is **UNVERIFIED**; the first live run will show it (`not_provided` is a valid, visible outcome).

## 4. Re-check of the fixed 18 questions (frozen scoring rules, unchanged)
| Check | Step 2 rerun | Now |
|---|---|---|
| Route | 16 / 18 | 16 / 18 |
| Entities | 18 / 18 | 18 / 18 |
| Evidence (frozen rule) | 16 / 18 | 16 / 18 |
| Irrelevant evidence in the bundle (new) | 10 of 18 questions affected (measured on the pre-change bundles) | 0 of 18 |
| Unsupported event premise recorded | not tracked | EI1 (BEL order) and EI2 (TCS research centre) |

The frozen counts did not move because the cleanup removes items that were not helping those rules; it does not add coverage. **BEL (EI1) and 3M India (CR2) stay honest "insufficient recent evidence" cases**: EI1's bundle is now empty (its only item was the tips article; its one event is 87 days old), CR2's is empty. The age filter was not loosened.

## 5. Honest limits
- Passing mentions still count. EI2's TCS bundle keeps a market-outlook news item because its text names TCS. It is eligible by the naming rule but weak evidence. A relevance score would be a separate change.
- Premise checking applies to company and comparison questions only. A sector-level premise ("Banking sector just reported stronger credit growth") is not checked.
- Premise matching is lexical, by event-word groups (order/contract, deal, results, ...). A premise phrased with an unlisted word is treated as "not required".
- The gate's irrelevance check uses the same scope module as retrieval, so it verifies consistency and catches regressions, not an independent notion of relevance.
- The tips regex is deliberately narrow ("stocks to watch" is not treated as tips because such roundups can carry real events). A mixed market wrap with a "stocks to buy" section is dropped (MP2's wrap).
- The claim-sources rules add roughly 150 prompt tokens and up to a few hundred output tokens; specialist `MAX_TOKENS` is unchanged, so a long answer may truncate sooner. Not measurable without live calls.
- MP2 (crude oil) and MP3 (rupee) still route to `direct_company_research` (the ui_mode classifier needs a named policy); unchanged.

## 6. Tests
AI Search selection **633 passed, 1 skipped, 2 xfailed** (496 baseline + earlier additions + 46 new in this step). The 23 related files outside it: 196 passed, 12 failed, the identical 12 `*_live` provider/network tests that fail without these changes.
