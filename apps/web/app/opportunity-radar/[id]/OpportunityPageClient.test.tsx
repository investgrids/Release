import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { LegacyOpportunityDetail, type OpportunityDetail } from "./OpportunityPageClient";

// These render real network-fetching widgets unrelated to this regression —
// stubbed to keep the test hermetic and focused on the score-history claim.
vi.mock("@/components/TrackPageVisit", () => ({ TrackPageVisit: () => null }));
vi.mock("@/components/RelatedContent", () => ({ RelatedContent: () => null }));
vi.mock("@/components/NextSteps", () => ({ NextSteps: () => null }));
vi.mock("@/components/OpportunityRippleGraph", () => ({ OpportunityRippleGraph: () => null }));

function baseV1Detail(overrides: Partial<OpportunityDetail> = {}): OpportunityDetail {
  return {
    id: 406, slug: "real-opportunity-406", title: "A Real Opportunity",
    summary: "Real summary text.",
    opportunity_score: 72, confidence: 0.65,
    trend: "positive", risk_level: "Medium", time_horizon: "3-6 months",
    sectors: ["Banking"],
    ai_summary: null,
    metrics: null,
    timeline: [],
    events: [],
    companies: [],
    news: [],
    sector_distribution: [],
    graph_nodes: [],
    graph_edges: [],
    primary_event: null,
    investment_verdict: null,
    historical_similarity: null,
    catalysts: [],
    ...overrides,
  };
}

describe("LegacyOpportunityDetail — score-history fabrication removal (2026-09-19 integrity fix)", () => {
  it("does not render an 'Opportunity Score Over Time' section or any synthetic historical month points for a real single current score", () => {
    render(
      <LegacyOpportunityDetail
        detail={baseV1Detail({ opportunity_score: 72 })}
        id="real-opportunity-406"
        hasInitialDetail={true}
        initialRelated={null}
      />
    );

    // The removed fabricated section/heading must never reappear.
    expect(screen.queryByText(/Opportunity Score Over Time/i)).not.toBeInTheDocument();

    // buildScoreHistory() used to invent fake calendar-month labels
    // ("Dec"/"Jan"/"Feb"/"Mar"/"Apr"/"May"/"Jun") around a single real
    // score — none of that fabricated content should exist anywhere on
    // the page for a plain, single-score opportunity.
    for (const month of ["Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]) {
      expect(screen.queryByText(month)).not.toBeInTheDocument();
    }

    // There must also be no leftover period-toggle control (1M/3M/6M/All)
    // that used to drive the fabricated chart.
    expect(screen.queryByRole("button", { name: "All" })).not.toBeInTheDocument();

    // The real current score must still be shown — this fix removes the
    // fabricated history, not the genuine persisted score.
    expect(screen.getByText("72")).toBeInTheDocument();
  });

  it("still renders no historical section when opportunity_score is null (no real score to even derive a hero number from)", () => {
    render(
      <LegacyOpportunityDetail
        detail={baseV1Detail({ opportunity_score: null, confidence: null })}
        id="real-opportunity-406"
        hasInitialDetail={true}
        initialRelated={null}
      />
    );

    expect(screen.queryByText(/Opportunity Score Over Time/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/No score history available yet/i)).not.toBeInTheDocument();
  });
});
