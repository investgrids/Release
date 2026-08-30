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

## Phase B — real blocker found, needs a decision before proceeding

The owner's Phase B design (`FinancialFact` grounding, a constrained "Why It Matters" LLM reasoning layer with numeric-claim validation) assumes `FinancialFact`/quality-quarantine data is reachable from this branch. **It is not.** Confirmed via `git merge-base`: `integration/warehouse-company-master` and `company-identity/c1-reconciliation` (where `FinancialFact`, the quality/quarantine system, and the MarketRipple Score all live) diverged well before either branch's recent work — the same real constraint already disclosed for `marketripple_score` in Phase A, now blocking Phase B's most substantive piece too.

Two honest paths, not decided here:
1. **Cherry-pick the read-only pieces** (`FinancialFact` model + `quality.py`'s quarantine/anomaly status, real DB tables) onto this branch so Phase B can *read* verified facts without needing the scoring engine itself.
2. **Wait for a real merge** of the two branches before building Phase B's `financial_context` — keeping the placeholder structure (`marketripple_score: None`, no `financial_context` field yet) until then.

Not implemented in this batch pending that decision. The "Why It Matters" reasoning layer (a real, constrained LLM call reusing AIPE's existing `_call_with_fallback` infrastructure, with a numeric-claim validator rejecting any number not present in the evidence bundle) is real, separate engineering that should follow once Phase B's data question is resolved — not built speculatively ahead of it.

## Status: Phase A.1 DONE, Phase B blocked on a real branch-divergence decision

**One real, honest limitation surfaced, not hidden**: TCS's grounded output picked a generic "Bagging/Receiving of orders/contracts" filing over a more newsworthy same-day Porsche AI-partnership press release, because both landed within the same minute and "most recent" isn't "most substantive." A real evidence-ranking heuristic (beyond recency) is needed before this becomes production-ready — noted as a genuine Phase A follow-up, not glossed over.

## Explicitly not done in this batch

- No wiring into AIPE's actual production pipeline — `compose_what_happened_from_evidence()` is called only by the demonstration script.
- No `fact_grounding_enforce` flip to `True` — that check doesn't validate most of what an article claims (financial numbers, causal reasoning, risks/opportunities), so enabling it now would create a false impression of "grounded" without fixing the deeper retrieval gap.
- No `FinancialFact` integration (Phase B).
- No "Why It Matters" reasoning layer — that's LLM reasoning *from* the grounded facts, a distinct, later stage.
- No company-resolution swap inside AIPE's existing pipeline (only the new Phase A bundle uses the real resolver) — migrating AIPE's own `_NSE_UNIVERSE` usage is a separate, larger change.
- No touching of `BANKING_V1`/S5-E — kept on the completely separate `company-identity/c1-reconciliation` branch throughout.

(Phase A status superseded below — the evidence-ranking gap noted above was fixed the same day; see Phase A.1.)
