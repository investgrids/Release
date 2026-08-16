"""
Phase 2E — Intelligence Outcome Research.

Read-only research over Market Ripple's own intelligence output (events,
per-company signals, announcements, score history), joined against the
existing PriceBar warehouse (Phase 2B/2D) for outcomes. Nothing here
writes back to any production table, changes production weighting, or
touches the frontend.

Structure:
  safe_sources.py       — the allowlist + why each source is/isn't safe
                           for historical (as-of) reconstruction (audit
                           finding, not a new decision).
  evidence.py            — shared evidence-pulling/normalization/
                           classification, reused by both the continuous
                           observation builder and the pilot.
  observation_builder.py — CompanyIntelligenceObservation: a forward-only,
                           continuously-collected snapshot, starting now,
                           independent of pilot results (owner: "start
                           this regardless of pilot results").
  pilot.py                — Phase 2E.2: the small, explicitly-labeled
                           exploratory pilot over the ~5-7 weeks of real
                           safe-source history that exists today.
"""
