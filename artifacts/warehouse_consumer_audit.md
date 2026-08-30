# Intelligence Warehouse — Consumer Audit

**Date:** 2026-08-29
**Scope:** Real code trace of all 7 real product surfaces (AI Search, AI Articles, Events, Company Intelligence, Newsroom, Ripple, Opportunity Radar) — current source → Warehouse availability → gap → proposed Warehouse source → migration complexity → expected quality gain → priority. Every finding below traces to real file:line citations from 7 parallel Explore agents reading `integration/warehouse-company-master`.
**Branch:** `integration/warehouse-company-master` (code); does not touch `BANKING_V1`/S5-E in any way.

## The cross-cutting pattern (read this first)

Before the per-consumer matrix, three real, recurring architectural facts explain almost everything below — they aren't 7 separate problems, they're the same 2-3 structural gaps showing up in 7 places.

**1. Three independent, unreconciled company-identity mechanisms exist side by side:**
- `company_entities` (2,557 rows, canonical Company Master) + `resolve_identifier()` — used **only** by `EvidenceEntityLink` and the Company Identity C1-C5 work.
- A **hardcoded, hand-maintained Python list**, `_NSE_UNIVERSE` (512 entries, `app/api/companies.py:43`) — used by AI Search's entity extraction, AIPE's article-company resolution, and company-score aggregation.
- **Ticker-string equality matching** against `IGNode.ticker` — used by the Ripple graph and Opportunity V2's identity anchoring.

These never reconcile. A company can resolve differently (or not at all) depending on which of the 7 surfaces is asking.

**2. The Warehouse is a real, populated, parallel ledger — not yet a read source.** For NSE/RBI/PIB/SEBI/Fed, the exact same `BaseProvider.fetch_and_normalize()` call that feeds every legacy table (`Event`, `CompanyAnnouncement`, `NewsArticle`, `RawEvent`) **also** writes a `raw_evidence` row, contemporaneously, via `capture_raw_evidence()`. This isn't a second, disconnected pipeline that would need new ingestion — it's the *same* fetch, fanned out to two destinations. `raw_evidence`'s own module docstring states plainly: "No consumer reads this table yet." That sentence is confirmed true across all 7 audits.

**3. Where the chain is closest to fixed, it breaks at a string, not a missing pipeline.** Company Intelligence's `AICompanySignal → IntelligenceArticle → RawEvent.origin` chain is real, traceable, and already flows through the same providers Warehouse captures — it just ends at a free-text label (`"Economic Times"`) instead of an ID. That's the cheapest real fix in this whole audit.

## Consumer matrix

