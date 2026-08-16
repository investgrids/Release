"""
Phase 2E.1 — the leakage-safety allowlist.

This is the audit's conclusion turned into code, not a fresh judgment
call: every table below was checked for (a) whether it is ever mutated
in place after creation and (b) whether a point-in-time reconstruction
is actually possible. Anything not on SAFE_SOURCES must not be read by
any Phase 2E code for historical reconstruction — if a signal isn't
recoverable, the rule (owner's explicit instruction) is UNKNOWN, never
"substitute today's value".

SAFE — append-only or genuinely versioned, confirmed by direct code
audit (grep for UPDATE/setattr/delete-reinsert against each model, see
this repo's Phase 2E audit conversation for full citations):

  EventTriage         — insert-only, one row per raw event, confirmed no
                         writer ever updates an existing row.
  AICompanySignal      — idempotent insert-only; `sector` is resolved and
                         FROZEN at write time (never re-derived later) —
                         this is the one place a company's historical
                         sector can be trusted.
  CompanyAnnouncement  — insert-if-not-exists, skips (never updates) on
                         duplicate; impact_score/sentiment set once.
  MarketSnapshot (snapshot_type="close" only) — one immutable row per
                         trading session.
  MarketStory          — new row generated per cycle, old rows untouched.
  ScoreHistory          — genuinely append-only, but NARROW: only
                         entity_type in ("event","company") is ever
                         actually populated in practice, despite the
                         model comment implying sector/theme/opportunity/
                         risk coverage too. Do not assume other entity
                         types have data.

EXCLUDED — mutated in place with no (or only partial) history, confirmed
by direct code audit:

  ThemeState            — overwritten every ~10 min, zero history anywhere.
  IntelligenceArticle    — key_takeaway/why_it_matters/what_to_watch_next/
                         companies_affected all rewritten in place
                         (continuous updater, duplicate-merge, two admin
                         backfills). confidence_score/quality_score/
                         event_score themselves are never rewritten
                         (safe if you need ONLY those three numbers), but
                         nothing else on this row is trustworthy as
                         historical belief.
  HistoricalMarketEvent  — outcome fields backfilled in place with no
                         updated_at to detect it; its own "verified
                         ground truth" framing is optimistic. Not used
                         here anyway — PriceBar is Phase 2E's outcome
                         source (see below), which has no such ambiguity.
  Fact                    — blind setattr overwrite of every field,
                         non-date-scoped key for events, no created_at.
  Opportunity + children — Opportunity itself is setattr-overwritten;
                         OpportunityCompany/Timeline/SectorDistribution/
                         Graph are hard DELETE+re-INSERT on every daily
                         run — prior state is physically destroyed.
  IGNode / IGEdge         — silently overwritten, IGEdge lacks even an
                         updated_at to signal mutation happened.
  Event.impact_score/.confidence (read directly) — mutated via explicit
                         UPDATE by two rescore paths. Use ScoreHistory's
                         entity_type="event" rows instead, which do
                         preserve previous_score at the moment of rescore.
  Live sector/company classification lookups (_NSE_UNIVERSE and the two
                         parallel lists in sectors.py/stocks.py) — single
                         non-date-stamped list, resolved live at read
                         time. Never call this for a historical row; use
                         AICompanySignal.sector (frozen at write time)
                         instead.

Outcomes: PriceBar (Phase 2B/2D) — a plain OHLCV warehouse, not an
opinion. There is no "verified vs backfilled" ambiguity the way there is
for HistoricalMarketEvent — a close price is a close price. Every Phase
2E outcome reuses the exact same absolute + Nifty-relative resolution
Phase 2D validated (app.services.quant.phase2d_backtest), so
outcome_source is always "pricebar" and never ambiguous.
"""
from __future__ import annotations

SAFE_ENTITY_TYPES_SCORE_HISTORY = ("event", "company")

RESEARCH_VERSION = "phase2e-pilot-v1"
OBSERVATION_SCHEMA_VERSION = "2e-observation-v1"
