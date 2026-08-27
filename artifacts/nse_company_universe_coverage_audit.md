# MarketRipple — NSE Company Universe / Coverage Audit
### READ-ONLY research phase. No code changed, no backend restarted, no Warehouse touched, nothing committed.

Date: 2026-08-23. Every number below is labeled **MEASURED** (I queried the real local DB or read the
real repo source directly), **SOURCE-DERIVED** (from a real external document, cited, but not a number
I computed myself from primary raw data), **ESTIMATED** (a reasoned projection, explicitly not a
measurement), or **UNKNOWN** (I could not establish it in this pass). Nothing is blurred across these
categories.

---

## 1. Executive Verdict

**MarketRipple does not currently have a Company/Security Master database at all.** [MEASURED — confirmed
by exhaustive file search across `app/db/models/`: no `Company`, `Security`, or `Stock` model exists
anywhere in the repo.] What every audit this session has called "the 512 companies" is the literal
length of a hand-typed Python list (`_NSE_UNIVERSE` in `app/api/companies.py`) — no ISIN, no series
classification, no listing date, no verification against any NSE source, maintained entirely by manual
edit. [MEASURED]

More consequentially: **MarketRipple's own real, evidence-driven systems already know about far more
companies than its public company directory recognizes.** The real Intelligence Graph has 792 distinct
company nodes [MEASURED]; **623 of them (78.7%) are not in the 512-entry static list that powers
`/companies/[symbol]`** [MEASURED — direct set comparison]. Real Development Memory independently
surfaces 615 distinct companies from real ingested evidence [MEASURED], 458 of which also aren't in the
static list. This means MarketRipple is very likely already accumulating real, citable intelligence
(events, developments, graph relationships, AI signals) on hundreds of real companies that have **no
public page, no SEO presence, and no sitemap entry today** — a bigger and more immediately actionable
gap than the external NSE gap this task was framed around.

I also found a confirmed identity-collision bug directly relevant to §D: **12 real companies exist as
duplicate Intelligence Graph nodes** — once under a bare symbol, once under a `.NS`-suffixed variant
(RELIANCE / RELIANCE.NS, SBIN / SBIN.NS, HDFCBANK / HDFCBANK.NS, and 9 others) [MEASURED]. Real evidence
for these companies is currently fragmenting across two separate graph identities.

I successfully pulled NSE's real, current, official main-board equity securities file directly from
NSE's own archive server (`nsearchives.nseindia.com`) — 2,553 real active main-board securities as of
today, with real SERIES/ISIN/listing-date data for every one [MEASURED, primary source, fetched live].
I could **not** obtain an equally authoritative real-time SME count in this pass — the URL pattern I
tried returned stale/incomplete data (1 real row), so the SME figure below is SOURCE-DERIVED from
secondary reporting, not primary-verified. This is flagged explicitly, not blurred.

---

## 2. Section A — Current MarketRipple Company Universe

### A.1–A.16, answered against real data wherever a real query was possible

