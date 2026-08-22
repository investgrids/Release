"""
Opportunity Engine V2 — replaces app/pipeline/opportunity_generator.py's
sector-keyword bucketing + single-provider AI generation with Development
Memory as the canonical input, real Intelligence Graph adjacency for
coherence, and a thesis identity separate from the AI-generated title.

V1 is not modified or stopped by this package. V2 runs in shadow
(source="opportunity_v2_shadow", public_status="shadow") purely as
TEMPORARY validation infrastructure (owner instruction, 2026-08-22) — the
end state is a single canonical V2 pipeline with V1 fully retired, not a
permanent second system running alongside it. See PROMOTION below.

Module layout:
  gate.py         — is_opportunity_evidence_worthy(): a Development-
                    worthy-of-becoming-a-thesis check, deliberately
                    separate from development_memory/graph_link.py's
                    is_graph_worthy() (that answers "persist in the
                    graph", not "investable").
  coherence.py    — candidate cluster discovery via real IG adjacency,
                    with an explicit STRONG/WEAK tier (shared sector
                    alone is never sufficient — the literal fix for the
                    Banking+FMCG regression).
  identity.py     — thesis identity (never the AI title) and the merge-
                    vs-create decision against existing OpportunityV2
                    rows. No raw_sector: fallback (removed 2026-08-22 —
                    it silently reproduced the same sector-only-merge bug
                    one layer up; company-less/ungraphed singletons
                    anchor on their own Development id instead).
  scoring.py      — bounded/capped scoring, direction-agreement-gated
                    company/sector confirmation.
  generation.py   — fail-closed AI narrative generation (never a
                    fabricated title/summary; leaves narrative_status=
                    "failed_capacity" instead).
  orchestration.py — run_shadow_pass(): the real end-to-end worker entry
                    point. Narratives regenerate only when
                    narrative_input_hash (computed from the opportunity's
                    FULL cumulative linked-Development set, not just the
                    current pass's transient cluster) actually changes —
                    unchanged evidence costs zero LLM calls on a rerun
                    (confirmed live, 2026-08-22: idempotent across
                    repeated passes with frozen input — 0 duplicate
                    opportunities, 0 duplicate theses, 0 unnecessary
                    generation calls).
  shadow_report.py — V1-vs-V2 comparison report (candidate counts,
                    duplicate/malformed-title rates, split/merge
                    detection) — the evidence PROMOTION below is decided
                    from.

PROMOTION — the concrete path from "V2 in shadow" to "V2 is the only
opportunity pipeline" (owner instruction, 2026-08-22: design toward this
end state explicitly, not an indefinite parallel system):

  1. Validation gate (in progress). Run run_shadow_pass() on a real
     recurring cadence (matching V1's own job_daily_opportunities()
     schedule — see app/tasks/daily_tasks.py) for a defined burn-in
     window. Each run's shadow_report.py output must keep showing: 0
     duplicate-thesis rows, 0 unexplained net-new opportunities on
     unchanged input, no title-quality regressions in a manual top-N
     read, and no AI-capacity fabrication (every failure stays
     narrative_status="failed_capacity", never a fake substitute).
  2. Serving cutover. Add a V2-backed read path — either a new
     opportunities-v2 branch in app/api/radar.py or a straight swap of
     its query source — that reads OpportunityV2/OpportunityV2Development
     instead of app/db/models/opportunity.py's Opportunity/
     OpportunityCompany, gated behind a flag so it can be flipped back
     instantly if a real quality issue surfaces post-cutover.
  3. Promote existing shadow rows: flip public_status "shadow" -> "public"
     on the OpportunityV2 rows meeting the same quality bar (or all of
     them, once step 1's gate is trusted), source stays
     "opportunity_v2_shadow" during a transition window so promoted vs.
     newly-shadow rows stay distinguishable if a rollback is needed.
  4. Frontend cutover. Point apps/web's opportunity-radar pages at the
     new V2-backed endpoint from step 2. No V1 UI change needed if step 2
     preserves the existing response shape.
  5. Stop V1 writes. Remove job_daily_opportunities()'s call into
     app/pipeline/opportunity_generator.py from app/tasks/daily_tasks.py
     (or delete the scheduled job entirely) so V1 stops producing new
     rows. V1's existing historical rows stay queryable read-only until
     step 7.
  6. Burn-in on the new serving path itself (separate from step 1's
     formation-quality burn-in) — confirm the V2-backed API/frontend path
     holds up under real traffic for a defined window before touching any
     V1 code.
  7. Remove V1 code and data, only after steps 1-6 are stable and
     reviewed — this step is destructive and needs its own explicit
     go-ahead, not bundled into a promotion PR:
       - app/pipeline/opportunity_generator.py
       - app/workers/opportunity_worker.py (if not already dead/unused —
         confirm before deleting; job_daily_opportunities() in
         daily_tasks.py may be the only real caller)
       - app/repositories/opportunity_repository.py's V1 query methods
       - app/db/models/opportunity.py (Opportunity, OpportunityCompany)
         and its opportunities/opportunity_companies tables (archive/
         export first — this is real historical production data, not
         disposable shadow data)
       - the source="opportunity_v2_shadow" / public_status distinction
         itself, once there is no more V1 to distinguish from — at that
         point OpportunityV2 stops being "V2" and just becomes the
         Opportunity pipeline; a rename out of the "_v2" suffix is
         cosmetic cleanup, not required for correctness.
"""
