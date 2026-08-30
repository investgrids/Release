# P1 — Scheduled-Article Zero-Trace Fix

**Date:** 2026-08-30
**Trigger:** the AI provider reliability audit found scheduled/synthetic candidates (`morning_intelligence`, `market_wrap`, and by the same code shape `historical_intelligence`) leave zero database trace when generation fails — 22 real occurrences in one 3h11m production log window.
**Scope:** owner's explicit design — a new durable lifecycle record for these candidates, never a fabricated `EventTriage` row.

## The precise mechanism (confirmed by code read, not assumed)

`_publish_new_article()` (`publisher.py`) unconditionally persists an `IntelligenceArticle` row **once it has real generated content** — even a validation/fact-grounding failure still creates a real row with `status="failed"`. The zero-trace gap is narrower and more specific: when `generate_intelligence_article()` itself returns `None` (every AI provider exhausted, or the LLM's output fails JSON/schema parsing), `_publish_new_article()` returns `None` *before ever constructing an article row*. For triage-driven candidates this is masked — a real `EventCoverage` row already exists from triage time, and `coverage_mark_failed(reason="generation_failed")` records it. Scheduled/synthetic candidates have no such row (nothing was ever triaged), so this exact case left nothing at all.

Real call sites with this shape, all now fixed:
- `run_aipe_cycle`'s scheduled path (`morning_intelligence` / `market_wrap`)
- `run_evergreen_cycle` (`educational_intelligence`)
- `run_historical_cycle` (`historical_intelligence`)

## What was built

- **`CandidateRun`** (`app/db/models/candidate_run.py`) — a new, durable lifecycle record scoped specifically to non-triaged content. Fields: `candidate_id`, `candidate_type`, `trigger_type`, `created_at`, `generation_started_at`, `provider_attempts` (JSON), `terminal_status`, `failure_reason`, `article_id`, `completed_at`. Terminal states: `PUBLISHED`, `PROVIDER_FAILED`, `VALIDATION_FAILED`, `INTERNAL_ERROR` (`SKIPPED` is defined but deliberately unused in this pass — see scoping note below).
- **`candidate_lifecycle.py`** — two small helpers, `start_candidate_run()` (committed immediately, before generation, so a crash mid-generation still leaves a real row) and `complete_candidate_run()` (writes the real terminal outcome).
- **Real provider-attempt visibility, not a synthetic summary**: `generate_intelligence_article()` and `_publish_new_article()` both gained an optional, purely-additive `failure_log` parameter, threaded down to the existing `_call_with_fallback(failure_log=...)` mechanism that was already built for this (per `_call_provider`'s own docstring) but never wired into these callers. Every existing caller that doesn't pass it sees identical behavior to before.
- Wired into all 3 real call sites: a `CandidateRun` starts right before the generation attempt, and completes with the real outcome — `PUBLISHED` + real `article_id`, `PROVIDER_FAILED` + real provider attempts when generation returns `None`, `VALIDATION_FAILED` + real `article_id` when a row was created but didn't pass, or `INTERNAL_ERROR` + the real exception message on an unexpected crash (caught locally, recorded, then re-raised so the existing cycle-level error handling is unaffected).

## Explicit scoping decision (matches the owner's framing, not over-built)

A `CandidateRun` is only created **right before a generation attempt** — not at the moment a candidate slot is first considered. A duplicate-match or an already-covered/thin-sample skip happens *before* that point and is not tracked here: a duplicate match already correctly updates a real, different existing article (a real outcome, not a loss), and a thin-sample skip was never going to attempt generation at all. The real, demonstrated gap was specifically "entered generation, then vanished" — this fix closes exactly that, not a broader candidate-funnel model the audit didn't ask for.

## Real verification

- 7 new tests, all real DB-backed (`tests/services/test_candidate_lifecycle.py`): `start_candidate_run` persists immediately and is visible from a separate session; the exact incident case (`PROVIDER_FAILED`, zero `IntelligenceArticle`, real terminal record with real provider attempts); `PUBLISHED` records the real article ID; `VALIDATION_FAILED` records both the article ID and reason; `INTERNAL_ERROR` records the real exception text; `failure_log` threading populates on a provider exception and stays fully backward-compatible when omitted. All 7 pass.
- 20 existing, adjacent publisher tests re-run (`test_comparison_publisher.py`, `test_signal_publisher_titles.py`) — no regression.
- Real syntax/import verification and confirmed the new `candidate_run` table registers on `Base.metadata` correctly.

## A real, separate finding surfaced while testing

`D:\IG`'s main branch has **no test-database isolation conftest at all** — `apps/backend/tests/` has no top-level `conftest.py`, so the full test suite (including these new tests) runs directly against the real local `ig_dev.db` file, not an isolated scratch database. A comparable guardrail (session-scoped scratch DB, auto-wiped, real DATABASE_URL override) was built on a separate feature branch during the Company Identity work (documented as closing a real repeated incident where test cleanup deleted real Company Master rows) but was **never ported back to `main`**. This fix's own new table had to be created directly against the local dev DB with a one-off script — the exact "no such table" symptom that guardrail was built to prevent surfacing elsewhere. Flagged for a separate decision; not fixed in this pass (out of scope for the incident being closed here).

## Explicitly not done

- No fix to the `historical_intelligence` path's separate `min_events`/thin-sample logic, duplicate detection, or content quality — only the zero-trace gap.
- No new admin/API endpoint to query `CandidateRun` rows — this is the durable persistence layer the next step (candidate lifecycle observability, per the locked roadmap) would build on top of.
- Not deployed yet — committed locally, pending review.

## P1.1 — test-DB isolation, ported before deploying P1 (owner decision)

Given the test-isolation gap above, the owner held P1's deployment and required porting the proven isolation guardrail from `company-identity/c1-reconciliation` (built there after a real repeated incident: test cleanup deleted real Company Master rows, twice) into `main` first — as its own, separately attributable commit (`2bf0642`), not bundled with `3f50d71`.

**Ported, not redesigned**: `apps/backend/tests/conftest.py` (new — none existed before) gives every test its own on-disk scratch DB, wiped fresh every session, DATABASE_URL overridden before `app.core.config`/`app.db.session` can be imported by anything else. One addition beyond the ported original: a **fail-closed guard** — after the override, the module imports `settings` for real and asserts its resolved `database_url` is neither the real dev DB's filename nor anything but the exact expected scratch URL, refusing to even collect tests otherwise.

Schema creation naturally imports `app.db.models` (registering every model, including the new `CandidateRun`) before `Base.metadata.create_all()` — no one-off manual table-creation script needed going forward, closing the exact gap that made this session create `candidate_run` by hand against the real dev DB.

**Full suite run against the isolated DB**: 1004 passed, 2 skipped, 2 xfailed, 27 failed — all categorized, none traced to the isolation mechanism itself:
- **14 pre-existing/unrelated**: live-network-named tests, plus 3 already independently confirmed today as pre-existing (a mock signature mismatch, a known flaky test).
- **1 real, separate, already-explained cause**: `test_weekend_intelligence_scheduler.py`'s hardcoded expected job count (29) didn't account for this session's earlier P0 fix adding a 30th recurring job (`job_check_ingestion_silence`) — a P0 consequence, not a P1.1 one. Not fixed here to keep this commit attributable to test isolation only.
- **12 genuine, previously-hidden data dependencies — exactly what isolation exists to surface**: `test_quant_leakage`/`test_quant_membership` need real historical `PriceBar`/`IndexMembership` rows; `test_warehouse_health` asserts on 20 real seeded `Source Registry` rows; `test_warehouse_market_observations` hit a **real `FOREIGN KEY constraint failed`** inserting into `market_observations` against an unseeded `source_registry` table; `test_warehouse_raw_evidence` shares the same pattern. None fixed here — they need their own real seed fixtures to become properly self-contained, a real, separate backlog item.

**Decision point**: P1 (`3f50d71`) and P1.1 (`2bf0642`) are both committed, separately attributable, neither deployed. Next: owner review, then deploy both together, then real production verification of one scheduled cycle (a successful run producing `PUBLISHED` + real `article_id`, and eventually a genuine failed run producing a durable failure state — never manufactured in production).
