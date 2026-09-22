// Representative fixtures for comparison (2026-09-22), mirroring
// exactly what aev2/comparison.py's assemble_comparison() produces
// server-side — see that module's own docstring and
// test_comparison_assembly.py for the real backend behavior these
// mirror. Infosys/TCS, matching "Compare Infosys and TCS" — entity
// order preserved (Infosys first), never alphabetized.
import type { SearchResult } from "@/app/ai-search/AISearchClient";
import type { AEV2Response, AEV2Comparison } from "../aev2Types";
import { baseAev2Response } from "./directCompanyResearch";

export function baseComparisonSearchResult(overrides: Record<string, unknown> = {}): SearchResult {
  return {
    query: "Compare Infosys and TCS",
    ui_mode: "company_comparison",
    intent: "compare",
    specialist: "comparison",
    synthesis_incomplete: false,
    answer: {
      summary: "", bottom_line: "", what_happened: "", why_it_happened: "",
      immediate_impact: "", medium_term: "", long_term: "", what_priced_in: "",
      risks: [], opportunities: [], confidence: null, confidence_level: "unscored",
      sentiment: "neutral", sources_count: 0,
    },
    key_drivers: [], insights: [],
    companies: [
      { symbol: "INFY", name: "Infosys Ltd", price: "1,845.20", change: "+0.60%", positive: true, impact_type: "direct", impact_score: 55, confidence: 55, reason: "", chart: [] },
      { symbol: "TCS", name: "Tata Consultancy Services Ltd", price: "4,102.50", change: "-0.20%", positive: false, impact_type: "direct", impact_score: 55, confidence: 55, reason: "", chart: [] },
    ],
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

export function baseComparison(overrides: Partial<AEV2Comparison> = {}): AEV2Comparison {
  return {
    relationship: "comparison",
    left_company: { symbol: "INFY", name: "Infosys Ltd" },
    right_company: { symbol: "TCS", name: "Tata Consultancy Services Ltd" },
    direct_comparison: {
      text: "Infosys's digital transformation win and TCS's new AI research center both reflect continued IT-sector demand.",
      evidence_refs: ["event:e-infy-1", "event:e-tcs-1"],
      validation_status: "validated",
    },
    dimensions: [
      {
        key: "recent_developments", label: "Recent developments",
        left_company: { display: "1 company-attributed development(s); most recent: Infosys wins 500 crore digital transformation deal", evidence_refs: ["event:e-infy-1"] },
        right_company: { display: "1 company-attributed development(s); most recent: TCS announces new AI research center", evidence_refs: ["event:e-tcs-1"] },
        evidence_refs: ["event:e-infy-1", "event:e-tcs-1"],
        comparable: true,
      },
      {
        key: "price_reaction", label: "Price reaction",
        left_company: { display: "1,845.20 (+0.60%)", evidence_refs: [] },
        right_company: { display: "4,102.50 (-0.20%)", evidence_refs: [] },
        evidence_refs: [],
        comparable: true,
      },
      {
        key: "evidence_freshness", label: "Evidence freshness",
        left_company: { display: "2026-09-17", evidence_refs: [] },
        right_company: { display: "2026-09-12", evidence_refs: [] },
        evidence_refs: [],
        comparable: true,
      },
    ],
    ...overrides,
  };
}

function withComparison(comparison: AEV2Comparison | null, overrides: Partial<AEV2Response> = {}): AEV2Response {
  return baseAev2Response({
    evidence: [
      { id: "event:e-infy-1", type: "event", title: "Infosys wins 500 crore digital transformation deal", date: "2026-09-17" },
      { id: "event:e-tcs-1", type: "event", title: "TCS announces new AI research center", date: "2026-09-12" },
    ],
    comparison,
    ...overrides,
  });
}

// 9. Two-company comparison succeeds.
export const completeComparisonAnswer = {
  result: baseComparisonSearchResult(),
  aev2: withComparison(baseComparison()),
};

// Not comparison-shaped at all — backend never assembled a comparison
// object (didn't resolve exactly 2 companies, or wasn't a comparison-
// specialist call).
export const notComparisonShapedAnswer = {
  result: baseComparisonSearchResult(),
  aev2: withComparison(null),
};

// Wrong entity count.
export const comparisonWrongEntityCountAnswer = {
  result: baseComparisonSearchResult({
    companies: [
      { symbol: "INFY", name: "Infosys Ltd", price: "1,845.20", change: "+0.60%", positive: true, impact_type: "direct", impact_score: 55, confidence: 55, reason: "", chart: [] },
      { symbol: "TCS", name: "Tata Consultancy Services Ltd", price: "4,102.50", change: "-0.20%", positive: false, impact_type: "direct", impact_score: 55, confidence: 55, reason: "", chart: [] },
      { symbol: "WIPRO", name: "Wipro Ltd", price: "265.00", change: "+0.10%", positive: true, impact_type: "direct", impact_score: 40, confidence: 40, reason: "", chart: [] },
    ],
  }),
  aev2: withComparison(baseComparison()),
};

// Entity mismatch.
export const comparisonEntityMismatchAnswer = {
  result: baseComparisonSearchResult(),
  aev2: withComparison(baseComparison({
    left_company: { symbol: "ICICIBANK", name: "ICICI Bank" },
  })),
};

// No attributable evidence for both companies.
export const comparisonNoCompanyEvidenceAnswer = {
  result: baseComparisonSearchResult(),
  aev2: withComparison(baseComparison({
    dimensions: [
      {
        key: "recent_developments", label: "Recent developments",
        left_company: { display: "1 company-attributed development(s); most recent: Infosys wins 500 crore digital transformation deal", evidence_refs: ["event:e-infy-1"] },
        right_company: null,
        evidence_refs: ["event:e-infy-1"], comparable: false,
        unavailable_reason: "No company-attributed development found for TCS",
      },
      {
        key: "price_reaction", label: "Price reaction",
        left_company: { display: "1,845.20 (+0.60%)", evidence_refs: [] },
        right_company: { display: "4,102.50 (-0.20%)", evidence_refs: [] },
        evidence_refs: [], comparable: true,
      },
      {
        key: "evidence_freshness", label: "Evidence freshness",
        left_company: { display: "2026-09-17", evidence_refs: [] },
        right_company: null,
        evidence_refs: [], comparable: false,
        unavailable_reason: "No dated evidence found for TCS",
      },
    ],
  })),
};

// Citation-invalid direct_comparison — fails closed.
export const comparisonUnvalidatedAnswer = {
  result: baseComparisonSearchResult(),
  aev2: withComparison(baseComparison({
    direct_comparison: {
      text: "A direct comparison could not be shown for this query because the generated text did not pass the research-language check.",
      evidence_refs: [],
      validation_status: "unvalidated",
    },
  })),
};

// Degraded response — never reaches the successful layout.
export const comparisonSynthesisIncompleteAnswer = {
  result: baseComparisonSearchResult({ synthesis_incomplete: true }),
  aev2: withComparison(baseComparison()),
};

// Entity order preserved: "Compare TCS and Infosys" (TCS mentioned
// first) must keep TCS as left_company, never alphabetized to Infosys.
export const reversedOrderComparisonAnswer = {
  result: baseComparisonSearchResult({ query: "Compare TCS and Infosys" }),
  aev2: withComparison(baseComparison({
    left_company: { symbol: "TCS", name: "Tata Consultancy Services Ltd" },
    right_company: { symbol: "INFY", name: "Infosys Ltd" },
  })),
};
