# MarketRipple Intelligence Brain — Phase 1A: Audit & Design

**Status: audit/design only, nothing implemented.** No schema changes, no new dependencies, no commits. Companion machine-readable artifact: `artifacts/intelligence_warehouse_phase1_before.json` (real, queried 2026-08-23 against the local dev DB).

---

## 1. BEFORE snapshot

**Database**: SQLite, `apps/backend/ig_dev.db`, **147,509,248 bytes (140.7 MB)**, 63 tables, **306,870 total structured records**. Per-table byte size is not measurable here — this SQLite build lacks the `dbstat` virtual table (confirmed live: `no such table: dbstat`); only the total file size is real. This is local dev scale, not production.

**Major intelligence counts** (all real, queried live):

| Table | Rows | Table | Rows |
|---|---|---|---|
| news_articles | 6,529 | opportunities (V1) | 128 |
| events | 3,035 | opportunities_v2 | 199 |
| event_companies | 189 | opportunity_v2_developments | 228 |
| developments | 1,137 | price_bars | 62,734 |
| development_evidence | 2,249 | index_memberships | 50 |
| ig_nodes | 1,805 | quant_research_predictions | 48,972 |
| ig_edges | 1,117 | quant_research_evaluations | 146,916 |
| prediction_records (legacy) | 6,974 | prediction_evaluations (legacy) | 8,361 |
| homepage_daily_snapshots | 17 | market_snapshots | **1** |
| company_intelligence_observations | 100 | company_announcements | 516 |

**Historical coverage** (real min/max, not estimated):

| Table | Depth | Note |
|---|---|---|
| price_bars | 2021-08-16 → 2026-08-17 (~5y) | Real, gap-checked depth |
| index_memberships | 2015-08-01 → 2025-03-28 | Sourced (Phase B0) |
| quant_research_predictions | 2021-09-24 → 2026-07-17 | |
| prediction_records | 2021-09-22 → 2026-08-22 | |
| developments / development_evidence | 2026-03-30 → 2026-08-23 (~5 months) | Genuinely new system |
| ig_nodes / ig_edges | 2026-07-12 → 2026-08-23 (~6 weeks) | Newer still |
| news_articles | 2026-06-28 → 2026-08-23 (via `created_at`) | see data-quality finding below |
| events | 2026-06-18 → 2026-08-23 (via `published_at`) | see data-quality finding below |
| market_snapshots | one single row, 2026-08-17 | |
| sector_data | one frozen moment, 2026-06-28 | not a time series at all |

**Source count**: ~18 distinct external sources actively wired (6 RSS feeds, NSE, BSE (broken), RBI, PIB, SEBI, Fed, GIFT Nifty, ~10+ yfinance-backed market/macro feeds, economic-calendar Tier-1 sources). See §7 for full classification.

**Fetch-and-discard count**: **at least 20 distinct live values** are fetched reliably today and never historically persisted — see §4.

**Two real, confirmed data-quality bugs found during this audit** (not previously known):
- `news_articles.published_at` stores **relative-time strings** ("2h ago", "1d ago") mixed with real dates and at least one mojibake character — ~5%+ of 6,529 rows unparseable. `created_at` is the only reliable timestamp on this table today.
- `events.event_date` is **100% NULL** across all 3,035 rows. `published_at` holds the real usable timestamp instead.

---

## 2. Complete current data-flow map

```
RSS (6 feeds) ──┐
NSE (announcements/board/corp-actions) ──┤
RBI / PIB / SEBI / Fed ──────────────────┼──► app/tasks/ingest_tasks.py ──► news_articles, events, government_policies, macro_releases (rare)
BSE (bot-walled, broken) ────────────────┘         (15min news / 60min policy)
                                                          │
company_announcements_service.py (30min, NSE only) ──► company_announcements

events ──► event_pipeline.py (job_enrich_events, 5min) ──► event_sectors/timeline/similar/policies, event_triage
event_triage ──► AIPE publisher.py (5min) ──► intelligence_articles

events + government_policies + company_announcements + news_articles + AICompanySignal + opportunities
   ──► evidence_window.py::collect_evidence_since() (30min, development_memory_sync)
   ──► developments / development_evidence
        ──► Intelligence Graph (ig_nodes/ig_edges)
             ──► Opportunity Engine V2 (shadow), AI Search, Weekend Intelligence

yfinance (price_bars only) ──► quant/backfill.py, refresh.py (daily 4:30PM IST) ──► price_bars
                                                                                        │
                                                                                   quant/ backtest harness (Phase B0-verified)

yfinance (everything else: VIX, GIFT Nifty, Bank Nifty, FII/DII, PCR, sector perf,
global indices, commodities, ADRs, macro_rates) ──► ~15 independent in-process caches
                                                       ──► Pre-Market / Homepage / Overview / Live pages
                                                       ──► DISCARDED after render (no history)
                                                       (except: price_monitor's once-daily 15:30-15:40 IST
                                                        capture_close_snapshot() ──► market_snapshots, 1 row)

Economic Calendar: 5 Tier-1 sources (RBI/MoSPI/Fed/BLS) ──► sync_orchestrator (3AM IST) ──► economic_calendar_events
                                                              (real, point-in-time-safe pipeline — 0 rows in dev,
                                                               unconfirmed whether it has actually run here)
```

---

## 3. Existing persisted historical datasets (real, genuinely accumulating)

| Dataset | Point-in-time safe? | Depth |
|---|---|---|
| `price_bars` | **Yes** — Phase B0-verified via executable adversarial tests | ~5y |
| `index_memberships` | **Yes** — sourced, Phase B0 | 2015-2025 |
| `quant_research_predictions/evaluations` | Yes (predictions frozen at insert) | 2021-2026 |
| `prediction_records/evaluations` (legacy, general-purpose) | Mostly — `experimental` flag scopes shadow work out of production stats | 2021-2026 |
| `development_evidence` | Yes — each row individually immutable, own `observed_at` | ~5 months |
| `homepage_daily_snapshots` | Yes — checked-before-insert, one row/day, never overwritten | ~1 month |
| `economic_calendar_events` | Yes by design (`identity_key`/`is_current`/`revision_of` versioning) | unconfirmed if running |
| `company_announcements` | Insert-if-not-exists (NSE side only; BSE contributes nothing) | ~1 week |

---

## 4. Important live values fetched but discarded (confirmed by code reading, not assumed)

All of these are fetched reliably today via working code paths and rendered live — **none reach a history table**:

