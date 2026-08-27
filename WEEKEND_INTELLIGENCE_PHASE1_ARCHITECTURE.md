# PHASE 1 — WEEKEND INTELLIGENCE BACKEND ARCHITECTURE DESIGN

**Architecture design only. Nothing in the codebase was modified, created, migrated, installed, committed, pushed, or deployed to produce this document.** Phase 0 (`a4159c6`) is untouched. The 3 local unpushed commits are untouched.

Repo root `D:\IG` (backend: `apps/backend`, frontend: `apps/web`). Method: 3 additional targeted read-only investigations run specifically to fill gaps the Phase 0 audit didn't cover (Friday-close reality, evidence/signal landscape, Kronos feasibility), consolidated here with everything already established in `WEEKEND_INTELLIGENCE_AUDIT.md`. Every material claim carries file/function/line; anything not directly verified says so.

---

## 1. Map the Existing Pipeline — Friday Market State Sources

| Source | Function | Model/Cache | Timestamp available? | Suitable for Friday baseline as-is? |
|---|---|---|---|---|
| Nifty/Bank Nifty/VIX (price-monitor alerting) | `run_price_monitor_cycle` — `app/services/intelligence/price_monitor.py:34-80` | none — in-memory `_last_prices` dict only | No | **No** — writes nothing durable, alert-only |
| Market narrative/mood/pulse/confidence | `StoryEngineWorker` → `read_story()` — `app/services/intelligence/engine.py:90-136` | `market_stories` table (`app/db/models/intelligence.py:56-73`) | Yes — `generated_at`, tz-aware | **Yes** — the one genuinely durable, timestamped producer; already carries Phase 0's `session_label_for` staleness labeling |
| Themes | `run_theme_scoring` — `app/services/intelligence/theme_worker.py:97,127` | `theme_state` table (`intelligence.py:79-93`), `updated_at` | Yes, but UPSERT-only | Partial — current value survives, history doesn't (unique on `theme`) |
| Sector performance | `get_sector_changes()` — `app/services/market_data.py:847` | in-process dict, 300s TTL | No persisted timestamp | No — pure TTL cache, gone on restart |
| VIX | `price_monitor.py:19`, `_fetch_enhanced_premarket` — `app/api/market.py:544` | in-process TTL cache only | No | No |
| Breadth (advances/declines) | `market_overview()` — `app/api/market.py:471-510` | **estimated**, not counted (`est_advances = round(sample_pos/sample_total*1200)`, `market.py:493-494`) | No | No — statistically scaled estimate off a gainers/losers sample, not a real A/D count, and not persisted |
| FII/DII | `_fetch_fii_dii()` — `app/api/market.py:168-204`, NSE scrape | in-process cache, 6h TTL | No | No — real data but cache-only, and NSE's own field already lags one session |
| PCR/Max Pain | `_fetch_pcr_data()` — `app/api/market.py:207-259`, NSE scrape | in-process cache, 15min TTL | No | No |
| Top movers | `get_top_movers()` — `app/services/market_data.py:752` | in-process cache | No | No |
| Opportunities (current state) | `OpportunityService` — `app/services/opportunity_service.py:38` | `opportunities` table, `created_at`/`updated_at` | Yes | Partial — live current-state table, not a dated history; tells you *when* it last changed, not what it looked like specifically Friday 3:30 PM unless nothing's changed since |

**Bottom line**: only `MarketStory` (and, more weakly, `ThemeState`/`Opportunity` as mutating current-state tables) is durable and timestamped enough today to reconstruct "Friday's close." Everything genuinely close-shaped — VIX, breadth, FII/DII, PCR, sector performance, top movers — lives only in short-TTL in-process caches with no queryable history. `MarketSnapshot` (`intelligence.py:36-51`) was clearly designed to be this exact table (its own docstring: `MarketSnapshot (PriceMonitor) → price context`) but **is dead code — confirmed zero writes anywhere in the repository.** `price_monitor.py` never imports it; the only two references are read-only (`market_story_engine.py:249-273`, `publishing.py:274` — the latter an ops-health check that will always show "never" in production as a direct symptom of this gap).

---

## 2. Friday Close Snapshot — Design

**Can existing `MarketSnapshot` be reused?** Yes, and it should be — but it needs two things neither exists today: (1) schema additions for fields it's missing (`pcr`, `top_movers`, an explicit opportunities/risks summary — `fii_net` already exists as a column but is never populated since nothing writes the table), and (2) an actual writer. Extending a dead-but-correctly-shaped table beats inventing a new one.

