// Representative fixtures for direct_company_research (2026-09-22).
// Each AEV2Response fixture is hand-authored to mirror EXACTLY what
// aev2/assemble.py would produce for the described real scenario —
// never a shape assemble_aev2() couldn't actually emit. validation_status
// (aev2.2) is the real backend-emitted claim status (schema.py's
// build_validated_claim) — no separate frontend trust flag.
import type { SearchResult } from "@/app/ai-search/AISearchClient";
import type { AEV2Response } from "../aev2Types";

export function baseSearchResult(overrides: Record<string, unknown> = {}): SearchResult {
  return {
    query: "Should I research HDFC Bank now?",
    ui_mode: "direct_company_research",
    intent: "general",
    specialist: "company",
    synthesis_incomplete: false,
    answer: {
      summary: "", bottom_line: "", what_happened: "", why_it_happened: "",
      immediate_impact: "", medium_term: "", long_term: "", what_priced_in: "",
      risks: [], opportunities: [], confidence: null, confidence_level: "unscored",
      sentiment: "neutral", sources_count: 0,
    },
    key_drivers: [], insights: [],
    companies: [{
      symbol: "HDFCBANK", name: "HDFC Bank", price: "1,712.40", change: "+0.85%", positive: true,
      impact_type: "direct", impact_score: 70, confidence: 65, reason: "", chart: [],
    }],
    sectors: [], related_events: [], news: [], policies: [], timeline: [],
    historical_comparison: [], ripple_chain: [], scenarios: {}, market_impact_horizons: [],
    what_to_monitor: [], ai_reasoning_methods: [], follow_up_questions: [], follow_up_groups: [],
    investment_verdict: {
      rating: "Not Applicable", direction: "neutral", confidence: null, horizon: null,
      top_picks: [], risks: [], catalysts: [], opportunity_score: null,
      risk_level: "", suitable_for: "", engine_verdict: null,
    },
    market_chart: { labels: [], series: [] },
    graph: { nodes: [], edges: [] },
    citations: [], decision_intelligence: null,
    ...overrides,
  } as unknown as SearchResult;
}

export function baseAev2Response(overrides: Partial<AEV2Response> = {}): AEV2Response {
  return {
    direct_conclusion: {
      text: "HDFC Bank's asset quality metrics have remained stable through its latest disclosed quarter.",
      evidence_refs: ["announcement:501"],
      validation_status: "validated",
    },
    what_happened: {
      summary: "HDFC Bank disclosed its quarterly results to the exchange on 12 Mar 2025.",
      evidence_refs: ["announcement:501"],
      items: [],
    },
    why_it_matters: {
      text: "Stable asset quality typically reduces near-term provisioning pressure on earnings.",
      evidence_refs: ["announcement:501"],
      is_fallback: false,
    },
    companies_affected: {
      currently_higher: [{
        symbol: "HDFCBANK", name: "HDFC Bank", price: "1,712.40", change: "+0.85%",
        fetched_at: "2025-03-12T10:24:00+00:00",
      }],
      currently_lower: [],
      omitted_unattributed: [],
    },
    time_horizon: {
      primary_horizon: "6-12 months",
      timeline_phases: [
        { phase: "immediate", text: "Market reaction to the disclosed results plays out over the next few sessions." },
      ],
    },
    risks_and_invalidation: {
      kind: "analysis",
      risks: ["A sharper-than-expected slowdown in deposit growth could pressure margins."],
      invalidates_if: [],
      watch_for: [],
    },
    evidence: [
      { id: "announcement:501", type: "announcement", title: "HDFC Bank Q3 FY25 results disclosure", date: "2025-03-12" },
    ],
    related_intelligence: { opportunities: [], events: [], ripple: null },
    follow_up_groups: [],
    confidence: { score: 61.4, level: "High", components_available: ["evidence_quality", "data_freshness"] },
    switch_analysis: null,
    comparison: null,
    event_impact: null,
    schema_version: "aev2.4",
    ...overrides,
  };
}

