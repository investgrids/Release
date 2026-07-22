# Phase 2 Completion Report — Decision & Verdict Engines

Date: 2026-07-22
Scope: AI Search — Investment Verdict Engine, Decision Engine, AI Recommendation Engine, plus enhancements to the existing Opportunity Score and Risk Score engines.

## Features

- **Investment Verdict Engine** (`app/services/investment_verdict_engine.py`) — computes the research-outlook rating from real signals (MIE market direction, blended confidence score, live VIX, real Opportunity Engine score when the entity/sector matches), reconciled against the AI's own stated rating rather than trusted outright.
- **Decision Engine** (`app/services/decision_engine.py`) — for genuine two-entity decisions, computes both sides independently and picks the data-favored one, or honestly returns "no clear edge" when neither has a real differentiator.
- **AI Recommendation Engine** (`app/services/ai_recommendation_engine.py`) — real sector/theme-matched candidates from the Opportunity Engine, cross-referenced against the real 202-company NSE universe, replacing an LLM-invented "top N stocks" list.
- **Opportunity Score Engine** (enhanced) — fixed a title-match substring bug at the repository root (`app/repositories/opportunity_repository.py`), protecting all 4 real callers.
- **Risk Score Engine** (enhanced) — added a real per-entity bearish-event signal (`app/services/market_scoring_engine.py::score_risk`); also now runs for `sell`-intent queries, previously excluded entirely.

## Bug fixes (9 verified)

1. `investment_verdict.confidence` disagreed with the canonical `confidence_data.score` — backend recurrence of a duplication bug already fixed on the frontend.
2. "switch/rotate/move **from** X **to** Y" unrecognized by intent detection.
3. `list_picks` missed sector-qualifier phrasing ("top 5 **banking** stocks").
4. A matched multi-sector Opportunity row fed companies from every tagged sector, not just the one that matched the search.
5. The word "me" substring-matched inside "invest**me**nt" in the Opportunity Engine's title search.
6. Word-boundary bug in entity matching — "ITC" inside "sw**itc**h", "REC" inside "r**ec**ent", "LIC" inside "po**lic**y".
7. Bare "X or Y?" and "compare A and B" phrasing never triggered comparison mode.
8. "move **investment** from X to Y" — a filler word broke the fix from #2.
9. "best/top X companies/stocks" with no digit at all wasn't recognized as a recommendation query.

## Testing

- **Tier 1** (`tests/services/test_ai_search_routing.py`) — offline, no DB/network/LLM: **15 passed, 2 expected xfail** (documented known gap: bare "\<sector\> stocks/companies" with no best/top/count qualifier).
- **Tier 2** (`tests/services/test_ai_search_engines_live.py`) — live, through the real pipeline: **12 passed** (full run, 245s).
- **CI**: `.github/workflows/ai-search-regression.yml` — Tier 1 on every push/PR touching `apps/backend/**`; Tier 2 (`release-e2e` job) on release-publish and manual dispatch. Not yet exercised on GitHub Actions itself (nothing pushed yet); the `release-e2e` job needs LLM provider secrets configured in the repo before it can run.

## Known limitations (intentionally deferred)

- **Typo tolerance** — "shoud i buy relaince ryt now" doesn't route or resolve entities correctly. Needs fuzzy matching or an LLM classifier; out of scope for a regex fix.
- **Superlative phrasing without best/top** — "which auto stocks look strongest?" doesn't reach the Recommendation Engine.
- **Novel/seasonal theme queries with no keyword anchor** — "stocks benefiting from monsoon" has nothing to hook a real data trigger on.
- **Bare "\<sector\> stocks/companies"** — "Pharma stocks", "Power companies" (no best/top/count) don't route to `list_picks`. Tracked as an `xfail` in Tier 1 rather than silently passing.
- None of the above crash or fabricate — they fall through to the pre-existing, ungrounded general path, same as before this phase.

## Status

All code is local — nothing committed or pushed as of this report.