| Consumer | Current source | Warehouse available? | Real gap | Proposed Warehouse source | Migration complexity | Expected quality gain | Priority |
|---|---|---|---|---|---|---|---|
| **AI Articles (AIPE)** | `EventTriage`/`Event` (LLM-derived company tags, resolved via `_NSE_UNIVERSE`); historical context from a separate curated table; **zero** structured facts beyond one live price-move signal | Populated in parallel, **zero** reads anywhere in 3 real pipelines (AIPE core, comparison, live signal) | No step in the 11-step generation chain is Warehouse-grounded (see deep trace below); `fact_grounding.py` exists, well-designed, but ships **shadow-mode, not enforced** | `read_service.py`'s own docstring already names the missing function: `get_evidence_for_entity()` — not yet built | Medium (one new retrieval function + prompt wiring + the company-resolution fix below) | **High** — directly addresses the stated Google-impression concern; real evidence text in "Why It Matters"/"What Happened" would be a genuine differentiator, not prose polish | **1** |
| **Company Intelligence (AI Score)** | `AICompanySignal` ← `IntelligenceArticle.sources` ← `RawEvent.origin` (free-text label, no ID) | Same providers capture `raw_evidence` at the same moment; chain just never stores the row ID | Provenance breaks at a string, not a missing mechanism — genuinely the cheapest real fix found | Add `raw_evidence_id`/`entity_id` at `RawEvent`/`IntelligenceArticle`/`AICompanySignal` creation, join via `EvidenceEntityLink` | **Small-medium** (3-4 files, no new ingestion) | Medium-high — closes a real, currently-invisible provenance gap for a score already shown on every Company page | **2** |
| **Events** | `Event`/`GovernmentPolicy`, deduped by provider item-id | `raw_evidence` captures the identical raw item, from the identical fetch call, for NSE/RBI/PIB/SEBI/Fed (not RSS, not BSE) | Real, confirmed duplication — same real-world item captured twice into two disconnected tables with independent dedup keys | Join `Event`/`raw_evidence` on a shared id; extend `EvidenceEntityLink` beyond NSE-only to cover RBI/PIB/SEBI/Fed (RSS already Warehouse-only, BSE already Event-only) | Medium (join key exists in principle; ~20+ real downstream consumers on `Event`'s flat `companies`/`sectors` strings make full migration a larger, product-wide rewrite) | Real, but consumers already work — this is architectural cleanup, not a currently-broken feature | 3 |
| **Opportunity Radar (V1+V2)** | `Development`/`DevelopmentEvidence` ← 6 normalizers reading the same legacy tables (`Event`, `CompanyAnnouncement`, `NewsArticle`, `AICompanySignal`, `Opportunity`) | Same duplication pattern as Events — pre-normalize capture (`raw_evidence`) vs. post-normalize capture (Development's source), same underlying items | V2 also runs a *third* independent company-identity scheme (ticker-string vs. `IGNode.ticker`), unrelated to the resolver | Reconcile the 6 normalizers' company resolution onto `entity_id`; join Development's evidence ancestry to `raw_evidence` where sources overlap | Medium | Real but not urgent — V2's own formation/scoring logic (deterministic, tiered coherence) is internally sound; this is a provenance/identity reconciliation, not a broken feature | 4 |
| **Newsroom** | `IntelligenceArticle` (same table AI Articles writes — Newsroom *is* the AIPE-article surface) **+** a separate legacy RSS pipeline (`news_articles`/`news_worker.py`) serving the homepage/sources page directly | `IntelligenceArticle`: none (converges with AI Articles above). Legacy RSS: `raw_evidence`'s `rss_provider.py` hits the **identical feed URLs** already | Two real gaps: (a) same as AI Articles for the main article content, (b) a genuinely separate, unconnected duplicate RSS ingestion feeding the homepage | (a) inherits AI Articles' fix; (b) redirect `news_worker.py`'s consumers to `raw_evidence`-backed RSS data, retire the duplicate fetch | Medium | Real — duplicate RSS fetching is pure waste once `raw_evidence` already has the same items with provenance | 5 |
| **AI Search** | `Event`/`NewsArticle`/`GovernmentPolicy` + live yfinance/VIX + `company_announcements_service` (a **third**, independent NSE-filing ingestion pipeline, separate from both `raw_evidence` and `Event`) | Zero — confirmed via grep, no reference anywhere in `ai_search/`, `ai_pipeline/`, or `ai_search_service.py` | Same company-identity fragmentation as AI Articles (`_NSE_UNIVERSE`, not `company_entities`); evidence aggregation is already broad (7+ real sources), so Warehouse's current NSE-only/533-link coverage is thin relative to what's already retrieved | Swap `entities.py`'s matching source for `resolve_identifier()`; **also** consider whether `company_announcements_service`'s independent NSE ingestion should collapse into `raw_evidence` (a 4th real duplication found, not originally in scope) | Medium (matching logic is centralized, but `_NSE_UNIVERSE`'s sector/industry/cap/alias fields aren't a 1:1 mirror of `company_entities`) | Real but partial — coverage/consistency win more than a grounding-depth win, since evidence is already broadly aggregated here | 6 |
| **Ripple / Intelligence Graph** | `IGNode`/`IGEdge` — ~90% hand-authored/manually seeded (hardcoded confidence floats, free-text descriptions written by an engineer), remainder auto-added with a bare string `source_event`, no FK | None — zero references to Warehouse tables anywhere in the graph code | The Company Ripple tab's own code comment claims "evidence-backed" — **that label is aspirational relative to what `IGEdge` actually stores.** No code path enforces or verifies it. | Warehouse should **feed** future edge construction (real evidence → new/refreshed edge with a real FK), not retroactively annotate the existing hand-seeded graph; seeded edges need an honest `provenance="curated"` marker instead | Medium-large — schema change is small, but building real evidence→edge derivation is new logic, and NSE-only coverage (533/1,008) means most of the ~150 seeded edges (which span sectors/themes/commodities/policies) would stay unbacked regardless | Real and important for trust (this is a live "claims real, isn't" gap similar to prior fabrication-audit findings this session), but architecturally the biggest lift and blocked on wider evidence coverage anyway | 7 |

## Deep trace: AI Article generation (AIPE core pipeline), step by step

Per your request for extra depth given the impression-decline concern. Three real, live article-generation pipelines exist (AIPE core / comparison pages / live signal enrichment), all scheduler-driven from `app/scheduler/scheduler.py`. Traced the primary one (AIPE core, `app/services/aipe/publisher.py`) end to end:

| Step | Classification | Real citation |
|---|---|---|
| 1. Trigger | REAL BUT OUTSIDE WAREHOUSE | `scheduler.py:301-308` — plain 300s interval trigger, unrelated to Warehouse cadence |
| 2. Source/event selection | REAL BUT OUTSIDE WAREHOUSE | `market_story_engine.py:96-170` reads `EventTriage`, never `raw_evidence` |
| 3. Company selection | LLM-DERIVED → resolved against a REAL BUT OUTSIDE WAREHOUSE static list | `triage_worker.py:49` (LLM guesses tickers) → `symbol_normalization.py:60` (`_NSE_UNIVERSE`, not `company_entities`) |
| 4. Facts/numbers | 1 real signal (outside Warehouse) + everything else LLM-DERIVED | `fact_grounding.py:44-65` (live price moves only); zero `FinancialFact` imports anywhere in `aipe/` |
| 5. Historical context | REAL BUT OUTSIDE WAREHOUSE | `market_story_engine.py:193-246` — a separate, hand-curated 24-event table |
| 6. Why It Matters / What Happened | LLM-DERIVED | `content_templates.py:44-45` — free-text schema fields, no per-claim source |
| 7. Title | Mostly LLM-DERIVED, FALLBACK override for one article type | `publisher.py:192-198` force-overwrites for `question_intelligence` only |
| 8. LLM prompt | Real inputs + LLM-DERIVED reasoning | `content_templates.py:38-71` — no evidence text, no citation IDs ever included |
| 9. Quality gate | REAL, but fact-grounding is shadow-mode | `publisher.py:207-215` — `settings.fact_grounding_enforce` defaults **False** |
| 10. Duplicate detection | REAL BUT OUTSIDE WAREHOUSE | `duplicate_detector.py:51-140` — solid 3-tier check, no Warehouse involvement |
| 11. Publication | REAL, code-determined | `publisher.py:356-357` |

**No step is Warehouse-grounded.** The gap isn't that the data doesn't exist — `raw_evidence`/`evidence_entity_links` are populated by the same providers, at the same moment, as the events AIPE triages. Nothing calls them.

**Recommended order (from the audit, not invented fresh):**
1. Flip `fact_grounding_enforce` to `True` — free, already built, currently inert.
2. Build `get_evidence_for_entity()` — the codebase's *own* docstring already names this as the next step (`read_service.py:6-13`) — and wire it into `article_generator.py`'s prompt construction for `company_intelligence`/`policy_intelligence` article types.
3. Migrate company resolution off `_NSE_UNIVERSE` onto `company_entities`/`entity_id`, so the Warehouse's real links have something real to join to inside the pipeline.

## Recommendation

Priority order above is derived from the real evidence gathered, not assumed going in: **AI Articles is the real, evidence-backed #1** — it's the only consumer directly tied to the stated business concern, it has the cheapest immediate win (flip a flag), and the codebase's own comments already mark the next real step. Company Intelligence is a close #2 — the smallest, most contained real fix in the whole audit. Everything else is real, worthwhile architectural debt, correctly not urgent.

**Do not migrate all 7 simultaneously.** Per the owner's own instruction: choose the first consumer, implement it, verify with real data, then move to the next.
