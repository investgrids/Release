# WAREHOUSE CONSUMPTION AUDIT — READ ONLY

Measured live against the **real production database** (Railway service `backend`, `sqlite+aiosqlite:////data/ig.db`, via `railway ssh` + a read-only (`mode=ro`) SQLite connection — zero writes, zero migrations, zero scheduler/config changes, zero deploys). All numbers below are re-measured now, not carried over from the Phase 1 local-dev audit. Code paths verified by direct file reads against `d:\IG` (branch `main`), not assumed. Timestamp of this audit: 2026-08-25, ~10:20–10:45 UTC.

**The question this audit actually answers**: not "did Warehouse collect rows" (yes, cleanly) — but *"can MarketRipple retrieve the right evidence for the right entity at the right time, with provenance, without contamination?"* The short answer, proven with real production data in §6: **not yet, for one specific, well-scoped, already-understood reason** — not a design failure, a fixable gap.

---

## 1. Warehouse health scorecard

Real production measurements, `market_observations` / `raw_evidence` / `sources`:

| Dimension | Verdict | Measurement |
|---|---|---|
| **Capture completeness** | **PASS** | Day 2 (2026-08-25, the first genuinely complete NSE session since deploy) captured **25/25 expected 15-minute buckets**, zero missing buckets, across all 54 tracked metrics. Day 1 (2026-08-24) captured 20/25 buckets — a partial day, because deploy/first-capture happened mid-session at 05:15 UTC (10:45 IST), exactly matching the known deploy time. |
| **Source reliability** | **WARN** | Day 2: 1044 fresh (77.3%) / 75 estimated (5.6%) / 231 source_failure (17.1%). **9 of 54 metrics failed 100% of the time, every single bucket, all day**: `SECTOR_REALTY`, `SECTOR_PRIVATE_BANK`, `SECTOR_METAL`, `SECTOR_MEDIA`, `SECTOR_IT`, `SECTOR_FMCG`, `SECTOR_ENERGY`, `PCR_NIFTY`, `MAX_PAIN_NIFTY` — not intermittent, a persistent, reproducible break. 36/54 metrics (67%) were 100% fresh all day. `SECTOR_PRIVATE_BANK`'s 100% failure directly affects the ICICIBANK case study below. |
| **Freshness** | **PASS (for what exists)** | Latest `market_observations` row: 2026-08-25 09:45 UTC. Latest `raw_evidence` row: 2026-08-25 10:20 UTC. Both current as of this audit — the writers are live and running right now. |
| **Continuity** | **WARN — too early to call, real depth is 2 days** | `market_observations`: 2026-08-24 05:15 → 2026-08-25 09:45 UTC (2 calendar days, 1 full session). `raw_evidence`: same window, 1526 rows. This is real, correct data — but genuinely 2 days deep, not the months implied by "collection exists." |
| **Deduplication** | **PASS, proven on real data** | 1526 raw_evidence rows / 1506 distinct `evidence_key`s → 17 keys have >1 version (a real content revision produced a new immutable version under the same key, exactly as designed) — not duplication, versioning. `MarketObservation`'s `UNIQUE(metric, source_id, observation_time)` constraint means the DB itself would reject a true duplicate; no `duplicate_suppressed` counter is persisted anywhere (an ephemeral per-call return value, not stored), so live duplicate-suppression can't be measured after the fact — only inferred from the absence of constraint violations, which is what the clean row count already shows. |
| **Evidence quality distribution** | **PASS, honestly labeled** | `raw_evidence.quality`: good=1256 (82.3%), filtered=270 (17.7%), invalid=0, parse_error=0. `published_at` NULL (honest, never a guessed relative string): 34/1526 (2.2%). |
| **Entity linkage** | **FAIL** | Zero. No entity/company/symbol column exists on `raw_evidence`, `market_observations`, or `sources` (confirmed via `PRAGMA table_info` on all three, live). A working *join* to any entity-linked table was tested empirically (§6) and also fails, for two independent structural reasons. This is the single blocking finding of this entire audit. |

**Source Registry**: 30 rows, `rights_basis` honestly populated for every one (`official_rss`=9, `vendor_data`=12, `unofficial_scraped_api`=5, `official_api`=2, `public_domain`=2). One real, minor gap found: `sources.last_success`/`last_failure` are **NULL for all 30 rows** — the health-tracking columns the schema was designed to carry are never actually written to, even though captures are demonstrably succeeding right now. Producer health has to be inferred from the data rows themselves (below), not from the registry's own bookkeeping fields.

