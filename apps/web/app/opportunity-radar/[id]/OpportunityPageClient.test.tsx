import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { LegacyOpportunityDetail, type OpportunityDetail } from "./OpportunityPageClient";

// These render real network-fetching widgets unrelated to this regression —
// stubbed to keep the test hermetic and focused on the score-history claim.
vi.mock("@/components/TrackPageVisit", () => ({ TrackPageVisit: () => null }));
vi.mock("@/components/RelatedContent", () => ({ RelatedContent: () => null }));
vi.mock("@/components/NextSteps", () => ({ NextSteps: () => null }));

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

describe("LegacyOpportunityDetail — honest-classification fix (2026-10-17)", () => {
  it("renders Unclassified for Trend, Risk Level, and Time Horizon when classification_status is unclassified, never the stored fallback values", () => {
    render(
      <LegacyOpportunityDetail
        detail={baseV1Detail({
          trend: "Neutral", risk_level: "Medium", time_horizon: "3 – 5 Years",
          classification_status: "unclassified",
        })}
        id="real-opportunity-406"
        hasInitialDetail={true}
        initialRelated={null}
      />
    );

    // The honest "Unclassified" label must appear exactly for the three
    // classification-derived stats -- and the misleading stored values
    // (which still exist in the fixture, same as a real unclassified
    // record would have) must never render as if they were real.
    expect(screen.getAllByText("Unclassified")).toHaveLength(3);
    expect(screen.queryByText("Neutral")).not.toBeInTheDocument();
    expect(screen.queryByText("Medium")).not.toBeInTheDocument();
    expect(screen.queryByText("3 – 5 Years")).not.toBeInTheDocument();
  });

  it("still renders the real trend/risk/time_horizon values when classification_status is classified (or absent, the pre-fix default)", () => {
    render(
      <LegacyOpportunityDetail
        detail={baseV1Detail({
          trend: "positive", risk_level: "Medium", time_horizon: "3-6 months",
          classification_status: "classified",
        })}
        id="real-opportunity-406"
        hasInitialDetail={true}
        initialRelated={null}
      />
    );

    expect(screen.queryByText("Unclassified")).not.toBeInTheDocument();
    expect(screen.getByText("positive")).toBeInTheDocument();
    expect(screen.getByText("Medium")).toBeInTheDocument();
    expect(screen.getByText("3-6 months")).toBeInTheDocument();
  });

  it("defaults to the classified rendering when classification_status is absent entirely (backward compatibility with pre-fix API responses)", () => {
    const { classification_status, ...withoutStatus } = baseV1Detail();
    render(
      <LegacyOpportunityDetail
        detail={withoutStatus as any}
        id="real-opportunity-406"
        hasInitialDetail={true}
        initialRelated={null}
      />
    );

    expect(screen.queryByText("Unclassified")).not.toBeInTheDocument();
  });
});
