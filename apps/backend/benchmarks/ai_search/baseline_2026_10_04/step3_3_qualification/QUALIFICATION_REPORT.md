# Step 3.3: provider qualification. Result: 0/3, STOP (provider-capacity blocker)

Run 2026-10-04 (about 17:50 IST), `release/ai-answer-v2` at 1d476fc. Entity, retrieval, evidence-scope, premise-check and claim-source code frozen; no prompt, provider, filter, age limit or benchmark expectation changed. Real pipeline, real finalizer, real current specialist prompts and schema, the app's configured provider chain. No credential read or printed. Not pushed, not deployed. The 18-question live run was **not** started (hard gate).

## Result
| Question | Purpose | Specialist request | Outcome | Structured output | Degraded |
|---|---|---|---|---|---|
| CR2 3M India | zero-evidence honesty | ~2,300 input tokens (est.), max 6,500 out | **failed**: HTTP 429 on all 9 models tried (Groq 3, OpenRouter 6), 3.3 s | none | capacity |
| EI1 BEL order | unsupported user premise | ~2,450 est., max 6,500 | **never reached a provider**: all models skipped as `already_exhausted` | none | capacity |
| CC1 TCS vs Infosys | rich bundle + claim_sources | ~3,060 est., max 7,000 | **never reached a provider**: same skip | none | capacity |

**Full specialist successes: 0/3.** Pipeline-level calls made: 6 of the cap of 8. Provider/model of any successful full call: none. Raw output, `claim_sources`, `claim_validation` and a final answer do not exist for any of the three. `premise_check` and the evidence bundles do (EI1: unsupported premise, empty bundle; CR2: empty bundle; CC1: 8 items), but that is retrieval, not a model result.

## What the data does and does not show
- Confirmed: the one realistic specialist request that reached the network (CR2) was rejected with 429 by every model in the chain within 3.3 s. The market-pulse classifier request (about 200 tokens, 5 output tokens) sent just before it **succeeded on Groq** (717 tokens counted), so the provider was reachable for a tiny request and refused the specialist-sized one.
- Confirmed: EI1 and CC1 were **not independently attempted**. After CR2's 429s the service marks each model exhausted for a cooldown and skips it, so those two inherited the failure with 0 ms latency. The 0/3 therefore rests on one real failed request plus two cooldown skips, not three independent refusals.
- Not established: why the specialist request is refused (Groq per-minute or per-day token limits, OpenRouter free-tier daily cap seen earlier at about 14.7 h cooldown, or something else), whether the same limits apply to production (production logs on 4 Oct showed Gemini succeeding), and whether the local keys share quota with production. Hypotheses only.
- Not exposed by the AI service and therefore not captured: finish reason, separate input and output token counts (only a cumulative total and an estimate from prompt length).

## Decision
Per the gate: stop. No 18-question run, no prompt tuning, no retrieval change. The next engineering task is a bounded **provider reliability and capacity audit**, because the product under test cannot currently be evaluated. A reasonable first question for it: can the configured chain complete one specialist-sized request at all, from a fresh process, outside any cooldown, and what limit does it hit.

## Known debt recorded (not worked on)
- **Hypothetical macro-transmission questions route to `direct_company_research`** (MP2 "higher crude oil prices -> Indian markets", MP3 "weaker rupee -> Indian IT exporters"). Entities and evidence are fine; the ui_mode classifier needs a named policy. Leave until after the first live-answer run.

## Checkpoint
| Layer | Status |
|---|---|
| Entity grounding | GREEN, 18/18 (frozen) |
| Routing | PARTIAL, 16/18 (MP2, MP3 known debt) |
| Evidence coverage | acceptable for the live gate, 16/18 |
| Evidence scope | GREEN on the frozen set, irrelevant-evidence questions 10/18 -> 0/18 |
| Honest insufficient evidence | CR2 and EI1 deliberately retained |
| Premise verification | implemented, company and comparison questions only |
| Claim / source contract | fixture GREEN, live UNVERIFIED |
| Degraded response | GREEN, 18/18 |
| Real answer quality | UNVERIFIED |
| Provider capacity | BLOCKER |
| Release | NO-GO |

Files: `qualify.py` (the harness), `qualification.json` (every call, failure log and bundle).
