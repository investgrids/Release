# MARKET RIPPLE — WEEKEND INTELLIGENCE PRE-IMPLEMENTATION AUDIT

**Audit only. Nothing in the codebase was modified, created, or deployed to produce this document.**
Repo root: `D:\IG` (backend: `apps/backend`, frontend: `apps/web`). All paths below are relative to those unless stated otherwise.

Method: gathered by 5 parallel read-only research passes over the actual repository (no assumptions), each required to cite file/function/line for every claim and write "NOT VERIFIED" rather than guess. This document consolidates their verified findings and adds the final architecture synthesis (§18–20).

---

## 1. Market Session Audit

**At least five independent, mutually-inconsistent session-detection implementations exist. None share a single source of truth, and none consult an NSE/BSE trading-holiday calendar.**

| File | Function | Line | States returned | Weekend check | Holiday check | Timezone |
|---|---|---|---|---|---|---|
| `app/services/market_data.py` | `get_market_status()` | 757-772 | weekend, pre_market, pre_open, open, closed | Yes (`weekday()>=5`) | No | IST (line 597) |
| `app/api/market.py` | `market_session()` (`GET /api/market/session`) | 425-464 | weekend, pre_market, pre_open, open, after_market | Yes | No | IST |
| `app/services/intelligence/engine.py` | `_market_session()` | 35-46 | weekend, pre_market, live, post_market | Yes | No | IST |
| `app/services/aipe/content_planner.py` | `_session()` | 28-36 | pre_market, live, post_market | **No weekday check at all** | No | IST |
| `app/services/intelligence/story_engine.py` | `_is_market_hours()` | 35-38 | boolean gate | **No weekday check — pure clock time** | No | IST |
| `apps/web/components/MarketSessionGate.tsx` | `getSession()` | 46-61 | pre-market / live / after-market / closed | Yes (`dow===0\|\|dow===6`) | No | manual +5:30 offset |
| `apps/web/components/market/tabs/PreMarketTab.tsx` | `useCountdown()` | 35-73 | isOpen + countdown text | **No weekday check** — compares minutes-of-day only | No | `Intl` Asia/Kolkata |

No `MARKET_HOLIDAY` state exists anywhere. A Diwali/Republic Day/Holi trading holiday is treated as a normal weekday everywhere in the codebase — no NSE/BSE holiday list is consulted by any session function.

### Weekend bug — root cause (verified, not fixed)

**Not a session-detection bug — session detection correctly identifies weekends in most places.** The "Friday data shown as Today" symptom is a chain of three compounding gaps:

1. **`StoryEngineWorker._run()`** (`story_engine.py:222-238`) only regenerates the AI market story when the live market-data context hash changes (`_context_hash`, lines 113-121). Weekend yfinance calls return an unchanged last-close price, so the hash never changes → no new `MarketStory` row is ever written Sat/Sun.
2. **`engine.py::read_story()`** (lines 57-92) is Redis-first (10-min TTL) and, on cache miss, falls back to `SELECT * FROM market_story ORDER BY generated_at DESC LIMIT 1` — **no date filter**. Once Friday's story ages out of Redis, every weekend read silently returns that same Friday row until Monday's first successful regeneration.
3. **`app/api/homepage_intelligence.py::homepage_intelligence()`** (lines 22-35) has the identical pattern: `ORDER BY published_at DESC LIMIT 1`, no `WHERE date = today` — despite its own docstring claiming it returns `{"available": False}` when there's no article "yet today." That check does not actually exist in the code.
4. **Hardcoded "today" copy masks the staleness**: `apps/web/app/page.tsx:555` (`<h1>Today's Market Outlook</h1>`), `page.tsx:539` (`"...today"`), `app/services/homepage_intelligence.py:124` (`f"...will likely be led by {best['name']}."` phrased as today's read) — none of these check the underlying article's actual date. The only staleness signal is a small `heroFreshnessLabel` (`page.tsx:521-531`) that can show "Updated 2 days ago" — but the verdict/outlook text itself doesn't change.
5. A **previously-confirmed related bug** is documented in-code (`page.tsx:392-400`): homepage showed "Bearish 92%" while Nifty/Sensex/BankNifty were all green and the Live Market tab correctly said "Bullish 70%" — two flagship surfaces independently derived contradictory verdicts from different sources. This was the motivation for wiring the homepage hero to MIE's `story` object — but MIE's `read_story()` has the exact same no-date-filter fallback (point 2), so the underlying class of bug wasn't eliminated, just relocated.
6. `PreMarketTab.tsx::useCountdown()` (lines 35-73) has no weekday check — on a Saturday it will still render an "Opens in Xh Ym" countdown implying same-day open.

---

## 2. Pre-Market Intelligence Pipeline

Two parallel pipelines exist:

**A. Minimal/likely-unused pipeline** — `app/api/premarket.py` `GET /` → `market_data.py::get_premarket_data()` (940-943) → `_fetch_premarket()` (902-937), 15-min in-process TTL. Warmed by `job_warm_premarket` (`daily_tasks.py:241-251`, `CronTrigger(hour=8, minute=0)`, `scheduler.py:120-128`, no day-of-week gate). No frontend caller found for this exact route.

**B. Real pipeline the UI renders** — `PreMarketTab.tsx` (839-1026) fires 4 parallel fetches on mount:
- `GET /api/market/premarket` → Gift Nifty proxy, Bank Nifty futures, VIX, FII/DII, ADRs, currencies, commodities (`api/market.py:513`+, reusing `market_data.py` helpers)
- `GET /api/market/opening-prediction` → `api/market.py:851-861` → `opening_prediction_service.py::build_opening_prediction()` (45-64) — 4-layer pipeline (Signal/Event/Historical/AI Reasoning), 30-min flat in-process TTL cache, **no session/weekend awareness on the cache itself**
- `GET /api/intelligence/market/themes`
- `GET /api/insights/?limit=6`

Rendering: `Hero` (410-487) shows "AI Opening Verdict" from `pred.direction`; `MorningBrief` (495-518) derives its own Bullish/Bearish/Neutral label via `outlookLabel()` (490-494) purely from `pred.direction`+`pred.confidence` — **a third independent bullish/bearish derivation**, distinct from both the homepage's and the ticker's.

No cron regenerates the opening-prediction cache specifically — it's request-driven with a 30-min TTL. `job_warm_premarket` only warms pipeline A's data, not this one.

---

## 3. Existing MIE Audit

File: `app/services/intelligence/engine.py` (core), `app/api/mie.py` (API surface), `app/services/intelligence/story_engine.py` (feeds it).

**State**: single `IntelligenceState` dict — story, themes (top 8), top_events (Critical/High tier), signals (mood/direction/risk/breadth), sector_themes, market_health, biggest_opportunity/risk, companies_to_watch, market_drivers, tomorrow_watch (`compute_intelligence_state()`, 485-553).

**Inputs**: `read_story()` (57-92, Redis→latest-row DB fallback), `read_themes()` (99-131), `read_top_events()` (138-190, `EventTriage` last 8h, urgency≥4), `read_opportunities()` (335-363, via `OpportunityService`), `read_upcoming_calendar()` (366-389, `crud.get_calendar` — note §7: this table is effectively empty in production).

**Refresh**: `IntervalTrigger(seconds=300)` (`scheduler.py:185-192`), interval-based, no day-of-week gate.

**Cache**: Redis `mie:state:v1`, TTL 300s live / 1800s otherwise (`_cache_ttl()`, 49-52) — weekend correctly gets the 30-min branch, but the job still refreshes every 5 min regardless.

**Persistence**: MIE writes no dedicated state table — pure read-through aggregator over `MarketStory`/`ThemeState`/`EventTriage`, materialized only in Redis.

**AI calls**: none directly in `engine.py` — it only reads output already produced by `StoryEngineWorker`, which calls a multi-provider free-tier fallback cascade (`ai_service.py::_call_with_fallback`, 394-490): OpenRouter → Mistral → Gemini → Groq (HQ+Fast) → Cerebras → OpenRouter small → Cloudflare Workers AI.

**Confidence**: the LLM self-reports it directly; MIE passes it through unverified.

**Can MIE maintain state across multiple days?** **No.** Every reader queries "latest only" (`ORDER BY ... DESC LIMIT N`) — none accept a date param, compare two dates, or read a "yesterday" record. Repo-wide grep for `yesterday|previous_day|prior_day|day_over_day` in the intelligence services: **zero matches**. No `IntelligenceStateHistory`-style table exists. This is the single most important gap for a "Weekend Intelligence" feature that would want to say "here's what changed since Friday."

---

## 4. News Pipeline Audit

Two non-overlapping code paths:

**Path A (ephemeral, public API only)** — `news_fetcher.py`, 20 yfinance tickers + 10 RSS feeds merged in-process, 15-min TTL, **never persisted to DB**. Serves `GET /api/news/` fast; not scheduler-driven.

**Path B (real scheduled ingestion)** — `job_ingest_news` (`IntervalTrigger(seconds=900)`, `scheduler.py:63-70`, no day-of-week gate) → `NSEProvider`/`BSEProvider`/`RSSProvider` (`app/providers/*.py`) → persists `NewsArticle` rows, creates `Event` rows for NSE/BSE only (RSS explicitly excluded — "too generic," `ingest_tasks.py:210`).

| Source | Mechanism | DB table |
|---|---|---|
| NSE (announcements/board meetings/corp actions) | REST JSON, no auth | `news_articles` + `events` |
| BSE | REST JSON — **confirmed broken in production** (Akamai bot-detection redirect, documented in `bse_provider.py:1-20`) | same, ~0 rows today |
| RSS (6 India-finance feeds) | RSS/XML | `news_articles` only |

**Dedup**: within-batch exact-ID only (`_existing_ids`, `ingest_tasks.py:62-66`). **Cross-source dedup does not exist** — the same real story from NSE and an RSS feed gets two separate rows (different ID schemes per provider). This is a known, hard-gated architectural issue (see memory: `[[project_rss_cross_source_dedup]]`).

**Can news already be collected on weekends? PARTIALLY** — the scheduler job has zero day gating and fires every 15 min regardless of day, and RSS does publish weekend content; but NSE/BSE corporate-announcement volume is naturally near-zero on non-trading days (source-side gap, not code), and BSE is broken regardless of day.

---

## 5. Events Pipeline Audit

Events are a **side effect of news/policy ingestion**, not an independent source. `_create_events()` (`ingest_tasks.py:108-138`) writes one `Event` row per new NSE/BSE item (`event_type="corporate"`) and per new RBI/PIB/SEBI/Fed item (`event_type="policy"`). RSS news never becomes an event.

**Schema** (`app/db/models/event.py:31-76`): `event_date` (nullable, often left NULL upstream), `published_at` (set to ingestion wall-clock time, **not** the real event date), `enrichment_status` + retry fields (added in the earlier-this-session "Events Scoring Incident" schema-patch fix — see memory `[[project_events_scoring_incident]]`).

**Enrichment**: `job_enrich_events` (`IntervalTrigger(seconds=300)`, `scheduler.py:81-88`, no day gate) → `run_event_pipeline()` (`app/pipeline/event_pipeline.py:117-370`, 10-stage AI pipeline: classify → summarize → extract companies/sectors → impact analysis → **centralized scoring via `scoring_engine.score_event_impact()`** (real feature-based signal, not the LLM's self-rated number) → timeline → similar events → graph → policy linking → persist).

**Historical events as distinct data**: yes — `EventCoverage` (triage/publish tracking) and `EventSimilar` (AI-ranked similar-event links) are separate registries; `historical_memory_service.find_similar_events` is already called inside the event pipeline itself.

**Can events already be processed on weekends? PARTIALLY** — `enrich_events` and the upstream ingestion jobs are all ungated and fire every day; RBI/PIB/SEBI-sourced events (which do publish on non-trading days) flow through normally; but the majority event source (NSE/BSE corporate events) produces near-zero new weekend data since exchanges aren't filing.

---

## 6. Policy / Government Data

| Sub-category | Status | Evidence |
|---|---|---|
| RBI | **IMPLEMENTED** | `providers/rbi_provider.py:29-77`, RSS, impact_score=9.0 |
| SEBI | **IMPLEMENTED** | `providers/sebi_provider.py:19-53`, RSS (docstring notes feed "often unreliable") |
| PIB | **IMPLEMENTED** | `providers/pib_provider.py:14,50-79`, ministry classifier maps Finance/Commerce/Defence/Railways/Power/Petroleum/RBI/SEBI/NITI Aayog |
| US Fed (bonus) | **IMPLEMENTED** | `providers/fed_provider.py:47-102` |
| Budget/macro numeric extraction | **PARTIALLY IMPLEMENTED** | `services/macro_extraction.py` — regex extraction of CPI/GDP/IIP/WPI/GST/trade-balance/fiscal-deficit from RBI/PIB text only; conservative by design, `expected_value` never populated |
| Defence policy (dedicated source) | **NOT IMPLEMENTED** | only surfaces incidentally via PIB's ministry-keyword match or news sector-tagging |

Job: `job_ingest_policy` (`IntervalTrigger(seconds=3600)`, `scheduler.py:72-79`, no day gate) → persists `NewsArticle` + upserts `GovernmentPolicy` (`event.py:157-167` — note: `announcement_date` is **always passed as `None`**, `ingest_tasks.py:182`, so that field is currently never populated from real data) + creates policy `Event` rows + attempts `MacroRelease` extraction (RBI+PIB only).

**Can policy already be collected on weekends? YES** — plain hourly interval, no gating, and RBI/SEBI/PIB do publish on non-trading days (architecturally the most weekend-viable of the four ingestion pipelines), though NOT VERIFIED against an actual historical weekend production log.

---

## 7. Calendar Audit — key finding: this system does not really exist in production

`app/api/calendar.py::list_calendar()` reads `CalendarEvent` rows — plain `SELECT *`, no filter/ordering. Schema: `date` is a **display string** (e.g. `"Jul 21, 2026"`), not a real datetime column.

**Data source is entirely hardcoded, not ingested**: `app/db/seed.py:140-211`, 10 static hand-written entries (WPI, TCS earnings, RBI MPC, CPI, IIP, Budget session, HCLTech, US PPI, Infosys). Dates are computed as `now() + timedelta(days=N)` **at process-start time** — "freshness" is an artifact of when the process last booted, not a real calendar.

**Critical**: `main.py:69-70` explicitly **skips this seed in production** (`if settings.is_production: log.info("db.seed_skipped", ...)`), with an in-code comment that this is "hand-written placeholder content" that "must never land in the production DB." Net effect: **`calendar_events` has no production-safe write path at all today** — it's populated only if a table happened to already have rows from an earlier non-production run.

A separate `EconomicCalendarProvider` class (`providers/economic_calendar_provider.py:64-89`) exists with its own hardcoded recurring-event list and an unimplemented Finnhub-supplement intent — confirmed via repo-wide grep to be **dead code**, imported in `providers/__init__.py` but never instantiated or called anywhere.

**Can calendar data already be collected on weekends? NO** — there is no real ingestion for this table on any day of the week.

---

## 8. Global Market Data

Every instrument is sourced through **`yfinance`** (unofficial Yahoo client), tickers hardcoded and **duplicated across three separate modules** (`api/market.py`, `services/market_data.py`, `api/commodities.py`) with no shared provider abstraction. (The one real provider abstraction, `services/market_data_service/` with Fyers support, backs only Indian single-stock quotes at `/api/data/*` — not used for any global instrument.)

| Instrument | Source | Cache | Notes |
|---|---|---|---|
| US indices (Dow/S&P/Nasdaq) | yfinance `^DJI`/`^GSPC`/`^IXIC` | 15-min in-process | |
| US futures (ES/NQ/YM) | yfinance | 15-min | |
| Asian (Nikkei/HSI/Shanghai/KOSPI) | yfinance | 15-min | |
| European (FTSE/DAX/CAC) | yfinance | 15-min | |
| Gift Nifty | **Synthetic proxy** — NSE near-month Nifty futures via yfinance, explicitly labeled "Gift City proxy" in code (`api/market.py:264-285`) | 15-min | Not a real SGX/Gift City feed |
| Bank Nifty futures | yfinance NSE futures ticker, spot fallback | 15-min | |
| India VIX | yfinance `^INDIAVIX` | 15-min (premarket) / Redis 60s (`/api/indices/`) | |
| USD/INR, EUR/INR, GBP/INR | yfinance | 15-min | |
| DXY | yfinance `DX-Y.NYB` | 15-min | No dedicated UI widget found beyond generic commodities list |
| Brent/WTI/Gold/Silver/Copper/Platinum/Nat Gas | yfinance | Redis `commodities:prices:v2`, 120s | India Petrol is a **derived estimate** from Brent, not a real retail feed |
| FII/DII flows | NSE scrape (`_fetch_fii_dii`) | 6-hour cache | |
| Nifty PCR/Max Pain | NSE option-chain scrape | 15-min | |
| Indian ADR premiums | yfinance NYSE tickers | 15-min | |
| **Bond yields (India/US G-Sec, 10Y Treasury)** | — | — | **NOT IMPLEMENTED** — no ticker, route, or model reference anywhere |

Cache is inconsistent: some routes use Redis (`commodities.py`, `indices.py`), `api/market.py` uses **private in-process Python dicts** — not shared across worker processes, resets on restart.

---

## 9. Company Intelligence

**No dedicated `Company` database table exists.** The company universe is a hardcoded, in-memory list, `_NSE_UNIVERSE` (`api/companies.py:39`+, ~510+ static entries), used as the resolution source almost everywhere else.

| Capability | Exists? | Evidence |
|---|---|---|
| Sector/industry mapping | YES (static field, not DB) | `_NSE_UNIVERSE`; also live yfinance `info.get("sector")` |
| Theme mapping | PARTIAL | Tagged per-announcement/per-article, no company-level aggregate field |
| Linked events | YES (two independent implementations) | `EventCompany` junction; `company_intelligence.py::get_active_events()` vs `stocks.py::_related_events_for_symbol()` — separate matching logic each |
| Linked news | PARTIAL | Live per-company news comes from **Finnhub** (external), not the `NewsArticle` table; **absent entirely** from `company_intelligence.py`'s own response |
| Corporate announcements | YES but siloed | `CompanyAnnouncement` table, real NSE/BSE ingestion, but its own endpoint (`/api/announcements/{symbol}`) — **not included** in either `/api/stocks/{symbol}` or `/api/company-intelligence/{symbol}` |
| Earnings data | PARTIAL | Live yfinance quarterly financials, only via `/api/stocks/{symbol}`, **absent** from `/api/company-intelligence/{symbol}` |
| Linked policies | PARTIAL/heuristic | No direct company→policy link; a `gov_score`/`gov_level` is a **fabricated heuristic** from sector-keyword matching (e.g. "defence"→88), not a real link to `GovernmentPolicy` rows |
| Historical performance ("similar event") | YES | `company_intelligence.py::get_historical()` wraps the real `historical_memory_service.find_similar_events()` |
| Peer/competitor relationships | PARTIAL/heuristic, 3 independent implementations | Static `_PEERS_MAP` dict, live Finnhub peers API, and a same-sector/industry-word-overlap matcher — three separate near-duplicate implementations |
| Supply-chain relationships | **NO — explicitly disclaimed** | `company_intelligence.py` module docstring: *"NOT built — no real data source in this app models supply-chain relationships, and fabricating one would violate this app's core rule."* |
| Related opportunities | YES | `OpportunityCompany` junction, real |

**Practical implication**: a Weekend Intelligence feature drawing only from `company_intelligence.py` would miss earnings, news, and announcements — it would need to separately call `/api/stocks/{symbol}` and `/api/announcements/{symbol}` to assemble a complete per-company picture.

---

## 10. Opportunity Engine

**Files**: `api/radar.py`, `services/opportunity_service.py` (read/DTO), `pipeline/opportunity_generator.py` (generation+scoring, has AI), `services/opportunity_intelligence.py` ("Radar 2.0" enrichment).

**Exact scoring formula** (`opportunity_generator.py:83-88`):
```python
base = 60.0
base += min(20, len(events) * 3)
base += min(10, len(companies) * 1.5)
base += min(10, len(sectors) * 2)
return round(min(99, base), 1)
```
Purely a deterministic event/company/sector count heuristic — not price-action, volatility, or backtest-derived. `confidence = min(0.95, score / 110)` — directly derived from the score, not independent.

**AI call**: single-provider DeepSeek (`_call_ai`, 112-131), keyword-heuristic fallback if unavailable.

**Trigger**: `job_daily_opportunities`, `CronTrigger(hour=7, minute=30, timezone=IST)` (`scheduler.py:111-118`), **no `day_of_week`** — fires every day including weekends. Only practical weekend suppressant: requires ≥3 qualifying `NewsArticle` rows from the last 26h (`_MIN_GROUP=3`), and upstream news ingestion is itself ungated.

**Direct reuse verdict (from source agent): YES, mechanically, with zero modification to the scoring function itself.** `_score_opportunity` and `generate_opportunity_from_events` are pure functions of "recent classified news" — nothing reads day-of-week or market session. Calling the same function at a different time with different framing metadata would work; the only real work is upstream framing/labeling, not the formula.

---

## 11. Historical Data

**`HistoricalMarketEvent`** (`db/models/historical_memory.py`): ~30 seeded, verified Indian market events (COVID crash, Budgets, Demonetization, 2024 election shock, Adani-Hindenburg, RBI cycles, IL&FS, GST, Lehman, etc.) with market-context fields, Nifty outcome returns at 1d/3d/1w/1m, sector reactions, `historical_winners`/`historical_losers`, `opportunity_score`/`risk_score`/`confidence`, `key_lesson`.

**Similar-event matching — CONFIRMED IMPLEMENTED**, `compute_similarity()` (`historical_memory_service.py:51-88`): a structured multi-factor score (category 30pts, sector-overlap Jaccard 25pts, sentiment 15pts, market regime 15pts, rate trend 8pts, crude trend 7pts = 100 max) — not a vector/embedding match, but a real, working, evidence-based system. `find_similar_events()` (138-193) is already reused in 3 confirmed places: Opportunity Radar detail pages, historical event detail pages, and AIPE's `run_historical_cycle` article generation.

**This already directly answers "what happened after similar events?"** — no new system needed, only a new caller.

`run_historical_cycle` (daily 9:30 AM IST cron, no weekend gate) generates one "History of X" article/day from a fixed topic list, reusing the exact same publish pipeline as every other AIPE article type.

---

## 12. Schedulers / Background Jobs

APScheduler `AsyncIOScheduler(timezone=IST)` (`scheduler.py:27`). **30 jobs total on a fresh boot (21 recurring + 9 one-time boot jobs). Zero jobs anywhere use `day_of_week` — every cron/interval job runs on Saturday and Sunday exactly as on weekdays.**

| Job | Trigger | Purpose | Runs weekend? |
|---|---|---|---|
| `fyers_token_refresh` | Cron 5:30 AM | Fyers token refresh | YES |
| `ingest_news` | Interval 900s | NSE+RSS news | YES |
| `ingest_policy` | Interval 3600s | RBI/PIB/SEBI/Fed | YES |
| `enrich_events` | Interval 300s | AI event enrichment | YES |
| `daily_generate` | Cron 6:00 AM | AI market summary + sector cache | YES |
| `daily_precompute` | Cron 7:00 AM | Full dashboard payload cache | YES |
| `daily_opportunities` | Cron 7:30 AM | Opportunity generation | YES |
| `warm_premarket` | Cron 8:00 AM | Pre-fetch Asian/US/commodity data | YES |
| `evaluate_predictions` | Cron 4:00 PM | Prediction calibration | YES |
| `backup_database` | Cron 2:00 AM | DB snapshot | YES |
| `theme_scoring` | Interval 600s | Score 12 themes | YES |
| `price_monitor` | Interval 120s | Price threshold breach events | YES |
| `ingest_announcements` | Interval 1800s | NSE+BSE corporate announcements | YES |
| `mie_refresh` | Interval 300s | Rebuild MIE Redis state | YES |
| `aipe_publish_cycle` | Interval 300s | Main AIPE article pipeline | YES |
| `aipe_evergreen_cycle` | Cron 9:00 AM | Timeless explainer articles | YES |
| `aipe_historical_cycle` | Cron 9:30 AM | "History of X" articles | YES |
| `comparison_cycle` (×2) | Cron 10:00 AM / 3:00 PM | Comparison-page pairs | YES |
| `media_generation` | Interval 60s | Hero image generation | YES |
| `signal_enrichment` | Interval 300s | Backfill live-signal narrative fields | YES |
| 9 one-time boot jobs (seed/repair/backfill) | `trigger="date"`, staggered +15s each | One-off data repairs at startup | N/A (boot-only) |

**No `CronTrigger(day_of_week=...)` pattern exists anywhere in this codebase today** — a Weekend Intelligence job introducing one would be a genuinely new (but small, additive) pattern.

---

## 13. Database Audit

Registration: `app/db/base.py` imports 16 model modules explicitly; importing any of those also runs `app/db/models/__init__.py`, which imports several more (e.g. `HomepageDailySnapshot`, `AISearchFeedback`). `create_all()` runs in `main.py`'s `lifespan()` after `Base` import.

Persistent storage is broadly available for: news (`NewsArticle`), events (`Event` + `EventCompany`/`EventSector`/`EventCoverage`/`EventSimilar`/`EventPolicy`), companies-adjacent (`CompanyAnnouncement`, `AICompanySignal`), themes (`ThemeState`), opportunities (`Opportunity` + 8 related tables), published articles (`IntelligenceArticle`), market snapshots (`MarketSnapshot`), historical outcomes (`HistoricalMarketEvent`), predictions/calibration (`PredictionRecord`/`PredictionEvaluation`/`CalibrationStat`), confidence audit trail (`ScoreHistory`), policy (`GovernmentPolicy`), macro releases (`MacroRelease`).

**Two confirmed/suspected registration gaps** — the same class of bug as the earlier-this-session "missing schema patches" production incident (see memory `[[project_sqlite_footgun_family]]`):
- `AICompanySignal` — **not imported in `base.py` or `db/models/__init__.py`**. Its table currently gets created today only as a side effect of an unrelated router-import chain (`main.py` → `api.company_scores` → `company_score_engine.py` imports the model, which happens to run before `create_all()`). Fragile — a future router refactor would silently stop this table from being created on a fresh DB.
- `ReturningUserFeedback` — same pattern, **not found imported anywhere** in this pass; NOT VERIFIED whether some other import chain saves it, but no such chain was found.

**MIE state is not a DB model at all** — purely Redis (`mie:state:v1`), no `mie_state` table exists.

**No dedicated `Company` table** — see §9.

---

## 14. Cache Audit

Two parallel cache-config systems that don't reference each other:
- `config.py`'s `redis_ttl_*` settings (dashboard/opportunity/event/market/news) — **mostly dead**: only `redis_ttl_default` and `redis_ttl_opportunity` are actually read anywhere in the codebase.
- `cache/cache_service.py`'s own hardcoded `TTL_*` constants — these are what's actually used, and today happen to numerically match the config settings but aren't wired to them. Two independent sources of truth for the same numbers.

Key cache entries: `dashboard:v1` (900s), `dashboard:ai_summary:v1` (900s), `mie:state:v1` (300s live/1800s otherwise), `market:story:latest` (600s), `live_intelligence:feed:v1` (300s), `indices:list` (60s), `commodities:prices:v2` (120s).

**Weekend staleness assessment**: the cache *mechanism* is not the risk — every relevant job keeps refreshing on its normal cadence through the weekend (no job freezes). The risk is that **nothing in `_build_dashboard_payload()` branches on `is_open`/session before writing to cache** — whatever a closed-market data fetch returns (Friday's last close, or an honest `"—"` fallback) simply gets cached for 15 minutes at a time, all weekend, with **no "market is closed" flag carried in the cached payload itself**. A weekend reader has to separately call `/api/market/session` to learn the data reflects a closed market — this matches and reinforces the §1 root-cause finding.

---

## 15. Homepage Audit

`apps/web/app/page.tsx` (1390 lines).

| Component | Session-aware? | Bullish/bearish source | "Today" source |
|---|---|---|---|
| `TickerStrip` | Yes — real `GET /api/market/session` call, shows "Weekend" label correctly | n/a | n/a |
| `MarketSessionGate`/Badge | Yes — own independent client `getSession()`, correctly shows "Market Closed" | n/a | n/a |
| `HomepageIntelligenceHero` | **No explicit check** — relies on upstream data being fresh (it isn't, per §1) | `deriveOutlookFromMie()` from MIE's `story.pulse`/`confidence`, or `deriveOutlook()` from sector counts in a (possibly stale) article | Hardcoded `<h1>Today's Market Outlook</h1>` (line 555) and `"...today"` (539); `heroFreshnessLabel` (521-531) is the *only* place that checks real article age |
| `TodaysBiggestEventsCard` | none | n/a | via `active`-sorted events (recency-decay ranking, not day-aware) |
| `TopOpportunitiesCard` | none | n/a | `Opportunity.opportunity_score` from the 7:30 AM cron (also ungated for weekends) |
| `KeyRisksCard` | none | n/a | same stale `morning_intelligence` article as the hero |
| "Stocks to watch" | none | n/a | merged from top event + active-events list, not session-aware |

The literal word "Today" is hardcoded in headline/summary copy in at least 3 places across frontend and backend — so even when the underlying data is stale, the UI language always claims currency.

---

## 16. Data Quality Audit

- **`Math.random()`**: not found anywhere in `apps/web` or `apps/backend/app` source. Backend also clean of `random.uniform`/`random.randint`/`np.random`/`random.choice`. Clean sweep.
- **`db/seed.py`** (397 lines): hand-written placeholder news attributed to real outlets (Economic Times, Business Standard, Mint, Financial Times) — **explicitly gated off in production** (`main.py:69-84`, with an in-code comment explaining exactly why this must never reach prod). Confirmed by-design, not a live bug.
- **`workers/opportunity_worker.py::_seed_static_opportunities`** (6 hardcoded "STATIC_SEEDS" opportunity themes): **registered unconditionally regardless of `is_production`** (`scheduler.py:288-294`) — unlike `db/seed.py`, this *would* seed placeholder opportunities into a fresh production DB. Self-labeled `source="seed"` so it's distinguishable from real data, but it is a real prod-data-integrity gap worth closing.
- Honest "market closed" patterns confirmed working: `_index_quote()` (`market_data.py:775-787`) returns literal `"—"` rather than a fabricated price on fetch failure; `MacroRelease.expected_value` is documented as never populated ("rule is absolute on this point"); several repair-job docstrings explicitly cite a "never fabricate — better empty than false" principle.
- No weekend-specific fake-data fallback found in the 4 dashboard-hero components checked; a full manual read of all 88 generically-flagged files was out of scope — **NOT VERIFIED** complete.

---

## 17. AIPE (AI Publishing Engine) Audit

**7 scheduled jobs, all without day-of-week gating** — every one is scheduled to fire on Saturday/Sunday exactly as on weekdays: `run_aipe_cycle` (interval 300s, triage-driven), `run_evergreen_cycle` (cron 9:00 AM, fixed topic list — event-independent), `run_historical_cycle` (cron 9:30 AM, event-independent), `run_comparison_cycle` ×2 (10:00 AM / 3:00 PM, DB-driven pairs — event-independent), `run_image_generation_cycle` (interval 60s), `run_signal_enrichment_cycle` (interval 300s).

**12 article types** (`content_templates.py::TEMPLATES`): morning_intelligence, breaking_intelligence, company_intelligence, sector_intelligence, theme_intelligence, policy_intelligence, ripple_intelligence, opportunity_intelligence, market_wrap, educational_intelligence, question_intelligence, historical_intelligence.

**Pipeline**: `generate_intelligence_article()` (MIE context + triggering event + verified historical context + Fact-Grounded live price moves) → cross-validated against real numbers → `compute_seo_intelligence()` (deterministic, no second LLM call — headline angle, keywords, internal-link candidates) → full JSON-LD (Article + optional FAQPage) → `IntelligenceArticle` persistence with `companies_affected`/`related_companies`/`related_themes`/`historical_refs` all populated.

**Direct reuse verdict (from source agent): YES, largely as-is.** `run_evergreen_cycle` and `run_historical_cycle` are already fully event-independent, already run daily including weekends, and already go through the same fully SEO-wired, internally-linked, historically-grounded publish pipeline as every other article type. A Weekend Intelligence surface could be built by adding one new `TEMPLATES` entry plus a new topic-driven cycle function modeled directly on `run_historical_cycle` — reusing article generation, SEO computation, validation, and persistence verbatim, without touching the AI provider cascade or the historical-matching engine. **The one genuine gap**: nothing in AIPE's scheduler distinguishes a weekend run from a weekday run — a `CronTrigger(day_of_week="sat,sun", ...)` pattern doesn't exist anywhere yet and would need to be introduced.

---

## 18. Final Architecture Map

```
DATA SOURCES
  NSE/BSE (announcements, board meetings, corp actions, filings)
  RSS (6 India-finance feeds)  ·  RBI / SEBI / PIB / US Fed (RSS)
  yfinance (India + global indices, futures, VIX, currencies, commodities)
  NSE scrape (FII/DII flows, PCR/max pain)  ·  Finnhub (per-company news, peers)
        │
        ▼
INGESTION  (app/tasks/ingest_tasks.py, app/providers/*, app/services/company_announcements_service.py)
  job_ingest_news (15min)  ·  job_ingest_policy (60min)  ·  ingest_announcements (30min)
  — ALL interval-based, ZERO day-of-week gating —
        │
        ▼
DATABASE  (NewsArticle, Event(+Company/Sector/Coverage/Similar/Policy), GovernmentPolicy,
           CompanyAnnouncement, MacroRelease, HistoricalMarketEvent, ThemeState,
           Opportunity(+8 related), IntelligenceArticle, MarketStory, MarketSnapshot,
           PredictionRecord/Evaluation, ScoreHistory)
  — CalendarEvent is the one exception: no production ingestion path exists (§7) —
        │
        ▼
ENRICHMENT / SCORING
  job_enrich_events (5min, 10-stage AI pipeline + scoring_engine)
  theme_worker (10min)  ·  opportunity_generator (7:30AM cron, deterministic formula + DeepSeek)
  historical_memory_service.find_similar_events() (on-demand, multi-factor similarity)
        │
        ▼
MIE  (services/intelligence/engine.py)
  Read-through aggregator: story + themes + top_events + opportunities → single "now" snapshot
  Refreshed every 5min, cached in Redis (mie:state:v1) — NO cross-day state, NO diffing
        │
        ▼
AI / AIPE PUBLISHING  (services/aipe/publisher.py, article_generator.py)
  12 article types, multi-provider AI fallback cascade, Fact-Grounding validation,
  deterministic SEO computation, JSON-LD, internal linking
  7 scheduled jobs — ALL zero day-of-week gating
        │
        ▼
CACHE  (Redis + inconsistent in-process dicts)
  dashboard:v1, mie:state:v1, market:story:latest, indices:list, commodities:prices:v2, ...
  Mechanism keeps refreshing on weekends — but no payload self-flags "closed market" data
        │
        ▼
API  (FastAPI routers — /api/mie, /api/radar, /api/events, /api/news, /api/market, /api/historical, ...)
        │
        ▼
HOMEPAGE / PRE-MARKET  (apps/web/app/page.tsx, PreMarketTab.tsx)
  5+ independent session-detection implementations, 3 independent bullish/bearish derivations
  Hardcoded "Today" copy regardless of underlying article's real date
```

**Where Weekend Intelligence plugs in without duplicating anything:**

```
                         ┌─────────────────────────────────┐
                         │   NEW: job_weekend_intelligence   │
                         │   CronTrigger(day_of_week="sat,sun")│
                         │   — the one genuinely new pattern —│
                         └───────────────┬───────────────────┘
                                          │
        ┌─────────────────────┬──────────┼──────────────┬───────────────────┐
        ▼                     ▼                          ▼                   ▼
 Opportunity Engine    historical_memory_service   news/policy tables    AIPE publish pipeline
 (existing formula,    .find_similar_events()      (already weekend-    (NEW: one TEMPLATES
  reused as-is —        (existing, reused as-is —   populated by RBI/    entry + one cycle fn
  §10 verdict: YES)      §11: already answers        PIB/SEBI ingestion   modeled on
                         "what happened after        that never stops)   run_historical_cycle
                         similar events?")                                — §17 verdict: YES)
```

No existing pipeline's internal logic needs to change. The new job is purely a **caller** that sits alongside `run_historical_cycle`/`run_evergreen_cycle`, reusing their exact downstream path (`generate_intelligence_article` → `compute_seo_intelligence` → persist).

---

## 19. Reuse vs New

| Capability | Already Exists? | Current Location | Can Reuse? | Needs Modification? |
|---|---|---|---|---|
| Market session detection | Yes (5+ times, inconsistently) | `market_data.py`, `api/market.py`, `intelligence/engine.py`, `aipe/content_planner.py`, `MarketSessionGate.tsx`, `PreMarketTab.tsx` | Partially — pick one as source of truth | Yes — consolidate, or at minimum don't add a 6th implementation |
| News ingestion | Yes | `tasks/ingest_tasks.py` + `providers/*` | Yes, as-is | No (already weekend-unrestricted) |
| Events | Yes | `pipeline/event_pipeline.py`, `db/models/event.py` | Yes, as-is | No |
| Policy (RBI/SEBI/PIB) | Yes | `providers/{rbi,sebi,pib}_provider.py` | Yes, as-is | No |
| Calendar | **No real ingestion** | `db/seed.py` (hardcoded, prod-disabled) | No | Yes — needs real ingestion if Weekend Intelligence wants calendar data; not required for a first version |
| Global markets | Yes | `api/market.py`, `market_data.py`, `api/commodities.py` | Yes, as-is | No (though duplicated ticker lists across 3 files) |
| Themes | Yes | `intelligence/theme_worker.py`, `ThemeState` | Yes, as-is | No |
| Company intelligence | Yes, but fragmented across 3 endpoints | `api/company_intelligence.py`, `api/stocks.py`, `api/announcements.py` | Yes, with multiple calls | No code changes, just multiple calls |
| Historical data / similar-event matching | Yes, fully implemented | `historical_memory_service.py` | **Yes, as-is** — directly answers "what happened after similar events?" | No |
| Opportunity scoring | Yes, deterministic formula | `pipeline/opportunity_generator.py` | **Yes, as-is** — confirmed reusable for "Monday Opportunities" | No |
| MIE | Yes, single-snapshot only | `intelligence/engine.py` | Yes, as a read layer — but cannot provide cross-day comparison | Only if "vs Friday" comparison is required |
| Pre-market pipeline | Yes (2 parallel versions) | `api/premarket.py` (unused) + `api/market.py`+`PreMarketTab.tsx` (real) | Not directly relevant to weekends (pre-market is a weekday concept) | N/A |
| Scheduler | Yes, 30 jobs, zero day-of-week gating anywhere | `scheduler/scheduler.py` | Yes as infrastructure | **Yes — needs one new job with a genuinely new `day_of_week` trigger pattern** |
| Cache | Yes, but two disconnected TTL config systems | `cache/cache_service.py` vs `core/config.py` | Yes, mechanically | No (pre-existing inconsistency, not blocking) |
| Homepage | Yes | `app/page.tsx` | Partially | Only if Weekend Intelligence needs its own homepage surface/section |
| AIPE publishing | Yes, 12 article types, full pipeline | `services/aipe/publisher.py` | **Yes, as-is** — confirmed reusable, model on `run_historical_cycle` | Additive only: one new `TEMPLATES` entry + one new cycle function |

---

## 20. Most Important Final Output

### A. What is already running

A real, working, mostly-unrestricted-by-day ingestion and intelligence stack: NSE/RSS news ingestion (BSE currently broken), RBI/SEBI/PIB/Fed policy ingestion, event creation+10-stage AI enrichment, a deterministic opportunity-scoring engine with DeepSeek enrichment, a ~30-event verified historical database with a real multi-factor similarity matcher (already reused by 2 other systems), a 5-minute-refresh MIE aggregation layer, a 12-article-type AIPE publishing pipeline with SEO/JSON-LD/internal-linking built in, global market data (yfinance-based) for indices/futures/VIX/currencies/commodities, and a 30-job APScheduler running on a fixed IST clock. All 30 scheduled jobs run every day of the week including Saturday/Sunday — nothing in this codebase currently has day-of-week awareness at all.

### B. What is broken

The reported weekend bullish/bearish bug is real and has a precise, three-part root cause: (1) `StoryEngineWorker` only regenerates the AI market story when live price data changes, and weekend prices don't move, so no new story is ever written; (2) both `MIE.read_story()` and `homepage_intelligence()` fall back to "most recent row, no date filter" when their cache misses, silently serving Friday's story all weekend; (3) hardcoded "Today"/"today" copy in three places (frontend and backend) presents that stale verdict as current. This is a stale-cache-plus-no-date-filter bug, not a session-detection bug — session detection is largely correct. Secondary, related issues: 5+ duplicated and inconsistent session-detection implementations (2 of which have zero weekend awareness at all); a pre-market countdown timer with no weekday check; an economic calendar with no real production ingestion path at all; confirmed-broken BSE ingestion; no cross-source news dedup; two DB models with fragile registration (mirrors a bug class already hit once this project — see `[[project_sqlite_footgun_family]]`); and one unconditional (non-prod-gated) placeholder-data seed job.

### C. What can be reused

Without modification: the Opportunity Engine's scoring formula (confirmed by direct source-code analysis to be a pure function of recent classified news, with no day-of-week logic baked in — reusable today for "Monday Opportunities"); the historical similar-event matching engine (already answers "what happened after similar events?" and is already used by two other systems); the entire AIPE publish pipeline (article generation, Fact Grounding, SEO computation, JSON-LD, internal linking — reusable by adding one new article type modeled on the already-event-independent `run_historical_cycle`); global market data fetching; and the news/policy ingestion pipelines, which already run unrestricted on weekends and already produce genuine weekend content (RBI/SEBI/PIB do publish on non-trading days).

### D. What is missing

A day-of-week-aware scheduler trigger pattern (doesn't exist anywhere in this codebase — would be new, but small and additive); any cross-day state comparison capability in MIE (no "vs. yesterday/Friday" diffing exists anywhere); an NSE/BSE trading-holiday calendar (no `MARKET_HOLIDAY` state exists — Diwali is currently treated as a normal Tuesday); a real, production-safe economic/earnings/IPO calendar ingestion path (today's calendar is 100% hardcoded and disabled in prod); bond yield data (not implemented at all); a single canonical session-detection source of truth; and an explicit "this data reflects a closed market" flag on cached payloads.

### E. Proposed integration point (smallest possible change)

Add exactly one new scheduled job — the first `CronTrigger(day_of_week=...)` in this codebase — that runs on Saturday/Sunday and does nothing more than call three already-existing systems in sequence: the Opportunity Engine's existing scoring function (for "opportunities heading into Monday"), `historical_memory_service.find_similar_events()` (for "what usually happens next" framing), and the AIPE publish pipeline via one new `TEMPLATES` entry modeled directly on `run_historical_cycle`'s structure. No schema changes are required — `IntelligenceArticle` already has every column this needs. No existing pipeline's internal logic changes. Separately, and arguably with higher priority regardless of whether Weekend Intelligence ships at all: add a date/session guard to `MIE.read_story()`'s and `homepage_intelligence()`'s "latest row" fallback queries, so a stale weekend read returns an explicit "stale — from Friday" signal instead of silently impersonating today's data. That is the actual fix for the reported bug, and it is currently a live, user-facing incorrect-information problem independent of any new feature work.

---

**AUDIT STATUS: COMPLETE**

**Recommendation for next phase**: before writing any new Weekend Intelligence code, fix the §1/§20-B root cause (add the date/session guard to the two "latest row" fallback queries) as its own small, isolated change — it's an existing correctness bug, not scope creep, and it removes the exact failure mode a new weekend-facing feature would otherwise inherit on day one. Then implement Weekend Intelligence as the single new scheduled job described in §20-E, deliberately choosing not to touch MIE, the Opportunity scoring formula, the historical matcher, or any ingestion pipeline — every one of those already works and already runs on weekends.