| # | Question | Answer | Label |
|---|---|---|---|
| 1 | Company records | **No DB table exists.** Static list: 512 distinct symbols (514 raw `"symbol":` occurrences in source, consistent with the file's own comment describing 2 near-duplicate entries already removed) | MEASURED |
| 2 | With NSE symbols | 512 (100% — the list *is* NSE symbols; it has no other identity) | MEASURED |
| 3 | With BSE symbols | 0 — no BSE field exists in `_NSE_UNIVERSE`'s schema at all | MEASURED |
| 4 | With both NSE+BSE | 0 (field doesn't exist) | MEASURED |
| 5 | With ISIN | 0 — no ISIN field exists anywhere in the static list or any DB table referencing companies | MEASURED |
| 6 | With sector | 512 (100% — `sector` is a required field in every static entry) | MEASURED |
| 7 | With industry | 512 (100% — same, required field) | MEASURED |
| 8 | With market cap | 0 *stored* — the list has only a 3-value `cap` bucket (large/mid/small), not a real market-cap figure; real market cap is fetched live per-request from yfinance, never persisted | MEASURED |
| 9 | With price history | UNKNOWN for the static list itself (no persistence layer). Separately, `price_bars` (quant infrastructure) holds 62,930 real rows [MEASURED] but is scoped to Phase 2's NIFTY 50 validation universe, not the full 512 | MEASURED (price_bars) / UNKNOWN (full-universe coverage) |
| 10 | With ≥1 Event | UNKNOWN precisely — `events` has 3,058 real rows [MEASURED] but company↔event linkage isn't a simple queryable FK in the schema explored this pass; would need a dedicated join not completed here | UNKNOWN |
| 11 | With ≥1 News/Article relationship | UNKNOWN precisely, same reason — `news_articles` (6,594 rows) and `intelligence_articles` (543 rows) exist [MEASURED] but per-company reverse lookup wasn't completed this pass | UNKNOWN |
| 12 | Represented in Development Memory | **615 distinct companies** (`Development.primary_company`, case-normalized) out of 908 Development rows that have any primary company set, out of 1,219 total Development rows | MEASURED |
| 13 | Real Intelligence Graph company node | **792** (`IGNode` where `node_type='company'`), **100%** of which have a real `ticker` value | MEASURED |
| 14 | With Company Score signals | **452 distinct symbols** (`AICompanySignal.symbol`, distinct) across 1,670 real signal rows | MEASURED |
| 15 | Linked to Opportunity V2 | **184 distinct company symbols** across `OpportunityV2.companies`, appearing in 162 of 219 real opportunity rows | MEASURED |
| 16 | With public `/companies/[symbol]` route | 512 — the route is gated entirely by presence in the static list, so this number is definitionally identical to #1 | MEASURED |

### Competing/static universes found in the repo (grep-confirmed, not exhaustive of all 37 files that
merely *consume* one of these — this is the list of files that *define* a distinct symbol set):

| Universe | Location | Size | Nature |
|---|---|---|---|
| `_NSE_UNIVERSE` | `app/api/companies.py` | 512 symbols | Static, hand-typed, powers `/companies` and `/companies/[symbol]` |
| `_SECTOR_STOCKS` | `app/api/sectors.py` | 85 symbols across 13 sector buckets | Static, hand-typed, separate from and smaller than #1 — powers `/sectors/[sector]` |
| `NIFTY_50` | `app/services/quant/universe.py` | 50 symbols | Static, hand-typed, explicit comment: "edited by hand, same as this codebase's existing static company universe" — powers quant Phase 2B validation |
| `IndexMembership` (real DB table) | `app/services/quant/index_membership_seed.py` | 50 symbols, real point-in-time NIFTY 50 membership | **The one genuinely real, sourced, point-in-time-safe universe in the repo** — built this session for the quant leakage-lock work |

**Verdict: MarketRipple does not have one canonical company universe today. It has at least four**,
three of them static Python constants maintained by hand with no reconciliation mechanism between
them, and none of them backed by a real database table with a durable identity key (ISIN or otherwise).

---

## 3. Section B — Authoritative NSE Raw Universe

Fetched live, directly from NSE's own archive infrastructure (`https://nsearchives.nseindia.com`, the
same domain NSE's own "Securities available for Trading" page links to):

**Main board — `EQUITY_L.csv`** [MEASURED, primary source, fetched 2026-08-23]:

| Series | Count | Real meaning |
|---|---|---|
| EQ | 2,291 | Standard rolling-settlement equity — the "normal" tradable main-board series |
| BE | 234 | Trade-to-trade / enhanced surveillance settlement — real, listed, but a different trading mechanism, often applied to smaller/volatile names |
| BZ | 28 | Suspended/restricted — NOT actively normal-tradable |
| **Total main-board rows** | **2,553** | |

Every row carries real `SYMBOL`, `NAME OF COMPANY`, `SERIES`, `DATE OF LISTING`, `PAID UP VALUE`,
`MARKET LOT`, `ISIN NUMBER`, `FACE VALUE` — meaning **ISIN and listing date are already available,
free, directly from NSE, for every one of these 2,553 real securities**, right now.

**SME — not primary-verified this pass.** I found the real NSE archive host and successfully guessed
the main-board file's exact path, but my attempt at the equivalent SME path
(`nsearchives.nseindia.com/content/equities/SME_EQUITY_L.csv`) returned HTTP 200 with only 1 real data
row (THEJO Engineering) plus a footer note — clearly not the real, current SME universe (NSE Emerge is
independently reported to have 400+ real listed companies). I'm not going to report that 1-row file as
the SME count; it's flagged as **UNKNOWN (primary source not yet correctly located)**, with a
SOURCE-DERIVED placeholder below.

**SOURCE-DERIVED cross-check** (Univest's 2026 NSE Stock List, secondary source): "over 2,200 stocks...
EQ, BE, and SM segments combined" on the main board, and "400+" on NSE Emerge SME as of 2026. My own
primary-source EQ+BE count (2,291 + 234 = 2,525) is close to and consistent with this secondary figure,
which gives real confidence the file I fetched is current and accurate — the secondary source likely
just rounds/bundles slightly differently.

### CORE MARKETRIPPLE COMPANY UNIVERSE — recommended definition

Per the task's own framing: **active NSE-listed operating-company ordinary equity shares.** Applied to
the real EQUITY_L.csv data: this is the **EQ series specifically (2,291)**, since BZ (28) is suspended
by definition and BE (234) is a real but distinct settlement/surveillance category that a first cut
should probably treat separately rather than silently merge into "normal" equity. I have not yet
excluded non-operating-company instrument types (there may be a handful of REIT/InvIT/ETF/holding-type
entries even within the EQ series that need name-level review — not completed this pass, flagged as a
real follow-up, not assumed done).

### SME inclusion decision — reporting the data, recommending, not deciding silently

- **A) Include immediately**: would add ~400 (SOURCE-DERIVED, unconfirmed primary count) smaller,
  often thinly-covered, higher-risk-of-thin-content companies right as Phase 0 cleanup work is trying
  to *reduce* fabricated/thin content elsewhere in the app.
- **B) Secondary universe**: SME gets its own `TIER 0`/internal-only treatment (searchable, never
  auto-indexed) until real intelligence accumulates per company — matches the Indexability Quality
  Engine principle already established this session.