**Is its current schema sufficient?** Close but not quite — it has `nifty_level`/`banknifty_level`/`vix`/`advances`/`declines`/`fii_net`/`sector_ranks`/`top_themes`/`mood`/`story_hash`, but no PCR, no top-movers list, no opportunities/risks summary, and — critically — no explicit "is this the market-close snapshot" marker (there's no `snapshot_type` column distinguishing a periodic tick from an intentional end-of-day capture).

**Does the app currently persist an actual closing snapshot?** No — confirmed above, zero rows ever written.

**Extend vs new table?** Extend. The table's docstring-stated purpose already matches; the gap is purely "never wired up," not "wrong shape."

**Should Friday Close be immutable once captured?** Yes — this should be a single INSERT at a well-defined moment (see below), never updated afterward. Mutating a "close" record after the fact would reintroduce exactly the kind of staleness ambiguity Phase 0 just fixed for `MarketStory`.

**How should holidays be handled?** The capture must be driven by `last_trading_date`, not a hardcoded "if today is Friday" check — see §18. The trigger condition should be "this is the final scheduled tick before the market's next session is not `live`" (derivable from `_market_session()`, `engine.py:35-46`, which already correctly detects weekend — it just doesn't yet detect holidays, a separately-scoped gap per §19).

**Recommended minimal design**: add one new field, `snapshot_type` (`"periodic" | "close"`), to `MarketSnapshot`, and add exactly one new call site — not a new scheduled job, but a condition check inside the *existing* `run_price_monitor_cycle` (`price_monitor.py:34`, already running every 120s) that fires an explicit `db.add(MarketSnapshot(snapshot_type="close", ...))` when the tick crosses 15:30 IST on a trading day, assembled from the same real sources §1 already maps (sector performance, FII/DII, PCR, top movers — each already has a working fetch function, just never persisted). This reuses the existing 2-minute cadence infrastructure instead of adding a new trigger, and turns "Friday's close" into `SELECT * FROM market_snapshots WHERE snapshot_type='close' ORDER BY ts DESC LIMIT 1` — a real, simple, durable query that does not exist today.

---

## 3. Weekend Evidence Collection

| Source | Persisted? | Real timestamp? | Query "> Friday close AND <= now"? | "New since Friday" identifiable? |
|---|---|---|---|---|
| News (`NewsArticle`) | Yes (`news_articles`) | Yes, `published_at` (string, source-derived) | Yes | Yes, by timestamp filter |
| Events (`Event`, `EventCompany`, `EventSector`, `EventPolicy`, `EventSimilar`, `EventTriage`) | Yes | `event_date` often NULL upstream; `published_at`/`created_at` reliable (ingestion time) | Yes, on `published_at`/`created_at` | Yes, though `event_date` gaps mean "when it happened" is sometimes only "when we saw it" |
| Policy (`GovernmentPolicy`) | Yes | `created_at` reliable; `announcement_date` always NULL (`ingest_tasks.py:182` always passes `None`) | Yes, on `created_at` | Yes |
| Company announcements (`CompanyAnnouncement`) | Yes | Real, NSE/BSE-sourced | Yes | Yes |
| Themes (`ThemeState`) | Yes, but UPSERT (one row per theme, no history) | `updated_at` | Only "last changed" — not a real interval query | Only for the single most recent change, not a full weekend timeline |
| Macro (`MacroRelease`) | Yes | `release_date` | Yes | Yes |
| Opportunities (`Opportunity`, `OpportunityCompany`, `OpportunityEvent`) | Yes | `created_at`/`updated_at` | Yes | Yes for new rows; UPSERT-style mutation on existing ones loses the "what it looked like Friday" version unless diffed at read-time before the weekend's mutations land |

**Can weekend evidence already be collected?** Yes for News/Policy/Events/Announcements — all their ingestion jobs are plain `IntervalTrigger`/unrestricted `CronTrigger` (§Phase-0-audit §12), so rows keep landing Saturday/Sunday exactly as on weekdays; RBI/PIB/SEBI genuinely do publish on non-trading days. NSE/BSE-sourced volume (the majority of News/Events/Announcements) will naturally be thin on weekends — a data-volume gap, not a code gap. `ThemeState`'s lack of history is the one real structural limitation in this list: it can tell you the *current* theme scores but not "what Banking's score was at Friday close" once the weekend's `run_theme_scoring` ticks (every 10 min, unrestricted) have overwritten it — which is exactly why §5's diff design cannot rely on `ThemeState` alone for its baseline half.

---

## 4. Evidence Normalization Layer

**Does this need a new DB model, or can it stay an in-memory DTO?**

Recommendation: **in-memory DTO, assembled at aggregation time from existing tables — no new persisted "EvidenceItem" table.**

Reasoning, grounded in the signal-classification investigation:

- `AICompanySignal` (`app/db/models/company_signal.py:27-59`) already has almost exactly the proposed `EvidenceItem` shape: `source_type`, `source_id`, `symbol`, `sector`, `signed_magnitude`, `confidence`, `quality`, `reason`, `signal_at`. It already has a working aggregation engine (`company_score_engine.py::compute_company_score()`, lines 247-322) with recency decay and a historical-accuracy multiplier.
- But: (1) it is **not registered** in `app/db/base.py` or `app/db/models/__init__.py` — confirmed still true, and independently confirmed by an in-repo test comment (`tests/test_migrations.py:210-212`) already flagging this exact gap. Its table only exists today as a side effect of an unrelated router-import chain. This is a pre-existing bug (same class as the `ReturningUserFeedback` gap from the earlier audit), not something Weekend Intelligence should build on top of uncorrected — but the fix (adding one import line to `base.py`) is trivial and separable from Weekend Intelligence itself.
- (2) Roughly half of `AICompanySignal`'s real-world rows (the opportunity-sourced half) carry `signed_magnitude`/`confidence` that are arithmetically derived from `_score_opportunity()`'s heuristic formula (`opportunity_generator.py:83-88`, position-decayed further by `max(70, score - i*2)`), not independent per-company evidence — despite in-code comments elsewhere calling this "real." Any evidence-normalization layer must treat this half as heuristic-derived, not ground truth.
- `Fact` (`app/db/models/fact.py`) is a different concern entirely — a daily claim-dedup cache for Daily Brief narrative writing, not company/sector evidence. Not a fit for this layer.
- `ScoreHistory` is a real audit trail of score progression, but per-entity-per-update, not evidence-item-shaped — it records outcomes of scoring, not the raw evidence that fed them.

Given the underlying source tables (`NewsArticle`, `Event`+junctions, `GovernmentPolicy`, `CompanyAnnouncement`, `AICompanySignal`) are all already durably persisted with real timestamps (§3), a normalized `EvidenceItem` view can be built as a **pure Python assembly function** (query each source table for the `> last_trading_close AND <= now` window, map each row type into a common lightweight dataclass/dict shape) called fresh every time the aggregator runs, with no new table. This avoids duplicating data that's already durable, keeps the new persistence footprint to the one genuinely missing piece (§6's snapshot), and matches the "prefer references/IDs over copied blobs" principle directly — the assembled `EvidenceItem` list, when it needs to be referenced from a persisted `WeekendIntelligenceSnapshot`, is stored as a list of `(source_type, source_id)` pairs, not copied content.

---

## 5. "What's Changed Since Friday"

**Does anything already support this?** Yes — with an important correction to the Phase 0 audit's finding that MIE has zero cross-day comparison. That's still true *for MIE specifically*, but a separate, narrower, already-shipped mechanism exists and is live today:

`app/db/models/homepage_snapshot.py::HomepageDailySnapshot` (table `homepage_daily_snapshots`, unique on `snapshot_date`) + `app/services/homepage_intelligence.py::record_snapshot_if_missing()` (lines 47-66) and `get_yesterday_changes()` (lines 69-111). This is a real, working, **already weekend-safe** day-over-day diff: it queries the most recent snapshot strictly *before* today (`snapshot_date < today`, ordered desc, `limit(1)` — not a naive `today - 1 day` subtraction), so calling it on Monday correctly walks back to Friday even though no Sat/Sun snapshot exists. It's wired into `app/api/homepage_intelligence.py:57` and actually rendered on the homepage (`apps/web/app/page.tsx:471`, the `changes` array). Its limitation for Weekend Intelligence: sector-level only (~a handful of named sectors, -3..+3 derived scores), sourced from a single AIPE article's `sectors_affected` field, written once per day driven by user/article traffic rather than a guaranteed job.

**Design for Friday → Saturday → Sunday → Monday-morning comparison**: extend this exact proven pattern rather than inventing a new one — a new table, keyed by *checkpoint* rather than calendar date (since §7 requires multiple same-day versions), storing a compact structured summary (top sectors, top companies, opportunity/risk counts) at each checkpoint, diffed against the *previous checkpoint's row* using the identical "most recent prior row, not a naive time subtraction" query shape `get_yesterday_changes()` already validates.

**A, B, or both?** **B — event/evidence deltas, computed from full snapshots, not full snapshots compared field-by-field.** Each checkpoint should persist a compact structured summary (small enough to diff cheaply and to keep dozens of weekend versions without bloat) plus references to the `EvidenceItem`s (§4) that were new since the prior checkpoint — not a full raw-data snapshot recomputed and diffed wholesale. Full snapshots (A) would work but cost more to store and diff for no real benefit, since the meaningful "what changed" signal is inherently evidence-level (a new event, a new opportunity, a theme score crossing a threshold), not a full state comparison.

---

## 6. Weekend Intelligence Persistence — the central decision

**Smallest new persistent layer that gives the required capability without duplicating existing data:**

One new table — call it `WeekendIntelligenceSnapshot` — is justified. Nothing existing covers its actual job: a versioned, queryable, weekend-scoped *synthesis* record. `HomepageDailySnapshot` is too narrow (sector-only, daily granularity, single-article-sourced). MIE state is Redis-only with zero persistence or versioning. `MarketStory`/`Opportunity`/`ThemeState` are all live current-state producers, not a synthesized product that references across all of them.

**Design principle applied**: reference IDs, don't copy blobs. Concretely:

```
WeekendIntelligenceSnapshot
  id
  target_trading_date        -- the Monday (or next trading day) this is FOR
  last_trading_date          -- the Friday (or prior trading day) this is BASED ON
  version                    -- monotonic per target_trading_date
  is_current                 -- boolean; exactly one current row per target_trading_date
  generated_at
  checkpoint_label           -- "Saturday AM" / "Sunday PM" / "Monday Final" etc., human-facing

  overall_bias                       -- small enum/string, this snapshot's own output
  production_confidence              -- float, from confidence_service (kronos weight=0)

  top_sector_refs             JSON   -- [{sector, score}] — small, synthesized here, not a ref
  top_company_refs            JSON   -- [{symbol, evidence_item_refs: [...]}]
  opportunity_refs            JSON   -- [opportunity_id, ...]              -- REFS not copies
  risk_refs                   JSON   -- [{description, evidence_item_refs: [...]}]
  historical_analogue_refs    JSON   -- [historical_market_event_id, ...]  -- REFS not copies

  changes_since_prior         JSON   -- the §5 delta, evidence-level
  evidence_refs                JSON  -- [(source_type, source_id), ...]    -- REFS not copies

  market_snapshot_id          -- FK to the §2 Friday-close MarketSnapshot row

  experimental_signals        JSON   -- {"kronos": {prediction_record_id, experimental_confidence}}
                                      -- internal-only, never surfaced to users in V1

  status                      -- "ok" | "insufficient_evidence" | "degraded" (see §22)
```

Every `*_refs` field is IDs, not copied content — `top_company_refs`/`opportunity_refs` resolve against `Opportunity`/`OpportunityCompany` at read time; `historical_analogue_refs` resolve against `HistoricalMarketEvent`; `evidence_refs` resolve against the source tables `EvidenceItem` was assembled from (§4). Only small, genuinely-synthesized-here fields (`overall_bias`, `top_sector_refs`, `changes_since_prior`) are inline JSON, matching what `HomepageDailySnapshot.sectors` already does successfully at a smaller scale.

---

## 7. Versioning Strategy

**Store every version, or only material changes?** Store only material-change versions, plus scheduled checkpoints regardless of materiality (so "nothing changed since Saturday morning" is itself a real, visible fact, not a gap in the timeline).

**Mutable current + immutable history, or all-immutable?** All rows immutable once written (matches §2's "Friday Close should be immutable" reasoning and the existing codebase-wide pattern of append-only audit tables like `ScoreHistory`). "Current" is tracked via an `is_current` boolean flipped atomically (set old row's `is_current=False`, insert new row with `is_current=True`) rather than mutating a row's content in place — this is exactly the pattern `ScoreHistory` already uses successfully for "the 83 → 87 → 91 progression" (its own module docstring).

**What counts as a material update?** A configurable threshold on `changes_since_prior`'s size/magnitude (e.g., ≥1 new Critical/High event, or ≥N new evidence items, or a sector/company entering/leaving the top-N) — cheap to check against §4's assembled evidence list before doing any LLM/synthesis work, which directly answers §17's "don't recompute every 5 minutes if nothing changed."

**Preventing snapshot bloat**: a fixed number of scheduled checkpoints (§17) rather than continuous recomputation, each gated by the materiality check above — if nothing material changed, either skip the write entirely or write a cheap "checked, unchanged" marker row (no new LLM synthesis, `changes_since_prior: []`) so the query "what's the latest state" always has a recent row without needing to distinguish "no row" from "checked and nothing changed."

**Querying "what changed since the user last visited"**: straightforward with this shape — `SELECT * FROM weekend_intelligence_snapshots WHERE target_trading_date = :monday AND generated_at > :user_last_seen ORDER BY generated_at`, then concatenate each row's `changes_since_prior`. No new mechanism needed beyond the table itself.

---

## 8. Sector / Company Signal Synthesis

Classification of every existing score/signal source relevant to "Most Likely Beneficiaries" / "Stocks to Watch" / "Sectors to Watch" / "Highest Conviction Opportunities" / "Biggest Risks":

| Score/Signal | Type | Evidence |
|---|---|---|
| `scoring_engine.score_event_impact`/`score_company_impact` | **(a) real, deterministic, feature-based** | `app/services/scoring_engine.py:317-403` — explicit rule "no score is ever invented" (lines 19-26); combines caller-supplied features, invents nothing itself |
| `company_score_engine._accuracy_multiplier` | **(a) deterministic** | `company_score_engine.py:176-213` — neutral (1.0) below a 10-sample minimum rather than fabricated |
| `company_score_engine.compute_company_score` | **(d) derived aggregate** over mixed-type inputs | `company_score_engine.py:247-322` |
| `AICompanySignal.confidence` (article-sourced) | **(c) LLM self-rated**, passthrough | `content_templates.py:70` — the LLM is prompted to output this directly |
| `AICompanySignal.quality` (article-sourced) | **(b) heuristic checklist** | `quality_validator.py:100-104` — rule-based pass/fail ratio, not learned |
| `AICompanySignal.*` (opportunity-sourced, ~half of real rows) | **(b) heuristic**, arithmetically derived from `_score_opportunity()` | `opportunity_generator.py:257-258,302-309` — despite in-code comments elsewhere calling this "real" |
| `confidence_service.calculate_confidence` | mixed: **(a)** for 7/8 factors, **(c)** for `ai_certainty` | `confidence_service.py:57-144`, `ai_certainty` explicitly documented "AI self-rating" (line 24) |
| `opportunity_intelligence.compute_investment_verdict` | **(b) heuristic** lookup table | `opportunity_intelligence.py:36-56` — explicitly "no LLM call" |
| `intelligence/engine._derive_companies_to_watch` | **(b) heuristic** dedup-pick, not a scored rank | `engine.py:502-524` — inherits the parent event's score, computes nothing of its own |

**What can be reused for Weekend Intelligence's beneficiary/watch lists**: `company_score_engine.compute_company_score()` as the aggregation entry point (it already does recency decay + accuracy weighting), fed by `AICompanySignal` rows widened to include weekend-arrived evidence (§3/§4) — but the design must **not** present its output as more trustworthy than it is, since roughly half its inputs are heuristic-derived. `confidence_service.calculate_confidence()` is the right deterministic formula for `production_confidence` at the snapshot level (§6), reusing its existing 8-factor shape with `ai_certainty` supplied honestly (either a real LLM self-rating if a synthesis LLM call is used for the weekend narrative, or a fixed neutral value per the `company_intelligence.py:230` precedent when no LLM call backs a given field).

---

## 9. Opportunity Engine Reuse

Per the Phase 0 audit, `_score_opportunity()` (`opportunity_generator.py:83-88`) is `60 + min(20, events×3) + min(10, companies×1.5) + min(10, sectors×2)`, capped at 99, with `confidence = min(0.95, score/110)` — directly derived from the same count, not independent.

**What it can contribute**: a real, already-running, already-weekend-unrestricted signal of "how much verified activity clustered around this theme" — genuinely useful as *one input* to Weekend Intelligence, and it already runs on the exact daily cadence (`job_daily_opportunities`, 7:30 AM cron, no day-of-week gate) that would naturally produce a fresh read each weekend morning.

**What it should NOT be trusted to represent**: a market-conviction ranking. It counts activity, not quality or magnitude of the underlying events — three low-importance filings score identically to three high-impact ones. Its "confidence" is not epistemic confidence in the prediction, just a rescaled version of the same count.

**Should Weekend Intelligence expose its score directly?** No — not as a headline number. It should be surfaced as one labeled input among several (alongside the historical-analogue match and the evidence-count-weighted `compute_company_score`), never as *the* Monday-opportunities ranking on its own, consistent with the classification in §8.

---

## 10. Historical Memory

`historical_memory_service.find_similar_events()` (`app/services/historical_memory_service.py:138-193`) takes a query dict (`category`, `sectors`, `sentiment`, `market_regime`, `interest_rate_trend`, `crude_trend`) and returns ranked matches against `HistoricalMarketEvent` rows with real outcome data (`nifty_1d/3d/1w/1m`, `historical_winners`/`losers`, `key_lesson`).

**Inputs needed**: exactly the query-dict shape above — no changes to the matcher required.

**Can weekend events map into its categories?** Yes, mechanically — the same `classify_text`/`classify_with_ai` machinery (`pipeline/classifier.py`) that already tags category/sector/sentiment for events and opportunities can classify the *aggregate* weekend evidence the same way it classifies a single event today.

**One event or combined weekend state?** Combined weekend state — a single synthesized query dict built from the dominant category/sectors/sentiment across the weekend's evidence (already implicitly how `opening_prediction_service.py::_gather_historical()` builds its own query today, per the Kronos-feasibility investigation's full read of that file — reuse that exact pattern rather than inventing a second one).