// 1. Complete company answer with citations and price provenance.
export const completeAnswer = {
  result: baseSearchResult(),
  aev2: baseAev2Response(),
};

// 2. Partial answer with no price data — price section omitted honestly.
export const noPriceDataAnswer = {
  result: baseSearchResult(),
  aev2: baseAev2Response({
    companies_affected: {
      currently_higher: [],
      currently_lower: [],
      omitted_unattributed: [{ symbol: "HDFCBANK", name: "HDFC Bank" }],
    },
  }),
};

// 3. No attributable company evidence — fails closed.
export const noCompanyEvidenceAnswer = {
  result: baseSearchResult(),
  aev2: baseAev2Response({
    direct_conclusion: { text: "HDFC Bank's recent disclosures show stable metrics.", evidence_refs: [], validation_status: "validated" },
    evidence: [],
  }),
};

// 4. Citation-invalid conclusion — fails closed (assemble.py's
// citation_validator rejected the claim; the returned text is already
// its fixed fallback string, evidence_refs cleared to [], validation_
// status "unvalidated").
export const citationInvalidAnswer = {
  result: baseSearchResult(),
  aev2: baseAev2Response({
    direct_conclusion: {
      text: "A direct conclusion could not be shown for this query because the generated text did not pass the research-language check.",
      evidence_refs: [],
      validation_status: "unvalidated",
    },
  }),
};

// 5. Advisory language present — fails closed (language_gate substituted
// its own fixed text; assemble.py's had_violation collapses BOTH a
// language-gate violation and a failed citation validation into the same
// validation_status: "unvalidated" outcome — genuinely indistinguishable
// from #4 in today's real backend contract, not a frontend gap).
export const advisoryLanguageAnswer = {
  result: baseSearchResult(),
  aev2: baseAev2Response({
    direct_conclusion: {
      text: "A direct conclusion could not be shown for this query because the generated text did not pass the research-language check.",
      evidence_refs: [],
      validation_status: "unvalidated",
    },
  }),
};

// 6. Two-company query incorrectly labeled direct-company — rejected.
export const twoCompanyAnswer = {
  result: baseSearchResult({
    companies: [
      { symbol: "HDFCBANK", name: "HDFC Bank", price: "1,712.40", change: "+0.85%", positive: true, impact_type: "direct", impact_score: 70, confidence: 65, reason: "", chart: [] },
      { symbol: "ICICIBANK", name: "ICICI Bank", price: "1,205.10", change: "-0.40%", positive: false, impact_type: "direct", impact_score: 55, confidence: 60, reason: "", chart: [] },
    ],
  }),
  aev2: baseAev2Response(),
};

// 9. Degraded response — never reaches the successful layout.
export const synthesisIncompleteAnswer = {
  result: baseSearchResult({ synthesis_incomplete: true }),
  aev2: baseAev2Response(),
};

// 10. Empty optional sections — no blank cards or placeholders.
export const minimalAnswer = {
  result: baseSearchResult(),
  aev2: baseAev2Response({
    what_happened: { summary: "", evidence_refs: [], items: [] },
    why_it_matters: { text: "", evidence_refs: [], is_fallback: true },
    time_horizon: { primary_horizon: null, timeline_phases: [] },
    risks_and_invalidation: { kind: "analysis", risks: [], invalidates_if: [], watch_for: [] },
  }),
};

// Entity-mismatch: AEV2 attributed a different company than the one V3
// itself resolved for this query.
export const entityMismatchAnswer = {
  result: baseSearchResult(),
  aev2: baseAev2Response({
    companies_affected: {
      currently_higher: [{ symbol: "ICICIBANK", name: "ICICI Bank", price: "1,205.10", change: "-0.40%", fetched_at: "2025-03-12T10:24:00+00:00" }],
      currently_lower: [],
      omitted_unattributed: [],
    },
  }),
};

// No company resolved at all.
export const noEntityAnswer = {
  result: baseSearchResult({ companies: [] }),
  aev2: baseAev2Response({
    companies_affected: { currently_higher: [], currently_lower: [], omitted_unattributed: [] },
  }),
};
