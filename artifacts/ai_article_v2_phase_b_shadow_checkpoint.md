# AI Article V2 — Phase B Shadow-Quality Checkpoint

**Date:** 2026-08-30
**Scope:** 20 real Warehouse events run through the full Phase B pipeline (ranked evidence → What Happened → FinancialFacts → Why It Matters → claims → numeric validation), manually reviewed for reasoning quality — not another correctness re-check of Phase B itself. No code changes made as a result of this checkpoint; no Phase B bug was found that would justify one.
**Branch:** `integration/warehouse-company-master`. Script: `scripts/wh_checkpoint_20events.py` (full raw trace: `wh_checkpoint_20events.log`, 844 lines, not committed — reproducible from the script).

## Selection method

20 symbols were chosen from real linked-evidence title keyword buckets (earnings/results ×3, orders/contracts ×3, partnerships/deals ×2, fundraising/debt ×2, regulatory/compliance ×2, management/board ×2, corporate actions ×2, M&A/investment ×2, other ×2), deliberately spanning strong evidence (HEG: 17 linked items), typical partial evidence (2-3 items, the majority of the sample), and sparse evidence (1 item: RATNAMANI, OIL, ASHIANA, MWL, MARATHON). Two events (UCOBANK, CANBK) were deliberately picked as Banking-sector cases to actually exercise `financial_context` — real data confirms `FinancialFact` coverage is Banking-only (`BANKING_V1` scope), so 18 of 20 non-bank events correctly show `available FinancialFacts: none` by design, not as a defect.

**Caveat on the uniqueness check**: the script's "recent published articles" lookup is a crude first-word-of-company-name substring match against recent headlines — good enough to surface an obvious pattern match (it caught URBANCO), but not a real same-event similarity check. A "none found" result here means "my crude check didn't catch anything," not "confirmed unique."

## 1. The 20-event result table

| # | Category | Symbol | Evidence | Financial facts | Classification | Notes |
|---|---|---|---|---|---|---|
| 1 | earnings_results* | HEG | 17 linked (3 used) | none (non-bank) | Factual update | *Top-ranked evidence was actually a board reshuffle (resignations/appointments), not earnings — a keyword-bucketing artifact of my selection script, not a Phase B defect |
| 2 | earnings_results | UCOBANK | 1 linked | 9 verified, 6 selected | **Full analysis** | Real CET1/NPA/ROA correctly cited, genuinely relevant to a board-meeting outcome |
| 3 | earnings_results* | MACPOWER | 2 linked | none (non-bank) | Factual update | *Also a management appointment, not earnings; correct but low materiality |
| 4 | orders_contracts | RATNAMANI | 1 linked | none (non-bank) | Factual update | Honest handling of a vague, sparse filing; correctly noted the order/price-decline divergence without inventing a cause |
| 5 | orders_contracts | KRYSTAL | 2 linked | none (non-bank) | Factual update | Weak/generic interpretation ("ongoing operational and regulatory activity") |
| 6 | orders_contracts | S&SPOWER | 2 linked | none (non-bank) | Factual update | Two unrelated real filings (postal ballot + order) stitched into one narrative |
| 7 | partnerships_deals | TCS | 3 linked | none (non-bank) | **Full analysis** | Coherent, well-grounded, matches Phase A/B's earlier TCS result |
| 8 | partnerships_deals | OIL | 1 linked | none (non-bank) | **Full analysis** | Specific, single clear event, well-grounded |
| 9 | fundraising_debt | CANBK | 2 linked | 9 verified, 6 selected | **Full analysis** | Real capital ratios directly relevant to a fundraising decision — the sample's clearest "financial context earns its place" case |
| 10 | fundraising_debt | ASHIANA | 1 linked | none (non-bank) | Factual update | Thin (single NCD payment filing), appropriately modest |
| 11 | regulatory_compliance | URBANCO | 2 linked | none (non-bank) | **Should skip** | Duplicate: 2 existing published headlines ("What Urban Company's Routine SEBI News/Disclosure Means...") match this same event; content itself is also low-value |
| 12 | regulatory_compliance | BHARATRAS | 2 linked | none (non-bank) | Factual update ⚠ | Recurring templated "SEBI Disclosure" headline pattern found for this company — flagged for a real duplicate check before publishing, not confirmed either way |
| 13 | management_board | CTE | 3 linked | none (non-bank) | Factual update | Honestly hedged ("without additional context... significance remains limited") |
| 14 | management_board | MWL | 1 linked | none (non-bank) | Factual update | Thin, appropriately modest |
| 15 | corporate_actions | GESHIP | 3 linked | none (non-bank) | **Full analysis** ⚠ | Good reasoning, but 2 of the 3 evidence items are the same real board-meeting notice from two feeds — within-bundle duplicate evidence |
| 16 | corporate_actions | NMDC | 2 linked | none (non-bank) | **Should skip** | Plain dividend record-date notice; reasoning manufactures significance ("signals commitment... bolsters confidence") from a purely administrative filing |
| 17 | mna_investment | SYNGENE | 2 linked | none (non-bank) | Factual update | Genuinely insufficient evidence detail (filing has zero specifics); correctly kept minimal rather than compensating with invention |
| 18 | mna_investment | COALINDIA | 2 linked | none (non-bank) | Factual update ⚠ | The 2 evidence items are a near-byte-identical duplicate (case-variant title) of the same real filing |
| 19 | other (surveillance query) | MARATHON | 1 linked | none (non-bank) | Factual update | Distinct event type (a pending exchange query, no news yet); well-calibrated uncertainty in the output |
| 20 | other (insolvency proceeding) | SIMBHALS | 2 linked | none (non-bank) | Factual update ⚠ | Real IRP (insolvency) context present in the evidence but under-explained in the output |

