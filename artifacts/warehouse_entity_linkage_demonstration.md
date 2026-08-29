# Intelligence Warehouse — Entity Linkage Real-Data Demonstration

**Date:** 2026-08-29
**Scope:** Demonstrate the real, already-built `EvidenceEntityLink` chain (Source → RawEvidence → EvidenceEntityLink → Canonical CompanyEntity) for 5 named companies, using only real, already-persisted local data — no synthetic rows, no re-running the backfill.
**Branch:** `integration/warehouse-company-master`

## What already existed (verified, not assumed)

Real, substantial prior work was found already committed on this branch — commit `4453009`, "feat(warehouse): EvidenceEntityLink -- real evidence-to-entity linking, the audit's 'major unlock'" — built on top of a real merge of Company Master (`company-identity/c1-reconciliation`, commit `c8b358c`). This closes the gap the earlier Warehouse Consumption Audit found (RawEvidence had zero usable entity linkage — an id-scheme mismatch for NSE evidence, an always-empty companies field for RSS evidence).

**One correction to the working assumption going in:** the architecture actually built uses a direct, non-nullable `entity_id` FK straight into `company_entities` (via the real `resolve_identifier()` resolver — the same one AI Search's `entity_resolver.py` already uses), not a nullable dual-key staging table (`source_symbol`/`entity_hint` with `canonical_entity_id` filled in later). That staging design was the contingency for "Company Master not yet available in this environment" — since Company Master was already merged into this branch before `EvidenceEntityLink` was built, the simpler, direct-FK version was built instead. Scope, deliberately narrow: NSE only, `relationship_type="subject"`, `resolution_method="source_symbol"` — RSS/RBI/PIB/SEBI/Fed evidence stays entirely unlinked, not guessed at.

Real DB state (this branch's local dev DB): 1,008 `raw_evidence` rows, 2,557 `company_entities` rows, 533 `evidence_entity_links` rows already populated from a prior real backfill run. 10/10 existing tests pass.

## Real trace results, 5 named companies

| Symbol | Resolver status | Canonical entity | Real links found |
|---|---|---|---|
| **ICICIBANK** | resolved | `cmp_7044ee48aeaa` (ICICI Bank Limited) | **3** |
| **HDFCBANK** | resolved | `cmp_fbbe116f6999` (HDFC Bank Limited) | 0 |
| **TCS** | resolved | `cmp_5b80a6770abd` (Tata Consultancy Services Limited) | **3** |
| **RELIANCE** | resolved | `cmp_f4f2ba15a91b` (Reliance Industries Limited) | 0 |
| **TMPV** | resolved | `cmp_3b01032c0bbb` (Tata Motors Passenger Vehicles Limited) | 0 |

All 5 symbols resolve correctly to a real, unambiguous `CompanyEntity` — including **TMPV**, which correctly carries its real historical alias chain (`old_symbol=TATAMOTORS`, `old_symbol=TELCO`), confirming this trace reuses the exact same resolver the Company Identity C1-C5 work already validated, not a second matching scheme.

### Real, complete chains (ICICIBANK, TCS)

Every link traced to a real NSE filing with a real title and real timestamp — for example:

- **ICICIBANK** → real NSE filing `nse-106754594`, published 2026-08-24 18:26:46: *"ICICI Bank Limited... has today at 10:45 a.m. IST priced USD 1 billion Senior Unsecured Fixed Rate Notes under the USD 7.5 billion Global Medium Term Note Programme... Moody's Ratings and S&P Global Ratings have vide letters dated August 24, 2026, assigned Baa3 and BBB rati[ngs]..."*
- **TCS** → real NSE filing `nse-106754353`, published 2026-08-24 16:57:29: *"TCS and Porsche AG Partner to Accelerate the Future of AI-Powered Mobility"*

### The 3 zero-link cases — a real coverage gap, not a linking defect

Checked directly: **zero raw NSE evidence rows in this dataset carry `symbol`/`bm_symbol` equal to HDFCBANK, RELIANCE, TATAMOTORS, or TMPV at all.** This is a genuine data-coverage fact, not a resolver or linking failure — the real 1,008-row `raw_evidence` sample clusters around a single real ingestion window (2026-08-24), and not every large-cap company necessarily filed an NSE announcement that specific day. The linking mechanism itself is proven correct by the 3/3 successful real traces on ICICIBANK and TCS — if evidence existed for the other 3, the same deterministic `source_symbol` resolution would have linked it.

## What this demonstrates

The real chain **Source → RawEvidence → EvidenceEntityLink → Canonical CompanyEntity** works end-to-end on real data, for a real, deterministic subset (NSE filings with a resolvable symbol field). The zero-link cases are honestly explained by coverage, not silently glossed over. `TMPV`'s alias resolution confirms the linkage layer correctly reuses the canonical identity system, not a parallel one.

## Status

Entity linkage demonstration complete. Next real step per the owner's sequencing: the **consumer audit** — for each real MarketRipple product surface (AI Search, Articles, Events, Company Intelligence, Newsroom, Ripple, Opportunity Radar), determine current source → Warehouse source → migration needed → quality gain. Not started in this batch.
