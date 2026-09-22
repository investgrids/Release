// Representative fixtures for event_impact (2026-09-22), mirroring
// exactly what aev2/event_impact.py's assemble_event_impact() produces
// server-side — see that module's own docstring and
// test_event_impact_assembly.py for the real backend behavior these
// mirror. Reliance Jio's 5G rollout, matching the backend test's own
// scenario for easy cross-reference.
import type { SearchResult } from "@/app/ai-search/AISearchClient";
import type { AEV2Response, AEV2EventImpact } from "../aev2Types";
import { baseAev2Response } from "./directCompanyResearch";

export function baseEventImpactSearchResult(overrides: Record<string, unknown> = {}): SearchResult {
  return {
    query: "Reliance Jio just announced its 5G rollout is complete, what does this mean?",
    ui_mode: "event_impact",
    intent: "news_reaction",
    specialist: "company",
    synthesis_incomplete: false,
    answer: {
      summary: "", bottom_line: "", what_happened: "", why_it_happened: "",
      immediate_impact: "", medium_term: "", long_term: "", what_priced_in: "",
      risks: [], opportunities: [], confidence: null, confidence_level: "unscored",
      sentiment: "neutral", sources_count: 1,
    },
    key_drivers: [], insights: [],
    companies: [{
      symbol: "RELIANCE", name: "Reliance Industries Ltd", price: "1,257.50", change: "+0.40%", positive: true,
      impact_type: "direct", impact_score: 60, confidence: 60, reason: "", chart: [],
    }],
    sectors: [],
    related_events: [{
      id: "e-reliance-1", slug: "reliance-jio-completes-pan-india-5g-rollout-e-reliance-1",
      title: "Reliance Jio completes pan-India 5G network rollout", date: "Sep 15, 2026",
      impact_score: 7.5, confidence: 8.0, category: "Corporate",
    }],
    news: [], policies: [], timeline: [],
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

export function baseEventImpact(overrides: Partial<AEV2EventImpact> = {}): AEV2EventImpact {
  return {
    event: {
      id: "e-reliance-1",
      title: "Reliance Jio completes pan-India 5G network rollout",
      summary: "Reliance Jio Infocomm Limited informed the Exchange that it has completed 5G network rollout across all 22 telecom circles in India.",
      published_at: "2026-09-15T09:30:00+00:00",
      source_name: "nse_announcements",
      internal_url: "/events/reliance-jio-completes-pan-india-5g-rollout-e-reliance-1",
      original_source_url: null,
    },
    linked_companies: [{ symbol: "RELIANCE", name: "Reliance Industries Ltd" }],
    linked_sectors: [{ name: "Telecom" }],
    observed_reactions: [],
    direct_conclusion: {
      text: "Jio's completion of its nationwide 5G rollout strengthens Reliance's telecom infrastructure position.",
      evidence_refs: ["event:e-reliance-1"],
      validation_status: "validated",
    },
    ...overrides,
  };
}

function withEventImpact(eventImpact: AEV2EventImpact | null, overrides: Partial<AEV2Response> = {}): AEV2Response {
  return baseAev2Response({
    evidence: [
      { id: "event:e-reliance-1", type: "event", title: "Reliance Jio completes pan-India 5G network rollout", date: "2026-09-15" },
    ],
    event_impact: eventImpact,
    ...overrides,
  });
}

// Complete, eligible event_impact answer.
export const completeEventImpactAnswer = {
  result: baseEventImpactSearchResult(),
  aev2: withEventImpact(baseEventImpact()),
};

// Backend never assembled one at all (source-null / no companies / not
// exactly one event, etc. — see aev2/event_impact.py's own structural
// gate; the frontend cannot distinguish which reason from a bare null).
export const notEventShapedAnswer = {
  result: baseEventImpactSearchResult(),
  aev2: withEventImpact(null),
};

// Two related events resolved — fails honestly, checked independently
// of whatever the backend did or didn't assemble.
export const eventImpactWrongEventCountAnswer = {
  result: baseEventImpactSearchResult({
    related_events: [
      { id: "e-reliance-1", slug: "reliance-jio-completes-pan-india-5g-rollout-e-reliance-1", title: "Reliance Jio completes pan-India 5G network rollout", date: "Sep 15, 2026", impact_score: 7.5, confidence: 8.0, category: "Corporate" },
      { id: "e-reliance-2", slug: "", title: "A second, unrelated Reliance event", date: "Sep 16, 2026", impact_score: 5.0, confidence: 5.0, category: "Corporate" },
    ],
  }),
  aev2: withEventImpact(baseEventImpact()),
};

// AEV2 cited a different event than the one V3 itself resolved.
export const eventImpactEntityMismatchAnswer = {
  result: baseEventImpactSearchResult(),
  aev2: withEventImpact(baseEventImpact({
    event: { ...baseEventImpact().event, id: "e-some-other-event" },
  })),
};

// No linked companies — fails closed (backend guarantees this can't
// really happen; this fixture exercises the frontend's own defense-in-
// depth re-check).
export const eventImpactNoCompanyEvidenceAnswer = {
  result: baseEventImpactSearchResult(),
  aev2: withEventImpact(baseEventImpact({ linked_companies: [] })),
};

// Citation-invalid / advisory-language-violating direct_conclusion —
// fails closed (assemble_event_impact's own text is already its fixed
// fallback string, evidence_refs cleared to [], validation_status
// "unvalidated").
export const eventImpactUnvalidatedAnswer = {
  result: baseEventImpactSearchResult(),
  aev2: withEventImpact(baseEventImpact({
    direct_conclusion: {
      text: "A direct conclusion could not be shown for this query because the generated text did not pass the research-language check.",
      evidence_refs: [],
      validation_status: "unvalidated",
    },
  })),
};

// Degraded response — never reaches the successful layout.
export const eventImpactSynthesisIncompleteAnswer = {
  result: baseEventImpactSearchResult({ synthesis_incomplete: true }),
  aev2: withEventImpact(baseEventImpact()),
};

// Sectors genuinely empty — omitted cleanly, not a rejection.
export const eventImpactNoSectorsAnswer = {
  result: baseEventImpactSearchResult(),
  aev2: withEventImpact(baseEventImpact({ linked_sectors: [] })),
};

// No observed price reactions (the real, current state of every
// response today — see aev2/event_impact.py's own docstring) — still a
// fully eligible, successful answer.
export const eventImpactNoPriceDataAnswer = {
  result: baseEventImpactSearchResult(),
  aev2: withEventImpact(baseEventImpact({ observed_reactions: [] })),
};

// A hypothetical future response WITH a real observed reaction —
// exercises the rendering path even though today's real backend never
// populates this (see aev2/event_impact.py's _build_observed_reactions
// docstring for why). Never phrased as causal.
export const eventImpactWithPriceReactionAnswer = {
  result: baseEventImpactSearchResult(),
  aev2: withEventImpact(baseEventImpact({
    observed_reactions: [{
      company: { symbol: "RELIANCE", name: "Reliance Industries Ltd" },
      window: "next_session",
      start_date: "2026-09-11",
      end_date: "2026-09-15",
      percent_change: 1.0,
      source: "price_bars",
      data_quality: "good",
      evidence_refs: [],
    }],
  })),
};