## 2. Failure-pattern summary

```
20 events
 5 -> full grounded article        (UCOBANK, TCS, OIL, CANBK, GESHIP)
13 -> useful factual update        (HEG, MACPOWER, RATNAMANI, KRYSTAL, S&SPOWER,
                                     ASHIANA, BHARATRAS, CTE, MWL, SYNGENE,
                                     COALINDIA, MARATHON, SIMBHALS)
 1 -> should skip: duplicate existing story           (URBANCO)
 1 -> should skip: no real value beyond the filing    (NMDC)
```

Cross-cutting quality flags observed within the 13 "factual update" cases (not separate buckets, but real patterns worth naming):

- **Weak/generic interpretation** (adds no real insight beyond restating the filing): KRYSTAL, mildly S&SPOWER.
- **Multiple unrelated real filings forced into one narrative**: S&SPOWER (postal ballot + order), BHARATRAS (SAST disclosure + Reg 30 disclosure), GESHIP (buyback + trading window).
- **Within-bundle duplicate evidence** (the same real filing linked twice, cited as if two independent facts): GESHIP, COALINDIA. This is an evidence-ingestion/linkage issue upstream of Phase B's own grounding logic, not a reasoning defect — flagged for a separate decision, not fixed here.
- **Under-explained materiality**: SIMBHALS's real IRP (insolvency) context existed in the evidence but wasn't foregrounded with appropriate weight.
- **Recurring template risk**: BHARATRAS's headline pattern ("What [Company]'s SEBI Disclosure Means...") appears to recur for this company — a real duplicate-content risk requiring a proper check, not confirmed here.

**On the specific question the owner asked — is `select_relevant_financial_facts()`'s heuristic good enough, or does event type need to drive selection?** This checkpoint did not produce a genuine mismatch case. Both real Banking events (UCOBANK, CANBK) happened to be inherently financial-themed (an earnings-adjacent board meeting; a fundraising decision), so the fixed "prefer NPA/CET1/ROA" heuristic looked relevant in both. **This is a gap in the checkpoint's own coverage, not a passed test** — the sample never included a Banking-sector event that is topically unrelated to financial health (e.g., a bank management change or bank M&A), which is the actual scenario that would expose whether the heuristic injects irrelevant ratios into an unrelated story. Recommend testing that specific scenario before concluding the heuristic is adequate.

## 3. Phase C requirements list (derived only from what was observed above)

1. **A "should this become an article at all" materiality gate, applied before Why It Matters runs.** NMDC and URBANCO show the reasoning layer will manufacture plausible-sounding significance from any input if asked — it does not reliably self-decline on its own. Some real, valid NSE filings (routine dividend record dates, generic administrative notices) are too immaterial to warrant a generated article regardless of how well-grounded the output is.
2. **Real duplicate/near-duplicate detection against already-published articles**, not just within-Warehouse evidence dedup. URBANCO shows a near-verbatim recent headline already exists for the same story. This checkpoint's own dedup check was a crude substring match — Phase C (or the scheduler audit that follows) needs the real thing, likely reusing `duplicate_detector.py`'s Jaccard machinery against recent published headlines rather than just against other raw evidence.
3. **Within-bundle evidence deduplication.** GESHIP and COALINDIA show the same real NSE announcement occasionally reaching `get_evidence_for_entity()` as two separate rows (one a case-variant, one a cross-feed restatement). This inflates apparent evidence count and produces redundant citations. Likely belongs in evidence ingestion/linkage rather than Phase C's article logic proper, but affects article quality and needs an owner decision on where it's fixed.
4. **Topical coherence in evidence selection**, not just top-3-by-substantiveness-score. S&SPOWER, BHARATRAS, and GESHIP show the current ranking sometimes selects 2-3 real but topically unrelated disclosures for the same company, forcing the reasoning layer to awkwardly connect them into one narrative. Phase C's event-aware context selection should consider whether selected evidence items are plausibly part of the same underlying story.
5. **Event-type-driven financial-fact relevance — genuinely untested here, not confirmed adequate.** Needs a dedicated follow-up check: a Banking-sector event that is NOT financially themed (e.g. a bank director resignation), to see whether the current heuristic's fixed NPA/CET1/ROA preference injects irrelevant ratios into an unrelated story.
6. **Materiality-aware emphasis for severity-bearing evidence.** SIMBHALS shows real, high-stakes context (an IRP/insolvency proceeding) present in the evidence but treated with the same even tone as a routine filing. Phase C may need either prompt structuring that flags severity-bearing NSE subject categories, or a materiality signal passed alongside evidence.
7. **An interpretation-quality floor for thin-evidence cases.** Several factual updates lean on generic boilerplate phrasing ("signals investor confidence," "reflects market sensitivity") that restates rather than illuminates. Worth considering whether thin evidence should produce a deliberately shorter factual note instead of a full paragraph padded with generic interpretive language.

## Explicitly not done in this checkpoint

- No Phase B code changes — no defect was found that met the "genuine software/data-integrity bug" bar the owner set; the within-bundle duplicate-evidence finding is flagged for a separate decision, not fixed unilaterally.
- No Phase C work started.
- No scheduler/publication-failure audit started (owner's next-listed step after this checkpoint).
- No production wiring, title/SEO work, or score integration.