**Operational footnote** (outside this audit's scope but worth flagging): the Railway volume is at 459MB/500MB (92%). The DB file itself is only 80MB — something else on that volume accounts for the other ~380MB. Not a Warehouse-specific finding; noted because any recommendation to grow Warehouse storage should account for this headroom constraint.

---

## 2. Current raw-material inventory

**MARKET** — real, 54 metrics, `market_observations`, 2 days deep:
- Indices: NIFTY-adjacent (BANKNIFTY, GIFT_NIFTY), 10 global indices (Dow/S&P500/Nasdaq/FTSE/DAX/CAC/Nikkei/HangSeng/Shanghai/KOSPI), 3 US futures.
- Volatility: INDIAVIX, US_VIX.
- FX/rates: USDINR, EURINR, GBPINR, US 2Y/10Y Treasury, US Fed Funds, India Repo Rate, India 10Y G-Sec.
- Flows/positioning: FII_NET, DII_NET (estimated quality — previous-session lag, honestly labeled), PCR_NIFTY / MAX_PAIN_NIFTY (**currently 100% broken in production**, see §1).
- Commodities: Gold/Silver/Copper/Platinum/WTI/NatGas/Brent/DXY.
- Sector: 12 sector ETF proxies (**7 of 12 currently 100% broken in production**, see §1) + market breadth (labeled `estimated`, sampled from a 49-symbol Nifty 500 subset — honest, not a real exchange-wide feed).
- ADRs: INFY/WIT/HDB/IBN.

**EVIDENCE** — real, `raw_evidence`, 1526 rows, 2 days deep, but only **6 of 30 registered sources are actually producing content**: `nse_corporate_announcements` (846, 55%), `rss_ndtv_profit` (292), `rss_economic_times_markets` (191), `rss_livemint_markets` (108), `rss_google_news_india` (84), `fed_press_releases` (5, one-time). **Zero rows from**: `rbi_press_releases`, `pib_finance`, `sebi_circulars`, `rss_business_standard_markets`, `rss_moneycontrol_latest` — consistent with the Phase 1A local-dev finding (RBI/SEBI returned 0 items, PIB hit a 403) now confirmed over a real 2-day production window rather than a 5-minute local test.

**ENTITY** — real evidence with real symbol/company tags **exists**, but not inside Warehouse: `news_articles.companies` is non-empty on 9,356/15,288 rows (61%); `events.companies` is non-empty on 9,378/9,563 rows (98%); `company_announcements.symbol` is populated on essentially all 1,639 rows. This is the entity-linked raw material MarketRipple's *existing* (non-Warehouse) pipeline already produces and already uses correctly (see [[project_page_intelligence_service fix]] earlier this session). Warehouse's own tables carry none of this.

**TEMPORAL** — real: `market_observations.observation_time` is bucketed and gapless for the one complete session measured; `raw_evidence.observed_at`/`ingested_at` are real, distinct, honest anchors (never a relative string). Largest real gap between consecutive raw_evidence ingests in the whole window: ~2.2 hours (consistent with a genuine overnight/low-content lull, not an outage — content arrival is inherently lumpy, not a steady clock).

**OUTCOME** — **not yet supportable**. Two days of Warehouse history and, separately, only **7 trading days of `price_bars`** in *production* (2026-08-14 → 2026-08-24, 49 symbols, 343 rows total — a materially different, much thinner dataset than the ~5-year/62,734-row `price_bars` documented in the earlier *local-dev* Phase 1A audit; production and local dev have diverged and must not be conflated). There is not enough real subsequent-observation history in production, in either table, to evaluate "what happened after X" yet.

---

## 3. Writer map

| Producer | Scheduler/job | Writes | Frequency | Last real activity (from data, `sources.last_success` is unpopulated) | Failure behavior |
|---|---|---|---|---|---|
| `capture_market_observations_if_due()` (`app/services/warehouse/market_observations.py`) | `price_monitor` job, `IntervalTrigger(seconds=120)`, internally gated to fire once per real 15-min bucket, `session=="live"` only | `market_observations` | Every 2 min (fires ~every 15 min in practice, market hours only) | 2026-08-25 09:45 UTC (real, current) | Per-metric: writes an honest `source_failure` row (never skips, never fabricates) — proven live for 9 metrics above |
| `capture_raw_evidence()` (`app/services/warehouse/raw_evidence.py`), hooked into `BaseProvider.fetch_and_normalize()` via `capture_raw_evidence=True` on 6 provider classes | `ingest_news` job (`IntervalTrigger(seconds=settings.ingest_news_interval_sec)`, ~15 min) for RSS+NSE; `ingest_policy` job (~60 min) for RBI/PIB/SEBI/Fed | `raw_evidence` | 15 min (RSS/NSE) / 60 min (RBI/PIB/SEBI/Fed) | 2026-08-25 10:20 UTC (real, current) | Silent per-item skip if no `source_id` resolves; identical-content refetch suppressed at write time (dedup key), never overwrites |
| `source_registry_seed.py` | one-time seed, upsert-based (corrected from delete-all-reinsert per the Phase 1A audit) | `sources` | Not scheduled — run manually when the source list changes | 30 rows present, matches current code's source list | N/A |
| BSE | *(not wired — explicit exclusion)* | none | — | — | `capture_raw_evidence=False` on `BSEProvider`, by design (bot-blocked, no real content to lose) |

No other writer exists. `job_enrich_events`, `job_daily_generate`, and every other scheduled job in `scheduler.py` were checked — none reference `MarketObservation`, `RawEvidence`, or `Source`.

---

## 4. Reader/consumer map — and the write-only answer

**Method**: exhaustive `grep` for the model class names (`MarketObservation`, `RawEvidence`) and the literal table-name strings (`market_observations`, `raw_evidence`) across the entire backend (`app/**/*.py`), then separately across `app/api/**/*.py` for any route mentioning "warehouse". Every hit was individually inspected.

**Result**: exactly **8 files** reference the model classes, and exactly **16 files** reference the table-name strings anywhere in the codebase. Every one of them is either a model definition, the `db/models/__init__.py` registry, or the warehouse service module itself (writers + `health.py`). One apparent hit, `app/ai_pipeline/orchestrator.py:47`, is a false positive — it's a local Python variable named `raw_evidence` holding AI Search's own retrieval-fusion output, unrelated to the `RawEvidence` table (confirmed by reading the surrounding code — this is exactly the class of false-positive the audit asked to guard against). **Zero API routes reference "warehouse" at all** — there is no `/api/warehouse/*` endpoint, not even the admin-only one `health.py`'s own docstring says it was built for; only `tests/services/test_warehouse_health.py` calls it.

| Feature | Warehouse consumption | Evidence |
|---|---|---|
| Company Intelligence | **NO** | `page_intelligence_service.py`, `company_score_engine.py` — zero references to warehouse models/tables (grep, exhaustive) |
| AI Search | **NO** | `ai_pipeline/retrieval/market_retriever.py` calls `market_data.py::get_extended_indices/get_sector_changes/get_top_movers` directly — the *same underlying live yfinance fetchers* Warehouse also captures, but re-fetched live on every query rather than read from the already-captured, already-deduplicated table. `entity_resolver.py` uses the Intelligence Graph, not Warehouse. `historical_similarity_retriever.py` uses `historical_memory_service.py` (a hand-curated static table), not Warehouse. |
| Opportunity Radar (V1/V2) | **NO** | Zero references in `services/opportunity_v2/*` or the legacy pipeline |
| Events | **NO** | `event_pipeline.py`, `event_triage` — zero references |
| Ripple | **NO** | `intelligence_graph_service.py` — zero references |
| Articles/Newsroom | **NO** | `aipe/publisher.py`, `article_generator.py` — zero references |
| Breaking Intelligence | **NO** | Zero references found anywhere matching this surface |
| Premarket | **NO** | `market.py::_fetch_enhanced_premarket` — live fetch, unrelated to Warehouse; confirmed unchanged in the Phase 1B verification note ("both real endpoints, both still respond 200 after the wiring, unmodified behavior — neither reads from MarketObservation") |
| Market Overview | **NO** | Same — `/api/market/overview` calls its own live fetchers directly |
| Historical Intelligence | **NO** | No such consumer exists yet to check |

### Is Warehouse currently primarily WRITE-ONLY?

**Yes, unambiguously — not primarily, entirely.** Not one feature reads it. Not even an internal admin page does. This matches the original design intent exactly (collection and consumption were deliberately separated in Phase 1A/1B), so this is not itself a failure — it is the expected state of a system that has only just finished its collection phase and has not yet had a consumption phase built. The question this audit exists to answer is whether it's now *safe* to build that consumption phase, not whether collection "worked."

---

## 5. Company Intelligence readiness matrix

Evaluated against the simplified design (MarketRipple View / Why This View / What Changed / Key Evidence / What To Watch) shipped earlier today.

| Section | Readiness | Why |
|---|---|---|
| **MarketRipple View** | N/A — already served | This is `company_score_engine.py`'s real Company Score, entirely independent of Warehouse. Nothing to add here from Warehouse. |
| **Why This View** | N/A — already served | `page_intelligence_service.py` (fixed earlier today for the 3IINFOLTD/IIFL wrong-entity-contamination bug) already reads real, entity-matched `EventTriage`/news rows. Warehouse doesn't currently offer anything this doesn't already have. |
| **What Changed** | **READY WITH SMALL READ-LAYER WORK — market/macro context only** | `MarketObservation` needs no entity linkage to answer "what was VIX/the sector doing when this changed" — that's inherently market-wide, not company-specific. A `get_market_context_at(timestamp)` read method (§9) could genuinely add real sector/VIX/macro framing to this section today, with the caveat that `SECTOR_PRIVATE_BANK` and 8 other metrics are currently 100% broken (§1) and would need to degrade honestly, not silently. |
| **Key Evidence** | **NOT SUPPORTED BY CURRENT DATA** | This is the section that would want `RawEvidence` — real, durable, provenance-tagged evidence items. But §6 proves, on real production data, that there is currently **no working path** from any `RawEvidence` row to a specific company. Building this today would mean either (a) building nothing, correctly, or (b) building a naive keyword/title match — which §6 proves would immediately reproduce a contamination bug of the same shape already fixed once this session (3IINFOLTD/IIFL). Not ready until the entity-linkage gap (§10/§11) is closed. |
| **What to Watch** | **READY WITH SMALL READ-LAYER WORK — market/macro context only** | Same reasoning as "What Changed": forward-looking macro/sector context (e.g., "Brent Crude is up 3% this week, INDIAVIX elevated") doesn't need entity linkage and is real, current data today. Genuinely company-specific "what to watch" (e.g., a linked upcoming filing) would need the same entity-linkage fix as Key Evidence. |

**Bottom line**: two of five sections could take a narrow, honest, market-context enrichment today. The one section most people would assume Warehouse was *for* — Key Evidence — is exactly the one that isn't safe yet, and for a specific, provable, fixable reason.

---

## 6. ICICIBANK case study

Read-only, real production data, no LLM involved in producing these numbers.

**What Warehouse currently knows about ICICIBANK directly: nothing, structurally — but the raw content passed through it.** A naive `title LIKE '%ICICI%'` scan of `raw_evidence` surfaces 12 recent items, including the exact same "$1 billion Senior Unsecured Fixed Rate Notes" story that also exists, correctly and fully, as a `company_announcements` row for symbol `ICICIBANK` — the same real event, sitting in two disconnected rows with no relationship between them.

**What actually exists, correctly, outside Warehouse** (real, entity-linked, from `company_announcements`/`news_articles`/`events`):
- 7 real `company_announcements` rows, symbol=`ICICIBANK` (AGM proceedings, board meeting outcome, $1B USD bond issuance, ESOP allotment, Regulation 30 disclosures) — real subjects, real dates (2026-08-18 → 2026-08-24), real `sentiment`/`impact_score`.
- 15 `news_articles` rows and 18 `events` rows, both correctly tagged `companies=["ICICIBANK"]`.
- 7 real `price_bars` rows for ICICIBANK, 2026-08-14 → 2026-08-24 (daily OHLCV only — no intraday).

**Direct join test — does `RawEvidence` reach any of this real content?**

| Join attempted | Real ICICIBANK rows | Reachable via `raw_evidence.evidence_key` | 
|---|---|---|
| → `company_announcements.id` | 7 | **0** |
| → `news_articles.id` | 15 | **0** |
| → `events.id` | 18 | **0** |

**Root cause, proven, not inferred**: for NSE-sourced content (846/1526 = 55% of all raw_evidence — the source that actually carries real company symbols downstream), `RawEvidence.evidence_key` is built from `seq_id` (a real NSE sequence number), while `NewsArticle.id`/`Event.id`/`CompanyAnnouncement.id` are all built from `an_no` — which the code's own comments confirm is *never actually present* in real NSE payloads, so every one of those downstream tables silently falls back to a content-hash id instead. Two different identity schemes for the same real item, confirmed on real sampled ids (`raw_evidence`: `nse:nse-106755682`; `news_articles`/`events`: `nse-097988265a`/`nse-bm-3e337c8b7d`; `company_announcements`: `ann_nse-b8579229ac`). For RSS-sourced content (44%), the ids *do* correlate (406/675 raw_evidence rows successfully join to `news_articles`) — but `news_articles.companies` is hardcoded to `[]` for every RSS-sourced row (`RSSProvider.normalize()` never extracts a company), so even the working join yields zero entity data (confirmed: 0/406 joined rows have a non-empty `companies` array). **Both of Warehouse's two dominant evidence sources fail to reach entity linkage, for two different, independent, structural reasons.**

**Proof of the contamination risk the user specifically asked about** — a naive `title LIKE '%ICICI%'` search of `raw_evidence` (the only linkage mechanism available today if someone built one quickly) returns, alongside genuine ICICI Bank content:
- *"ICICI Lombard General Insurance Company Limited has informed the Exchange regarding Allotment of 71,297 Shares"* — **a different, legally separate real company** (ICICI Lombard, not ICICI Bank) that only shares a brand prefix.
- *"Senores Pharmaceuticals Limited has informed the Exchange regarding giving corporate guarantee for credit facilities availed by Apnar Pharma... from ICICI Bank Limited"* — a **Senores Pharmaceuticals** announcement that merely names ICICI Bank as its lender.
- *"NSE and BSE to Remain Open 1st February 2026... — ICICI Direct"* — a general market-holiday notice attributed to ICICI Direct (the brokerage) as its **byline/source**, not content about the bank at all.

This is the exact shape of the 3IINFOLTD/IIFL bug fixed earlier this session, reproduced here on demand against real, current production data. It is direct, empirical proof that entity linkage cannot be safely built on top of `RawEvidence` today without either (a) fixing the id-correlation gap above, or (b) building real entity resolution (the same kind AI Search's `entity_resolver.py` already does via the Graph) rather than string matching.

**Price confirmation**: computable, but only at daily granularity, and not via Warehouse — `price_bars` (7 real days) is the only per-symbol price series; `MarketObservation` has no per-symbol series at all, only sector-level aggregates, and the one sector aggregate most relevant to a private bank (`SECTOR_PRIVATE_BANK`) is the metric that failed **100% of the time** in the full session measured (§1) — confirmed again here, specifically, at the exact timestamp nearest ICICI's most recent real announcement.

---

## 7. AI Search readiness

Real pipeline traced (`app/ai_pipeline/orchestrator.py::run_pipeline`): **Intent Detection → Parallel Retrieval → Evidence Fusion → Driver Ranking → Decision Intelligence → Answer Template → Model Call → Answer Validation.**

| Pipeline stage | What exists today | Warehouse involvement |
|---|---|---|
| Intent classification | `fast_classify()`, real | None expected here |
| Entity resolution | `entity_resolver.py` → `intelligence_graph_service.get_full_graph()` — real, working, Graph-based | **None** — and this is actually good news: a real entity-resolution mechanism already exists independent of Warehouse's own (currently nonexistent) linkage. Any future Warehouse consumer should resolve through *this*, not reinvent entity matching. |
| Market retrieval | `market_retriever.py` → `market_data.py` live fetchers (same underlying yfinance calls Warehouse also now captures) | **None — duplicate fetch.** This is the single cheapest, lowest-risk Warehouse win identified anywhere in this audit: swapping a live re-fetch for a read of the already-captured, already-deduplicated `market_observations` row needs no entity linkage at all. |
| News/Event retrieval | `news_retriever.py`, `event_retriever.py`, `company_retriever.py` — real, entity-linked (`news_articles.companies`, `events.companies`) | None — these already read the real, entity-tagged tables, same ones §6 shows Warehouse can't currently reach |
| Historical similarity | `historical_similarity_retriever.py` → `historical_memory_service.find_similar_events()` → the hand-curated `historical_market_events` table | None. This table's own reliability was already separately flagged as "optimistic" per this codebase's prior audit; Warehouse's 2-day depth couldn't replace it even if wired |
| Evidence fusion / ranking / decision / answer | Real, downstream of the above | None |

**Bottom line**: AI Search already has a working entity-resolution layer it could hand a Warehouse consumer for free. The one concrete, safe, immediate win is the market retriever's duplicate live-fetch — everything else needs the same entity-linkage fix Company Intelligence needs before it can safely use `RawEvidence`.

---

## 8. Historical-readiness matrix

| Question | Verdict | Reason |
|---|---|---|
| "What happened earlier today?" | **READY** | `market_observations` has real, gapless intraday buckets for the current session; `raw_evidence` has real same-day items with honest timestamps. |
| "What changed since yesterday?" | **READY, barely** | Exactly one prior complete day exists (2026-08-24, partial) plus today (2026-08-25, complete). A yesterday-vs-today comparison is technically possible on 2 real data points — genuinely thin, but real, not fabricated. |
| "What happened after this event?" | **NOT READY** | Needs real subsequent observations across a meaningful window; only 2 days of Warehouse history exist total. |
| 5-day reaction analysis | **NOT READY** | Same reason, and separately: production `price_bars` (the per-symbol series that would carry this) is only 7 trading days deep for a 49-symbol subset — confirmed live, materially different from the ~5-year local-dev `price_bars` documented in the earlier Phase 1A audit. Do not assume production has that depth; it does not, today. |
| 20-day reaction analysis | **NOT READY** | Same — not enough elapsed real days in either table. |
| Historical event matching | **NOT READY** | The only real matching mechanism today (`historical_memory_service.py`) runs on hand-curated static data, not Warehouse; Warehouse has nowhere near the depth to support this on its own yet. |
| Success-rate percentages | **NOT READY** | No real outcome-labeled dataset exists yet tying a Warehouse-observed event to a real subsequent result. |
| Probability estimates | **NOT READY** | Same — would require the above first. |
| Predictive pattern intelligence | **NOT READY** | Same, and separately out of scope per this audit's own instruction not to let a one-day gate imply this capability. |

No LLM-generated statistic was accepted as evidence for any row above — every "NOT READY" is backed by a real row count or a real code-path absence, stated above.

---

## 9. Storage vs. intelligence — explicit boundary

Warehouse stores observations and evidence. It correctly does **not** currently invent bullish/bearish verdicts, scores, similarity percentages, probabilities, or recommendations anywhere in its own code (`market_observations.py`/`raw_evidence.py`/`health.py` — read in full; none of them compute or store any interpretive judgment, only capture/dedup/quality-label real fetched values). That discipline should be preserved by any consumer built on top of it: a future `get_company_evidence()`/`get_market_context_at()` read layer should return raw rows with provenance, never a derived verdict — verdicts stay downstream, in the existing decision-intelligence layers (`company_score_engine.py`, `ai_pipeline/decision/`), exactly as today.

---

## 10. Proposed consumption boundary (design only — not implemented)

```
Warehouse (market_observations, raw_evidence, sources)
    ↓
Warehouse Read Service  (new: app/services/warehouse/read_service.py —
                          same package the writers/health.py already live in,
                          not a new top-level service)
    ↓
  ┌─ get_market_context_at(timestamp) -> real sector/VIX/macro snapshot near a given time
  │    justified by: real, gapless, entity-independent data (§1); no blocker
  │
  ├─ get_recent_market_observations(metric, since) -> real time-series slice
  │    justified by: same, real query already proven by health.py's own aggregate queries
  │
  └─ get_evidence_for_entity(entity_id, since)  -- NOT implementable correctly today
       blocked on: the evidence_key/entity-id correlation gap (§6). Do not build this
       method until that gap is closed — a stub that "mostly works" here is exactly how
       the 3IINFOLTD/IIFL bug happened the first time.
```

Fits the existing architecture directly: `health.py` already lives in `app/services/warehouse/`, already does read-only aggregate queries against these exact tables, and is the natural home for the entity-independent methods above — no new service layer needed for those two. `get_evidence_for_entity` is deliberately listed as *not yet implementable*, not merely deferred, because implementing it today without the linkage fix would require either doing nothing (dead code) or building the naive matching §6 proves is unsafe.

---

## 11. Exact first recommended consumer

**Not** "Company Intelligence / AI Search evidence retrieval," despite that being the natural first guess (and the owner's own stated likely preference) — the measurements say that specific slice isn't safe yet. The narrower, genuinely-ready first consumer:

**AI Search's `market_retriever.py`, switched from a live re-fetch to `get_market_context_at()`/`get_recent_market_observations()`.** This is the single lowest-risk, highest-confidence win in this entire audit:
- Needs zero entity linkage (§1's one real blocker doesn't apply).
- Removes a real, currently-duplicated live fetch (the exact same yfinance calls already run twice — once for the live page render, once now for Warehouse capture).
- The data is real, current, gapless, and honestly quality-labeled today.
- Immediately gives AI Search something it doesn't have today: a real point-in-time market snapshot instead of "whatever yfinance returns right now," which starts to matter the moment a query isn't about this exact instant.

A close second, same risk profile: enrich Company Intelligence's "What Changed"/"What to Watch" sections with the same `get_market_context_at()` call — real sector/macro framing, no entity linkage required, degrading honestly on the 9 currently-broken metrics rather than silently.

---

## 12. Remaining data/history requirements

- **Fix the evidence_key ↔ entity-id correlation gap** (§6) before building any RawEvidence-based entity consumer. This is narrow and already fully diagnosed: either backfill `RawEvidence.external_id`/`evidence_key` for NSE items to use the same id scheme `NewsArticle`/`Event`/`CompanyAnnouncement` actually use (the content-hash fallback, since `an_no` doesn't exist in real data), or add a genuine join column at write time. Not proposing which — that's implementation, out of scope for this audit.
- **Fix the 9 permanently-broken market metrics** (§1), especially `SECTOR_PRIVATE_BANK` and `PCR_NIFTY`/`MAX_PAIN_NIFTY`, before leaning on sector-level "What Changed" framing for financial-sector companies specifically.
- **Populate `sources.last_success`/`last_failure`** — currently dead columns; would make producer-health monitoring real instead of inferred from data rows.
- **More elapsed real days** before any "what happened after X" / reaction-analysis / probability work — no shortcut exists; this is calendar time, not engineering.
- **Re-confirm production `price_bars` depth** before assuming any reaction-analysis capability exists — it is 7 days/49 symbols today, not the 5-year dataset the local-dev environment has; these two databases have diverged and should not be conflated again in a future audit.

---

## 13. FINAL VERDICT

**B. WAREHOUSE READY FOR LIMITED CONSUMPTION**

Not (A) — the collection mechanics are real, honest, deduplicated, gapless where measured, and actively running right now; there's real, usable raw material, not nothing. Not (C) — broad consumption, especially anything entity-specific, would reproduce a bug this session already spent real effort fixing once.

**WHAT WE CAN USE NOW**: `market_observations` for entity-independent market/macro/sector context (§10's `get_market_context_at`/`get_recent_market_observations`) — real, current, safe. First consumer: AI Search's market retriever (§11).

**WHAT NEEDS MORE DATA**: anything historical — reaction windows, event matching, success rates, probabilities (§8). No shortcut; needs real elapsed days, in both `market_observations`/`raw_evidence` and, separately, production's own thin `price_bars`.

**WHAT SHOULD REMAIN DISABLED**: any `RawEvidence`-based entity/company evidence retrieval (Company Intelligence's "Key Evidence", any per-company AI Search evidence, any future Article Truth Layer evidence sourcing from Warehouse) until the evidence_key/entity-id correlation gap (§6, §12) is closed. Building this today, even carefully, risks re-deriving the exact contamination pattern already fixed once.

**WHAT TO BUILD NEXT** (when you're ready to implement, not now): (1) the two entity-independent read methods and wire AI Search's market retriever to them; (2) separately, fix the NSE evidence_key/entity-id correlation gap; (3) only after (2) is verified on real data the same way §6 verified its absence, build `get_evidence_for_entity` and let Company Intelligence's Key Evidence section consume it.
