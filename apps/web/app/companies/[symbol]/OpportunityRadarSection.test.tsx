import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { OpportunityRadarSection } from "./CompanyPageClient";
import type { StockDetail } from "./CompanyPageClient";
import type { CompanyScoreData } from "./CompanyPageClient";

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

// One-score migration sweep (2026-09-26, owner instruction): the
// Opportunities tab's OpportunityRadarSection duplicated the exact same
// "AI Company Intelligence Score" standalone rating already removed from
// the Intelligence tab's CompanyScoreContributors — living under a
// different title on a different tab did not exempt it. Renamed to
// "Recent Intelligence Evidence" and stripped of the score headline, "AI
// Powered" badge, and "Evidence quality" gauge; the real per-signal
// evidence cards (reason, source, date, link, signed magnitude) are
// unchanged.
describe("OpportunityRadarSection — Recent Intelligence Evidence (2026-09-26 sweep)", () => {
  it("renders the new title and never the old numeric score, AI-powered badge, or evidence-quality gauge", async () => {
    const data: CompanyScoreData = {
      symbol: "TESTCO", score: 62.4, confidence: 0.71,
      signal_count: 3, contributing_signal_count: 2, sector: "Banking",
      trend: "up", risk_level: "Low",
      verdict: { label: "Bullish", tone: "positive", reasoning: "Opportunity score 62/100 · Low risk · up trend" },
      top_contributors: [
        { reason: "Real published analysis found strong Q3 earnings growth.", source_type: "article", href: "/newsroom/article/real-q3-earnings", signed_magnitude: 40, signal_at: "2026-09-10T00:00:00Z" },
        { reason: "A real opportunity flagged margin compression risk.", source_type: "opportunity", href: "/opportunity-radar/real-margin-risk", signed_magnitude: -15, signal_at: "2026-09-12T00:00:00Z" },
      ],
    };
    mockFetchOnce(data);

    render(<OpportunityRadarSection stock={stock} />);

    await waitFor(() => expect(screen.getByText("Recent intelligence evidence")).toBeInTheDocument());

    // --- REMOVED: no standalone numeric score, AI-powered badge, or evidence-quality gauge ---
    expect(screen.queryByText("AI Company Intelligence Score")).not.toBeInTheDocument();
    expect(screen.queryByText("62.4")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Score")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Powered")).not.toBeInTheDocument();
    expect(screen.queryByText("Evidence quality")).not.toBeInTheDocument();

    // --- RETAINED: the real per-signal evidence cards, including their
    // individual signed magnitude (not a company rating, an evidence-item
    // weight — same concept ContributorRow already kept on the Intelligence tab) ---
    expect(screen.getByText("Real published analysis found strong Q3 earnings growth.")).toBeInTheDocument();
    expect(screen.getByText("A real opportunity flagged margin compression risk.")).toBeInTheDocument();
    expect(screen.getByText("+40")).toBeInTheDocument();
    expect(screen.getByText("-15")).toBeInTheDocument();
    expect(screen.getByText(/2 contributing signals/)).toBeInTheDocument();
    expect(screen.getByText(/Current Intelligence pillar/)).toBeInTheDocument();
  });

  it("renders nothing when there are no real signals yet", async () => {
    const data: CompanyScoreData = {
      symbol: "TESTCO", score: null, confidence: null,
      signal_count: 0, contributing_signal_count: 0, sector: null,
      top_contributors: [],
    };
    mockFetchOnce(data);
    const { container } = render(<OpportunityRadarSection stock={stock} />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
