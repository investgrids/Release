# B.5 Iteration 2 — Gate 1 fixes + Gate 2 (event-specific evidence matching)

**Date:** 2026-08-30 (evening)
**Authorization:** owner approved exactly six items — aggregator-suffix stripping, replace the ad hoc stoplist with a systematic rule, proper-noun collision guards, iterative suffix stripping, build Gate 2, re-run the benchmark — with the explicit constraint "optimize precision, not coverage" and the Gate 2 invariant "same company ≠ same event."
**Branch:** `integration/warehouse-company-master` (`D:\ig-integration-wh-cm`). No production code touched, no backfill, no Article V2 wiring.
**Scripts:** `scripts/b5_entity_resolver_v4.py` (Gate 1), `scripts/b5_gate2_event_matching.py` (Gate 2), plus supporting dump scripts (`b5_dump_v4_single.py`, `b5_dump_v4_multi.py`, `b5_dump_v4_unlinked_sample.py`, `b5_dump_gate2_pass.py`, `b5_entity_resolver_v3_rerun.py`).

## Corpus note

The real RSS `RawEvidence` corpus grew from 594 items (original v3 benchmark) to 630 items (continued local ingestion in this worktree between sessions). All v3-vs-v4 comparisons below re-run v3's exact original logic against today's 630-item corpus (`b5_entity_resolver_v3_rerun.py`) rather than comparing against the old 594-item numbers, so the delta reflects the algorithm change only, not corpus drift.

## Gate 1 v4 — full census results

| | v3 logic (630-item corpus, re-run today) | v4 (this iteration) |
|---|---|---|
| Unlinked | 466 (74.0%) | 505 (80.2%) |
| Single-entity | 106 (16.8%) | 88 (14.0%) |
| Multi-entity | 58 (9.2%) | 37 (5.9%) |
| **Single-bucket precision (full census)** | 77.3%* | **98.9% (87/88)** |
| **Multi-bucket precision (full census)** | not separately re-censused this pass | **100% (37/37)** |
| **Combined linked-item precision** | ~78%* | **99.2% (124/125)** |

\* v3's 77.3%/22.7% figure is the original full-census result from the first benchmark (594-item corpus); the underlying resolver code is unchanged, so the same error classes apply to the 630-item re-run.

**Every single item in both the single-entity (88) and multi-entity (37) buckets was individually reviewed against real title+summary text** — a full census, not a sample, matching the original benchmark's methodology. Two multi-entity matches with truncated summaries ("AU Small Finance Bank, Aditya Birla Capital..." and "Ather Energy, Nazara Technologies...") were verified against their full untruncated text before being counted correct.

## What each fix did, with real before/after evidence

