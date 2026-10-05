# Step 3.4G.6 report: claims-as-observations (model-free)

Scope: output contract only. Gate A, Gate B, retrieval, ranking, routing and visibility are unchanged. Zero provider calls. Nothing pushed or deployed.

## Change
- The model emits `evidence.observations: [{"text", "sources"}]` once. It no longer writes `what_happened`.
- `schema.render_observations` (called in `flatten_nested`) renders `what_happened` from the observation texts and puts the same texts and sources into `claim_sources`. Exact (case/punctuation-insensitive) duplicates merge into one sentence with merged sources.
- Nothing is validated, repaired or dropped: wrong figures, unknown or missing sources, hidden-evidence dates and scope overreach flow through unchanged to Gate B. Entries with no text carry no claim and are not rendered.
- Synthesis (`summary`, `bottom_line`), limitations and other fields remain model prose. Factual sentences there still need their own `claim_sources` entry (or are caught as `uncovered_factual_sentences`). A model entry that repeats an observation is merged into it.
- A response without an `observations` list (older shape) passes through untouched.
- Prompts: `EVIDENCE_GROUP`, the comparison inline schema and `COMPOSITION_RULES` (1) and (3) updated; `CLAIM_SOURCES_GROUP` now describes claims for fields other than observations.

## Verification
- `test_ai_search_claims_as_observations.py`: 19 tests. Rendered once with identical sources; a model-written `what_happened` is not a second representation; listed-but-unwritten and written-but-unlisted impossible for 0/1/2/3/5 observations; duplicates merge; empty observations give an honest limited answer; unsupported figure, wrong source, no source, hidden-summary date, synthesis assertion and uncited factual sentence in another field all still fail Gate B.
- Mutation check: disabling the assembler fails 14 of 19.
- Replay of the saved SR2 g5 generation on its own evidence: before, Gate B rejected with `claim_not_in_answer` only; with the same ten claims emitted as observations, the ten claims are unchanged, all are written, Gate B authorizes with no reasons.
- AI Search selection: 690 passed, 3 xfailed (live-engine tests excluded as before).
- Caveat: the replay shows the mismatch cannot recur; it does not show the model's observation choices will be good on a new call (no further SR2 call, per plan).

## Status
3.4G evidence usefulness: GREEN subject to the above. Year-less-date xfail stays separate. Next: latency/reasoning-budget qualification.