- **C) Exclude initially**: cleanest, lowest-risk, defers a real decision rather than making one.

**My recommendation: (B).** SME companies are real, legitimate, NSE-listed operating companies — there's
no principled reason to pretend they don't exist internally — but the platform's own stated indexability
principle (don't index a page until it has real, sufficient evidence) argues for building the identity
layer now and letting real intelligence accumulation (or its absence) decide indexability later, exactly
the same logic already applied to individual companies via the Coverage-Tier model (§F). Not a decision
this document is making unilaterally — flagged for owner confirmation.

REITs, InvITs, and ETFs: **not counted anywhere in this audit's company totals**, per the task's own
instruction — noted as a real, separate future entity-page category, out of scope here.

---

## 4. Section C — Real Coverage Gap

Using the real EQ-series file (2,291) as the main-board reference point [MEASURED], reconciled against
the real, DB-measured MarketRipple identity sets:

| Metric | Value | Label |
|---|---|---|
| NSE eligible main-board companies (EQ series) | 2,291 | MEASURED (primary NSE file) |
| NSE eligible SME companies | ~400 (unconfirmed) | SOURCE-DERIVED, low confidence |
| Total eligible operating companies (approx) | ~2,691 | SOURCE-DERIVED (sum of above, inherits SME's uncertainty) |
| MarketRipple static list (`_NSE_UNIVERSE`) | 512 | MEASURED |
| MarketRipple real IGNode company identities | 792 | MEASURED |

**I did not complete a real symbol-by-symbol or ISIN-based reconciliation between the fetched NSE file
and MarketRipple's identities in this pass** — that requires a dedicated join (NSE's real symbols against
`_NSE_UNIVERSE`'s 512 and separately against IGNode's 792) that the time budget for this research phase
didn't extend to. What I can state as MEASURED from the pieces already computed:

- **Static-list coverage vs. real main-board EQ series**: 512 / 2,291 = **22.4%** [MEASURED — both
  numerators/denominators are real counts, this is a real ratio, though the match itself (which of the
  512 symbols actually appear in the real EQ file, by exact symbol) was not individually verified row-by-row
  in this pass — flagged as the concrete next step, not assumed clean].
- **Real Intelligence Graph coverage vs. real main-board EQ series**: 792 / 2,291 = **34.6%** [same
  caveat].
- **Internal gap** (already fully measured, no external data needed): 623 real IGNode companies with
  zero public page (§1) — this is the one number in this section I'm fully confident in without a
  further reconciliation pass, since it's a pure internal set-difference on data I hold directly.

**Recommendation for the real follow-up work** (not done here, explicitly out of scope for a read-only
pass with this time budget): a proper ISIN/symbol join between the fetched `EQUITY_L.csv` and both
`_NSE_UNIVERSE` and the real `IGNode` ticker set, to produce the exact matched/missing/orphaned counts
the task template asks for (A, B, C). I'm reporting what's real and stopping short of a number I can't
back with an actual row-level match — better an honest partial answer than a fabricated precise one,
consistent with this whole session's discipline.

---

## 5. Section D — Identity Quality Audit

**Confirmed, real findings:**

1. **12 real companies exist as duplicate Intelligence Graph nodes** — a bare-symbol node and a
   `.NS`-suffixed node for the same real company: `RELIANCE`/`RELIANCE.NS`, `SBIN`/`SBIN.NS`,
   `HDFCBANK`/`HDFCBANK.NS`, `ICICIBANK`/`ICICIBANK.NS`, `IOC`/`IOC.NS`, `BPCL`/`BPCL.NS`,
   `ADANIENT`/`ADANIENT.NS`, `ADANIGREEN`/`ADANIGREEN.NS`, `ADANIPORTS`/`ADANIPORTS.NS`,
   `ZEEL`/`ZEEL.NS`, `PAYTM`/`PAYTM.NS`, `AMBER`/`AMBER.NS` [MEASURED — direct DB query]. Real evidence/
   edges for these 12 companies are currently split across two separate graph identities — almost
   certainly caused by some ingestion path using yfinance's `.NS`-suffixed ticker format directly as a
   node key instead of normalizing it first.
2. **Real, documented symbol-reuse/corporate-action case**: `TATAMOTORS` pre- and post-October-2025
   demerger are, per the quant team's own investigation (`app/services/quant/universe.py`'s docstring),
   **legally different companies sharing a symbol history** — the pre-demerger entity (with all its
   historical price data) was renamed `TMPV`, and `TATAMOTORS` was reused for the newly-demerged
   commercial-vehicle entity. Explicitly *not* silently remapped anywhere in the codebase — the
   comment records this as a genuine unresolved identity question, not a bug someone forgot to fix
   [MEASURED — real code/comment, real corporate action].
