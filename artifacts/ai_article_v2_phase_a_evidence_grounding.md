# AI Article V2 — Phase A: Evidence Grounding Foundation

**Date:** 2026-08-29
**Scope:** First Warehouse consumer, chosen after a real 7-consumer audit. Phase A only — retrieval foundation + shadow-mode demonstration. No production switch, no mass regeneration, no SEO/title redesign, no score integration.
**Branch:** `integration/warehouse-company-master`

## How this consumer was chosen

A real, parallel 7-agent audit traced AI Search, AI Articles, Events, Company Intelligence, Newsroom, Ripple, and Opportunity Radar through actual code (not assumptions) to determine current source → Warehouse availability → gap → migration complexity. Headline findings across all seven:

- **Events** and **Opportunity Radar** both independently re-capture the *same* real source items the Warehouse already captures, via a separate pre-Warehouse pipeline with its own dedup key — real, confirmed duplication, not distinct data.
- **AI Search** resolves companies via a completely separate, hardcoded ~510-entry list (`app.api.companies._NSE_UNIVERSE`), never the canonical `company_entities`/resolver the Warehouse's own `EvidenceEntityLink` is built on — a real architectural inconsistency.
- **Company Intelligence**'s provenance chain breaks at `RawEvent.origin`, a free-text source label with no ID back to the actual document — a real, closeable gap.
- **Ripple**'s graph is mostly hand-authored with hardcoded confidence values, not evidence-backed at all, despite the Company Ripple tab's own code claiming otherwise.
- **Newsroom** *is* the AI Articles surface (same `IntelligenceArticle` table) and separately still serves a legacy, duplicate RSS feed shadowing the Warehouse's own RSS capture.
- **AI Articles** (deep-dive): **zero of the 11 real generation stages are Warehouse-grounded.** Company selection is LLM-guessed then validated against the same hardcoded 510-entry list AI Search uses. Only one real number (today's price move) grounds any article; everything else — revenue/valuation claims, causal reasoning, ripple mechanisms — is free-text LLM narrative. The one real fact-grounding check that exists (`fact_grounding.py`) ships in shadow/log-only mode and blocks nothing.

Given the real, observed decline in Search impressions, **AI Article V2 was chosen as the first Warehouse consumer** — the Warehouse already captures the raw material AIPE's own triage consumes in parallel; the gap is purely that nothing retrieves it.

## What was built

- **`read_service.get_evidence_for_entity(db, entity_id)`** — the exact method this file's own docstring named as the next step once `EvidenceEntityLink` existed. Real, linked evidence only; zero links returns an empty list, never a fuzzy fallback.
- **`article_evidence_bundle.ArticleEvidenceBundle`** — resolves a company through the **real canonical resolver** (`resolve_entity_by_any_symbol`, the same one `EvidenceEntityLink` itself is built on) — never the hardcoded `_NSE_UNIVERSE` list AIPE currently uses for the same job. Assembles real linked evidence, a real live price move (reused verbatim from `fact_grounding.py`), and real verified historical context (reused verbatim from `market_story_engine.py` — kept as-is, not replaced; expanding historical context to Warehouse memory is a later pass, not Phase A).
- **`marketripple_score` field: always `None`.** Two real reasons, both disclosed rather than worked around: the owner's explicit instruction that AIPE must never receive an internal, not-yet-publishable score while S5-E runs — and eventually only through the same public-projection boundary S5-C established, never a raw snapshot; and the plain fact that `marketripple_score` doesn't exist at all on this branch (`integration/warehouse-company-master` and `company-identity/c1-reconciliation` diverged well before either's recent work — confirmed via `git merge-base`).
- **`compose_what_happened_from_evidence()`** — code-composed, never a second LLM call, mirroring the pattern the audit found and praised in `comparison_publisher.py`. States only what the real linked evidence says (title, source type, real published date, real price move) — no interpretation, no invented numbers. Returns `None` (never a fabricated placeholder) when there's no real evidence to compose from.
- 3 new real DB-backed tests: resolves + includes real linked evidence, unresolved symbol returns an honest empty bundle, resolved-but-zero-evidence never fabricates a "What Happened." Full relevant Warehouse/evidence test suite: 132/133 pass (1 pre-existing, unrelated failure — `test_development_historical_retrieval.py`, the same flaky test seen earlier this session on a different branch).

## Real, live demonstration

Ran the bundle builder against the two companies with confirmed real linked evidence (ICICIBANK, TCS):

**ICICIBANK** — grounded What Happened: *"On 24 August 2026, ICICI Bank Limited was the subject of an NSE regulatory filing: 'ICICI Bank Limited has informed the Exchange about disclosure under Regulation 30... priced USD 1 billion Senior Unsecured Fixed Rate Notes under the USD 7.5 billion Global Medium Term Note Programme... Moody's... assigned Baa3 and BBB rating...' ICICIBANK shares declined 1.4% on the day this was reported."* — every fact traces to the real filing and a real live price quote.

**Honest disclosure — no exact same-event article exists to fact-check against.** Checked directly against all 552 real published `IntelligenceArticle` rows: none cover the same real events as either linked evidence item. This is a same-*approach* comparison (fact-grounded extraction vs. free-text narrative), not a same-event fact-check — never presented as more than that.

**The comparison that *is* real and damning**: a real current AIPE article ("Adani Ports Boost Expected from Vizhinjam...") lists its `sources` field as `['MarketRipple Intelligence Engine', 'NSE India', 'BSE India']` — generic, non-traceable labels — while its actual `what_happened` text asserts specific, unverifiable numbers ("Axis Capital highlighted... roughly Rs 1,410 crore," named FII/DII net-flow direction) that trace to none of those three sources. This is exactly the LLM-fabrication pattern the audit diagnosed, now shown concretely side-by-side with what a grounded version looks like for a comparable real event.

## Phase A.1 — Evidence ranking + claim provenance structure (owner review, same day)

Phase A's own honest disclosure (TCS picking a generic "Bagging/Receiving of orders" filing over the more newsworthy same-minute Porsche press release) was treated as a real defect to fix, not a footnote.

- **`evidence_ranking.rank_evidence()`** — real, deterministic, explainable ranking. Never an LLM judgment call ("which filing looks most important?"), never a hand-assigned importance score. Combines a real, code-based NSE subject-line substantiveness classifier with real title/query-token overlap (Jaccard) against a trigger context — reusing `duplicate_detector.py`'s exact tokenizer/similarity function verbatim, the same mechanism the original 7-consumer audit already found and praised, never reimplemented. Recency is a tie-breaker only. Every ranked result carries its own real `reasons` list.
- The fix itself was non-trivial to get right: "Bagging/Receiving of orders" is a real NSE category, but a *bare* instance with no further real detail isn't more substantive than a press release with a real quoted title — that distinction, not a blanket keyword ban, is what the classifier encodes.
- **`Claim`/`claims_from_what_happened()`** — the initial claim-provenance structure from the owner's Phase B design, built now since it needs zero `FinancialFact` dependency. `FACT` claims cite real `evidence_ids`; the `INTERPRETATION` half waits for an actual reasoning stage (not yet built).
- 6 new tests (including the real TCS case verbatim as a regression test) + 2 existing bundle tests extended. Full relevant suite: 141/142 (same 1 pre-existing unrelated flaky failure).
- **Re-verified live**: re-ran the Phase A demo script — TCS now correctly ranks the real Porsche press release above the generic order filing. ICICIBANK unaffected (was already correct).

## Phase B — FinancialFact grounding (owner decision: Option 1, cherry-pick)

The branch-divergence blocker above was real (confirmed via `git merge-base`: `integration/warehouse-company-master` and `company-identity/c1-reconciliation` diverged before either branch's recent work). The owner's decision was **Option 1** — cherry-pick only the minimum read-only `FinancialFact`/quality dependency set onto this branch, explicitly excluding the scoring engine, publication policy, score UI, S5-E machinery, and any score recomputation code.

**What was cherry-picked, and nothing more:**
- `app/db/models/financial_fact.py` — copied verbatim from `company-identity/c1-reconciliation` (`diff` confirmed byte-identical). Zero cross-branch imports: only `sqlalchemy`, `datetime`, `app.db.base.Base`.
- The real `financial_facts` table + all **2,481 real rows**, copied directly via the `sqlite3` module (explicit column list, no ORM round-trip) from the Score branch's dev DB into this branch's own, separate dev DB.
- No scoring code, no `marketripple_score` package, no eligibility/publication logic came along — confirmed by construction (only one new model file was added) and by `git status` on this branch.

**The new read boundary — `read_service.get_verified_financial_context(db, symbol)`:**
- Returns a `VerifiedFinancialContext` (real `symbol`, `as_of`, and a list of `VerifiedFinancialFact` — each carrying `metric_code`, `metric_name`, `value`, `unit`, `fiscal_year`, `fiscal_quarter`, `period_type`, `source_document_url`, `quality_status`).
- Excludes `ANOMALY`, `IMPLAUSIBLE_SCALE`, and `SOURCE_DOCUMENT_QUARANTINED` rows via a **locally-redeclared** tuple of literal quality-status strings — deliberately not imported from the Score package, so this read-only Warehouse boundary carries no dependency on the scoring engine's own module.
- Keeps only the latest quality-passed value per `metric_code` (by fiscal year/quarter) — never a stale value when a newer real one exists.
- A symbol with zero rows, or whose only rows are bad-quality, returns a real, honest empty context (`has_real_facts=False`) — never a fallback estimate, never a fabricated placeholder.
- **The article pipeline never queries `FinancialFact` directly.** `ArticleEvidenceBundle.financial_context` is populated only through this one function — a quarantine decision made once (S4.5-B, on the Score branch) is honored here too, not re-litigated per-consumer.

**Claim provenance extended**: `claims_from_what_happened()` now emits one real `FACT` claim per verified financial fact (e.g. *"ICICI Bank Limited's real Gross NPA % was 0.0196 (pct) as of 2025 Q3"*). `evidence_ids=[]` for these — a `FinancialFact` row isn't a `raw_evidence` row, so there's no evidence ID to cite yet; that's an honest gap, not silently smoothed over.

**Real verification:**
- 2 real bugs found and fixed while building this: a missing `field` import (`NameError`), and a lazy function-body import of `FinancialFact` that silently broke the isolated pytest DB's schema-creation fixture (the model was never registered on `Base.metadata` before the fixture ran) while working fine against the real dev DB — fixed by moving the import to module level.
- 4 new real DB-backed tests for `get_verified_financial_context()` (real quality-passed facts surface; quarantined/implausible facts are excluded and produce an honest empty context when they're the only rows; zero rows also produce an honest empty context; a mix of good and bad-quality metrics surfaces only the good one). Full relevant suite: 13/13 passing (9 pre-existing + 4 new).
- **Real, live demonstration** (re-ran `wh_article_evidence_bundle_demo.py` against ICICIBANK, TCS, YESBANK): ICICIBANK's bundle now carries 14 real, quality-passed financial facts (CET1 Ratio, Gross/Net NPA, ROA, Deposits, Advances, etc.), each flowing through into a real `FACT` claim. TCS and YESBANK — including YESBANK, whose facts are real but the ones sampled were entirely quarantined/implausible on the Score branch — both correctly return `has_real_facts=False` rather than any fallback.

**Not yet built** (the remaining piece of the "Phase B GO" authorization): the constrained "Why It Matters" LLM reasoning layer with numeric-claim validation. That's real, separate engineering — a call reusing AIPE's existing `_call_with_fallback` infrastructure, prompted with the real evidence bundle (including `financial_context`), with a hard rule that any number in its output must match a number already present in the bundle or the output fails validation. Follows next.

## Status: Phase A.1 DONE, Phase B blocked on a real branch-divergence decision

The TCS ranking limitation Phase A surfaced (picking a generic "Bagging/Receiving of orders/contracts" filing over the more newsworthy same-minute Porsche press release) is fixed as of Phase A.1 — see the section above. Re-running the demo confirms TCS now correctly ranks the Porsche press release first.

## Explicitly not done in this batch

- No wiring into AIPE's actual production pipeline — `compose_what_happened_from_evidence()` is called only by the demonstration script.
- No `fact_grounding_enforce` flip to `True` — that check doesn't validate most of what an article claims (financial numbers, causal reasoning, risks/opportunities), so enabling it now would create a false impression of "grounded" without fixing the deeper retrieval gap.
- No `FinancialFact` integration (Phase B).
- No "Why It Matters" reasoning layer — that's LLM reasoning *from* the grounded facts, a distinct, later stage.
- No company-resolution swap inside AIPE's existing pipeline (only the new Phase A bundle uses the real resolver) — migrating AIPE's own `_NSE_UNIVERSE` usage is a separate, larger change.
- No touching of `BANKING_V1`/S5-E — kept on the completely separate `company-identity/c1-reconciliation` branch throughout.

(Phase A status superseded below — the evidence-ranking gap noted above was fixed the same day; see Phase A.1.)
