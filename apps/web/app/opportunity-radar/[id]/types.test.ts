/**
 * isV2Detail() — the version discriminator OpportunityPageClient.tsx's
 * dispatcher and page.tsx's server-side metadata generation both depend
 * on to route a real API response to the correct renderer. A false
 * negative here would silently render V2's real fields through the V1
 * legacy component (which doesn't know those field names) or vice versa.
 */
import { describe, it, expect } from "vitest";
import { isV2Detail, type OpportunityDetail, type OpportunityV2Detail } from "./types";

function v1Detail(): OpportunityDetail {
  return {
    id: 42, slug: "some-v1-opportunity", title: "A V1 Opportunity", summary: "Real V1 summary.",
    opportunity_score: 80, confidence: 0.7, trend: "positive", risk_level: "Medium", time_horizon: "6-12 months",
    sectors: ["Banking"], ai_summary: null, metrics: null, timeline: [], events: [], companies: [], news: [],
    sector_distribution: [], graph_nodes: [], graph_edges: [], primary_event: null, investment_verdict: null,
    historical_similarity: null, catalysts: [],
  };
}

function v2Detail(): OpportunityV2Detail {
  return {
    id: "uuid-1234", slug: "some-v2-opportunity", title: "A V2 Opportunity",
    thesis_anchor: "company:testco", direction: "positive", current_strength: 55, evidence_count: 2,
    candidate_status: "formed", narrative_status: "generated", public_status: "public",
    why_this_exists: "Real reason.", what_changed: null,
    companies_connected: [], sectors_themes: ["Banking"],
    ripple: { anchor: "company:testco", nodes: [], edges: [] },
    supporting_evidence: [], contradictions_risks: [],
    created_at: "2026-08-24T00:00:00Z", updated_at: "2026-08-24T00:00:00Z",
  };
}

describe("isV2Detail", () => {
  it("returns false for a real V1 response shape", () => {
    expect(isV2Detail(v1Detail())).toBe(false);
  });

  it("returns true for a real V2 response shape", () => {
    expect(isV2Detail(v2Detail())).toBe(true);
  });

  it("a numeric V1 id and a string V2 id both route correctly regardless of id type", () => {
    // V1's id is a number, V2's is a uuid string — the discriminator must
    // key off thesis_anchor, never off id's type, or radar.py's dual
    // numeric/slug lookup and this frontend guard could disagree.
    const v1 = v1Detail();
    const v2 = v2Detail();
    expect(typeof v1.id).toBe("number");
    expect(typeof v2.id).toBe("string");
    expect(isV2Detail(v1)).toBe(false);
    expect(isV2Detail(v2)).toBe(true);
  });
});
