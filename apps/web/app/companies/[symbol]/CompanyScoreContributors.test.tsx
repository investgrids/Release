import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { CompanyScoreContributors, type CompanyScoreData } from "./CompanyPageClient";
import type { StockDetail } from "./CompanyPageClient";

const stock = { symbol: "TESTCO", name: "Test Company Ltd" } as StockDetail;

function mockFetchOnce(data: CompanyScoreData | null) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: data !== null,
    json: async () => data,
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

// One-score migration regression guard (2026-09-26, owner instruction):
// this section was renamed from "AI Company Score" to "Recent Intelligence
// Evidence" and stripped of every standalone numeric score, rating,
// verdict, and score-based colour gauge — a second public company rating
// living on a different tab under a different name was still a second
// rating. These tests prove the removed elements are gone and the real,
// dated evidence content (the actual reason this section exists) survives
// untouched.
describe("CompanyScoreContributors — Recent Intelligence Evidence (2026-09-26 rename)", () => {
  it("renders the new title and never the old numeric score, risk/trend pills, or verdict text", async () => {
    const data: CompanyScoreData = {
      symbol: "TESTCO", score: 62.4, confidence: 0.71,
      signal_count: 3, contributing_signal_count: 2, sector: "Banking",
      trend: "up", risk_level: "Low",
      verdict: { label: "Bullish", tone: "positive", reasoning: "Opportunity score 62/100 · Low risk · up trend" },
      top_contributors: [],
      positive_reasons: [
        { reason: "Real published analysis found strong Q3 earnings growth.", source_type: "article", href: "/newsroom/article/real-q3-earnings", signed_magnitude: 40, signal_at: "2026-09-10T00:00:00Z" },
      ],
      risk_factors: [
        { reason: "A real opportunity flagged margin compression risk.", source_type: "opportunity", href: "/opportunity-radar/real-margin-risk", signed_magnitude: -15, signal_at: "2026-09-12T00:00:00Z" },
      ],
    };
    mockFetchOnce(data);

    render(<CompanyScoreContributors stock={stock} />);

    await waitFor(() => expect(screen.getByText("Recent Intelligence Evidence")).toBeInTheDocument());

    // --- REMOVED: no standalone numeric score, rating, verdict, or colour gauge ---
    expect(screen.queryByText("AI Company Score")).not.toBeInTheDocument();
    expect(screen.queryByText("62.4")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Score")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Powered")).not.toBeInTheDocument();
    expect(screen.queryByText("Evidence quality")).not.toBeInTheDocument();
    expect(screen.queryByText(/Low Risk/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Trending Up/)).not.toBeInTheDocument();
    expect(screen.queryByText("Bullish")).not.toBeInTheDocument();
    expect(screen.queryByText(/Opportunity score 62\/100/)).not.toBeInTheDocument();

    // --- RETAINED: the actual dated, sourced evidence content ---
    expect(screen.getByText("Real published analysis found strong Q3 earnings growth.")).toBeInTheDocument();
    expect(screen.getByText("A real opportunity flagged margin compression risk.")).toBeInTheDocument();
    expect(screen.getByText(/From published analysis/)).toBeInTheDocument();
    expect(screen.getByText(/From opportunity tracking/)).toBeInTheDocument();
    expect(screen.getByText(/10 Sept? 2026/)).toBeInTheDocument();
    expect(screen.getByText(/12 Sept? 2026/)).toBeInTheDocument();
    expect(screen.getByText(/2 contributing signals/)).toBeInTheDocument();
    // Explains the evidence's real relationship to the score without
    // itself being a competing rating.
    expect(screen.getByText(/Current Intelligence pillar/)).toBeInTheDocument();
  });

  it("renders the honest empty state under the new title when there is no real evidence yet", async () => {
    const data: CompanyScoreData = {
      symbol: "TESTCO", score: null, confidence: null,
      signal_count: 0, contributing_signal_count: 0, sector: null,
      top_contributors: [],
    };
    mockFetchOnce(data);

    render(<CompanyScoreContributors stock={stock} />);

    await waitFor(() => expect(screen.getByText("Recent Intelligence Evidence")).toBeInTheDocument());
    expect(screen.getByText(/No intelligence evidence tracked for Test Company Ltd yet/)).toBeInTheDocument();
    expect(screen.queryByText("AI Company Score")).not.toBeInTheDocument();
  });

  it("renders nothing while the fetch is pending or fails", async () => {
    mockFetchOnce(null);
    const { container } = render(<CompanyScoreContributors stock={stock} />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
