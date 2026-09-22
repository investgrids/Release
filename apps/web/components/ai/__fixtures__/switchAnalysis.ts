// Representative fixtures for switch_analysis (2026-09-22), mirroring
// exactly what aev2/switch_analysis.py's assemble_switch_analysis()
// produces server-side — see that module's own docstring and
// test_switch_analysis_assembly.py for the real backend behavior these
// mirror. BEL/HAL, matching the approved reference mockup's query
// ("Should I continue holding BEL or switch to HAL?").
import type { SearchResult } from "@/app/ai-search/AISearchClient";
import type { AEV2Response, AEV2SwitchAnalysis } from "../aev2Types";
import { baseAev2Response } from "./directCompanyResearch";

export function baseSwitchSearchResult(overrides: Record<string, unknown> = {}): SearchResult {
  return {
    query: "Should I continue holding BEL or switch to HAL?",
    ui_mode: "switch_analysis",
    intent: "switch",
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
      { symbol: "BEL", name: "Bharat Electronics Ltd", price: "285.40", change: "+1.10%", positive: true, impact_type: "direct", impact_score: 60, confidence: 55, reason: "", chart: [] },
      { symbol: "HAL", name: "Hindustan Aeronautics Ltd", price: "4,512.00", change: "-0.30%", positive: false, impact_type: "direct", impact_score: 58, confidence: 55, reason: "", chart: [] },
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

export function baseSwitchAnalysis(overrides: Partial<AEV2SwitchAnalysis> = {}): AEV2SwitchAnalysis {
  return {
    relationship: "switch",
    current_company: { symbol: "BEL", name: "Bharat Electronics Ltd" },
    alternative_company: { symbol: "HAL", name: "Hindustan Aeronautics Ltd" },
    direct_comparison: {
      text: "BEL's recent order win and HAL's delivery milestone both reflect strong defence-sector demand.",
      evidence_refs: ["event:e-bel-1", "event:e-hal-1"],
      validation_status: "validated",
    },
    dimensions: [
      {
        key: "recent_developments", label: "Recent developments",
        current_company: { display: "1 company-attributed development(s); most recent: BEL wins defence order worth 1,200 crore", evidence_refs: ["event:e-bel-1"] },
        alternative_company: { display: "1 company-attributed development(s); most recent: HAL delivers first batch of Tejas Mk1A jets", evidence_refs: ["event:e-hal-1"] },
        evidence_refs: ["event:e-bel-1", "event:e-hal-1"],
        comparable: true,
      },
      {
        key: "price_reaction", label: "Price reaction",
        current_company: { display: "285.40 (+1.10%)", evidence_refs: [] },
        alternative_company: { display: "4,512.00 (-0.30%)", evidence_refs: [] },
        evidence_refs: [],
        comparable: true,
      },
      {
        key: "evidence_freshness", label: "Evidence freshness",
        current_company: { display: "2026-09-18", evidence_refs: [] },
        alternative_company: { display: "2026-09-10", evidence_refs: [] },
        evidence_refs: [],
        comparable: true,
      },
    ],
    conditions_favoring_current: [
      { text: "More recent evidence available", evidence_refs: [] },
    ],
    conditions_favoring_alternative: [],
    what_changes_the_comparison: [],
    ...overrides,
  };
}

function withSwitch(switchAnalysis: AEV2SwitchAnalysis | null, overrides: Partial<AEV2Response> = {}): AEV2Response {
  return baseAev2Response({
    evidence: [
      { id: "event:e-bel-1", type: "event", title: "BEL wins defence order worth 1,200 crore", date: "2026-09-18" },
      { id: "event:e-hal-1", type: "event", title: "HAL delivers first batch of Tejas Mk1A jets", date: "2026-09-10" },
    ],
    switch_analysis: switchAnalysis,
    ...overrides,
  });
}

// 1. Complete switch comparison — validated, cited, all 3 dimensions comparable.
export const completeSwitchAnswer = {
  result: baseSwitchSearchResult(),
  aev2: withSwitch(baseSwitchAnalysis()),
};

// Not switch-shaped at all — backend never assembled a switch_analysis
// (e.g. not a comparison-specialist query, or holding/target didn't resolve).
export const notSwitchShapedAnswer = {
  result: baseSwitchSearchResult(),
  aev2: withSwitch(null),
};

// Wrong entity count — the query resolved 3 companies, not the 2 a
// switch comparison needs.
export const wrongEntityCountAnswer = {
  result: baseSwitchSearchResult({
    companies: [
      { symbol: "BEL", name: "Bharat Electronics Ltd", price: "285.40", change: "+1.10%", positive: true, impact_type: "direct", impact_score: 60, confidence: 55, reason: "", chart: [] },
      { symbol: "HAL", name: "Hindustan Aeronautics Ltd", price: "4,512.00", change: "-0.30%", positive: false, impact_type: "direct", impact_score: 58, confidence: 55, reason: "", chart: [] },
      { symbol: "BDL", name: "Bharat Dynamics Ltd", price: "1,200.00", change: "+0.5%", positive: true, impact_type: "direct", impact_score: 40, confidence: 40, reason: "", chart: [] },
    ],
  }),
  aev2: withSwitch(baseSwitchAnalysis()),
};

// Entity mismatch — AEV2 attributed roles to companies V3 itself didn't
// resolve for this query.
export const switchEntityMismatchAnswer = {
  result: baseSwitchSearchResult(),
  aev2: withSwitch(baseSwitchAnalysis({
    current_company: { symbol: "ICICIBANK", name: "ICICI Bank" },
  })),
};

// No attributable evidence for both companies — recent_developments not comparable.
export const switchNoCompanyEvidenceAnswer = {
  result: baseSwitchSearchResult(),
  aev2: withSwitch(baseSwitchAnalysis({
    dimensions: [
      {
        key: "recent_developments", label: "Recent developments",
        current_company: { display: "1 company-attributed development(s); most recent: BEL wins defence order worth 1,200 crore", evidence_refs: ["event:e-bel-1"] },
        alternative_company: null,
        evidence_refs: ["event:e-bel-1"],
        comparable: false,
        unavailable_reason: "No company-attributed development found for HAL",
      },
      {
        key: "price_reaction", label: "Price reaction",
        current_company: { display: "285.40 (+1.10%)", evidence_refs: [] },
        alternative_company: { display: "4,512.00 (-0.30%)", evidence_refs: [] },
        evidence_refs: [], comparable: true,
      },
      {
        key: "evidence_freshness", label: "Evidence freshness",
        current_company: { display: "2026-09-18", evidence_refs: [] },
        alternative_company: null,
        evidence_refs: [], comparable: false,
        unavailable_reason: "No dated evidence found for HAL",
      },
    ],
  })),
};

// Citation-invalid direct_comparison — fails closed.
export const switchUnvalidatedAnswer = {
  result: baseSwitchSearchResult(),
  aev2: withSwitch(baseSwitchAnalysis({
    direct_comparison: {
      text: "A direct comparison could not be shown for this query because the generated text did not pass the research-language check.",
      evidence_refs: [],
      validation_status: "unvalidated",
    },
  })),
};

// No genuinely comparable dimension at all.
export const switchNoComparableDimensionAnswer = {
  result: baseSwitchSearchResult(),
  aev2: withSwitch(baseSwitchAnalysis({
    dimensions: [
      {
        key: "recent_developments", label: "Recent developments",
        current_company: null, alternative_company: null,
        evidence_refs: [], comparable: false,
        unavailable_reason: "No company-attributed development found for BEL or HAL",
      },
      {
        key: "price_reaction", label: "Price reaction",
        current_company: null, alternative_company: null,
        evidence_refs: [], comparable: false,
        unavailable_reason: "Live price data unavailable",
      },
      {
        key: "evidence_freshness", label: "Evidence freshness",
        current_company: null, alternative_company: null,
        evidence_refs: [], comparable: false,
        unavailable_reason: "No dated evidence found",
      },
    ],
  })),
};

// Degraded response — never reaches the successful layout.
export const switchSynthesisIncompleteAnswer = {
  result: baseSwitchSearchResult({ synthesis_incomplete: true }),
  aev2: withSwitch(baseSwitchAnalysis()),
};

// Only price_reaction and evidence_freshness comparable — recent_developments
// unavailable for one side. Still ineligible per the eligibility contract
// (both companies must have attributable EVENT evidence specifically),
// even though "a comparable dimension exists" in the general sense.
export const switchPriceOnlyComparableAnswer = {
  result: baseSwitchSearchResult(),
  aev2: withSwitch(baseSwitchAnalysis({
    dimensions: [
      {
        key: "recent_developments", label: "Recent developments",
        current_company: { display: "1 company-attributed development(s); most recent: BEL wins defence order worth 1,200 crore", evidence_refs: ["event:e-bel-1"] },
        alternative_company: null,
        evidence_refs: ["event:e-bel-1"], comparable: false,
        unavailable_reason: "No company-attributed development found for HAL",
      },
      {
        key: "price_reaction", label: "Price reaction",
        current_company: { display: "285.40 (+1.10%)", evidence_refs: [] },
        alternative_company: { display: "4,512.00 (-0.30%)", evidence_refs: [] },
        evidence_refs: [], comparable: true,
      },
      {
        key: "evidence_freshness", label: "Evidence freshness",
        current_company: { display: "2026-09-18", evidence_refs: [] },
        alternative_company: null,
        evidence_refs: [], comparable: false,
        unavailable_reason: "No dated evidence found for HAL",
      },
    ],
  })),
};

// Empty optional sections — no blank cards or placeholders.
export const switchMinimalAnswer = {
  result: baseSwitchSearchResult(),
  aev2: withSwitch(baseSwitchAnalysis({
    conditions_favoring_current: [],
    conditions_favoring_alternative: [],
    what_changes_the_comparison: [],
  })),
};
