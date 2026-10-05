# Step 3.4D-1 report: CC1 live rejection forensic

Source: the saved Step 3.4C artifact only (`../step3_4c/openai_qualification.json`). No provider call, no pipeline run, no change to AI Search, Gate A/B or production. The committed Gate B validators were re-applied unchanged to the saved generation and saved evidence index (`forensic.py`, `forensic.json`). No fuzzy or semantic matching was introduced and Gate B was not loosened.

## Verdict in one paragraph
The Gate B rejection was **correct under the committed contract**, and the integration is not defective (no class D finding). It is mostly **a model contract failure (A)**: the model claim-sourced one canonical copy of each fact but then restated the same supported facts in about a dozen other public fields, and Gate B requires every factual sentence in the answer prose to be covered by a claim. Three of the eight uncovered sentences are limitation statements the factual-sentence detector flags only because of a word match, which is a **narrow validator false positive (B)**. No rejected sentence is an unsupported claim (**C = 0**): every number and fact in the rejected text traces to the evidence. A real integrity concern was found elsewhere in the same generation (see Finding 2).

## Gate B reconciliation
Saved diagnostics: `claim_not_in_answer`, `uncovered_factual_sentences`; 12 factual sentences, 6 claim_sources entries, 0 unsupported figures or dates (re-confirmed). Validator re-run: 5 claims OK, 1 problem, 8 uncovered sentences.

### The six claim_sources entries
| # | Claim (model) | Cited | Sources support it? | In answer verbatim | Result |
|---|---|---|---|---|---|
| C0 | TCS P/E 15.1, P/B 6.85 vs Infosys P/E 13.3, P/B 4.54 | C1, C2 | yes (exact figures) | yes | OK |
| C1 | 52-week ranges (TCS 1976.8-3350.0, Infosys 980.4-1728.0) | C1, C2 | yes | yes | OK |
| C2 | TCS press release dated 2026-10-01 "Best Buy s Global Capability Center..." | A2 | yes (title copied incl. source typo) | yes | OK |
| C3 | Infosys-Columbia University collaboration on 2026-10-01 | A3 | yes | yes | OK |
| C4 | "The supplied market news says RBI MPC policy, oil prices, and bond yields may drive the market this week" | N1 | yes | **no**: answer says "RBI MPC policy, oil prices, and bond yields are identified as market drivers this week, but their effects ... are not established" | `claim_not_in_answer` |
| C5 | "The supplied related event says US enterprise IT spending contracts for a second consecutive quarter" | E1 | yes | not verbatim (committed matcher still pairs it with an answer sentence) | OK |

### The twelve factual sentences
| # | Sentence (start) | Claim entry | Cited sources support it? | Validator | Class | Correct authorization result |
|---|---|---|---|---|---|---|
| 1 | "On the evidence available, Infosys is the stronger valuation-led choice ... P/E 13.3 vs TCS 15.1, P/B 4.54 vs 6.85" | none | numbers: yes (C1/C2) | uncovered | A | supported (derived comparison of sourced numbers); rejected only because unclaimed |
| 2 | "Infosys is stronger on the available valuation evidence, with a P/E of 13.3 and P/B of 4.54 versus TCS at 15.1 and 6.85" | none (best Jaccard 0.59 to C0) | yes | uncovered | A | supported; unclaimed restatement |
| 3 | "TCS is at P/E 15.1 and P/B 6.85, versus Infosys ..." | C0 | yes | covered | n/a | authorized |
| 4 | "TCS's 52-week range is ..." | C1 | yes | covered | n/a | authorized |
| 5 | "TCS disclosed a press release dated 2026-10-01 ..." | C2 | yes | covered | n/a | authorized |
| 6 | "Infosys announced a strategic collaboration with Columbia University on 2026-10-01." | C3 | yes | covered | n/a | authorized |
| 7 | "The direct comparison favors Infosys on both supplied valuation measures; the Best Buy and Columbia University announcements are company developments, but their financial impact is not available." | none | comparison supported; caveat is a limitation | uncovered | A/B: compound sentence unclaimed, and the "announc" word triggers the factual detector on the caveat half | supported |
| 8 | "US enterprise IT spending is reported to have contracted for a second consecutive quarter, but the company-specific impact is not quantified." | C5 covers the first clause only | first clause: yes (E1) | uncovered | A: claim merged with a caveat clause, so the sentence no longer matches the claim | supported |
| 9 | "The TCS Best Buy transition announcement and Infosys-Columbia ... are disclosed developments whose financial contribution can be assessed when company-specific evidence becomes available." | C2/C3 cover the disclosure fact | yes | uncovered | B: limitation statement flagged by word match ("announc"/"disclosed") | supported (no new fact) |
| 10 | "Lower supplied multiples Infosys's P/E of 13.3 and P/B of 4.54 are below TCS's 15.1 and 6.85, giving Infosys the evidence-based relative valuation edge." (key driver) | none (restates C0) | yes | uncovered | A | supported; unclaimed |
| 11 | "TCS is the higher-multiple comparator at P/E 15.1 and P/B 6.85; its Best Buy-related announcement is specific, but the financial effect is not available." (company reason) | none (restates C0) | yes | uncovered | A | supported; unclaimed |
| 12 | "Infosys has the lower supplied P/E at 13.3 and P/B at 4.54, supporting a relative valuation advantage rather than a conclusion about superior operating performance." (company reason) | none (restates C0) | yes | uncovered | A | supported; unclaimed |

Counts: A = 6 (1, 2, 8, 10, 11, 12), A/B = 1 (7), B = 1 (9), D = 0, C = 0. Sentences 3-6 passed. (The validator lists 8 uncovered sentences: 1, 2, 7, 8, 9, 10, 11, 12.)

