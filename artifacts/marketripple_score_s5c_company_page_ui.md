# MarketRipple Score — S5-C: Company Page UI

**Date:** 2026-08-29
**Scope:** Third S5 sub-phase. Backend read boundary + real Overview-tab UI. Local/shadow only — not deployed or pushed to production, matching the standing `publishable=False` phase lock.
**Branch:** `company-identity/c1-reconciliation`

## Naming collision found and resolved before writing any UI code

Before touching the Company page, a real, load-bearing conflict was found: the page already had a card called **"MarketRipple Score"** (a `CompanyHero` KPI tile) and a second card called **"MarketRipple View"** — both fed by the *older*, single-engine AI/evidence company score (`/api/company-scores/{symbol}`), not the new four-pillar `BANKING_V1` model this session built through S1-S5B. Shipping the new score under the same name would have created a *third*, competing "MarketRipple Score" — precisely the failure mode a prior session batch (commit `b22ac06`) already spent effort fixing once.

Flagged to the owner before writing any component code. Decision (owner, following external review): **"MarketRipple Score" is reserved exclusively for the unified four-pillar methodology going forward.** The older engine's real evidence isn't discarded — it continues powering the Current Intelligence pillar (Banking) and, standalone, a renamed "Current Intelligence" card (non-Banking, or not-yet-scored).

## Backend — the read boundary

- **`app/services/marketripple_score/public_projection.py`** — `get_marketripple_score_projection(db, raw_symbol)`, the one real read path. Resolves the input through the real Company Identity resolver (`resolve_entity_by_any_symbol`) first, so a historical/alias symbol lands on the exact same record a current-symbol request would — never a second score identity for the same real company. Reads only `get_latest_snapshot()` (S5-A) — zero live computation, zero yfinance/NSE calls. Deterministic, priority-ordered reason-code → user-copy mapping (data-quality reasons outrank evidence-thinness; never a concatenation of raw codes).
- **`GET /api/companies/{symbol}/marketripple-score`** — thin route wrapper, matching the existing `/{symbol}/tier` and `/{symbol}/ripple` pattern exactly.
- 7 new real DB-backed tests, covering all 4 acceptance profiles plus alias resolution, unresolved-symbol, and no-snapshot-yet edge cases.

## Frontend — `CompanyPageClient.tsx`

- **`CompanyHero`**'s header KPI tile now reads the new unified score via a new `useMarketRippleScore` hook. Never renders a blocked company's internal number — shows "Not available yet" for both "no methodology for this sector" and "blocked by evidence quality," matching the honest-tile philosophy the tile already had before this change.
- **`MarketRippleViewCard` → `CurrentIntelligenceCard`** ("Current Intelligence") — same real old-engine content (score, verdict, one helping/holding-back reason each), just renamed. Now the Overview-tab fallback shown only when no unified-score snapshot exists for the company.
- **New `MarketRippleScoreCard`** — the real unified score. Headline number dominates; the four pillars render as a compact horizontal row (not four competing gauges); one understated "Evidence coverage NN%" line (not a second confidence meter, not labeled "confidence" — coverage and confidence are different things); no per-pillar weights (reserved for S5-D's methodology page). A blocked company renders only the server-computed `block_headline`/`block_message` — the raw score is never sent to this state at all.
- **New `MarketRippleScoreSection`** — the one real decision point for which card renders, driven entirely by the snapshot's `resolved`/`snapshot`/`eligible` fields (no client-side re-derivation of eligibility).

## Real, live verification (Playwright, local FastAPI + Next.js dev servers, real persisted S5-A/B data)

| Profile | Hero tile | Overview card |
|---|---|---|
| **ICICIBANK** (eligible) | `60/100 · NEUTRAL` (real) | Real score, 4 pillars (69/31/78/56), evidence coverage 83%, updated date |
| **KOTAKBANK** (partial-but-eligible) | `58/100 · NEUTRAL` (real) | Real score, 4 pillars (73/17/76/55), evidence coverage 80% |
| **YESBANK** (data-quality block) | "Not available yet" | "Unavailable — Insufficient verified financial data — Some financial evidence could not be verified..." — real internal score (52.8) confirmed absent from the entire page |
| **INDUSINDBK** (evidence-thinness block) | "Not available yet" | "Unavailable — Evidence still building — MarketRipple does not yet have enough current evidence..." — the distinct message, confirming the two block reasons render differently |
| **TCS** (non-Banking) | "Not available yet" | Unified card correctly absent; "Current Intelligence" fallback correctly renders instead |

`tsc --noEmit` clean. 43/43 backend tests pass (7 new + 36 carried over).

## Explicitly not done in this batch

- **Not deployed.** Built and verified entirely on the local worktree branch; nothing pushed, nothing wired into the real production Company page.
- **S5-D** (methodology page, `/methodology/marketripple-score`) — the card's copy deliberately omits pillar weights and stays out of methodology explanation, reserved for that page.
- **S5-E** (multi-cycle shadow validation) — still the gate for flipping `publishable` to `True`; this batch's real score rendering is a *local verification*, not a production go-live.

## Status: S5-C DONE

Backend read boundary and Overview-tab UI built, tested, and verified end-to-end with real data across all 4 owner-named acceptance profiles plus a real non-Banking fallback case. Ready for S5-D or S5-E, per the owner's own sequencing.
