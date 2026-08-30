# Intelligence Warehouse — Consumer Audit

**Date:** 2026-08-29
**Scope:** Trace all 7 real product surfaces (AI Search, AI Articles, Events, Company Intelligence, Newsroom, Ripple, Opportunity Radar) through actual code — current source, real Warehouse availability, gap, migration complexity. Read-only audit, no code changes in this batch. Followed by a real, chosen first consumer (AI Article V2 Phase A, separate report).
**Branch:** `integration/warehouse-company-master`

## Method

7 parallel research agents, each tracing UI → API → service → query/retriever → DB tables/external sources → LLM (if any) → fallback, with real file:line citations required for every claim.

## Consumer matrix

| Consumer | Current source | Warehouse available? | Real gap found | Migration complexity |
|---|---|---|---|---|
| **AI Search** | `Event`/`GovernmentPolicy`/`NewsArticle` (legacy tables); entity matching via hardcoded `_NSE_UNIVERSE` (~510 rows) | No — zero references to `raw_evidence`/`evidence_entity_links` anywhere in `ai_search/` | A second, independent company-identity system running parallel to the Warehouse's resolver; `company_announcements_service` duplicates NSE-filing ingestion the Warehouse already does | Medium — matching logic used by many downstream files, but callers expect a flat symbol list, so the resolver swap is plausible without reshaping callers |
| **AI Articles** (deep-dive) | `EventTriage`/`Event` for selection; LLM-guessed companies validated against the same `_NSE_UNIVERSE`; one real number (today's price move) grounds anything | No — zero references in `aipe/`, `ai_pipeline/`, `ai_search/` to any Warehouse table | **None of the 11 real generation stages are Warehouse-grounded.** Real fact-grounding check exists but ships shadow-mode, blocks nothing | Medium — chosen as the first real consumer; see Phase A report |
| **Events** | Real `Event` ingestion (`ingest_tasks.py`) fed by the *same* provider fetch call that also writes `raw_evidence` | Partially, structurally — same source, disconnected destination | Real, confirmed duplication for NSE/RBI/PIB/SEBI/Fed: one fetch, two independently-deduped tables, no join between them | Medium — capture already shared; the harder part is migrating 20+ real downstream consumer files off flat `Event.companies` strings |
| **Company Intelligence** | `AICompanySignal` ← `IntelligenceArticle` ← `RawEvent.origin` (free-text label) | No | Provenance chain breaks at a string label — no ID ever links a signal back to the document that produced it, despite both pipelines sharing the same 6 providers | Medium — 3-4 files, no new ingestion needed, just an ID reference added at 3 points |
| **Newsroom** | `IntelligenceArticle` (same table as AI Articles — Newsroom *is* that surface) + a separate legacy RSS pipeline (`news_articles`/`news_worker.py`) hitting the *same* real feed URLs the Warehouse's RSS provider already captures | No | Two real, disconnected RSS pipelines fetching identical sources; `IntelligenceArticle` has zero evidence/provenance linkage | Medium — the AIPE-generation gap is the same one Phase A addresses; the legacy RSS duplication is a separate, real cleanup item |
| **Ripple / Intelligence Graph** | `IGNode`/`IGEdge`, populated by (a) ~90 hand-authored nodes/~150 hand-authored edges with hardcoded confidence values, (b) event-triggered auto-add with a bare, unlinked `source_event` string, (c) Development-linked via a different, older evidence abstraction | No | Most of the graph (the seeded majority) has **no real evidence backing at all**, despite the Company Ripple tab's own code describing it as "evidence-backed" — that claim is aspirational relative to what's actually stored | Medium-large — schema change is small, but NSE-only Warehouse coverage means most seeded edges (sectors/themes/commodities/policies) would stay unbacked regardless; a real evidence→edge derivation pipeline is new logic, not a migration |
| **Opportunity Radar (V1+V2)** | `Development`/`DevelopmentEvidence`, sourced from 6 normalizers reading the same legacy tables (`Event`, `CompanyAnnouncement`, `NewsArticle`, `AICompanySignal`, `Opportunity`) — never `raw_evidence` | No | Same real duplication pattern as Events (pre- vs. post-normalize capture of the same source item); a **third**, independent ticker-string-based company-identity scheme (graph-node matching), not the resolver | Medium — clean seams (6 normalizers in one file), but real quality gain judged not urgent; V2's evidence model is internally sound, just built on ungoverned/duplicated raw capture |

## What this demonstrates

The Warehouse's `raw_evidence`/`evidence_entity_links` (1,008 rows / 533 real links, NSE-only) sits **parallel to, not underneath**, every one of the 7 real consumers today — populated by the same provider fetches most of them already use, but read by none of them. The real problem is not "the Warehouse doesn't have data" — it's that **every consumer independently re-derives its own evidence/identity path**, producing at least three separate, unreconciled company-identity schemes (the canonical resolver; the hardcoded `_NSE_UNIVERSE` list used by AI Search and AI Articles; the ticker-string graph-node matching used by Opportunity V2/Ripple) and at least two real instances of the same raw source item being captured twice into disconnected tables (Events, Opportunity Radar).

## Decision: first consumer

**AI Article V2**, given the real, observed Search-impression decline and the audit's finding that this consumer has the cleanest, highest-leverage gap (raw material already captured, zero retrieval, one real number grounding everything else). Full implementation: `artifacts/ai_article_v2_phase_a_evidence_grounding.md`.

## Explicitly not started

Migrating any of the other 6 consumers, expanding evidence linkage beyond NSE (RSS/RBI/PIB/SEBI/Fed remain unresolved by design), and reconciling the 3 separate company-identity schemes found — each a real, scoped follow-up once AI Article V2's Phase A quality gain is confirmed on more real cases.