### Are `claim_not_in_answer` and `uncovered_factual_sentences` paired paraphrase consequences?
**Only partly.**
- The model **copied 4 of 6 claims verbatim**, so it did not paraphrase wholesale. Exactly one claim (C4) was paraphrased and produced `claim_not_in_answer`; that is a genuine paired effect for that sentence only.
- The 8 uncovered sentences are **not** paraphrases of claim text (best Jaccard 0.12-0.59, only one above 0.5). They are additional factual-looking sentences the model never claim-sourced. The dominant cause is **redundancy across fields**: the same valuation comparison appears in `summary`, `bottom_line`, `what_happened`-area prose, `key_drivers`, `companies[].reason`, `risks`, `opportunities` and `ai_conclusion`, and the model claim-sourced it once.

## Payload structure and where the 6,379 completion tokens went
API artifact: `prompt_tokens 3,361`, `completion_tokens 6,379`, `reasoning_tokens 1,561`, `finish_reason stop`, latency 55.2 s, `max_completion_tokens 7,000` (91% used, little headroom).
- **Reasoning (hidden): 1,561 tokens (24%).** **Visible structured output: 4,818 tokens (76%)** = 22,248 characters (about 4.6 chars/token).
- The artifact gives no per-field token counts; per-field figures below are character shares of the 19,684 parsed characters (the rest is JSON syntax and key overhead), so token figures are estimates.

| Field | Chars | Share | Est. tokens |
|---|---|---|---|
| decision_intelligence | 6,953 | 35% | ~1,700 |
| monitoring | 1,657 | 8% | ~410 |
| decision_engine_v2 | 1,341 | 7% | ~330 |
| scenarios | 893 | 5% | ~220 |
| ai_conclusion | 791 | 4% | ~190 |
| claim_sources | 780 | 4% | ~190 |
| investment_verdict | 752 | 4% | ~185 |
| timeline_intelligence | 722 | 4% | ~180 |
| opportunity_risk_matrix | 710 | 4% | ~175 |
| companies | 547 | 3% | ~135 |
| key_drivers, risks, opportunities, sectors, timeline, insights, follow_ups | ~2,500 | 13% | ~620 |
| core prose (summary, bottom_line, what_happened, why_it_happened, immediate_impact, medium/long term, what_priced_in) | ~1,880 | 10% | ~460 |

About 90% of the visible output is structured decoration around about 10% core prose and 4% claim_sources. Roughly a third is `decision_intelligence`, which this question's evidence cannot support in detail. This is where the 55 s latency and the 91% token headroom use come from.

## Was the saved evidence sufficient for the comparison the model attempted?
Saved bundle: 11 index items: 1 event (E1: US enterprise IT spending contracts), 1 news item (N1: generic RBI/crude/yields), 6 announcements, 3 context items (valuation lines for TCS and INFY, plus a generic MIE market line about a Metals & Mining theme).
- Announcements: A1 "Schedule of meet" (administrative), A2 TCS press release about a Best Buy capability-center transition (substantive but a PR item with no figures), A3 Infosys-Columbia collaboration (PR item), A4 "Investor Conference" (administrative), A5 allotment of 175,865 shares (administrative), A6 change in management (minor). No results, growth, margins, cash flow, order book, ROE, price momentum or any quantified operating data for either company.
- **Gate A was right to allow it** under its committed definition (valuation or filings for each side), and the model's hedged output shows it understood the limits.
- **It was not sufficient for what the question asks.** "Which is stronger?" is a business-strength comparison; the evidence supports only a narrow valuation-multiple comparison (P/E, P/B, 52-week range) plus two PR-type developments. The model said so itself ("a durable ranking requires comparable growth, margins, cash flow..."). So Gate A's "sufficient" means "enough for a valuation-multiple statement", not "enough for the question". I did not change Gate A.

## Finding 2 (separate, more serious): authorized-looking answers can carry ungrounded verdicts
Gate B does not read structured numeric/label fields, only prose strings. This generation, despite hedged prose ("evidence is insufficient to declare it fundamentally stronger"), contains: `investment_verdict` rating "Selectively Constructive", direction "bullish", confidence 69, horizon "12-18 months", top_picks, `scenarios` probabilities 30/50/20 with confidences, `impact_score` 58/50, key-driver confidence 86, and `ai_conclusion.current_view` "Positive". None of these is derived from any evidence item. Had the prose passed Gate B, a directional verdict and invented probabilities would have been published. This is an **unaddressed integrity gap** independent of the rejection; it shows the rejection was effectively protecting the user from it.

## Recommended smallest next change (not implemented)
1. **Prompt/contract change only, no Gate B change:** tell the specialist that each fact is stated once, as a verbatim claim_sources sentence, and that other fields (key_drivers, companies reasons, risks, opportunities, ai_conclusion) must not restate numeric/factual claims but refer to them without new facts or be left out; and that a limitation statement must not be a separate factual sentence. Re-run CC1 once (~10K tokens; about 96K remain in the project window) and compare the Gate B reasons.
2. **Before any live answer is shown as authorized**, decide (separately, with the owner) how to handle structured verdict/probability fields when evidence is valuation-only: the smallest deterministic form is to null `investment_verdict`, `scenarios` probabilities and `impact_score`/`confidence` unless an evidence-based rule supports them. This is the next integrity item, not a throughput item.
3. **Not recommended now:** loosening the sentence-claim match (for example "all numbers and entities appear in some claim"). That is the fuzzy/semantic route you ruled out, and it would also admit the redundant restatement problem.

Open questions for the owner: whether valuation-only evidence should be allowed to answer "which is stronger" at all, or only a narrower "how do their valuations compare" framing (a Gate A / question-type decision, not changed here).