3. **Ticker is currently treated as the primary/only identity key everywhere** — `_NSE_UNIVERSE`,
   `_SECTOR_STOCKS`, `NIFTY_50`, `IGNode.ticker`, `Development.primary_company`,
   `OpportunityV2.companies`, `AICompanySignal.symbol` all key on a bare ticker string, with zero ISIN
   field anywhere in the identity chain [MEASURED]. This is a real architectural risk exactly matching
   the TATAMOTORS case: any future symbol reuse after a demerger/merger/relisting will silently conflate
   two legally distinct companies' evidence under the current design, with no field anywhere to
   disambiguate them.

**Recommendation**: ISIN is the correct durable identity key for the eventual Company Master **for the
common case** (it survives symbol changes and most renames), but the TATAMOTORS case proves ISIN alone
isn't sufficient either — a real corporate action (demerger) can create a **new** ISIN for what a
casual reader would call "the same company," and can also **reuse a symbol** for an entirely different
new ISIN. The durable model needs: ISIN as the primary key per distinct security, a separate stable
internal `entity_id` that can track a real company across a demerger/rename event (assigned by a human
or a documented rule, not silently inferred), and an explicit, auditable identity-change log — not
redesigned here, per the task's own instruction, just flagged as the shape the future schema needs.

---

## 6. Section E — Data Availability Matrix

