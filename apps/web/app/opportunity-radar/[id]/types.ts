// Shared V1/V2 opportunity types + the version discriminator. Deliberately
// NOT in OpportunityPageClient.tsx: that file is "use client", and
// page.tsx (a Server Component) needs to call isV2Detail() directly during
// generateMetadata/server rendering — importing a runtime function out of a
// "use client" module for direct server-side invocation isn't possible in
// Next.js (confirmed live: "Attempted to call isV2Detail() from the server
// but isV2Detail is on the client"). Plain types would have been fine
// either way; the function is what forced this file to exist.

// ── V1 types ──────────────────────────────────────────────────────────────────
interface MetricSchema { revenue_potential: string; expected_cagr: string; eps_growth: string; investment_cycle: string; market_size: string; }
interface TimelineStep  { order: number; phase: string; date_label: string; title: string; description: string; status: string; }
interface EventSchema   { event_id: string; title: string; event_date: string; tag: string; description: string; importance: number; }
interface CompanySchema { symbol: string; company_name: string; impact_score: number | null; impact_label: string; trend: string; confidence: number | null; reason: string; }
interface NewsSchema    { news_id: string; headline: string; source: string; published_at: string; url: string; }
interface SectorDist   { sector: string; percentage: number; color: string; }
interface GraphNode    { node_id: string; label: string; node_type: string; metadata: Record<string, any>; }
interface GraphEdge    { source: string; target: string; relationship: string; }
interface AISummary    { matters: string; benefits: string; risks: string[]; invalidate: string; why_bullets: string[]; }

export interface OpportunityDetail {
  id: number; slug: string; title: string; summary: string;
  opportunity_score: number | null; confidence: number | null;
  trend: string; risk_level: string; time_horizon: string;
  sectors: string[];
  ai_summary: AISummary | null;
  metrics: MetricSchema | null;
  timeline: TimelineStep[];
  events: EventSchema[];
  companies: CompanySchema[];
  news: NewsSchema[];
  sector_distribution: SectorDist[];
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
  // Opportunity Radar 2.0 — Event -> Ripple -> ... -> Investment Verdict
  // chain (see opportunity_intelligence.py's module docstring).
  primary_event: EventSchema | null;
  investment_verdict: { label: string; tone: string; reasoning: string } | null;
  historical_similarity: { event_title: string; similarity: number; key_lesson: string | null; winners: string[]; losers: string[] } | null;
  catalysts: { label: string; category: string; date: string; days_until: number }[];
}

// ── V2 types ──────────────────────────────────────────────────────────────────
// Mirrors app/services/opportunity_v2/read_service.py's
// OpportunityV2DetailResponse field-for-field. Deliberately NOT a port of
// OpportunityDetail above — V1's confidence/risk_level/trend/time_horizon/
// revenue_potential/expected_cagr/eps_growth/market_size/timeline/
// sector_distribution/graph_nodes+graph_edges/per-company impact_score are
// either fabricated formulas or concepts V2 was deliberately built without
// (see the read_service.py module docstring). No compatibility mapper
// turns a V2 response into fake V1-shaped fields — this is a separate,
// honest contract, rendered by its own component in OpportunityPageClient.tsx.
export type ThesisDirection = "positive" | "negative" | "neutral" | "mixed";

export interface CompanyConnectedV2 {
  symbol: string; company_name: string;
  real_score: number | null; real_direction: ThesisDirection | null;
  confirms_thesis: boolean; contradicts_thesis: boolean;
}
export interface SupportingEvidenceV2 {
  development_id: string; canonical_title: string; evidence_count: number;
  current_confidence: number | null; current_impact_tier: string | null;
  first_observed_at: string | null; source_types: string[];
}
export interface RippleNodeV2 { id: string; node_type: string; label: string; ticker: string | null; }
export interface RippleEdgeV2 { id: string; source: string; target: string; edge_type: string; weight: number | null; }
export interface RippleV2 { anchor: string | null; nodes: RippleNodeV2[]; edges: RippleEdgeV2[]; }
export interface WhatChangedV2 {
  formation_title: string | null; formation_score: number | null;
  current_title: string | null; current_score: number | null;
}

export interface OpportunityV2Detail {
  id: string; slug: string; title: string;
  thesis_anchor: string; direction: ThesisDirection;
  current_strength: number | null; evidence_count: number;
  candidate_status: string; narrative_status: "pending" | "generated" | "failed_capacity" | string;
  public_status: string;
  why_this_exists: string | null; what_changed: WhatChangedV2 | null;
  companies_connected: CompanyConnectedV2[]; sectors_themes: string[]; ripple: RippleV2;
  supporting_evidence: SupportingEvidenceV2[]; contradictions_risks: string[];
  created_at: string; updated_at: string;
}

export type AnyOpportunityDetail = OpportunityDetail | OpportunityV2Detail;

// thesis_anchor only exists on the V2 shape — V1's OpportunityDetailResponse
// has no field by this name at all, so this is a safe, permanent
// discriminator rather than a heuristic that could drift.
export function isV2Detail(d: AnyOpportunityDetail): d is OpportunityV2Detail {
  return "thesis_anchor" in d;
}
