// TypeScript mirror of app/services/ai_search/aev2/schema.py's
// build_response() shape (2026-09-21 AI Answer UI work, direct_company_
// research layout). Kept in exact lockstep with that module — every
// field here must have a real counterpart there, and nothing here may
// invent a field the backend doesn't actually produce.
//
// This is intentionally a PLAIN DATA mirror, not a live API contract:
// AEV2_BUILD_COMPLETE is False (aev2/mode.py), so assemble_aev2()'s
// output is never serialized to any HTTP response today. Until the
// dedicated activation commit flips that latch and wires a real route,
// this type exists only so the frontend can be built and tested against
// exact, representative fixtures of what assemble_aev2() already
// produces server-side (see answerTypes.ts's DirectCompanyResearchAnswer
// and the __fixtures__ directory) — never against a live fetch.

export interface AEV2EvidenceCatalogEntry {
  id: string; // "event:123" / "news:45" / "policy:7" / "announcement:9"
  type: "event" | "news" | "policy" | "announcement";
  title: string;
  date: string | null;
}

// The shared validated-claim shape (aev2.2, 2026-09-22) — every citation-
// validated free-text claim (direct_conclusion today, switch_analysis's
// direct_comparison as of this version) carries the SAME validation_status
// field, mirroring schema.py's build_validated_claim exactly. One status
// field for every UI mode's claims, never a separate validity boolean
// per mode (2026-09-22 spec).
export type AEV2ValidationStatus = "validated" | "unvalidated";

export interface AEV2DirectConclusion {
  text: string;
  evidence_refs: string[];
  validation_status: AEV2ValidationStatus;
}

export interface AEV2WhatHappened {
  summary: string;
  evidence_refs: string[];
  items: unknown[]; // always [] in the current assemble_aev2() output
}

export interface AEV2WhyItMatters {
  text: string;
  evidence_refs: string[];
  is_fallback: boolean;
}

export interface AEV2PricedCompany {
  symbol: string;
  name: string;
  price: string;
  change: string;
  fetched_at: string;
}

export interface AEV2UnattributedCompany {
  symbol: string;
  name: string;
}

export interface AEV2CompaniesAffected {
  currently_higher: AEV2PricedCompany[];
  currently_lower: AEV2PricedCompany[];
  omitted_unattributed: AEV2UnattributedCompany[];
}

export interface AEV2TimelinePhase {
  phase: "immediate" | "medium_term" | "long_term";
  text: string;
}

export interface AEV2TimeHorizon {
  primary_horizon: string | null;
  timeline_phases: AEV2TimelinePhase[];
}

export interface AEV2RisksAndInvalidation {
  kind: "analysis";
  risks: string[];
  invalidates_if: string[]; // always [] today — no CoreAnswer source yet
  watch_for: string[]; // always [] today — no CoreAnswer source yet
}

export interface AEV2RelatedEvent {
  id: string;
  title: string;
  date: string | null;
}

export interface AEV2RelatedIntelligence {
  opportunities: unknown[]; // always [] today — no CoreAnswer source yet
  events: AEV2RelatedEvent[];
  ripple: unknown | null; // always null today — no CoreAnswer source yet
}

export interface AEV2Confidence {
  score: number | null;
  level: string;
  // WHICH of the 4 approved components contributed — not their
  // individual percentages (compute_aev2_confidence never returns those;
  // see aev2/confidence.py). Do not invent per-component values this
  // shape doesn't carry.
  components_available: string[];
}

// ── switch_analysis (aev2.2, 2026-09-22) — mirrors aev2/switch_analysis
// .py's build_response() shape exactly. Phase-one implements only 3
// comparison dimension keys (see that module's own docstring for why
// business_exposure/risk_evidence have no real per-company data source
// today) — the key union below is intentionally not wider than that.
export interface AEV2CompanyRef {
  symbol: string;
  name: string;
}

export interface AEV2ComparisonValue {
  display: string;
  evidence_refs: string[];
}

export type AEV2ComparisonDimensionKey =
  | "recent_developments" | "price_reaction" | "evidence_freshness";

export interface AEV2ComparisonDimension {
  key: AEV2ComparisonDimensionKey;
  label: string;
  current_company: AEV2ComparisonValue | null;
  alternative_company: AEV2ComparisonValue | null;
  evidence_refs: string[];
  comparable: boolean;
  unavailable_reason?: string;
}

export interface AEV2SupportedFactor {
  text: string;
  evidence_refs: string[];
}

export interface AEV2MonitoringCondition {
  text: string;
}

export interface AEV2SwitchAnalysis {
  relationship: "switch";
  current_company: AEV2CompanyRef;
  alternative_company: AEV2CompanyRef;
  direct_comparison: AEV2DirectConclusion;
  dimensions: AEV2ComparisonDimension[];
  conditions_favoring_current: AEV2SupportedFactor[];
  conditions_favoring_alternative: AEV2SupportedFactor[];
  what_changes_the_comparison: AEV2MonitoringCondition[];
}

