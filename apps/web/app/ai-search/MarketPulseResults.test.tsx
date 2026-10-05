// Market Pulse degraded rendering — Phase 1 fix (2026-09-21 intent audit
// finding 2). Before this fix, MarketPulseResults had no dedicated
// degraded renderer: a synthesis-failed response could still show empty
// AI Conclusion shells, an empty narrative line per mover, and mixed
// styling scattered across per-section conditionals. DegradedMarketPulse
// mirrors DegradedSearchAnswer's architecture — one early return, one
// self-contained tree showing only real, deterministic data.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MarketPulseResults } from "./AISearchClient";

function basePulse(overrides: Record<string, unknown> = {}) {
  return {
    type: "market_pulse",
    query: "What are today's top gainers?",
    synthesis_incomplete: false,
    generated_at: "2026-09-21T10:00:00Z",
    market_status: { status: "open", time_ist: "10:00" },
    indices: [{ ticker: "NIFTY", name: "Nifty 50", value: "25,000", change: "+0.5%", positive: true }],
    market_mood: "Neutral", market_direction: "sideways",
    market_summary: "Markets are trading flat with mixed global cues.",
    sector_narrative: "IT and banking are leading while metals lag.",
    leading_sectors: [{ id: "it", name: "IT", value: "+1.2%", positive: true, momentum_score: 70 }],
    lagging_sectors: [{ id: "metals", name: "Metals", value: "-0.8%", positive: false, momentum_score: 30 }],
    top_gainers: [{
      company: "Reliance Industries", ticker: "RELIANCE", value: "+2.1%", subtitle: "1,402.50",
      positive: true, verified_drivers: [], evidence_strength: 80,
      narrative: "Reliance gained on strong quarterly results.",
    }],
    top_losers: [{
      company: "Tata Motors", ticker: "TATAMOTORS", value: "-1.2%", subtitle: "950.00",
      positive: false, verified_drivers: [], evidence_strength: 60,
      narrative: "Tata Motors slipped on weak volume data.",
    }],
    most_active: [],
    biggest_opportunity: null, biggest_risk: null,
    ai_conclusion: "Today's move looks broad-based across sectors.",
    what_to_watch_next: [{ id: "w1", category: "Earnings", title: "TCS Q2 results", date: "Sep 25" }],
    what_to_watch_summary: "Watch for TCS results this week.",
    scores: { opportunity_score: 50, risk_score: 30, market_confidence: { score: 70, level: "High", reasons: [], breakdown: {} }, catalyst_score: 40 },
    ...overrides,
  } as unknown as import("./AISearchClient").MarketPulseResult;
}

function degradedPulse() {
  return basePulse({
    synthesis_incomplete: true,
    market_summary: "A written market summary could not be shown because the generated text did not pass the research-language check. The real index and mover data below is unaffected.",
    sector_narrative: "",
    ai_conclusion: "",
    what_to_watch_summary: "",
    top_gainers: [{
      company: "Reliance Industries", ticker: "RELIANCE", value: "+2.1%", subtitle: "1,402.50",
      positive: true, verified_drivers: [], evidence_strength: 80, narrative: "",
    }],
    top_losers: [{
      company: "Tata Motors", ticker: "TATAMOTORS", value: "-1.2%", subtitle: "950.00",
      positive: false, verified_drivers: [], evidence_strength: 60, narrative: "",
    }],
  });
}

describe("Market Pulse — degraded response", () => {
  it("renders through the dedicated DegradedMarketPulse component", () => {
    const { container } = render(<MarketPulseResults result={degradedPulse()} />);
    expect(container.querySelector('[data-testid="degraded-market-pulse"]')).toBeInTheDocument();
  });

  it("shows the honest synthesis-unavailable notice", () => {
    render(<MarketPulseResults result={degradedPulse()} />);
    expect(screen.getByText(/AI narrative couldn.t be generated for this query/i)).toBeInTheDocument();
  });

  it("still shows real deterministic index and mover data", () => {
    render(<MarketPulseResults result={degradedPulse()} />);
    expect(screen.getByText("Nifty 50")).toBeInTheDocument();
    expect(screen.getByText("Reliance Industries")).toBeInTheDocument();
    expect(screen.getByText("Tata Motors")).toBeInTheDocument();
    expect(screen.getByText("IT")).toBeInTheDocument();
  });

  it("shows no empty AI conclusion or narrative shells", () => {
    render(<MarketPulseResults result={degradedPulse()} />);
    expect(screen.queryByText("AI Conclusion")).not.toBeInTheDocument();
    expect(screen.queryByText("Reliance gained on strong quarterly results.")).not.toBeInTheDocument();
    expect(screen.queryByText(/IT and banking are leading/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Watch for TCS results this week/i)).not.toBeInTheDocument();
  });

  it("shows no confidence or recommendation-adjacent chips", () => {
    render(<MarketPulseResults result={degradedPulse()} />);
    expect(screen.queryByText(/Market Confidence/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Catalyst Score/i)).not.toBeInTheDocument();
  });

  it("still shows the real scheduled calendar (not LLM-generated)", () => {
    render(<MarketPulseResults result={degradedPulse()} />);
    expect(screen.getByText("TCS Q2 results")).toBeInTheDocument();
  });
});

describe("Market Pulse — successful response unaffected", () => {
  it("shows the AI conclusion, narratives, and confidence chips", () => {
    render(<MarketPulseResults result={basePulse()} />);
    expect(screen.getByText("AI Conclusion")).toBeInTheDocument();
    expect(screen.getByText("Reliance gained on strong quarterly results.")).toBeInTheDocument();
    expect(screen.getByText(/Market Confidence/i)).toBeInTheDocument();
  });

  it("does not render the degraded component", () => {
    const { container } = render(<MarketPulseResults result={basePulse()} />);
    expect(container.querySelector('[data-testid="degraded-market-pulse"]')).not.toBeInTheDocument();
  });
});