1. **Aggregator-suffix stripping** — extended beyond the original title-only design after the census found Google News RSS actually wraps the byline in a separate `<font color="#6f6f6f">{Publisher}</font>` span inside the *summary*, not a trailing title dash. Closed 5 of the first census's 10 wrong matches ("NDTV" firing on holiday-schedule stories that were never about NDTV).
2. **CompanyAlias matching made case-sensitive** — real data showed every `CompanyAlias` row is an uppercase scrip-style code ("STANLEY", "20MICRONS"), not a natural-language alias. This closed the "Stanley inside Morgan Stanley" false positive as a side effect, without a hand-added guard.
3. **Single-word `company_name` matches excluded** (multi-word only; symbols unaffected) — removed every one of v3's 18 generic-English-word false positives (persistent, deep, rain, spectrum, clean, advance, suraksha, affordable, gopal, take, total, race, shree, rishabh, oil, dollar, retail, worth, shah) in one shot. Real, accepted recall trade: single-word-named companies (Nuvama, Zaggle, Meesho, Swiggy, Siemens, Vedanta, Wipro, IndiGo, and ~30 others) are no longer reachable via name text, only via their ticker symbol.
4. **Proper-noun collision guard** — "Bank of India" correctly rejected when preceded by "Reserve" (confirmed working on a real "Reserve Bank of India policymakers..." sentence).
5. **Iterative legal-suffix stripping** — found and fixed a real interaction bug during the review: iterating "Corp"/"Corporation"/"Company" as disposable suffixes reduced real 2-word short-forms ("Welspun Corp", "Urban Company") to a single word that fix 3 then correctly-but-unintentionally dropped. Added a narrow guard (only for these 3 ambiguous tokens, never "Limited"/"Ltd"/"Inc"/"plc") so these tokens aren't stripped below 2 words. Recovered 3 real, previously-lost matches with zero new false positives.
6. **Also found and fixed during the census** (extensions of the same approved classes, not new mechanisms): a Reuters wire-dateline tag ("GLOBAL-FOREX/") colliding with a real alias literally spelled "GLOBAL" — closed with a narrow regex guard on the same case-sensitive alias/symbol buckets, same principle as fix 1 (don't trust source-formatting artifacts).

## One new residual finding, deliberately NOT patched

**"ACC" (the cement company) collided with "ACC Men's Premier Cup" (the Asian Cricket Council)** in the final 88-item census — 1 wrong match, the only one remaining. This is a genuinely new false-positive class (a well-known *other organization* sharing an exact acronym with a listed company) outside all six approved fixes. Per the owner's explicit "don't tune thresholds" instruction and this workstream's own earlier finding that ad hoc pattern-list growth doesn't converge, this was reported honestly rather than hand-patched with a one-off guard.

## Recall spot-check (40-item random sample of the 505 unlinked items)

Zero clear new false negatives. All correctly-unlinked items were either genuinely company-free (macro/politics/sports/weather news) or fell into already-documented, accepted categories: 2 pre-IPO companies not yet in `CompanyEntity` (a real data-model boundary), one generic ambiguous "Bajaj" brand reference (correctly unlinked — Bajaj Group has 4+ distinct listed entities), one "SBI" abbreviation not yet in the alias table (a pre-existing coverage gap, not a new regression).

## Gate 2 — event-specific evidence matching (built for the first time this iteration)

Real code (`b5_gate2_event_matching.py`) against real data: the 619-row `EvidenceEntityLink` table (NSE evidence already linked to `CompanyEntity` via `resolution_method="source_symbol"`) and the 632-row NSE `RawEvidence` corpus, whose real structured `desc` field (a genuine SEBI LODR disclosure taxonomy — "Bagging/Receiving of orders/contracts", "Dividend", "Acquisition", etc., extracted from the real distribution) drives category classification, with a keyword fallback for vague/`None` desc values. Both sides classify into the same fixed taxonomy; a ±5-day date window narrows candidates (support only, never sufficient alone, per the owner's instruction); 2+ same-category candidates trigger a token-overlap tiebreak, and an inconclusive tiebreak rejects rather than guesses.

**Run against Gate 1's 88 real single-entity-linked RSS items:**

| Outcome | Count |
|---|---|
| PASS (event confirmed) | 3 |
| FAIL — no same-category NSE evidence in window | 44 |
| FAIL — RSS category undetermined | 41 |

**All 3 PASS cases hand-verified against the real matched NSE filing text — 3/3 genuinely correct, zero known wrong-event matches:**
- ICICI Bank's $1B bond-pricing RSS story → matched the exact real NSE filing announcing that same $1B note pricing.
- Hindustan Copper's government-OFS story (2 separate RSS items reporting the same real event) → both matched the exact same real NSE OFS filing.

**Spot-checked why the real HDFC Bank CEO-exit cluster (7 RSS items, correctly classified `management_board`) all FAIL**: not a Gate 2 logic defect — a direct query confirms `cmp_fbbe116f6999` (HDFC Bank) has **zero** NSE evidence linked via `EvidenceEntityLink` at all in the current corpus. Gate 2 correctly refuses to fabricate a match when no real evidence exists for that entity, rather than loosening the category/window requirement to force a hit — exactly the design's intent.

**Acceptance-bar assessment**: the owner's hard rule — "zero known wrong-event matches" — is met on the observed PASS set (3/3 verified correct). Recall is intentionally very low (3/88 = 3.4%), driven mostly by real NSE-evidence-coverage gaps in the current corpus snapshot (`EvidenceEntityLink` only covers 376 of ~2,500+ real entities) rather than Gate 2's classification logic. Improving recall (broader `desc` mapping, richer keyword taxonomy, more complete NSE linkage) is real future work, explicitly not chased this pass.

## Iteration 3 (same evening) — multi-entity Gate 2 + failure-cause audit + demonstrated-only fixes

Owner authorized three specific pieces of follow-up: run Gate 2 independently per entity across the multi-entity bucket, audit the 85 single-entity failures into root causes before touching the algorithm, and extend the taxonomy only where the audit demonstrates a real miss. Scripts: `b5_gate2_multi_entity.py`, `b5_gate2_failure_audit.py`, commit on `integration/warehouse-company-master`.

### Multi-entity Gate 2 — per-entity independence, not per-story

`b5_gate2_multi_entity.py` reuses `run_gate2_for_item()` unchanged, calling it once per entity within each multi-company story rather than once per story — a multi-company story never gets a single blanket verdict.

Run against Gate 1's 37 multi-entity stories (104 per-entity checks): **1 PASS, 103 FAIL**. The PASS case (ICICI Bank's $1B bond pricing, hand-verified against the real matching NSE filing — the same real event also confirmed in the single-entity bucket from a different RSS source) sits inside a real **mixed-verdict story**: *"ICICI raises $1 billion, Union Bank $600 million through dollar bonds"* — `ICICI Bank` → PASS, `Union Bank of India` → FAIL, `UCO Bank` → FAIL, all three within the same story. This is direct, real proof the per-entity independence requirement does actual work, not just a theoretical safeguard: two of the three genuinely-mentioned companies in that story get zero fabricated evidence just because their sibling company had a real, confirmed filing.

### Failure-cause audit (single-entity bucket, `b5_gate2_failure_audit.py`)

Every one of the original 85 failures was traced to a specific, checkable root cause *before* any algorithm change:

| Root cause | Count | What it means |
|---|---|---|
| `rss_category_undetermined` | 41 | RSS text didn't classify into any category |
| `no_nse_evidence_at_all` | 33 | Entity has **zero** `EvidenceEntityLink` rows, period |
| `category_mismatch_in_window` | 11 | Real linked evidence exists nearby in time, but its category ≠ the RSS item's category |

Hand-reviewing each bucket found the large majority are **correct rejects, not bugs**: most `rss_category_undetermined` items are genuinely category-less content (pure price-movement listicles, analyst-recommendation round-ups, sports content) where "undetermined" is the right answer; most `category_mismatch_in_window` items have real nearby NSE evidence that is genuinely a *different* disclosure (e.g. a routine "Trading Window closure" notice sitting near an IPO-listing story) — the specific filing the RSS item describes just isn't linked yet, which Gate 2 is correctly refusing to fabricate.

**4 real, demonstrated fixes found and applied** (all traced to a specific failing case, nothing speculative):
1. Added `sue(s/d)|lawsuit|allegation` to `regulatory_compliance` — the real *Urban Company v. Kent RO* lawsuit story was undetermined without it; it now correctly PASSES against the exact real NSE "Regulation 30" disclosure of that same lawsuit.
2. Added `usfda|fda|inspection` to `regulatory_compliance` — 2 real Aurobindo Pharma USFDA-inspection stories were undetermined without it.
3. Broadened `fundraising_debt` to include `listing debut|shares list at|market debut|listing date` (and `allotment`→`allot` to also catch "allotted") — several real IPO-listing-debut stories (Lalithaa Jewellery Mart, Horizon Industrial Parks) never used the literal word "IPO" in their own text.
4. **Removed the bare `management` keyword from `management_board`** — it was a real, demonstrated false trigger: *"TCS To Acquire Porshce Arm MHP **Management**"* misclassified as a management-change story purely because the acquired subsidiary's own legal name contains the word "Management," when it's genuinely an acquisition. The category's other keywords (ceo/cfo/director/resign/appoint/board/chairman/kmp) already cover real management-change language without this generic trigger.

### Result of the 4 fixes — re-run, re-verified

Single-entity Gate 2: **PASS went from 3 → 6, FAIL from 85 → 82.** All 6 PASS cases hand-verified against their real matched NSE filing text — **6/6 genuinely correct**, including the TCS/MHP acquisition (now correctly matched to the real "Acquisition" filing) and the BLS International visa-allegations story (matched to an NSE filing that is textually near-identical to the RSS story). Combined with the 1 multi-entity PASS, **7/7 total confirmed matches are genuinely correct — zero known wrong-event matches, maintained**.

Re-running the failure audit after the fixes: root causes shift to **38 no-evidence / 32 undetermined / 12 mismatch** (82 total) — `no_nse_evidence_at_all` is now the *largest* single bucket (46%), reinforcing that **NSE evidence coverage, not matching logic, is now Gate 2's dominant recall constraint**. `EvidenceEntityLink` currently covers only 376 of ~2,500+ real entities.

### Explicitly not done this pass

- No semantic/fuzzy matching introduced — every fix above is a literal keyword addition traced to a specific real failing case.
- No threshold tuning to inflate the 6/88 or 1/37 numbers — recall stays low and is reported as-is.
- Multi-entity failures (103) were not individually root-cause-audited this pass (only single-entity was, per the explicit ask) — a natural next step if multi-entity recall becomes a priority.
- The "ACC" acronym-collision class remains unpatched. Worth noting: because Gate 2 independently classifies "ACC Men's Premier Cup 2026..." as `rss_category_undetermined` (no describable corporate event), it would **never have produced a wrongly-grounded article anyway** — the two-gate architecture already contains that specific Gate 1 error.
- No `EvidenceEntityLink`-style writes for RSS evidence, no backfill, no Article V2 wiring — still zero.

## Conclusion

Gate 1's real, full-census precision moved from 77.3% (v3) to 99.2% (v4, 124/125). Gate 2 now exists as real, tested code, runs independently per entity (proven via a real mixed-verdict story), and — after 4 fixes traced to specific demonstrated failures, not guesses — has **7/7 hand-verified correct matches, zero known wrong-event matches**, at low but now better-understood recall (6/88 single, 1/37 multi). The dominant remaining constraint is real NSE evidence coverage (`EvidenceEntityLink`), not matching quality — B.5's next real lever is likely a separate coverage-expansion workstream, not further precision tuning. **Still not ready for backfill.**