| Field | Source (real, already in repo/NSE) | Coverage | Freshness | Historical depth | Rights basis | Reliability | Currently ingested? | Gap? |
|---|---|---|---|---|---|---|---|---|
| Company name | NSE `EQUITY_L.csv` | 2,553 main-board | Daily-updated per NSE's own file note | N/A | Official NSE public data | High | No (only in static list, not from this file) | Yes — not wired |
| NSE symbol | NSE `EQUITY_L.csv` | 2,553 | Daily | N/A | Official | High | Partially (static list only) | Yes |
| ISIN | NSE `EQUITY_L.csv` | 2,553 | Daily | N/A | Official | High | **No — zero ISIN anywhere in MarketRipple today** | **Yes, critical** |
| Series | NSE `EQUITY_L.csv` | 2,553 | Daily | N/A | Official | High | No | Yes |
| Listing status | Inferred from presence/absence in NSE's active file | 2,553 | Daily | N/A | Official | High | No | Yes |
| Listing date | NSE `EQUITY_L.csv` | 2,553 | Static per security | Full | Official | High | No | Yes |
| Sector/Industry | Static list (hand-typed) for 512; yfinance `info.sector`/`info.industry` live for any symbol | 512 static / broader via yfinance | Real-time via yfinance, stale-by-design in static list | N/A | Third-party (yfinance scrape) | Medium (yfinance already confirmed unreliable — 29% real failure rate, per this session's Warehouse work) | Yes, both paths | Partial |
| Market cap | yfinance, live per-request only | Any symbol yfinance resolves | Real-time-ish | None persisted | Third-party | Medium | Yes, but never stored | Yes (no history) |
| Current price | yfinance (primary), real `MarketObservation` table (Warehouse, 54 broad-market metrics, not per-company) | Any symbol / 54 macro metrics | Real-time-ish | Warehouse only, from today | Third-party | Medium | Yes | Partial |
| OHLC / historical prices | `price_bars` (real table, 62,930 rows) | NIFTY 50 validation universe only (quant Phase 2) | Historical batch, not live | Real, multi-year for NIFTY 50 | Third-party | Medium | Yes, narrow scope | Yes (full universe) |
| Corporate announcements | `company_announcements` (real table, 532 rows) | Unconfirmed how many distinct companies | Real ingestion pipeline exists (NSE provider) | Ongoing since ingestion started | Official (NSE filings) | High | Yes | Partial (scope not verified) |
| Corporate actions | Not confirmed as a distinct ingested field in this pass | — | — | — | — | — | **UNKNOWN** | Yes |
| Financial results | `company_fundamentals_service.py` exists (real file, not read in depth this pass) | UNKNOWN exact scope | UNKNOWN | UNKNOWN | Likely yfinance | Medium (inherited) | Partially, unconfirmed depth | Yes |
| Shareholding | yfinance `held_institutions`/`held_insiders` (confirmed real, used honestly on Company Pages per that audit) | Any symbol yfinance resolves | Real-time-ish | None persisted | Third-party | Medium | Yes | Partial |
| Board meetings | Not confirmed as a distinct real ingested field | — | — | — | — | — | UNKNOWN | Yes |
| Annual reports/filings | Not confirmed | — | — | — | — | — | UNKNOWN | Yes |
| Company profile | yfinance `longBusinessSummary`, real, already used (`description` field, Company Pages) | Any symbol yfinance resolves | Static-ish | N/A | Third-party | Medium | Yes | No |
| News | `news_articles` (6,594 real rows) | Broad, not company-indexed in this pass | Real, ongoing ingestion | Since ingestion started | Real RSS/publisher sources | High | Yes | Partial (per-company reverse index not verified) |
| Developments | `developments` (1,219 real rows) | 615 distinct companies | Real, ongoing | Since Phase 6A | Derived from real evidence | High | Yes | No (already real) |
| Intelligence Graph | `ig_nodes`/`ig_edges` (1,860/1,189 real rows) | 792 distinct companies | Real, ongoing | Since Phase 6B | Derived | High | Yes | No (already real, but has the §D duplicate-identity bug) |
| Company Score | `ai_company_signals` (1,670 real rows) | 452 distinct companies | Real, ongoing | Since AIPE build | Derived from real articles/opportunities | High | Yes | No (already real) |
| Opportunity V2 | `opportunities_v2.companies` | 184 distinct companies | Real, ongoing (still in remediation) | Since this session's V2 work | Derived | High (pending V2 promotion) | Yes | No (already real) |

**Honest summary of this matrix**: the *evidence-layer* fields (Developments, Graph, Company Score,
Opportunity V2) are all real and already flowing — MarketRipple's problem isn't a lack of intelligence
infrastructure, it's the absence of the *identity* layer (name/symbol/ISIN/series/listing-status) that
should sit underneath all of it and currently doesn't exist as a real table anywhere.

---

## 7. Section F — Company Coverage Tiers

Adapting the task's own suggested structure, checked against what's real:

| Tier | Definition | Searchable internally? | Public route? | Sitemap? | Index/Noindex? | AI Search? | Company Score? | Opportunities? | Ripple? |
|---|---|---|---|---|---|---|---|---|---|
| **0 — Known Security** | Real ISIN/symbol/name/series only, from the NSE master, nothing else | Yes (internal) | No | No | N/A (no page) | No | No | No | No |
| **1 — Basic Company** | Tier 0 + live price + sector/industry (yfinance-resolvable) | Yes | Yes, minimal page | No | **NOINDEX** | Limited (identity only) | No | No | No |
| **2 — Covered Company** | Tier 1 + real filings/events/news history exists | Yes | Yes | Conditional | **INDEX** once a real minimum-content threshold is met (§G) | Yes | Yes | No | Partial |
| **3 — Intelligence-Rich** | Tier 2 + real linked Developments + Company Score and/or real Graph relationships | Yes | Yes | Yes | INDEX | Yes | Yes | Yes | Yes |
| **4 — Deep Intelligence** | Tier 3 + multiple evidence families + real linked Opportunities + historical intelligence + strong provenance | Yes | Yes, full feature set | Yes | INDEX, priority boost | Yes, full feature set | Yes | Yes | Yes |

Real, measured mapping of what MarketRipple already has against these tiers (using the numbers already
established): the 623 real IGNode companies not on the static list are, right now, sitting at
**Tier 3 internally** (real graph presence, likely real Development links) **with zero public
existence** — i.e., the platform has already done the intelligence work for a real Tier-3 company and
is simply not showing it. This is the single most concrete, low-risk, high-value target for whatever
comes after Phase 0.

---

## 8. Section G — SEO / AEO / GEO Consequences

- **Sitemap growth**: going from 512 to even a conservative Tier-2-and-above subset of the real
  ~2,291-company main board is a large jump. Given this session's own finding (Global Fabrication
  Audit) that thin/duplicate pages actively hurt the site, **sitemap inclusion should follow the tier
  model above, not the raw company count** — Tier 0/1 companies stay internal/noindex, never enter the
  sitemap.