**Multiple analogues retained?** Yes — `find_similar_events(limit=5, ...)` already returns a ranked list; the `WeekendIntelligenceSnapshot.historical_analogue_refs` field (§6) should keep the top 3-5 as references, not collapse to one.

---

## 11. Kronos Integration Architecture

**Storage decision**: reuse `PredictionRecord`/`PredictionEvaluation`/`CalibrationStat` — do **not** build a parallel prediction framework.

Confirmed: `PredictionRecord.source` is `String(32)`, `nullable=False`, with **no DB constraint, no Python enum, no schema-level allow-list** anywhere (`predictions.py:25-54`; confirmed via `app/services/prediction_service.py:100-113`'s `store_prediction(source: str, ...)` taking a plain string). Real production values today are `"aipe"`, `"ai_search"`, `"triage"` (the model's own inline comment listing `"ai_search | triage | graph"` is stale — `"graph"` isn't a real writer, `"aipe"` isn't in the comment but is real). `"kronos"` and `"weekend_intelligence"` slot in with zero schema changes.

**Design**:
- Kronos's raw prediction gets its own `PredictionRecord` row, `source="kronos"`, `target_entities` set to whichever symbols it scored, `prediction_text`/`confidence_score` from the model's own output. This flows through the **existing, unmodified** `job_evaluate_predictions` (`daily_tasks.py:256-271`) exactly like every other source — no new evaluator needed.
- The production `WeekendIntelligenceSnapshot.production_confidence` (§6) is computed via `confidence_service.calculate_confidence()` with **Kronos excluded entirely** — not "weight zero" as a term inside the formula (the formula has no Kronos-shaped input slot today), but genuinely not called.
- `experimental_confidence` is computed by additionally folding a Kronos-derived adjustment into a parallel, second computation, stored in `WeekendIntelligenceSnapshot.experimental_signals` (a JSON field, §6) referencing the Kronos `PredictionRecord.id` — never shown in any user-facing API response, only readable internally.
- **Stored fields for later evaluation** (`symbol`, `prediction_time`, `target_session`, `predicted_direction`, `predicted_range`, `model_version`, `input_window`, `confidence`/`uncertainty`, `actual_outcome`, `evaluation_status`) map directly onto existing `PredictionRecord` columns (`created_at`, `target_entities` including baseline price, `direction`, `confidence_score`, `horizon_days`) plus `PredictionEvaluation` (`actual_direction`, `actual_move_pct`, `verdict`, `evaluated_at`) — the only two fields with no existing home are `model_version` and `input_window`, which fit naturally into `PredictionRecord.confidence_factors` (already a JSON column, currently used for exactly this kind of supplementary metadata per its schema role) without a new column.