// ── comparison (aev2.3, 2026-09-22) — the neutral, no-holding-
// relationship counterpart to switch_analysis. Mirrors aev2/comparison
// .py's build_response() shape exactly. Deliberately carries NO switch
// vocabulary (no current_company/alternative_company, no conditions_
// favoring_*, no what_changes_the_comparison) — "only compares
// evidence," per the approved spec's semantic-differences table.
export interface AEV2PairComparisonDimension {
  key: AEV2ComparisonDimensionKey;
  label: string;
  left_company: AEV2ComparisonValue | null;
  right_company: AEV2ComparisonValue | null;
  evidence_refs: string[];
  comparable: boolean;
  unavailable_reason?: string;
}

export interface AEV2Comparison {
  relationship: "comparison";
  // The user's own entity order (query mention order) — never
  // alphabetized or otherwise resorted. "Compare Infosys and TCS" must
  // have left_company.symbol === "INFY".
  left_company: AEV2CompanyRef;
  right_company: AEV2CompanyRef;
  direct_comparison: AEV2DirectConclusion;
  dimensions: AEV2PairComparisonDimension[];
}

// ── event_impact (2026-09-22, narrow contract) — mirrors aev2/
// event_impact.py's build_response() shape exactly. Deliberately
// carries NO transmission-chain, beneficiary/loser, monitoring-
// checklist, Ripple-graph, or Intelligence-Graph-propagation concept —
// see that module's own docstring for the 2026-09-22 audit finding
// this narrower contract was built from.
export interface AEV2EventImpactEvent {
  id: string;
  title: string;
  summary: string;
  published_at: string;
  source_name: string;
  internal_url: string;
  // Event carries no original-publisher-URL column at all today — this
  // is None/absent for virtually every event, the honest normal state,
  // not a per-row failure. See EventImpactLayout's fallback notice.
  original_source_url: string | null;
}

// Deliberately just {symbol, name} / {name} — no impact/direction key.
// "Connected company," never "beneficiary"/"loser"/"affected company."
export type AEV2EventImpactCompanyRef = AEV2CompanyRef;
export interface AEV2EventImpactSectorRef {
  name: string;
}

export type AEV2ObservedReactionWindow = "next_session" | "five_sessions";

export interface AEV2ObservedReaction {
  company: AEV2EventImpactCompanyRef;
  window: AEV2ObservedReactionWindow;
  start_date: string;
  end_date: string;
  percent_change: number;
  source: string;
  // Always "good" — a holiday/thin-volume/gap-detected bar can never
  // reach this shape (aev2/event_impact.py's _build_observed_reactions
  // filters at the source; see that module's own docstring for the
  // 2026-09-22 Repair 2 incident this rule closes).
  data_quality: "good";
  evidence_refs: string[];
}

export interface AEV2EventImpact {
  event: AEV2EventImpactEvent;
  linked_companies: AEV2EventImpactCompanyRef[];
  linked_sectors: AEV2EventImpactSectorRef[];
  // Empty today for every real response — CoreAnswer carries no
  // price_bars-derived observation field yet (see aev2/event_impact.py's
  // module docstring). The shape and its "association, not causation"
  // rendering rule are still real and tested against a future source.
  observed_reactions: AEV2ObservedReaction[];
  direct_conclusion: AEV2DirectConclusion;
}

export interface AEV2Response {
  direct_conclusion: AEV2DirectConclusion;
  what_happened: AEV2WhatHappened;
  why_it_matters: AEV2WhyItMatters;
  companies_affected: AEV2CompaniesAffected;
  time_horizon: AEV2TimeHorizon;
  risks_and_invalidation: AEV2RisksAndInvalidation;
  evidence: AEV2EvidenceCatalogEntry[];
  related_intelligence: AEV2RelatedIntelligence;
  follow_up_groups: unknown[];
  confidence: AEV2Confidence;
  // null for every non-switch query — see aev2/switch_analysis.py's
  // assemble_switch_analysis for the "not applicable" vs "rejected"
  // distinction (this is the former; ineligibility is decided by
  // toSwitchAnalysisAEV2Answer on the frontend).
  switch_analysis: AEV2SwitchAnalysis | null;
  // null for any query that didn't resolve exactly 2 companies via the
  // comparison specialist — see aev2/comparison.py's assemble_comparison.
  // Can be non-null on the SAME response switch_analysis is also
  // non-null for (a switch-shaped query still gets a neutral comparison
  // object too) — ui_mode alone decides which layout renders.
  comparison: AEV2Comparison | null;
  // null for any query that didn't resolve exactly one Event, or whose
  // Event failed the structural eligibility gate (no source, no linked
  // companies, missing title/summary/published_at/internal_url) — see
  // aev2/event_impact.py's assemble_event_impact. Never a rejection by
  // ID; the 3 leaked seed fixtures removed 2026-09-22 fail this on
  // shape alone.
  event_impact: AEV2EventImpact | null;
  schema_version: string;
}