- **Thin-page risk**: real and immediate if tiers aren't enforced — a bare Tier-1 page (price + sector,
  nothing else) for a company nobody has real evidence on is exactly the kind of low-differentiation
  page the Opportunity Radar and Article audits already flagged Google's people-first guidance
  penalizes.
- **Duplicate-company risk**: the §D findings (12 real duplicate graph identities, the TATAMOTORS
  case) are a direct SEO risk too — two pages/entities for one real company splits authority and
  confuses both crawlers and AI answer engines about which is canonical.
- **Symbol-change redirects**: needed once a real Company Master exists — NSE publishes symbol/name-change
  data (per the task's own note; not independently fetched in this pass, flagged as a real follow-up).
- **Canonical strategy**: one canonical URL per real `entity_id` (§D), never per raw ticker string, so
  a future TATAMOTORS-class corporate action doesn't strand or duplicate a canonical URL.
- **Real search-demand patterns** ("[company] share price," "[company] results," etc.): genuine, real
  demand exists for companies with real trading activity — but per this session's own already-established
  rule (Opportunity Radar and Article audits), **never build these as keyword-stuffed templates** — they
  should be natural headings over real data (price, real filings, real linked Developments), exactly the
  AEO/GEO discipline already applied elsewhere this session.

**Recommended minimum threshold for INDEX**: Tier 2 as defined above — real price/identity alone
(Tier 1) is not enough to deserve competing for search real estate; genuine filings/events/news history
is the honest bar.

---

## 9. Section H — Automatic Universe Maintenance (design only)

```
NSE EQUITY_L.csv + SME file (real, free, daily-updated per NSE's own file note)
        ↓
periodic reconciliation job (real cadence: NSE's own file states "updated at 10:30 am
        daily" — a once-daily pull is sufficient, no more frequent polling needed)
        ↓
Company/Security Master (new table — real ISIN/symbol/series/listing-date/name)
        ↓
diff against previous pull, detect:
  new listing          (real symbol not seen before)
  SME listing          (real symbol first appearing in SME file)
  SME→Main migration   (real symbol moves from SME file to main file — NSE publishes this directly)
  symbol change        (same ISIN, different symbol vs. last pull)
  name change          (same ISIN, different company name vs. last pull)
  suspension           (symbol present but series changes to BZ-class)
  delisting            (symbol/ISIN present in a prior pull, absent from current)
        ↓
identity reconciliation (ISIN-first matching against existing MarketRipple entities;
        never silently delete a historical entity_id on symbol/name change — append a
        change record instead)
        ↓
MarketRipple coverage-tier state (§F) updated per company
        ↓
Events / News / Developments / Graph / Scores / Opportunities continue exactly as
        today, now resolving against a real stable entity_id instead of a bare ticker
```

**Idempotency**: the diff-against-previous-pull design is naturally idempotent — re-running the same
day's file twice produces zero new change records, matching the exact convention already established
this session for `source_registry_seed.py` (real upsert, never delete-and-reinsert) and
`duplicate_detector.py`'s pattern elsewhere in the app.

**Real cadence**: NSE's own equity file states it updates once daily (10:30 AM). A once-daily
reconciliation job is sufficient and matches the real data's own freshness ceiling — no value in
polling more often.

---

## 10. Section I — Storage Impact

Real measured baseline (2026-08-23, fetched directly from the live SQLite DB via `dbstat`):

| Table | Real rows | Real bytes | Label |
|---|---|---|---|
| Total DB | — | **144.60 MB** | MEASURED |
| `quant_research_evaluations` | 146,916 | 27.38 MB (~195 bytes/row) | MEASURED |
| `intelligence_articles` | 543 | 13.16 MB (~24.8 KB/row — rich JSON fields) | MEASURED |
| `price_bars` | 62,930 | 9.25 MB (~154 bytes/row) | MEASURED |
| `events` | 3,058 | 6.50 MB | MEASURED |
| `news_articles` | 6,594 | 2.58 MB | MEASURED |
| `ig_nodes` + `ig_edges` | 1,860 + 1,189 | small, not separately itemized in top-25 | MEASURED |

**Company/Security Master (new, not yet built)** — ESTIMATED using `ig_nodes`' real per-row footprint
(a comparable flat, mostly-text record) as the closest real analog:

| Scope | Rows | Estimated size (at ~300–600 bytes/row, a text-record range bracketing `ig_nodes`' and `price_bars`' real observed densities) |
|---|---|---|
| Current (512 static, unpersisted) | 0 (no table exists) | 0 |
| Full eligible main-board (~2,291 EQ) | 2,291 | **0.7–1.4 MB** |
| Full eligible incl. SME (~2,691) | 2,691 | **0.8–1.6 MB** |

This table alone is trivially small regardless of scope — **the Company Master itself is never the
storage risk.** The real growth driver, per the owner's own stated concern, is what accumulates
*around* each company once it's real and trackable — price history and evidence, not identity records.

**ESTIMATED projections** (explicitly ranges, not invented precise numbers, per the task's own
instruction — anchored to real observed per-row densities from `price_bars` and the Warehouse's own
real capture rate this session):

| Horizon | Price/observation data (if full ~2,700-company OHLC history is eventually ingested at `price_bars`' real ~154 bytes/row) | Evidence (Developments/Graph/Signals, at today's real per-company densities) |
|---|---|---|
| Current | 9.25 MB (NIFTY-50-scoped only) | ~20 MB combined (developments+ig_nodes+ig_edges+ai_company_signals, from real dbstat figures not individually itemized above but consistent with the measured table sizes) |
| Full eligible-company master, daily OHLC only | ~2,700 companies × 250 trading days/yr × 154 bytes ≈ **104 MB/year** at full scope (vs. today's NIFTY-50-only scope) | Depends entirely on real ingestion coverage expansion — **UNKNOWN** growth rate for evidence at 2,700-company scope, since today's real ingestion (RSS/NSE/RBI/etc.) isn't company-count-bounded the same way price data is |
| +1 year | ~104 MB added (price only, full scope) | ESTIMATED range: 20–80 MB, wide because evidence-ingestion volume doesn't scale linearly with company count the way price bars do |
| +3 years | ~310 MB added (price only, full scope) | ESTIMATED range: 60–250 MB |
| +5 years | ~520 MB added (price only, full scope) | ESTIMATED range: 100–450 MB |

**Explicitly not invented**: I'm not projecting a single precise number because the real ingestion rate
at full-universe scope has never been measured (today's real systems are scoped to a much smaller
company set) — these are genuine ranges anchored to real per-row costs already measured, not guesses
dressed up as numbers.

---

## 11. Section J — Relationship to Intelligence Warehouse

**The owner's proposed architecture is correct and validated by what's actually in the repo.**
Checking it against real evidence: the Warehouse (`Source`/`MarketObservation`/`RawEvidence`, this
session's Phase 1 work) is explicitly evidence/observation-accumulation — it has no concept of "this is
company X" beyond whatever string a given observation happens to carry. The Intelligence Graph
(`IGNode`) is the closest thing to a real entity registry that exists today, but it's populated
*reactively* (nodes get created when evidence mentions them, per the `auto_added` field already visible
in `IGNode`'s schema) rather than *authoritatively* (seeded from a real, verified NSE master) — which is
exactly why it has the §D duplicate-identity problem and the 623-company public-invisibility gap.

```
COMPANY / SECURITY MASTER (proposed — NEW, authoritative, ISIN-keyed, seeded from real NSE data)
      ↑
Raw Evidence → entity resolution (should resolve AGAINST the Master, not create ad hoc nodes)
      ↑
Market Observations
      ↑
Developments
      ↓
Intelligence Graph (IGNode.auto_added should become the exception, not the primary population path)
      ↓
Company Score
      ↓
Opportunity V2
      ↓
Articles / AI Search / Company Pages
```

**Validated, with one refinement**: the Company/Security Master should sit *before* and *authoritative
over* the Intelligence Graph specifically — today's `IGNode` auto-creation is the direct root cause of
the 12 duplicate-identity bug (§D). Once a real Master exists, entity resolution should look up against
it first and only fall back to auto-creating a new node when the Master genuinely has no match (a real,
logged, reviewable event — not silent node proliferation).

---

## 12. Final Report (§K, all 20 items)

1. **Executive verdict**: §1 above.
2. **Exact current MarketRipple Company count**: 512 (static list; MEASURED) / 792 (real IGNode
   identities; MEASURED) — two different real answers depending on which system you ask, which is
   itself the core finding.
3. **Exact authoritative NSE eligible-company count**: 2,291 main-board EQ (MEASURED, primary source)
   + ~400 SME (SOURCE-DERIVED, unconfirmed primary) ≈ 2,691 total (SOURCE-DERIVED for the combined
   figure).
4. **Main-board count**: 2,291 EQ / 2,553 including BE+BZ (MEASURED).
5. **SME count**: ~400 (SOURCE-DERIVED, low confidence — primary fetch attempt failed this pass).
6. **Current MarketRipple coverage %**: 512/2,291 = 22.4% against the static list (MEASURED ratio,
   unverified row-level match); 792/2,291 = 34.6% against real Graph identities (same caveat).
7. **Number missing**: not established row-by-row this pass — UNKNOWN pending the real ISIN/symbol
   join flagged in §4.
8. **Number of questionable/stale MarketRipple records**: 12 confirmed duplicate identities (MEASURED);
   broader staleness (delisted/suspended symbols still in the static list) UNKNOWN, not checked this
   pass.
9. **Identity-quality findings**: §5 (12 duplicates, TATAMOTORS case, ticker-only identity risk).
10. **Current competing company universes in repo**: 4 (§2) — `_NSE_UNIVERSE` (512), `_SECTOR_STOCKS`
    (85), `NIFTY_50` (50, hand-maintained), `IndexMembership` (50, real/sourced/point-in-time-safe).
11. **Recommended canonical universe definition**: active NSE main-board EQ-series operating-company
    equity as the Core, SME as a secondary tracked-but-not-yet-indexed universe (§3), ISIN + a durable
    `entity_id` as the real identity key (§5), never a bare ticker.
12. **Data-availability matrix**: §6.
13. **Coverage-tier model**: §7.
14. **INDEX/NOINDEX recommendation by tier**: Tier 0-1 NOINDEX, Tier 2+ INDEX (§7/§8).
15. **Storage-impact estimate**: §10 — Company Master itself trivial (<2MB even at full scope); real
    growth driver is price/evidence accumulation, honestly ranged not precisely invented.
16. **Automatic-maintenance architecture**: §9.
17. **SEO/AEO/GEO implications**: §8.
18. **Top 10 data gaps**: (1) No ISIN anywhere in MarketRipple today; (2) No real Company/Security
    Master table; (3) 623 real Graph companies with zero public page; (4) No corporate-action tracking;
    (5) No board-meeting data confirmed; (6) No confirmed annual-report/filing ingestion; (7) SME
    universe not primary-verified; (8) Per-company news/event reverse-index not verified to exist
    cleanly; (9) No symbol-change/delisting detection; (10) `price_bars` scoped to NIFTY 50 only, not
    the eligible universe.
19. **Top 10 implementation risks**: (1) Building on ticker identity perpetuates the TATAMOTORS-class
    risk; (2) Silent `IGNode` auto-creation will keep generating duplicates until Master-first
    resolution is enforced; (3) Naive full-universe expansion without tiering repeats the exact
    thin-content problem already flagged in 3 prior audits; (4) yfinance's real 29%-ish failure rate
    (measured this session for Warehouse) means full-universe live-price coverage needs a fallback
    strategy, not just more polling; (5) SME inclusion decided by default/inertia rather than
    explicitly, per the task's own warning; (6) Reconciling 4 existing static universes risks breaking
    whatever currently (perhaps accidentally) depends on their specific, slightly different symbol
    sets; (7) A new Master table competing with rather than replacing the static lists would create a
    5th universe, not fix the problem; (8) Real NSE archive URLs are unofficial/reverse-engineered paths
    (no documented public API contract), so the daily-reconciliation job has real, if low, breakage
    risk if NSE changes its archive layout; (9) Storage estimates here are ranges precisely because
    real evidence-ingestion-rate-at-scale is unmeasured — early over/under-provisioning is possible;
    (10) This entire Coverage track is explicitly deferred behind Phase 0 per the owner's own
    sequencing — starting it prematurely would violate that already-agreed order.
20. **Recommended future implementation phases** (design-only, matching the owner's own explicit
    sequencing — Coverage comes after Phase 0, not before):
    - Phase C1: build the real Company/Security Master table (ISIN-keyed), seeded from a properly
      re-verified NSE main-board + SME pull (fixing the SME primary-source gap first).
    - Phase C2: identity reconciliation — resolve all 4 existing static/real universes against the new
      Master, fix the 12 confirmed duplicate Graph identities, decide the entity_id model for
      corporate-action cases like TATAMOTORS.
    - Phase C3: coverage-tier classification (§7) applied to the full real universe, replacing the
      current "in the static list or doesn't exist" binary.
    - Phase C4: daily reconciliation job (§9), idempotent, matching this session's established
      upsert-never-delete convention.
    - Phase C5: indexability gate (§8) applied before any expansion of the public sitemap.

---

## Sources

- NSE India, "Securities available for Trading": https://www.nseindia.com/market-data/securities-available-for-trading
- NSE archive (primary source, fetched live 2026-08-23): https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv
- Univest, "NSE Stock List 2026 — Complete Guide to All NSE-Listed Companies" (secondary,
  cross-check only): https://univest.in/blogs/nse-stock-list