**Can existing `PredictionRecord`/`Evaluation`/`CalibrationStat` support this? YES.**

---

## 12. Kronos Data Availability Audit

**Direct answer: no durable historical-price warehouse exists anywhere in this codebase.** Every OHLCV path found is a live fetch behind at best a short in-process cache:

- `MarketDataService.get_historical_candles()` (`app/services/market_data_service/market_data_service.py:151-165`) — `MemoryCache`, `TTL_HISTORY = 300` (5 minutes, `memory_cache.py:65`), process-local `dict` + `RLock`, wiped every restart.
- Both providers behind it (`yfinance_provider.py:172-191`, `fyers_provider.py:129-141`) call the live API on every cache miss with no DB write-back.
- `GET /{symbol}/chart` (`stocks.py:78-80` → `market_data.py::get_stock_chart()`, lines 516-551) has **no cache at all** — fresh `yf.download()` every single request.
- Exposed period presets top out around ~130 daily bars (`"6M"`→weekly bars, `"1Y"`→weekly, `"3Y"/"5Y"`→monthly; only `"1M"` gives daily granularity, ~22 bars) — nowhere near a useful training/inference window through any UI-facing path. (`/api/data/history/{symbol}` does accept an arbitrary `interval` param that could in principle request more daily bars in one live call — but nothing persists the result either way.)
- Corporate-action adjustment relies entirely on yfinance's own `auto_adjust=True` — no in-app split/bonus handling exists.

