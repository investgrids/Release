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

// ── market_pulse (2026-09-22, canonical-core audit) — mirrors aev2/
// market_pulse.py's assemble_market_pulse() shape exactly. This is a
// FULLY SEPARATE top-level shape from AEV2Response below, never nested
// inside it — assemble_aev2() (the shared dispatcher) returns EITHER
// this OR the standard envelope, dispatched on which CanonicalAnswerCore
// variant (CoreAnswer | CoreMarketPulse) it was given. See aev2/
// assemble.py's own CanonicalAnswerCore docstring for why Market Pulse
// is not "a second AI-answer pipeline" despite this structural
// difference: both variants pass through the identical response
// finalizer / safety gate / telemetry boundary / cache discipline /
// AEV2 dispatch / public-serialization gate — only the PRESENTED SHAPE
// differs, because a market snapshot and a company research answer are
// genuinely different kinds of content.
//
// No standard research confidence formula (evidence_quality/market_
// confirmation/historical_similarity/data_freshness) — Market Pulse has
// no comparable historical_similarity or company-attribution contract;
// AEV2MarketPulseEvidenceCoverage below is what it shows instead.

// Every market value carries its own provenance envelope rather than a
// bare display string — never a fresh per-item fetch timestamp (the
// whole payload is fetched in one batch), `as_of`/`session` are the
// SAME single generation timestamp/session the top-level response
// carries; `source` names which real feed produced that CATEGORY of
// value (a fixed label, e.g. "yfinance_sector_etf" — never SectorData,
// never invented per item).
export interface AEV2MarketValue {
  value: string;
  as_of: string | null;
  source: string;
  session: string | null;
}

export interface AEV2MarketIndex {
  name: string;
  ticker: string;
  price: AEV2MarketValue | null;
  change: AEV2MarketValue | null;
  chart: { label: string; value: number }[];
}

export interface AEV2SectorMove {
  id: string;
  name: string;
  change: AEV2MarketValue | null;
  momentum_score: number | null;
}

export interface AEV2VerifiedDriver {
  driver: string;
  driver_type: string;
  confidence_tier: string;
  driver_strength: number | null;
  // "event:{id}" — real EventTriage.event_id rows, never invented. []
  // is the honest "no real driver found" state, not a placeholder.
  evidence_refs: string[];
}

export interface AEV2MarketMover {
  company: string;
  ticker: string;
  price: AEV2MarketValue | null;
  change: AEV2MarketValue | null;
  verified_drivers: AEV2VerifiedDriver[];
  // null when generated text didn't pass validation (advisory-language
  // scan, numbers_supported, entities_supported against the real
  // structured payload) — omitted, never a fabricated placeholder.
  narrative: string | null;
}

export interface AEV2ThemeMomentum {
  theme: string;
  score: number | null;
  momentum: string | null;
  price_signal: number | null;
  news_signal: number | null;
}

export interface AEV2OpportunityRef {
  title: string;
  href: string;
  // Explicitly an Opportunity score, never a forecast probability —
  // see aev2/market_pulse.py's own _opportunity_ref docstring. Already
  // exclusively sourced from public, non-shadow rows upstream.
  opportunity_score: number | null;
}

// Discriminated union (2026-09-22 spec) — the two branches are NEVER
// rendered with the same trust label. "ai_synthesis" is declared here
// for completeness of the type (matching the approved spec's own
// shape) but aev2/market_pulse.py's _risk_context never actually
// produces it in this slice: that branch has no real Event or
// structured fact behind it, so it can never carry a valid
// evidence_refs entry, and the rule is to omit rather than substitute
// uncited narrative — see that function's own docstring. Frontend
// rendering rule: "tracked_event" -> "Verified market risk"; the
// (currently unreachable) "ai_synthesis" branch -> "AI-identified
// consideration". Neither branch carries the raw self-rated confidence
// number backing it — dropped entirely upstream.
export type AEV2RiskContext =
  | {
      source: "tracked_event";
      event_id: string;
      title: string;
      published_at: string | null;
      evidence_refs: string[];
    }
  | {
      source: "ai_synthesis";
      text: string;
      validation_status: "validated";
      evidence_refs: string[];
    };

export interface AEV2CalendarEvent {
  id: string;
  title: string;
  date: string | null;
  category: string | null;
  description: string | null;
}

export interface AEV2MarketPulseEvidenceCoverage {
  movers_with_driver: number;
  movers_total: number;
  tracked_event_count: number;
  calendar_event_count: number;
}

export interface AEV2MarketPulse {
  kind: "market_pulse";
  as_of: string | null;
  market_session: string | null;
  market_status: string | null;

  indices: AEV2MarketIndex[];
  sector_movement: {
    leading: AEV2SectorMove[];
    lagging: AEV2SectorMove[];
  };
  movers: {
    gainers: AEV2MarketMover[];
    losers: AEV2MarketMover[];
    most_active: AEV2MarketMover[];
  };

  theme_momentum: AEV2ThemeMomentum[];
  biggest_opportunity: AEV2OpportunityRef | null;
  risk_context: AEV2RiskContext | null;
  upcoming_events: AEV2CalendarEvent[];

  // Both null when generated text failed validation — the structured
  // fields above remain fully populated regardless (see
  // synthesis_status). Reuses the same shared validated-claim shape
  // (AEV2DirectConclusion) every other AEV2 mode's claims use — no
  // per-mode validity boolean.
  generated_summary: AEV2DirectConclusion | null;
  generated_conclusion: AEV2DirectConclusion | null;

  synthesis_status: "complete" | "unavailable";
  evidence_coverage: AEV2MarketPulseEvidenceCoverage;
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