| Signal | Fetcher | Cache only |
|---|---|---|
| GIFT Nifty | `gift_nifty_service.py` | endpoint-level, no DB path at all (by explicit design) |
| Bank Nifty futures + premium | `market.py::_fetch_enhanced_premarket` | 15min in-process |
| India VIX | **4 independent fetch sites** (Pre-Market, close-snapshot, AI Search enrichment, and a dead `MarketStory.vix_at` column that's never assigned) | mixed |
| US futures, European indices, Asian markets, US indices | `market_data.py`, `market.py` (2-3 separate ticker maps) | 15min |
| Indian ADRs (INFY/WIT/HDB/IBN) | `market.py::_ADR_TICKERS` | 15min |
| FII/DII net flow | `market.py::_fetch_fii_dii` (scrape) | 6h; only reaches DB via the once-daily close snapshot |
| Nifty PCR / Max Pain | `market.py::_fetch_pcr_data` (full option-chain scrape) | 15min; same once-daily DB path |
| Sector performance (live, accurate) | `market_data.py::get_sector_changes()` (12 sector ETF proxies) | 5min — **the stale `sector_data` DB table is a completely different, dead system** |
| Commodities (gold/silver/copper/platinum/Brent/WTI/NatGas) | `commodities.py` **and separately** `market_data.py::_COMMODITIES` | Redis 2min / in-process 15min — two independent implementations |
| Global indices board | `market.py::_fetch_global_indices` **and separately** `market_data.py::get_extended_indices` | two independent ticker maps/cache keys |
| Market breadth | Derived from a hardcoded 49-symbol Nifty500 sample, scaled — explicitly labeled `"Estimated from Nifty 500 sample"` in code (honest, not fabricated, but not real breadth either) | 15min |
| US Treasury 2Y/10Y, Fed Funds, RBI WSS rates | `macro_rates/` package | 6h — has a **fully-built, zero-caller persistence layer sitting unused** (`macro_rates/persistence.py::upsert_rate_observation`) |

This is the single largest, cheapest fix available in Phase 1: **every one of these is already fetched reliably** — the gap is purely "no canonical persistence hook exists," not "we need new source integration."

---

## 5. Mutable / non-point-in-time-safe datasets

| Table/field | Mechanism | Risk |
|---|---|---|
| `Development.current_direction/current_impact_tier/current_confidence` | Live rollup, updated on every evidence merge | Confirmed leak risk if read naively by as-of date (only `formation_*` is frozen) — same finding as Phase B0's quant audit, extended here to Development Memory itself |
| `ig_nodes`/`ig_edges` | `upsert_node`/`upsert_edge` — updated in place | No historical graph-state reconstruction possible; "what did the graph look like at T" cannot be answered today |
| `government_policies` | Blind `setattr` upsert keyed on `external_id` | No version history |
| `facts` | Blind `setattr` upsert keyed on `fact_key`, no `created_at` even | Explicitly flagged unsafe in the codebase's own internal audit (`intelligence_research/safe_sources.py`) |
| `event_sectors`/`event_timeline`/`event_similar`/`event_policies` | Delete+reinsert on every re-enrichment cycle | Active but not point-in-time safe |
| `intelligence_articles` narrative fields | Rewritten in place by continuous-updater/dedup-merge | Only `confidence_score`/`quality_score`/`event_score` are frozen |
| `historical_market_events` | Hand-curated, outcome fields backfilled in place, no `updated_at` | Fine as static reference data; not a live pipeline, and its own "verified ground truth" framing is optimistic per the codebase's own audit |
| `sector_data` | 100% seed data (`app/db/seed.py` hardcoded literals) | Dead — no live writer exists at all |
| `calendar_events` (legacy) | Seed-only, re-upserted every boot | Dead-end table still served by one live endpoint (`/api/market/calendar`) that hasn't migrated to the real `economic_calendar_events` |

---

## 6. Duplicate ingestion/persistence paths (confirmed, with file evidence)

1. **RSS**: `RSSProvider` (persisted → `news_articles`) vs `news_fetcher.py::get_live_news` (cache-only, 5 of 6 feed URLs byte-identical, separate id scheme — same article can enter under two different identities).
2. **NSE announcements**: hit independently by `ingest_tasks.py` (15min) and `company_announcements_service.py` (30min) — id-correlated to avoid row duplication, but the fetch itself is duplicated.
3. **Two fully dead worker files**: `app/workers/news_worker.py`, `app/workers/announcement_worker.py` — reimplement the above, imported by nothing.
4. **Sector performance**: dead `sector_data` table vs. live, accurate `get_sector_changes()` — two systems, zero relationship.
5. **Global indices**: `market_data.py` vs `market.py` — two independent ticker maps and cache keys for the same board.
6. **Commodities**: `commodities.py` vs `market_data.py::_COMMODITIES` — two independent implementations.
7. **`market_data_service`** — documented in its own docstring as "the single entry point for all market data," actually used by only 3 files; ~6 other files call yfinance directly with their own ad hoc caching.
8. **`macro_releases`**: one real writer (regex extraction from RBI/PIB text, correctly wired to a real API reader) and one **fully dead** writer (`macro_rates/persistence.py`, zero callers) targeting the same table.
9. **Two calendar tables**: `calendar_events` (legacy, seed-only) still served by `/api/market/calendar`; `economic_calendar_events` (real, versioned) already adopted by `opening_prediction_service` and MIE — a half-finished migration, not two designs coexisting on purpose.

---

## 7. Source inventory and classification

| Source | Class | Frequency | Persistence | Raw retained? |
|---|---|---|---|---|
| RSS ×6 (ET, Moneycontrol, NDTV, Business Standard, Livemint, Google News) | C | 15min | `news_articles`, insert-only | No |
| `news_fetcher.py` duplicate RSS bundle + yfinance news | D + E | 15min cache | none | No |
| NSE announcements/board/corp-actions | A/E | 15+30min (dup) | `news_articles`+`events`+`company_announcements` | No (`attachment_url` always None) |
| BSE announcements | G/D (broken) | attempted 15/30min, always fails | none real | No |
| RBI / PIB / SEBI press+circulars | B | 60min | `news_articles`+`government_policies`(mutable)+`events` | No |
| US Fed press releases | A/B | 60min | same | No — but only source with an explicit public-domain rights note |
| `macro_extraction.py` regex extraction | A design / D effect | every policy cycle | `macro_releases` (real, narrow) | No |
| `macro_rates/persistence.py` | **F (dead)** | n/a | never called | n/a |
| GIFT Nifty | D | live, endpoint-cached | none by design | No |
| VIX (4 sites) | D (3 of 4), A (1 row) | 15min–120s | `market_snapshots` only via 1 daily row | No |
| FII/DII, PCR/Max Pain | D (live) / A (1 row/day) | 15min–6h | `market_snapshots` only via 1 daily row | No |
| Sector performance (live) | D, dup of dead `sector_data` | 5min | none | No |
| Commodities, global indices, ADRs, macro rates | D, several E (duplicated) | 15min–6h | none | No |
| Economic calendar (5 Tier-1 sources) | G (correct design, unconfirmed running) | scheduled, 3AM+recheck | `economic_calendar_events`, versioned | n/a |
| `historical_market_events` | B (static reference, not live) | manual | mutated in place, no history | n/a |
| `event_news` | **F (dead)** | never called | 0 rows | n/a |
| Development Memory ingestion (`collect_evidence_since`) | A (bounded-window, per-source isolated) | 30min | `developments`/`development_evidence` | n/a |

---

## 8. Proposed canonical Warehouse architecture

One logical warehouse, three specialized stores — not a single giant table, matching the user's explicit instruction:

```
Sources ──► Raw Evidence ──► (existing) normalization paths ──► Development Memory ──► Intelligence Graph
                │
                └──► Canonical Market Observations (parallel, for numeric time-series signals)

Source Registry describes every row in both of the above.
```

### 9. Raw Evidence design

**Genuinely new — confirmed no existing layer satisfies this.** The news/evidence audit found, with certainty: every one of the ~10 external sources (RSS×2, NSE, BSE, RBI, PIB, SEBI, Fed) discards the original fetched bytes the instant parsing completes. `DevelopmentEvidence` is a *normalized* evidence-item layer built from already-summarized data — it is not, and was never meant to be, a raw-payload layer. Building Raw Evidence does **not** duplicate DevelopmentEvidence; it sits one layer *below* it.

```
RawEvidence
  id
  source_id            -> Source Registry FK
  source_type           # rss | nse | bse | rbi | pib | sebi | fed | yfinance_news | ...
  external_id            # source's own id where one exists (NSE ann id, RSS guid); else null
  title
  published_at           # NULLABLE — many sources don't reliably provide one (see news_articles bug)
  observed_at             # when MarketRipple's fetcher first saw it — the reliable anchor
  ingested_at              # when written to DB (usually = observed_at, kept separate for backfill honesty)
  source_url
  content_hash              # sha256 of normalized (source_type, external_id or title, published_at) — dedup key
  raw_payload               # the actual fetched text/JSON/XML fragment — see storage boundary, §19
  mime_type
  quality                     # good | truncated | parse_error | duplicate
```

Given every payload here (an RSS item, an NSE JSON announcement) is small (KB-scale, not PDFs), `raw_payload` stays a `TEXT` column in the structured DB for Phase 1 — see §19 for the object-storage boundary and why it's deferred.

Append-only. Never updated after insert — if a source revises an item, a new row with a new `content_hash` is written; nothing overwrites history.

### 10. Canonical Market Observations design

**Hybrid recommendation, not pure-generic or pure-typed.**

- **`price_bars` stays exactly as-is** — it is already a correctly-designed, Phase-B0-verified canonical typed table for one instrument family (equity/index OHLCV). Canonical Market Observations must **not** duplicate it; it covers everything else.
- For the ~15-20 known, named, permanently-important instruments (VIX, Bank Nifty, GIFT Nifty, USD/INR, Brent, FII_NET, DII_NET, PCR, MAX_PAIN, per-sector performance, US Treasury 2Y/10Y, Fed Funds, RBI WSS, market breadth, global indices board) a **generic table** is the right call over N typed tables — the fields are structurally identical (metric, value, unit, timestamps, source, quality) across all of them, and a typed-table-per-metric approach would mean 15+ near-identical schemas for what's fundamentally one shape. This directly matches `PriceBar`'s own precedent of "one table, a `timeframe`/type discriminator column" rather than a table per candle interval.

```
MarketObservation
  id
  metric                # NIFTY50 | BANKNIFTY | INDIAVIX | USDINR | BRENT | GIFT_NIFTY | FII_NET | DII_NET |
                         # PCR_NIFTY | MAX_PAIN_NIFTY | SECTOR_<NAME> | US10Y | US2Y | FEDFUNDS | RBI_WSS |
                         # MARKET_BREADTH_ADV | MARKET_BREADTH_DEC | GLOBAL_<INDEX> | COMMODITY_<NAME>
  value
  unit
  observation_time        # when the underlying value is true-as-of
  market_date               # trading date this observation belongs to
  session                    # pre | regular | post | close
  source_id                   -> Source Registry FK
  captured_at                  # when MarketRipple's job ran
  quality                        # fresh | stale | estimated | source_failure
  metadata                        # JSON — e.g. PCR's put/call OI breakdown, FII/DII's session label
  UNIQUE(metric, market_date, session, source_id)   # dedup — mirrors PriceBar's own (symbol, timeframe, bar_date)
```

**Why not fully generic (pure EAV)**: would lose the ability to put a real `NOT NULL`/type constraint on `value`, and the codebase already shows the cost of over-generic tables (`MarketSnapshot`'s many optional columns for one row/day). **Why not fully typed**: 15+ near-identical tables for a single narrow purpose is worse maintenance burden than one table with a `metric` discriminator, and this pattern is already proven in-repo (`PriceBar.timeframe`, `MarketSnapshot.snapshot_type`).

### 11. Source Registry design

```
Source
  id
  name                    # "Economic Times - Markets RSS", not just "RSS"
  domain
  source_type              # rss | api | csv | json | http | scrape | document
  collection_method
  frequency
  priority
  rights_basis                # NEW field this audit's finding demands — "public_domain" | "official_rss" |
                               # "unofficial_scraped_api" | "unverified" — every source gets an honest answer,
                               # not just the Fed feed
  robots_checked                # boolean — honest "no" is fine, "unknown" is not
  rate_limit
  last_success
  last_failure
  freshness
  health
```

Do not overbuild: `source_health.py` already tracks per-fetch success/failure/latency in-process for the health API — Source Registry's `last_success`/`last_failure`/`health` fields should read from that existing mechanism, not reimplement it.

### 12. Existing tables/services to REUSE unchanged

`price_bars`, `index_memberships`, the entire `quant/` harness, `PredictionRecord`/`PredictionEvaluation`/`CalibrationStat` (see §Prediction Ledger below — already the right shape, just underused), `homepage_daily_snapshots`, `economic_calendar_events` + its 5 Tier-1 sources, `evidence_window.py::collect_evidence_since()` (the real Development Memory ingestion point — Raw Evidence sits alongside it, doesn't replace it), `RSSProvider`/`NSEProvider`/`RBIProvider`/`PIBProvider`/`SEBIProvider`/`FedProvider` (reused as fetchers — just need a Raw Evidence write added alongside their existing writes, not rebuilt), `source_health.py`.

### 13. Existing tables/services requiring modification

- `story_engine.py::_save_story` — one-line fix, `vix_at` is simply never assigned.
- `price_monitor.py::capture_close_snapshot` — currently the ONLY DB path for FII/DII/PCR/VIX; once Canonical Market Observations exists, this becomes one *source* writing into it rather than the sole destination.
- `/api/market/calendar` — migrate to read `economic_calendar_events` (matching `opening_prediction_service`/MIE, already done there).
- `sector_data` — retire; wire `get_sector_changes()` into Canonical Market Observations instead of fixing the dead table.

### 14. New tables/files needed

`RawEvidence`, `MarketObservation`, `Source` (registry), a warehouse-health measurement module (`app/services/warehouse/health.py`), a scorecard generator reusing the same measurement functions for before/after comparison.

---

## 15. Source acquisition strategy

**No strong Crawl4AI case found in the current source list.** Every source either (a) already has a working deterministic fetcher (RSS/NSE/RBI/PIB/SEBI/Fed — all API- or RSS-shaped, none need JS rendering), or (b) is BSE, which fails at the network/bot-detection layer (Akamai), not the JS-rendering layer — a headless browser or Crawl4AI would not clear an Akamai challenge any better than the `curl_cffi` TLS-impersonation attempt already tried and documented as failed in-repo. BSE's own docstring already points at the right next step: a paid/registered "Corporate Data API" or "Self Data Feed," not more sophisticated scraping.

- **Crawl4AI**: no genuinely justified use case identified. The one plausible future case — extracting content from NSE/BSE filing **PDF attachments** (currently never fetched at all, `attachment_url` always `None`) — doesn't need Crawl4AI either; that's a PDF-parsing problem, not a dynamic-page-rendering problem, and it's not urgent since the plain-text `attchmntText` NSE already returns covers today's summary use case.
- **Scrapy**: no case found — nothing here needs a crawl frontier/spider architecture; every source is a single known endpoint or feed URL.
- **Recommendation**: do not add either in Phase 1. The actual gap is persistence of already-reliable fetches, not acquisition technology.

**Licensing/robots concerns**: only the Fed feed carries an explicit rights-basis comment (public domain, 17 U.S.C. §105). RBI/SEBI/PIB (official government RSS) and NSE/BSE (commercial exchange data via unofficial internal APIs, spoofed browser User-Agent, no robots.txt logic anywhere) carry no such reasoning in-code today. The Source Registry's new `rights_basis` field (§11) is the concrete Phase 1 fix — document what's actually known per source, including honest "unverified"/"unofficial" answers, rather than silence.

---

## 16. Structured DB vs. object storage boundary

**Recommendation: no object storage in Phase 1.** Nothing currently fetched or proposed for Raw Evidence is large — RSS item fragments and NSE JSON announcements are KB-scale, not PDFs. `RawEvidence.raw_payload` stays a `TEXT` column in SQLite. The schema includes a `content_reference` concept reserved for later (not built now) so that if NSE/BSE PDF attachment retrieval becomes a real Phase 2+ need, object storage can be introduced without a Raw Evidence schema migration.

**If/when object storage becomes necessary**: Cloudflare R2 (S3-compatible, egress-free) is worth evaluating first given cost sensitivity, but this is explicitly not a Phase 1 decision — no current data justifies it.

---

## 17. Estimated storage (clearly labeled as projection, not measurement — Phase 1 hasn't run yet)

Basis: real current `news_articles` growth rate = 6,529 rows / 56 days ≈ **117 rows/day**. Assuming Raw Evidence captures at a similar order of magnitude across all sources combined (RSS+NSE+RBI+PIB+SEBI+Fed), and each raw payload averages ~1-2KB:

| Horizon | Raw Evidence (est.) | Market Observations (est., ~20 metrics, hourly during market hours) | Total est. |
|---|---|---|---|
| Per day | ~150-250 rows, ~300-500KB | ~140 rows, ~30KB | ~350-550KB/day |
| 7-day | ~1,000-1,750 rows | ~980 rows | ~2.5-4 MB |
| 30-day | ~4,500-7,500 rows | ~4,200 rows | ~10-16 MB |
| 1-year | ~55,000-91,000 rows | ~51,000 rows | ~125-200 MB |

For context: the current 140.7MB total DB reflects ~2 months of much broader existing activity (all 63 tables). This projected addition is well-bounded and does not threaten a repeat of the Railway volume incident — but it is a **projection**, not a measured fact, and should be re-measured after a real Phase 1 collection cycle (§26).

---

## 18. Point-in-time contract

- **Raw Evidence**: `published_at` (nullable — many sources don't reliably provide one; never store an unparseable relative string here, that's the exact `news_articles` bug this design must not repeat), `observed_at` (reliable anchor), `ingested_at`.
- **Market Observations**: `observation_time` + `market_date` + `session`, `captured_at` (when the job ran, separate from when the value is true-as-of).
- **Revised macro data** (CPI/GDP/etc. from `macro_releases`): preserve revision semantics — a later revision is a new row, not an overwrite, matching `economic_calendar_events`'s existing `revision_of` pattern rather than inventing a new one.
- **Mutable intelligence fields** (`Development.current_*`, `intelligence_articles` narrative fields): explicitly out of Phase 1 scope to fix — noted as a known limitation, not silently pretended away.

## 19. Deduplication/idempotency

`content_hash` (sha256 of source_type + external_id-or-title + published_at) for Raw Evidence — reusing the exact id-correlation pattern already proven in `company_announcements_service.py`'s NSE duplicate-id fix, not inventing a new scheme. `UNIQUE(metric, market_date, session, source_id)` for Market Observations, mirroring `PriceBar`'s own `UNIQUE(symbol, timeframe, bar_date)`.

## 20. Data quality strategy

Extend `PriceBar.data_quality`'s existing enum convention (`good | thin_volume | gap_detected | corporate_action_uncertain`) rather than inventing a new one: `fresh | stale | missing | partial | estimated | source_failure`. Never forward-fill, never substitute current for historical, never silently relabel an estimate as real — matching `gift_nifty_service.py`'s own already-correct "never substituted and relabeled" principle, applied consistently everywhere.

## 21. Proposed warehouse-health measurement

New `app/services/warehouse/health.py`, reusable by both the daily observability requirement (§10 of the original ask) and the before/after scorecard: total records + storage, records added today/7d, by category (raw evidence, market observations, news, events, development evidence, prices, graph), distinct active sources, distinct persisted metrics, oldest/newest observation per category, freshness, failed-source count (reading `source_health.py`). Admin/API-only, no public UI, per instruction.

## 22. Before-vs-after scorecard (to be generated at Phase 1 completion)

Same shape as §1 above, run again, diffed: storage volume (DB size, record count), data coverage (sources/metrics/instruments/date ranges), point-in-time-safe coverage (how many datasets can genuinely be queried as-of T — currently: price_bars, index_memberships, quant tables, development_evidence, homepage_daily_snapshots; NOT: news_articles/events timestamps as they stand, government_policies, facts, sector_data), fetch-and-discard reduction (before: ~20 signals; after: target count), daily data creation rate. 7/30-day figures measured if a real cycle has run by then; 1-year stays a projection, explicitly labeled.

---

## 23. Recommended Phase 1 implementation batches, ordered by risk/value

1. **Canonical Market Observations + wire the ~15 already-reliable fetches into it** (VIX, GIFT Nifty, Bank Nifty, FII/DII, PCR/Max Pain, sector performance, global indices, commodities, macro rates). Zero new source-integration risk — every one of these already works today, this batch only adds a persistence hook at the existing fetch point. Highest value-to-risk ratio in the whole plan.
2. **Raw Evidence table + wire into the 6 existing content fetchers** (RSS, NSE, RBI, PIB, SEBI, Fed) — additive alongside existing writes, doesn't change current behavior for any consumer.
3. **Source Registry**, formalizing the ~18 sources already found, including the new `rights_basis` field.
4. **Fix the two trivial, real bugs found**: `story_engine.py`'s missing `vix_at` assignment, and (lower priority, cosmetic) `news_articles.published_at`'s relative-string contamination — the latter needs a decision (backfill-parse vs. deprecate-in-favor-of-created_at), not a quick patch.
5. **Retire duplicate pipelines**: `news_fetcher.py`, the two dead worker files, `macro_rates/persistence.py`'s dead writer, `sector_data`, legacy `calendar_events` (once `/api/market/calendar` migrates) — cleanup, lower urgency, no data-loss risk either way.
6. **Warehouse-health measurement + before/after scorecard automation**.

## 24. Explicit list of things deferred to Phase 2+

Prediction/Outcome ledger wiring beyond what already exists (`PredictionRecord`/`PredictionEvaluation`/`CalibrationStat` — real, active, just underused at 4 calibration rows), Confidence Engine calibration rollout to all surfaces, Chronos-Bolt/TimesFM/TTM benchmarking, any LLM training/fine-tuning, BSE fix (needs a paid-API/legal decision, not more engineering), object storage adoption, `Development.current_*`/`ig_nodes`/`ig_edges`/`government_policies`/`facts`/`intelligence_articles` point-in-time-safety fixes (real, known, explicitly out of scope here), any UI change, economic-calendar-pipeline verification (needs a real running check, flagged not fixed).

## 25. Architecture conflicts checked

- **Development Memory**: none. Raw Evidence sits below the existing normalized tables `evidence_window.py::collect_evidence_since()` already reads — additive, not a replacement.
- **Intelligence Graph**: none. Downstream of Development Memory, untouched.
- **Opportunity V2**: none. Shadow-only, untouched, per its own explicit freeze (still in effect).
- **quant infrastructure / PriceBar / index_memberships**: none — explicitly designed to *not* duplicate `PriceBar` (§10). `index_memberships` stays exactly as Phase B0 built it.
- **`PredictionRecord`/`CalibrationStat`**: none — Phase 1 doesn't touch these, just notes (§24) that they're the right foundation for the later Confidence Engine, already partially built.

## 26. Final recommendation

**Yes, sufficient as the shared long-term data foundation**, with two conditions: (1) the two Raw Evidence / Market Observation tables must go in exactly as designed — generic-with-discriminator, not typed-per-metric, not fully-EAV — to avoid the same "15 near-identical tables" problem already visible elsewhere in the schema; (2) Phase 1's actual implementation work should follow the batch order in §23 — start with Market Observations (cheapest, highest value, zero new source risk) before Raw Evidence, since the market/macro fetch-and-discard list is both larger and lower-risk to close than the news/evidence one.

---

---

## Phase 1B Batch 1 — Corrections Applied, Implemented, Verified Live (2026-08-23)

Architecture approved with four mandatory corrections. All four applied; Batch 1 (Source Registry + Canonical Market Observations) built and run through two real collection cycles.

### Correction 1 — MarketObservation identity must preserve multiple intraday observations

**Fixed.** The original §10 design used `UNIQUE(metric, market_date, session, source_id)` — this would have collapsed every intraday tick within one session into a single row, silently discarding the exact granularity the original storage estimate assumed existed. Corrected identity: **`UNIQUE(metric, source_id, observation_time)`** — `observation_time` (a real, precise timestamp) is now part of the natural key; `market_date`/`session` are denormalized, informational columns for querying, never part of uniqueness. **Verified live**: two real collection cycles run 65 seconds apart produced 40 distinct rows (2 distinct `observation_time` values × 20 metrics), not 20 — confirmed by direct query, not asserted.

### Correction 2 — RawEvidence must separate stable evidence identity from payload/version hash

**Design corrected (Raw Evidence itself is still deferred to Batch 2, per the authorized sequencing — not built this round).** The original §9 draft conflated a single `content_hash` as both dedup key and identity, which cannot represent "the same real-world item, updated content" — exactly the "if the same external item changes later, preserve what MarketRipple saw at the earlier timestamp" requirement from the original brief. Corrected design for Batch 2:
- `evidence_key` — stable identity across time (source_type + external_id where the source provides one, else source_type + normalized_title + source_url as a fallback), constant across versions.
- `payload_hash` — sha256 of the actual raw content, changes when the source's content changes.
- A new row is inserted only when `(evidence_key, payload_hash)` hasn't been seen before — an unchanged re-fetch dedupes to zero new rows; a genuine content change produces a new row under the same `evidence_key`, forming an append-only version history instead of either an overwrite or an unrelated duplicate.

### Correction 3 — Seed minimal Source Registry before tables that reference it

**Fixed and sequenced correctly.** `Source` model built and the table created first; `sources` seeded with **20 real rows** — every one traced to a source the Phase 1A audit actually found and verified (6 RSS feeds, NSE, BSE, RBI, PIB, SEBI, Fed, 4 yfinance index/rate quotes, 12-sector-ETF proxy source, GIFT Nifty, FII/DII, PCR/option-chain) — before `MarketObservation` (which FKs into it) was built or written to. Every row answers `rights_basis` honestly, including `unofficial_scraped_api` for NSE/BSE/GIFT-Nifty/FII-DII/PCR and `official_rss`/`public_domain` where that's genuinely true — closing the Phase 1A finding that only the Fed feed had any such reasoning in code.

### Correction 4 — Recalculate storage projections from the actual canonical persistence cadence

**Fixed — the original §17 estimate assumed an unverified "hourly during market hours" cadence.** The real, decided Batch 1 cadence: 15-minute ticks, gated to NSE regular trading hours only (9:15 AM–3:30 PM IST, 6.25h). This isn't arbitrary — the real weekend test run below shows *why* it must be gated: 9 of 20 metrics (mostly the NSE option-chain PCR/Max Pain and several sector ETFs) return `source_failure` outside a live trading session; capturing 24/7 would mostly accumulate empty rows.

**Real, measured per-cycle count** (not projected): **20 rows/cycle**, confirmed identically on two separate real runs.

**Real per-cycle result** (weekend, 2026-08-23 — an honest, non-cherry-picked live run, not a cherry-picked trading-day example):
```
total=20  fresh=11  source_failure=9  session=weekend
```
11 fresh: INDIAVIX, BANKNIFTY, USDINR, BRENT, GIFT_NIFTY, FII_NET, and 4 of 12 sector ETFs (Banking, Pharma, Auto, Infra, PSU Bank — 5 actually, all with real weekend-stale-but-valid last-close data from yfinance). 9 `source_failure`, never fabricated: SECTOR_IT/ENERGY/FMCG/METAL/REALTY/PRIVATE_BANK/MEDIA (weekend-thin ETF quote gaps) and PCR_NIFTY/MAX_PAIN_NIFTY (NSE's option-chain endpoint has no live session to scrape on a weekend). This is the "never fabricate, never forward-fill" data-quality contract (§20) working exactly as designed, verified against a real failure case rather than only a happy path.

**Recalculated projection, from the real per-cycle count and the real decided cadence:**

| Cadence | Rows/day | Note |
|---|---|---|
| 15min, 24/7 (no gating — not the deployment plan) | 96 cycles × 20 = 1,920 | Shown only to demonstrate why gating matters |
| **15min, market-hours-gated (actual Phase 1B plan)** | **25 cycles × 20 = 500** | |

Row size: file-size delta was **not usable** for this measurement — two real cycles' worth of rows (40 total) produced a **zero-byte** file-size change (SQLite reused already-allocated free pages; the DB file only grew during the one-time table/index creation, not per-row). Using a bottom-up column estimate instead (id 36B + metric ~15B + value 8B + unit ~10B + 3 timestamp columns ~19B each + session ~10B + source_id ~20B + quality ~10B + extra JSON ~0–50B + SQLite row/index overhead ~50–80B): **~300 bytes/row**, stated as a computed estimate, not a measured one.

| Horizon | Market Observations (recalculated) |
|---|---|
| Per day | 500 rows, ~150 KB |
| 7-day | 3,500 rows, ~1 MB |
| 30-day | ~15,000 rows, ~4.5 MB |
| 1-year | ~182,500 rows, ~54 MB |

This is roughly a third of the original §17 estimate for this category — the original "hourly" assumption overstated the real, decided cadence.

### What was actually built (files, real)

- `app/db/models/source_registry.py` — `Source`
- `app/db/models/market_observation.py` — `MarketObservation` (corrected identity)
- `app/services/warehouse/source_registry_seed.py` — 20 real, sourced rows
- `app/services/warehouse/market_observations.py` — `capture_market_observations()`, reuses existing canonical fetchers only (`market_data.py::_fetch_quote`/`_SECTOR_ETFS`, `gift_nifty_service.py::get_gift_nifty_sync`, `app/api/market.py::_fetch_fii_dii`/`_fetch_pcr_data`) — no fetch logic reimplemented anywhere
- Tables created, `sources` seeded (20 rows), `market_observations` populated via two real runs (40 rows total)

### Not yet done (deliberately, per the authorized sequencing)

- **Not scheduled yet** — `capture_market_observations()` exists and is verified correct, but is not yet wired into the scheduler with the 15-minute/market-hours gate. That's the natural next step once this checkpoint is reviewed, not assumed.
- **Raw Evidence not built** — held per explicit instruction, pending this Batch 1 review.
- Batch 1 currently covers 8 of the ~20 signals identified in the original §4 fetch-and-discard list (VIX, BankNifty, USDINR, Brent, GIFT Nifty, FII/DII, PCR/Max Pain, 12 sector ETFs counted as one family) — global indices, commodities beyond Brent, and macro rates (US Treasury/Fed Funds/RBI WSS) remain for a Batch 1 continuation, same table, same pattern, no new architecture needed.

---

---

## Phase 1B Batch 1D — Scheduler Wiring + Verification (2026-08-23)

Batch 1 approved. `capture_market_observations()` wired into the scheduler and verified end-to-end.

### Design

Reused the existing 2-minute `run_price_monitor_cycle` job (registered as `"price_monitor"`, `max_instances=1, coalesce=True`) rather than adding a new independent scheduled job — mirrors this same file's own `capture_close_snapshot()` pattern exactly (piggyback on an existing cadence, gate internally). Gate: only captures once per real 15-minute bucket, only during NSE regular trading hours (`session == "live"`, i.e. 9:15 AM–3:30 PM IST weekdays).

**Duplicate-row prevention, two layers** (owner's explicit "scheduler startup/restart must not create duplicate rows" requirement):
1. In-process guard (`_last_captured_bucket`) — cheap fast path, resets on restart.
2. **Real cross-restart guarantee**: `observation_time` is now the *bucketed* 15-minute mark, not exact wall-clock time — a restart within the same bucket produces the identical `(metric, source_id, observation_time)` identity as the original capture. Before fetching anything, the DB is checked for an existing row at that exact bucket; if found, the entire cycle is skipped with zero new fetches, not just zero new rows.

### Verification — real scheduled cycle, real weekend

Called the actual scheduler entrypoint (`price_monitor.run_price_monitor_cycle()`) directly, exactly as APScheduler does:
```
row count before: 40 -> row count after: 40 (unchanged)
```
Today is genuinely a weekend — the gate correctly declined to capture, proving it respects real market hours rather than firing blindly. This is real, not simulated: no monkeypatching involved.

### Verification — capture + dedup mechanics (simulated live session, real fetchers/data)

Since a live NSE session can't be summoned on demand, `tests/services/test_warehouse_market_observations.py` monkeypatches only the *session-gate check* to simulate "live" — every fetch inside still calls the real yfinance/NSE/GIFT-Nifty functions and persists whatever real values they return right now. **4/4 tests pass**:

| Test | Proves |
|---|---|
| `test_scheduled_capture_persists_real_rows_when_gate_is_live` | A live-gated cycle persists exactly 20 real rows, `capture_attempts=20`, `duplicate_suppressed=0` |
| `test_second_call_in_same_bucket_is_suppressed_not_duplicated` | A second call in the same bucket (simulating a restart) is skipped, `duplicate_suppressed=20`, `capture_attempts=0` — **zero re-fetches, zero new rows**, the literal owner requirement |
| `test_in_process_guard_skips_without_a_db_round_trip` | The cheap fast path works independently of the DB-level check |
| `test_no_api_route_imports_the_capture_functions` | Structural guard (AST-free, plain source grep across every file in `app/api/`) — fails loudly if a future change ever wires persistence into a request path |

### Verification — existing consumers unchanged

`/api/market/premarket`, `/api/market/overview` — both real endpoints, both still respond `200` after the wiring, unmodified behavior (neither reads from `MarketObservation`; both still call their original live fetchers exactly as before). Full backend test suite (quant + warehouse, 39 tests) still passes.

### Per-cycle metrics now returned (owner's requested addition)

Every call to `capture_market_observations_if_due()` returns `capture_attempts`, `successful_metric_rows` (renamed from `fresh` for clarity), `source_failure_rows`, `duplicate_suppressed` — logged on every real capture and available for the eventual BEFORE/AFTER daily-growth measurement (§21/§22).

---

## Status: Batch 1 complete (1A/1B/1C/1D), verified live end-to-end.

---

## Phase 1B Batch 2 — Raw Evidence (2026-08-23)

Purely additive. `RawEvidence` table + hooked into the single shared entrypoint all 6 approved providers already call — `app/providers/base.py::BaseProvider.fetch_and_normalize()` — via an explicit per-provider opt-in flag (`capture_raw_evidence = True`, set on RSS/NSE/RBI/PIB/SEBI/Fed; **not** set on BSE). Every raw item is captured *before* `normalize()` filters/transforms it — including items that get filtered or fail to parse — then `fetch_and_normalize()` returns the exact same `list[RawItem]` as before. `job_ingest_news()`/`job_ingest_policy()` and every other caller are **completely unmodified**.

### Identity, exactly as corrected

`evidence_key = f"{source_type}:{provider's own raw id}"` (reuses each provider's own id scheme — news_articles.id/events.id already use the same ids, so this doesn't introduce a competing notion of identity). `payload_hash = sha256(raw dict)`. `UNIQUE(evidence_key, payload_hash)` — identical re-fetch suppressed, genuine content change becomes a new immutable version.

### Two real bugs found and fixed during live verification

Reading provider code doesn't always match real API responses — verified by running the actual real fetch and inspecting actual captured rows, not by trusting the source:
- `nse_provider.py::_normalize_announcement` reads `raw.get("an_no")` for its own id, but **real NSE announcement JSON has no `an_no` field at all** — confirmed live, this is a pre-existing dead reference in that code (it already silently falls back to a content hash today). The real, stable field is `seq_id`. Fixed `_extract_external_id` to use it.
- NSE's raw dict has no `"published_at"`/`"headline"` keys either — real fields are `sort_date`/`attchmntText`/`desc` (announcements) or `bm_timestamp`/`bm_desc`/`bm_purpose` (board meetings). Fixed `_extract_title`/`_extract_published_at_raw` to read the real fields, mirroring `nse_provider.py`'s own existing precedence rather than inventing a new one.

### Verification — real fetches, real external sources, real results

Ran the actual unmodified `job_ingest_news()`/`job_ingest_policy()` twice in a row against live RSS/NSE/RBI/PIB/SEBI/Fed:

| Run | NSE | RSS | Fed | RBI/PIB/SEBI |
|---|---|---|---|---|
| 1st (fresh) | attempted=60, written=60, suppressed=0 | attempted=95, written=95, suppressed=0 | attempted=5, written=5 | RBI=0 items, SEBI=0 items, PIB 403 Forbidden (real, honest failures — zero raw evidence written, correctly, since nothing was ever received) |
| 2nd (identical re-fetch) | attempted=60, **written=0, suppressed=60** | attempted=95, **written=0, suppressed=95** | (not re-run) | — |

`raw_evidence` table: 0 → 160 after run 1, **still 160 after run 2** — real, live proof of case #1 and #8 (identical re-fetch suppressed; restart/re-fetch idempotent), not simulated.

Existing tables grew by exactly the logged deltas and nothing more: `news_articles` +1, `events` +1, `government_policies` unchanged (5 real upserts to *existing* rows, matching that table's already-known mutable-upsert design — not a new-row bug) — proving case #6.

### Verification — the 10 requested cases

| # | Case | Result |
|---|---|---|
| 1 | Same RSS item twice → one version | **Proven live** — 95/95 suppressed on real re-fetch |
| 2 | Changed payload → two versions under one evidence_key | Proven via `test_same_stable_item_changed_payload_creates_a_new_version` — real DB, deterministic content mutation |
| 3 | NSE stable external ID → deterministic identity | **Proven live** — real `seq_id` values (e.g. `nse-106753642`), confirmed via direct row inspection |
| 4 | No reliable pub timestamp → `published_at=NULL`, `observed_at` valid | Proven via `test_source_without_reliable_publication_timestamp_stays_null` |
| 5 | Parse failure/filtered → stored with honest quality flag | **Proven live** — 29 real RSS items came back `quality=filtered` (off-topic/geography-filtered) and are real, queryable rows, not discarded; also unit-proven for a synthetic parse case |
| 6 | Existing normalized tables unaffected | **Proven live** — exact delta match, twice |
| 7 | No page/API request writes RawEvidence | Structural test, scans every file in `app/api/` |
| 8 | Restart/re-fetch idempotent | **Proven live** — identical second run, 0 new rows |
| 9 | Per-source counts measurable | **Proven live** — `capture_raw_evidence()`'s own return dict (`attempted`/`written`/`suppressed_duplicate`/`skipped_no_source`), logged every call |
| 10 | Warehouse health reports Raw Evidence totals + growth | New `app/services/warehouse/health.py::warehouse_health_report()` — real output: 160 raw_evidence rows, 3 source types, 2 quality buckets, 6 distinct active sources, `added_today`/`added_last_7d` both real |

**14 tests, all passing** (`test_warehouse_raw_evidence.py` ×8, `test_warehouse_health.py` ×1, plus the pre-existing 5 warehouse tests re-confirmed). Full backend suite: **48/48 passing**.

### `published_at` relative-string regression guard

`test_published_at_parser_never_accepts_a_relative_string` directly asserts `_parse_published_at("2h ago")`, `"1d ago"`, and the exact mojibake character found live in `news_articles.published_at` all return `None` — the specific bug class this whole design exists to prevent, pinned as an executable test, not just a design note.

### Scope discipline held

Only RSS/NSE/RBI/PIB/SEBI/Fed wired (confirmed: no `capture_raw_evidence` reference anywhere in `bse_provider.py`). No Crawl4AI, no Scrapy, no new dependencies. No consumer reads `RawEvidence` yet — it exists purely as the provenance layer underneath the unchanged existing pipeline.

---

## Status: Batch 1 + Batch 2 complete, verified live end-to-end against real external sources.

---

# Phase 1 BEFORE-vs-CURRENT Scorecard (2026-08-23)

All numbers below are real, queried live against the local dev DB — `BEFORE` is the exact snapshot in `artifacts/intelligence_warehouse_phase1_before.json` (captured before any Phase 1 implementation work); `CURRENT` is a fresh query run for this scorecard. No projections are presented as measurements in this table.

## 1. BEFORE vs CURRENT

| Metric | BEFORE | CURRENT | Δ |
|---|---|---|---|
| DB size | 147,509,248 B (140.7 MB) | 148,144,128 B (141.3 MB) | **+634,880 B (+0.61 MB)** |
| Total structured records (all tables) | 306,870 | 323,401 | **+16,531** |
| Table count | 63 | 66 | +3 (`sources`, `raw_evidence`, `market_observations`) |
| Source registry rows | 0 (didn't exist) | **20** | +20 |
| Raw Evidence rows | 0 (didn't exist) | **160** | +160 |
| Market Observation rows | 0 (didn't exist) | **40** | +40 |
| Distinct persisted market metrics | 0 | **20** | +20 |
| Point-in-time-safe datasets | 7 (price_bars, index_memberships, quant_research, prediction_records/evaluations, development_evidence, homepage_daily_snapshots, economic_calendar_events-by-design) | **9** (+ raw_evidence, market_observations) | +2 |
| Fetch-and-discard *market* signals remaining | ~20 (audit estimate) | **~12** (VIX/BankNifty/USDINR/Brent/GIFT-Nifty/FII-DII/PCR-MaxPain/sector-performance now captured, 8 families closed) | ~-8 |
| Fetch-and-discard *content* sources remaining | 7 found (RSS, NSE, RBI, PIB, SEBI, Fed, BSE) | **1** (BSE only — excluded by design, needs a paid-API decision, not more engineering) | -6 |
| news_articles | 6,529 | 6,538 | +9 (organic — existing pipeline, unmodified) |
| events | 3,035 | 3,040 | +5 (organic) |
| developments | 1,137 | 1,145 | +8 (organic) |
| development_evidence | 2,249 | 2,259 | +10 (organic) |
| ig_nodes | 1,805 | 1,815 | +10 (organic) |
| ig_edges | 1,117 | 1,146 | +29 (organic) |
| price_bars | 62,734 | 62,734 | 0 (unchanged — Phase 1 didn't touch quant) |
| index_memberships | 50 | 50 | 0 (Phase B0, unchanged) |
| quant_research_predictions | 48,972 | 48,972 | 0 |
| quant_research_evaluations | 146,916 | 146,916 | 0 |
| prediction_records (legacy) | 6,974 | 6,976 | +2 (organic) |
| prediction_evaluations (legacy) | 8,361 | 8,361 | 0 |

The "organic" rows (news_articles/events/developments/ig_nodes/ig_edges/prediction_records) grew from this app's own **pre-existing, unmodified** scheduled jobs continuing to run in the background during this work — not from anything built in Phase 1. Listed for completeness so the scorecard isn't misread as claiming Phase 1 caused all growth.

## 2. NEW SINCE PHASE 1 START

| Metric | Value |
|---|---|
| Raw Evidence added | **160** |
| Market Observations added | **40** |
| Sources formalized | **20** |
| Duplicates suppressed (real, production — not test) | **155** (60 NSE + 95 RSS, on a real identical second fetch) |
| New point-in-time-safe observations | **200** (160 + 40) |
| Signals no longer fetch-and-discard | **14 families** (8 market signal families via MarketObservation + 6 content source families via RawEvidence) |
| Storage growth (total DB, this window) | **+0.61 MB** — includes organic background-job growth, not attributable to the new warehouse tables alone (SQLite has no `dbstat` support here to split it precisely) |
| Average bytes/new record | **Measured bottom-up per table** (see below), not from the gross file-size delta, which conflates warehouse growth with organic growth |

**Real, measured average row composition** (not the file-size-delta method — more honest given the conflation above):
- Raw Evidence: real avg `raw_payload` = **761.7 chars**, real avg `title` = **96.8 chars** → computed row size (all columns + 2 indexes) ≈ **~1.3–1.4 KB/row**
- Market Observation: real avg `extra` JSON = **14.2 chars**, all other columns fixed-width/short → computed ≈ **~300 bytes/row** (unchanged from the earlier Batch 1 estimate, now cross-checked)

### Estimated growth — Market Observations (well-grounded: fixed cadence × fixed metric count, not content-dependent)

| Horizon | Rows | Size |
|---|---|---|
| Daily (15min, market-hours-gated — the real decided cadence) | 500 | ~150 KB |
| 30-day | 15,000 | ~4.5 MB |
| 1-year | 182,500 | ~54 MB |

### Estimated growth — Raw Evidence (⚠️ **provisional, early measured — see caveat below**)

| Horizon | Rows (wide, honest bound) | Size |
|---|---|---|
| Daily | **Not yet established — see caveat** | — |
| 30-day (if daily settles near the low end of the caveat's range) | ~150–4,500 | ~0.2–6 MB |
| 1-year (same caveat) | ~1,800–54,000 | ~2.4–70 MB |

**Caveat, exactly as instructed:** the 160 real Raw Evidence rows were captured across **two back-to-back manual fetch cycles within roughly 5 minutes of wall-clock time**, not a real production day. The second cycle proved the *ceiling* case (near-zero genuinely new content when nothing has changed since the last fetch, 0/155 new) — it did not establish a *steady-state* rate, since real content only appears as real news/filings actually happen over real elapsed hours. This is **not** a demonstrated daily rate. Do not treat the 30-day/1-year Raw Evidence figures above as forecasts — they're a bounded range between "almost nothing new" and "a full daily refresh of everything currently tracked," pending a real measurement after one full weekday collection cycle.

## 3. Quality section

**Raw Evidence** (160 rows):
| Quality | Count |
|---|---|
| good | 131 |
| filtered | 29 |
| invalid | 0 |
| parse_error | 0 |

Rows lacking a trustworthy `published_at` (correctly `NULL`, never a relative string or guess): **20 / 160 (12.5%)**.
Duplicates suppressed on real re-fetch: **155**.
Source revisions preserved as separate immutable versions: **0 in real production data so far** (expected — a genuine content revision takes real elapsed time to occur; not evidence of a gap) — **1 proven via a real, deterministic DB-backed test** (`test_same_stable_item_changed_payload_creates_a_new_version`).

**Market Observations** (40 rows):
| Quality | Count |
|---|---|
| fresh | 22 |
| source_failure | 18 |
| stale | 0 |
| estimated | 0 |

No "partial" quality state exists in either schema today — both use `good/filtered/invalid/parse_error` (Raw Evidence) or `fresh/stale/estimated/source_failure` (Market Observations); reporting the real enum values rather than forcing a category that isn't part of either design.

## 4. Bottom line

Phase 1 has closed **8 of ~20** identified market fetch-and-discard signals and **6 of 7** identified content sources, added **200 real point-in-time-safe observations**, proven duplicate suppression works on real data (155 real suppressions), and cost **~0.61 MB** of total DB growth in this window (with organic background activity, not warehouse growth, accounting for an unknown share of that — not separable without `dbstat`). Market Observations' growth rate is well-grounded (fixed cadence, deterministic). Raw Evidence's growth rate is **not yet established** and is explicitly labeled provisional pending a real weekday measurement — that's the next checkpoint's job, not this one's.

---

## Status: Batch 1 + Batch 2 complete, BEFORE-vs-CURRENT scorecard run with real numbers.

---

# Phase 1C — Complete Canonical Market Observation Coverage (2026-08-23)

## Batch 3A — highest-confidence existing fetchers

One canonical producer chosen per metric, per the explicit "no duplicate persistence pipelines" instruction. Real duplicates found and resolved:

| Signal family | Canonical producer chosen | Duplicate NOT used (left in place for its existing callers) |
|---|---|---|
| Global indices (Dow/S&P500/Nasdaq/FTSE/DAX/CAC/Nikkei/HangSeng/Shanghai/KOSPI) | `app/api/market.py::_GLOBAL_INDICES` (10-ticker superset) | `market_data.py`'s own narrower, overlapping `_US_INDICES`/`_ASIAN_MARKETS` |
| Commodities (Gold/Silver/Copper/Platinum/WTI/NatGas) | `app/api/commodities.py::_METALS_DEF`/`_ENERGY_DEF` (more complete, includes unit metadata) | `market_data.py::_COMMODITIES`'s narrower, overlapping Brent/Gold/Silver set |
| US futures (ES/NQ/YM) | `market.py::_US_FUTURES_TICKERS` | none found |
| ADRs (INFY/WIT/HDB/IBN) | `market.py::_ADR_TICKERS`, premium computed vs. a **real live** USD/INR quote (not a hardcoded rate — see bug below) | none found |
| DXY, EUR/INR, GBP/INR | `market_data.py::_COMMODITIES["DXY"]` / `market.py::_CURRENCY_PAIRS` | none found (only one place has these) |
| Macro rates (US 2Y/10Y Treasury, US Fed Funds, India Repo Rate, India 10Y G-Sec) | `macro_rates.service.get_macro_rate_state()` — the SAME real, cached function `opening_prediction_service.py`/weekend intelligence already call | none — reused the existing shared entrypoint directly rather than calling the 3 underlying sources independently |
| US VIX | `market_data.py::_US_INDICES["VIX"]` (`^VIX`) — a genuinely distinct instrument from India VIX, not a duplicate | — |

### One real bug caught before it shipped

The first draft of the ADR-premium calculation used a **hardcoded `83` for USD/INR** — a fabricated stale constant, a direct violation of this codebase's own no-fabrication discipline. Caught during self-review before any real capture ran; fixed to fetch the real live USD/INR quote (reusing the exact same quote already captured for the `USDINR` metric) instead.

## Batch 3B — derived/lower-confidence signals, honest metadata added

| Signal | Quality | Metadata now attached |
|---|---|---|
| Market breadth (advancing/declining) | `estimated` (new) | `method="sampled — 49-symbol Nifty 500 subset, not a real exchange-wide feed"`, `sample_size=49` |
| FII/DII net flow | `estimated` (upgraded from `fresh` — Batch 1's original label understated how derived this figure is) | `method="NSE previous-session FII/DII net flow"`, `source_lag="previous_session"`, `as_of` |
| PCR / Max Pain | `estimated` (upgraded from `fresh`) | `method="computed from live NSE option-chain open interest"`, `source_lag="live"`, `as_of` |

`"estimated"` is now a real, distinct success state (not a failure) — `capture_market_observations()`'s own summary counting was fixed to reflect this (a real bug caught by re-running the test suite after adding it: the first test run showed `42 fresh + 9 failed != 54 total`, exposing that 3 rows in `"estimated"` quality weren't being counted anywhere).

## Real verification — live capture, 54 metrics (up from 20)

```
{'total': 54, 'fresh': 42, 'estimated': 3, 'source_failure': 9, 'duplicate_suppressed': 0, 'session': 'weekend'}
```

The 9 real failures are honest, explainable, and consistent with Batch 1's own weekend findings: 7 thin-quote sector ETFs (same ones as before) + PCR_NIFTY + MAX_PAIN_NIFTY (NSE's option-chain has no live session to scrape on a weekend). Every new Batch 3A signal family (global indices, US futures, ADRs, commodities, currency pairs, macro rates) succeeded — these are genuinely available even off-hours via yfinance/Treasury/Fed data, unlike NSE-specific intraday-only signals. A real, incidental finding surfaced too: RBI's WSS source hit a live parse issue (`week_ended_header_not_found`) — pre-existing in that provider, unrelated to this batch, correctly resulted in `INDIA_REPO_RATE`/`INDIA_10Y_GSEC` failing honestly rather than masking it.

**Source Registry**: 20 → **30** sources (10 new), via a **corrected upsert-based seed function** — the original delete-all-then-reinsert pattern was a real risk once `MarketObservation`/`RawEvidence` rows started holding real foreign keys into this table; fixed to update-in-place before any real re-seed ran.

Full test suite: **48/48 passing**, including the fixed `capture_attempts`/`duplicate_suppressed` assertions (both were hardcoded to `20` in the Batch 1 tests — now derived from the real per-cycle count instead of a number that would silently drift out of sync every time a signal family is added).

## ⚠️ Full weekday verification — genuinely not possible right now

**Today is a real weekend.** Everything above is honestly verified against real external sources, but it is not, and cannot yet be, the "one full real weekday collection-cycle verification" you asked for as the Phase 1 completion gate — that requires real elapsed trading hours (9:15 AM–3:30 PM IST) with the scheduler actually running across the day, which isn't something this session can fast-forward through or fabricate. What's confirmed instead: the off-hours gate behaves correctly (Batch 1D), all Batch 3 signal families fetch and persist correctly against real data right now, and the full pipeline is live and scheduled (`run_price_monitor_cycle` → `capture_market_observations_if_due`, still wired from Batch 1D, now capturing 54 metrics instead of 20 whenever it fires during real market hours).

**Recommendation**: leave the system running as-is (scheduler already wired, nothing further to build) and revisit the real weekday scorecard on the next trading day — that's a measurement checkpoint, not more implementation work.

---

## Status: Phase 1C (Batch 3A + 3B) complete — all identified reliable market signals are now either canonically persisted (54 metrics) or explicitly excluded with a documented reason (BSE, India Petrol retail estimate, duplicate ticker maps left for their existing live-render callers only). Raw Evidence live for RSS/NSE/RBI/PIB/SEBI/Fed. Source Registry covers 30 real sources. No new duplicate persistence pipelines were introduced — every duplicate found was resolved to a single canonical producer. **Blocked only on real elapsed trading hours** for the final full-weekday scorecard.