**Answer to the direct question: NO, Kronos cannot realistically run against the existing data infrastructure without first creating a historical-price warehouse.** The smallest missing prerequisite is a new, dedicated persistence job (and likely a new table, e.g. `symbol × date → OHLCV`) that pulls and stores a rolling window (however many days Kronos's input window requires) per symbol, on its own schedule, independent of and prior to any Kronos inference work. This is real, non-trivial new infrastructure — not a Weekend Intelligence detail, a hard gate on Kronos existing at all.

---

## 13. Kronos Backtesting Design

Given §11's storage design, backtesting is largely "let the existing evaluation loop run and query it," not new machinery:

- **Direction accuracy / hit rate**: `PredictionEvaluation.verdict` (`correct|partial|incorrect|inconclusive`) aggregated by `source="kronos"`, exactly how `CalibrationStat` already aggregates by confidence level — the same rollup, filtered/grouped by source instead.
- **Precision among highest-confidence predictions**: filter `PredictionRecord.confidence_level="Very High"` (or top-decile `confidence_score`) joined to `PredictionEvaluation.verdict`, source-scoped.
- **Sector/top-5-stock ranking accuracy**: not directly covered by the existing per-symbol evaluation shape — would need a small new query comparing `WeekendIntelligenceSnapshot.top_company_refs`' ranking order at generation time against realized Monday returns, computed at evaluation time rather than stored as a new persistent field.
- **Incremental lift from Kronos**: the entire reason for storing `production_confidence` and `experimental_confidence` (§11/§14) separately — compute `CalibrationStat`-style accuracy for `source="weekend_intelligence"` (production) vs. a synthetic "production + kronos" cohort (reconstructable from `experimental_signals` at evaluation time) against the same `PredictionEvaluation.actual_direction`, and diff the two accuracy rates. This is a reporting query over existing data, not new storage.
- **Volatility error / calibration**: `CalibrationStat.calibration_factor` (`actual_accuracy/expected_accuracy`) already exists as a formula — apply it per-source the same way.

No second evaluator, no new evaluation table — genuine reuse, confirming §11's "YES."

---

## 14. Production vs Experimental Confidence

Already designed in §11/§6. Restated precisely:

- **`production_confidence`** — a real field on `WeekendIntelligenceSnapshot`, computed by `confidence_service.calculate_confidence()` using only the 8 existing factors, Kronos never in the input set. This is the only confidence value any external API response (§21) exposes.
- **`experimental_confidence`** — computed the same way, plus one additional Kronos-derived factor folded in, stored only inside `WeekendIntelligenceSnapshot.experimental_signals` (JSON), referencing the Kronos `PredictionRecord.id` so its own outcome can be evaluated independently via the existing pipeline (§11/§13). Never serialized in any user-facing route.
- Promotion path (increasing Kronos's real weight) is a future, evidence-gated decision made by comparing accumulated `CalibrationStat`-style accuracy for `source="kronos"` against the production baseline — not something this phase implements, just the storage that makes it possible later.

---

## 15. Monday Pre-Market Handoff

**Full read of `build_opening_prediction(db)`** (`app/services/opening_prediction_service.py`, 551 lines):

- Signature: `async def build_opening_prediction(db) -> dict:` — one positional arg, no extension point today.
- 4 layers, sequential, merged into one flat dict (lines 50-64): Signal (`_gather_signals`, 67-194/197-301), Event (`_gather_events(db)`, 304-347 — **already reads `CalendarEvent`**, i.e. the effectively-empty-in-prod calendar table, per §19), Historical (`_gather_historical`, 350-398 — calls `find_similar_events`), AI Reasoning (`_run_ai`, 401-517, prompt built from all three prior layers, `_call_with_fallback`, deterministic `_fallback_prediction` on failure).
- Cache: single global, non-keyed, in-process dict entry `"opening_prediction"`, 30-min TTL (`_TTL=1800`, lines 22-23) — not session-aware, not weekend-aware, lost on restart.

**Smallest interface for Weekend Intelligence to feed in**: add one optional parameter, `async def build_opening_prediction(db, weekend_context: dict | None = None)`, threaded into `_gather_historical()` (folding weekend analysis into the "similar past setups" framing) and into `_run_ai()`'s prompt assembly (a new `weekend_lines` block alongside the existing `signal_lines`/`event_lines`/`hist_lines`, before the final prompt string is built) and included in the returned `result` dict as a new `"weekend"` key. Purely additive — no restructuring of the 4-layer flow.

**Feeding it**: the Monday-morning caller (whatever currently calls `build_opening_prediction(db)` — this wasn't in scope for the sub-investigation to trace exhaustively, so treat the caller site as **NOT VERIFIED** without a follow-up read of `api/market.py:851-861`) would pass `weekend_context = resolve(current WeekendIntelligenceSnapshot for today's target_trading_date)`.

**Freshness rejection**: `weekend_context` should carry its own `generated_at`, and the Monday caller should discard it (pass `None`) if its age exceeds a threshold (e.g., >12h stale by market open) — the same freshness-check *shape* Phase 0's `session_label_for()` already established, generalized to a second use.

**Cache implication**: because `build_opening_prediction`'s cache key is currently the hardcoded literal `"opening_prediction"` with no variation, adding a context-dependent parameter means either keying the cache on whether `weekend_context` was present/its version, or accepting that the 30-min TTL and once-per-morning consumption pattern already make this a non-issue in practice — needs a small explicit decision at implementation time, not a blocker now.

**Tuesday–Friday**: `weekend_context` defaults to `None`; every existing code path is byte-for-byte unchanged. This is the property that keeps the change's blast radius to zero on non-Monday days.

---

## 16. Prediction Evaluation Loop

Fully covered by §11/§13: `job_evaluate_predictions` (`daily_tasks.py:256-271`, 4 PM IST cron, unrestricted by day-of-week) → `run_evaluation_cycle()` (`prediction_evaluator.py:292-319`) already evaluates *any* `PredictionRecord` regardless of `source`, fetching real outcome prices live from yfinance and recomputing `CalibrationStat` per confidence level. Both Weekend Intelligence's own production prediction and Kronos's experimental one need only be written as ordinary `PredictionRecord` rows (`source="weekend_intelligence"` and `source="kronos"` respectively) to flow through this **completely unmodified**. No second evaluator required — confirmed reuse, not a gap.

---

## 17. Scheduler Design

Evaluating the four options against what's actually true today: continuous ingestion (news/events/policy/announcements) already runs unrestricted through the weekend (Phase 0 audit §12), so evidence keeps accumulating regardless of when Weekend Intelligence itself recomputes — the question is purely about *synthesis* cadence, not evidence collection.

- **Option A (hourly)** — wasteful; weekend evidence volume is thin (Phase 0 audit: NSE/BSE volume near-zero, only RBI/PIB/SEBI/RSS trickle in), so most hourly runs would find nothing new and still pay for an LLM synthesis call.
- **Option B (event-driven)** — no event-driven trigger infrastructure exists anywhere in this codebase today (the in-process `EventIngestionBus` is transient, best-effort, and not built for cross-job triggering); building this would be exactly the kind of new heavyweight infrastructure §24 prohibits.
- **Option D (reuse 5-min MIE refresh)** — wrong shape; MIE's refresh is a cheap Redis-aggregation read, not an LLM-backed synthesis. Running Weekend Intelligence's actual synthesis every 5 minutes would be needless LLM cost for no benefit, since evidence doesn't change that fast on a weekend.
- **Recommended: Option C — scheduled checkpoints + dirty flag.** A small fixed number of `CronTrigger(day_of_week="sat,sun", hour=..., minute=...)` checkpoints (e.g. Sat 09:00/18:00, Sun 09:00/21:00) plus one Monday-early-morning final checkpoint, each first running the cheap §4/§7 "how much new evidence since the last checkpoint" count — a handful of `SELECT COUNT(*) WHERE created_at > :last_checkpoint` queries against already-indexed columns — and only proceeding to the expensive historical-match + LLM-synthesis step if that count clears the §7 materiality threshold. This directly answers "we do NOT need the feature recomputing an expensive LLM output every 5 minutes if nothing changed" — the checkpoint schedule bounds worst-case cost, the dirty-flag check bounds typical-case cost.

This also introduces the codebase's **first** `CronTrigger(day_of_week=...)` usage (confirmed: zero matches for this pattern anywhere in `scheduler.py` today) — a small, additive, well-precedented pattern, not a structural change to how the scheduler works.

---

## 18. Market Holidays

The design above already avoids hardcoding "Friday → Monday": `MarketSnapshot`'s new `snapshot_type="close"` capture (§2) fires on "last tick before session leaves `live`," not "if today is Friday"; `WeekendIntelligenceSnapshot` is keyed by `last_trading_date`/`target_trading_date`, not day names; §5's diff logic walks back to "most recent prior checkpoint," the same pattern `get_yesterday_changes()` already proves handles gaps correctly (it doesn't care *how many* days back the prior row is). A Thursday-close → Friday-holiday → weekend → Monday-target sequence works conceptually under this design **once a real holiday calendar exists to tell `_market_session()` that Friday isn't a trading day** — today `_market_session()` only checks `weekday() >= 5` (Phase 0 audit §1), so a Friday holiday would currently be misdetected as a normal trading day, meaning the §2 close-capture would fire Friday and the §17 checkpoint schedule (hardcoded to `sat,sun`) would miss capturing the actual holiday day's non-event. This is explicitly the same pre-existing gap §19 covers — not something this phase fixes, but the design's use of `last_trading_date`/`target_trading_date` fields (rather than day-name logic) means fixing the holiday calendar later is a drop-in improvement to session detection, not a rework of Weekend Intelligence's schema.

---

## 19. Calendar Data

Re-confirmed: no real trading-holiday or economic-release calendar exists in production. `CalendarEvent` (`app/db/crud.py::get_calendar`) is seeded entirely from hand-written data in `app/db/seed.py`, explicitly skipped in production (`main.py:69-70`); `EconomicCalendarProvider` (`app/providers/economic_calendar_provider.py`) is dead code, never called. Grep for "holiday" across `app/services`/`app/scheduler` confirms nothing implements a real NSE/BSE holiday list.

**Design implication**: `weekend_context`/`WeekendIntelligenceSnapshot` must treat calendar input as **optional** — the Event Layer of `opening_prediction_service.py` already silently queries an effectively-empty `CalendarEvent` table in production today (a pre-existing, separately-scoped gap this investigation surfaces but does not fix). Weekend Intelligence should not add a second dependency on that same broken input.

**Degraded without it**: no reliable "CPI releases Monday" / "earnings this week" framing — Weekend Intelligence's evidence (News/Events/Policy/Announcements, all real) can still surface an *actual* RBI/SEBI notice that happened to publish over the weekend, but it cannot proactively say "watch for X on Tuesday" from a calendar, only react to what's already landed as evidence. This is an accepted V1 limitation, not something to patch here.

---

## 20. AIPE Relationship

Minimal addition, one direction only:

```
WeekendIntelligenceSnapshot (is_current=True row)
        ↓
new content_templates.py TEMPLATES entry: "weekend_intelligence"
        ↓
new cycle function, modeled directly on run_historical_cycle
(publisher.py:1059-1196 — event-independent, topic/DB-driven, same shape needed here)
        ↓
generate_intelligence_article() → compute_seo_intelligence() → publish
(existing, unmodified — same pipeline every other article type already uses)
```

The new cycle function's only real job is resolving one `WeekendIntelligenceSnapshot`'s references (§6) into the prompt context `generate_intelligence_article()` expects — no changes to Fact Grounding, SEO computation, JSON-LD, or internal linking. AIPE never becomes a Weekend Intelligence input (no reverse arrow) — confirmed no existing article-generation code needs to change for this to work, since `IntelligenceArticle` already has every column (`article_type`, `companies_affected`, etc.) a new type needs.

---

## 21. Homepage API Shape

Grounded in §6's actual persistence shape rather than the prompt's example — the response is a **resolved/hydrated view** of the current `WeekendIntelligenceSnapshot`, since that row stores references, not blobs:

```json
{
  "target_trading_date": "2026-08-17",
  "last_trading_date": "2026-08-14",
  "version": 4,
  "checkpoint_label": "Sunday PM",
  "generated_at": "...",
  "status": "ok",

  "overall_bias": "...",
  "production_confidence": 62,

  "top_sectors": [{"name": "...", "score": ...}],
  "top_companies": [{"symbol": "...", "why": "...", "evidence_count": ...}],
  "opportunities": [/* resolved from opportunity_refs via existing OpportunityService DTOs */],
  "risks": [{"description": "...", "evidence_count": ...}],

  "changes_since_prior": [{"name": "...", "delta": ..., "is_new": false}],

  "historical_context": [/* resolved from historical_analogue_refs, same shape find_similar_events already returns */],

  "evidence_summary": {"news": N, "events": N, "policy": N, "announcements": N}
}
```

`experimental_signals` (Kronos) is deliberately **not** in this shape — internal-only per §14. Resolution of `opportunity_refs`/`historical_analogue_refs` at read time reuses existing DTO-assembly functions (`OpportunityService`, `historical_memory_service`) rather than introducing new serialization logic — matching how every other read endpoint in this codebase already hydrates junction-table references into response DTOs.

---

## 22. Failure / Degradation Behavior

The codebase already has a strong, consistent "never fabricate, degrade honestly" pattern to extend rather than invent: `scoring_engine.py`'s explicit "no score is ever invented" rule, `_index_quote()`'s literal `"—"` fallback instead of a fake price, `MacroRelease.expected_value` documented as never populated, `opportunity_generator.py`'s `_MIN_GROUP=3` threshold that skips generation entirely rather than publishing thin content.

Applied to Weekend Intelligence, per failure mode:

| Failure | Behavior |
|---|---|
| Redis unavailable | MIE-sourced inputs degrade to their existing DB-fallback path (already how `read_story()` behaves); Weekend Intelligence's own checkpoint state lives in Postgres/SQLite, unaffected |
| LLM unavailable | Synthesis step fails closed — no snapshot version written this checkpoint rather than a template-only guess; matches `opening_prediction_service._fallback_prediction()`'s existing deterministic-fallback precedent for the *signal* layer, but the narrative/bias layer should not silently substitute a fabricated verdict |
| yfinance unavailable | §2's close-capture and any live price checks degrade the same way `_index_quote()` already does — literal "unavailable" marker, not a fabricated number |
| No new weekend news | Not a failure — a real "checked, unchanged" checkpoint (§7), `changes_since_prior: []` |
| BSE unavailable | Already true today (Phase 0 audit — confirmed broken in production); Weekend Intelligence simply has less announcement/event evidence, same as every other feature already living with this gap |
| Historical match unavailable | `historical_analogue_refs: []`, not a fabricated analogue |
| Kronos unavailable | No effect on `production_confidence` at all (it was never in that formula); `experimental_signals` simply absent for that checkpoint |
| Friday snapshot missing | `market_snapshot_id: null`; the snapshot's `status` should be `"degraded"`, and downstream consumers (Monday handoff, §15) should treat a degraded weekend_context the same as a stale one — reject/ignore rather than propagate a hole as if it were data |
| Incomplete company mapping | Same posture as the rest of the app's `_NSE_UNIVERSE`-keyed lookups — an unmapped symbol is simply excluded from company-level output, not guessed |

General rule carried through: below a minimum evidence threshold, `WeekendIntelligenceSnapshot.status = "insufficient_evidence"` and the API should say exactly that rather than emitting a low-but-present confidence number that reads as more certain than it is.

---

## 23. Cost / Performance

- **New LLM calls**: bounded by §17's checkpoint+dirty-flag design — worst case ~5 synthesis calls per weekend (one per checkpoint), typical case fewer once the materiality gate skips no-change checkpoints. Reuses the existing multi-provider free-tier fallback cascade (`ai_service._call_with_fallback`), no new provider integration.
- **DB reads/writes**: reads are the same source tables every other feature already queries (News/Events/Policy/Announcements/Opportunity/ThemeState), no new indexes strictly required beyond what those tables already have on their timestamp columns. Writes are small — one `MarketSnapshot` row per trading-day close (§2), a handful of `WeekendIntelligenceSnapshot` rows per weekend (§7), one or two `PredictionRecord` rows per weekend cycle (§11).
- **Kronos inference cost**: **not assessable yet** — blocked on §12's finding that no historical-price warehouse exists; that warehouse's own persistence-job cost (pulling and storing OHLCV for however many symbols, on some cadence) is the real, currently-unscoped cost driver, separate from inference itself.
- **Scheduler frequency**: 5-6 new triggers total (§17), all cron-based, negligible marginal load on APScheduler.
- **Redis usage**: no new Redis keys strictly required if `WeekendIntelligenceSnapshot` reads go straight to Postgres/SQLite (a checkpoint-cadence feature doesn't need sub-second cache freshness) — though a thin Redis cache for the "current" row would be a reasonable, optional addition mirroring `mie:state:v1`'s pattern.
- **Railway memory impact**: the confirmed process model (`gunicorn -w 1`, everything in-process, no ML libraries currently loaded — §Kronos-investigation §4) means the existing memory footprint is unaffected by anything in this design *except* Kronos, which is exactly why the next point matters.
- **Kronos: in-process or separate service?** **Separate service/worker, not in-process.** Two independent reasons, both evidence-based: (1) §12 already establishes Kronos needs new persistent infrastructure it doesn't have — that infrastructure (a price-history warehouse + its own ingestion cadence) is naturally a separate concern from the request-serving API regardless of inference placement; (2) the confirmed `gunicorn -w 1` single-worker model means any blocking, CPU/GPU-bound inference work running in-process would stall the entire API's request handling for every user, not just the Weekend Intelligence path — a categorically different risk from the existing external-API-call pattern (LLM/yfinance/Finnhub calls are I/O-bound and async, not local compute). This is a design constraint to carry into whenever Kronos implementation is actually scoped, not something to build now.

---

## 24. Do NOT Introduce These Yet

Confirmed compliance — none of Temporal, GraphRAG, Qdrant, LangGraph, Neo4j, CrewAI, Mem0, Airflow, or Kafka appear anywhere in this design. Every persistence recommendation above uses the existing SQLAlchemy/Postgres-or-SQLite models and the existing APScheduler in-process scheduler. The one new infrastructure concept this design does introduce — a price-history warehouse for Kronos (§12) — is a plain new table + a persistence job using the same `yfinance`/Fyers providers already in use, not a new category of infrastructure.

---

## 25. Final Architecture Diagram

```
LAST TRADING SESSION (Friday, or whatever last_trading_date resolves to)
         │
         ▼
Closing Snapshot  ── extends existing MarketSnapshot (dead table, revived)
  session-boundary capture inside the EXISTING run_price_monitor_cycle (120s tick)
         │
         ├───────────────────────────────┬───────────────────────────────┐
         ▼                               ▼                               ▼
  Existing Weekend Ingestion      Existing Market/Intelligence      Existing Prediction
  (News/Events/Policy/            Data (MarketStory, ThemeState,    Framework
  Announcements — already         Opportunity — already durable,   (PredictionRecord/
  running unrestricted 7 days)    current-state)                   Evaluation/Calibration
         │                               │                          — already source-agnostic)
         └───────────────┬───────────────┘                               │
                          ▼                                               │
              Evidence Normalization                                      │
              (in-memory DTO, assembled from existing tables               │
               at aggregation time — no new EvidenceItem table)            │
                          ▼                                               │
              Scheduled Checkpoint + Dirty-Flag Gate                      │
              (new: first CronTrigger(day_of_week="sat,sun") in repo)     │
                          ▼                                               │
              ┌───────────┼────────────┐                                  │
              ▼           ▼            ▼                                  │
        Opportunity  Historical    Kronos (experimental,                  │
        Engine       Memory        separate service, needs                │
        (reused      (reused       new OHLCV warehouse first;             │
        as-is)       as-is)        stored via ↓ existing framework) ──────┘
              └───────────┼────────────┘
                          ▼
              WeekendIntelligenceSnapshot   ← ONE new table (§6)
              production_confidence (Kronos excluded)
              experimental_signals (Kronos included, internal-only)
                          │
              ┌───────────┴────────────┐
              ▼                         ▼
      Structured API (§21)      AIPE Weekend Article
      (hydrates refs at         (new TEMPLATES entry,
       read time)                modeled on run_historical_cycle)
              │
              ▼
      Monday Pre-Market Handoff
      (build_opening_prediction(db, weekend_context=None|snapshot) — additive param)
              │
              ▼
        Actual Monday Outcome
              │
              ▼
      Prediction Evaluation (existing job_evaluate_predictions — unmodified)
              │
              ▼
      Calibration (existing CalibrationStat — unmodified, now source-segmented)
```

This differs from the prompt's suggested shape in two evidence-driven ways: the Closing Snapshot box explicitly says "extends existing `MarketSnapshot`" (not a new concept), and Kronos is drawn with an explicit new-infrastructure dependency (OHLCV warehouse) rather than plugging in directly, because §12 found that prerequisite doesn't exist.

---

## 26. Reuse Matrix

| Capability | Existing Component | Reuse As-Is | Extend | New |
|---|---|---|---|---|
| Friday snapshot | `MarketSnapshot` (dead table) | | ✅ (add `snapshot_type`, wire a writer) | |
| News | `NewsArticle` + `job_ingest_news` | ✅ | | |
| Events | `Event`+junctions + `job_enrich_events` | ✅ | | |
| Policy | `GovernmentPolicy` + `job_ingest_policy` | ✅ | | |
| Announcements | `CompanyAnnouncement` + `ingest_announcements` | ✅ | | |
| Themes | `ThemeState` + `run_theme_scoring` | ✅ (current-state input) | | |
| Opportunities | `Opportunity`+junctions + `opportunity_generator` | ✅ | | |
| Historical memory | `historical_memory_service.find_similar_events` | ✅ | | |
| Evidence normalization | — | | | ✅ (in-memory DTO only, no table) |
| Weekend state / versioning | — | | (builds on `HomepageDailySnapshot`'s proven pattern) | ✅ `WeekendIntelligenceSnapshot` |
| Kronos inference | — | | | ✅ (blocked on OHLCV warehouse, separate service) |
| Kronos evaluation | `PredictionRecord`/`PredictionEvaluation`/`CalibrationStat` | ✅ | | |
| Production confidence | `confidence_service.calculate_confidence` | ✅ | | |
| Experimental confidence | — | | (reuses `confidence_service` formula) | ✅ (storage only — new JSON field) |
| Monday handoff | `opening_prediction_service.build_opening_prediction` | | ✅ (one optional param) | |
| Outcome evaluation | `job_evaluate_predictions` | ✅ | | |
| AIPE article | `publisher.py` pipeline + `content_templates.py` | | ✅ (one TEMPLATES entry + one cycle fn) | |
| Weekend API | — | | | ✅ (new route, hydrates existing DTOs) |

---

## 27. Final Recommendation

**A. Smallest new persistent Weekend Intelligence layer?** One new table, `WeekendIntelligenceSnapshot` (§6), storing synthesized summary fields plus reference IDs into existing tables — not copied content. Paired with reviving `MarketSnapshot` (schema extension + a writer, not a new table) as the Friday-close anchor it was always meant to be but never became.

**B. Do we need a new DB table? YES**, exactly one genuinely new one (`WeekendIntelligenceSnapshot`) plus reviving one dead one (`MarketSnapshot`). No new table is needed for evidence normalization (§4, stays in-memory) or for Kronos's prediction storage (§11, reuses `PredictionRecord`). A separate, later-scoped new table *is* needed for Kronos's OHLCV warehouse (§12) — that one is a hard prerequisite for Kronos specifically, not part of Weekend Intelligence's own persistence.

**C. Existing models/services to reference, not duplicate:** `MarketStory`, `ThemeState`, `Opportunity`+junctions, `Event`+junctions, `GovernmentPolicy`, `CompanyAnnouncement`, `NewsArticle`, `HistoricalMarketEvent` (via `find_similar_events`), `AICompanySignal`+`company_score_engine` (once its registration bug is fixed — a separable, pre-existing issue), `confidence_service`, `PredictionRecord`/`PredictionEvaluation`/`CalibrationStat`, `opening_prediction_service.build_opening_prediction`, the AIPE publish pipeline, and — a new finding worth calling out explicitly — the `HomepageDailySnapshot`/`get_yesterday_changes()` pattern as the proven template for versioned, weekend-safe day-over-day diffing, generalized rather than reinvented.

**D. Versions / "What's Changed Since Friday":** immutable rows, `is_current` flag, a small fixed set of scheduled checkpoints (§17) gated by a cheap materiality check (§7) before any expensive synthesis runs, deltas computed at evidence-item granularity (not full-snapshot diffing), following the exact "most recent prior row" query shape `get_yesterday_changes()` already validates in production.

**E. Where Kronos plugs in:** as an independent service (not in-process, §23), reading from a new OHLCV warehouse that does not exist yet (§12, the actual gate on Kronos existing at all), writing its raw prediction as an ordinary `PredictionRecord` with `source="kronos"` (§11), never included in `production_confidence`, optionally folded into `WeekendIntelligenceSnapshot.experimental_signals` for internal-only comparison, evaluated by the existing unmodified `job_evaluate_predictions` loop (§13/§16).

**F. Can existing PredictionRecord/Evaluation/CalibrationStat support Kronos and Weekend Intelligence? YES** — confirmed via schema (free-text `source`, no constraints) and confirmed via the real evaluation job's source-agnostic query logic.

**G. Smallest Monday Pre-Market change:** one optional parameter, `weekend_context: dict | None = None`, on `build_opening_prediction(db, weekend_context=None)`, threaded additively into the existing Historical and AI Reasoning layers; every existing call site keeps working unchanged by simply not passing it.

**H. What V1 should intentionally NOT include:** a real trading-holiday calendar (§18/§19 — treat as optional input, don't fix the underlying gap here), bond yields (confirmed not implemented anywhere in the platform, out of scope), fixing BSE ingestion (a separate, already-known production bug — Weekend Intelligence should degrade gracefully around it, not depend on it being fixed), any supply-chain/peer-relationship graph (the codebase's own `company_intelligence.py` docstring already disclaims this as unbuildable without fabrication), Kronos actually running (blocked on the OHLCV warehouse — track as its own prerequisite workstream), and any of §24's excluded infrastructure categories.

**I. Implementation sequence** (adjusted from the prompt's suggestion based on actual dependency evidence):

```
1. Fix AICompanySignal's DB registration (base.py import) — trivial, unblocks §4/§8 cleanly
2. Extend + wire MarketSnapshot (schema + close-capture inside run_price_monitor_cycle)
3. WeekendIntelligenceSnapshot persistence (table + is_current/versioning mechanics)
4. Evidence-normalization DTO + materiality/dirty-flag check
5. Aggregator: Opportunity Engine + Historical Memory + confidence_service → production_confidence
6. Checkpoint scheduler jobs (first day_of_week="sat,sun" triggers)
7. Structured API (§21), read-only, hydrating references
8. Monday handoff: optional weekend_context param on build_opening_prediction
9. AIPE weekend_intelligence TEMPLATES entry + cycle function
10. Prediction Evaluation wiring: WeekendIntelligenceSnapshot's own prediction as a PredictionRecord (source="weekend_intelligence")
11. (Separate, later workstream — has its own prerequisite chain) OHLCV warehouse → Kronos service → PredictionRecord(source="kronos") → experimental_signals
12. Homepage UI last, against the real API from step 7
```

Step 1 is promoted ahead of everything else versus the prompt's suggested order because it's a one-line fix that several later steps (§4, §8) would otherwise silently inherit as a landmine. Kronos is pushed to its own late, separable track (step 11) rather than interleaved, because §12 established it has a hard, currently-unscoped prerequisite that shouldn't gate the rest of Weekend Intelligence's delivery.

**J. Files likely to change during implementation:**

*Existing files:*
- `app/db/models/intelligence.py` (extend `MarketSnapshot`)
- `app/services/intelligence/price_monitor.py` (add close-capture condition)
- `app/db/base.py` (register `AICompanySignal` — the pre-existing bug fix)
- `app/scheduler/scheduler.py` (new checkpoint jobs)
- `app/services/opening_prediction_service.py` (`weekend_context` param)
- `app/services/aipe/content_templates.py` (new `TEMPLATES` entry)
- `app/services/aipe/publisher.py` (new cycle function, modeled on `run_historical_cycle`)
- `app/main.py` (mount new router)

*New files:*
- `app/db/models/weekend_intelligence.py` (new `WeekendIntelligenceSnapshot` model)
- `app/services/weekend_intelligence/` — evidence normalization, checkpoint aggregator, snapshot builder (exact module split is an implementation-time decision, not fixed here)
- `app/api/weekend_intelligence.py` (new route)
- (separate, later track) a price-history persistence module + its own new table, prerequisite for Kronos specifically

---

**PHASE 1 ARCHITECTURE STATUS: COMPLETE**

No implementation has begun. Stopping here for review.
