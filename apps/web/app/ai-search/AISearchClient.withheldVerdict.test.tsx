// Step 3.4D-2.1: the V2 contract is that a withheld verdict is null / "Not Applicable" / empty, meaning "no authorized conclusion". The page must represent that faithfully: never as Neutral,
// Cautious or a zero-valued gauge, and never with the verdict-only widgets (risk level, suitable-for, hero panel, scenarios) that only make sense next to a verdict.
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { SearchResults, RightSidebar } from "./AISearchClient";
import { useResearchSession } from "@/lib/hooks/useResearchSession";

vi.mock("@/components/ai/InvestmentWatchPanel", () => ({ InvestmentWatchPanel: () => <div data-testid="investment-watch-panel" /> }));
vi.mock("@/components/ai/ResearchWorkspace", () => ({ ResearchWorkspace: () => <div data-testid="research-workspace-stub" /> }));

function withheldResult(overrides: Record<string, unknown> = {}) {
  return {
    query: "TCS vs Infosys, which is stronger?",
    synthesis_incomplete: false,
    answer: {
      summary: "TCS is at P/E 15.1 and P/B 6.85, versus Infosys at P/E 13.3 and P/B 4.54.",
      bottom_line: "TCS is at P/E 15.1 and P/B 6.85, versus Infosys at P/E 13.3 and P/B 4.54.",
      what_happened: "", why_it_happened: "", immediate_impact: "", medium_term: "", long_term: "", what_priced_in: "",
      risks: ["Current evidence does not include recent operating results for either company."], opportunities: [],
      confidence: 55, confidence_level: "Medium", sentiment: null, sources_count: 6,
    },
    key_drivers: [{ icon: "valuation", title: "Lower supplied multiples", explanation: "Infosys has lower P/E and P/B than TCS.", confidence: null }],
    insights: [], sectors: [], related_events: [], news: [], policies: [], timeline: [], historical_comparison: [], ripple_chain: [],
    companies: [{ symbol: "TCS", name: "TCS", price: "", change: "", positive: true, impact_type: null, impact_score: null, confidence: null, reason: "Higher-multiple comparator.", chart: [], why_it_matters: "Higher-multiple comparator." }],
    scenarios: {}, market_impact_horizons: {}, what_to_monitor: [], ai_reasoning_methods: [], follow_up_questions: [], follow_up_groups: [],
    investment_verdict: { rating: "Not Applicable", direction: null, confidence: 55, horizon: "", top_picks: [], risks: [], catalysts: [], opportunity_score: null, risk_level: "", suitable_for: "", engine_verdict: null },
    market_chart: { labels: [], series: [] }, graph: { nodes: [], edges: [] }, citations: [], decision_intelligence: {},
    confidence_data: { level: "Medium", score: 55, reasons: [], breakdown: {}, caveats: ["This is a valuation comparison only."] },
    decision_engine_v2: {}, ai_conclusion: {}, timeline_intelligence: {}, opportunity_risk_matrix: {},
    evidence_score: { stars: 3, checklist: {}, source_count: 6 }, confidence_breakdown: undefined,
    conclusion_scope: { requested: "overall_strength", authorized: "valuation_comparison", partial: true },
    structured_authorization: { state: "unavailable", withheld: ["investment_verdict"] },
    context_used: { companies: [], sectors: [] }, watch_subject: null,
    ...overrides,
  } as unknown as import("./AISearchClient").SearchResult;
}

const noop = () => {};
const renderResults = (r: ReturnType<typeof withheldResult>) => render(<SearchResults result={r} onFollowUp={noop} resultTime={new Date()} resultMeta={null} onRefined={noop} />);
function SidebarHarness({ result }: { result: ReturnType<typeof withheldResult> }) {
  const session = useResearchSession();
  return <RightSidebar result={result} onAction={noop} onReopenSearch={noop} activeQuery={undefined} session={session} />;
}

describe("withheld verdict (null direction/sentiment, rating Not Applicable) is shown as not available", () => {
  it("says the verdict is not available instead of drawing a neutral one", () => {
    renderResults(withheldResult());
    expect(screen.getByTestId("verdict-not-available")).toHaveTextContent("Verdict: Not available");
    expect(screen.queryByText(/^neutral$/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Not Applicable")).not.toBeInTheDocument();
    expect(screen.queryByText(/cautious/i)).not.toBeInTheDocument();
  });

  it("hides the verdict-only widgets: risk level, suitable-for, hero panel, scenarios, decision panel", () => {
    renderResults(withheldResult());
    expect(screen.queryByText("Risk Level")).not.toBeInTheDocument();
    expect(screen.queryByText("Suitable For")).not.toBeInTheDocument();
    expect(screen.queryByText("Scenarios")).not.toBeInTheDocument();
    expect(screen.queryByText("Bull Case")).not.toBeInTheDocument();
  });

  it("keeps what is authorized: the sourced prose, the deterministic confidence, the grounded risk text and the partial-scope caveat", () => {
    renderResults(withheldResult());
    expect(screen.getAllByText(/P\/E 15\.1 and P\/B 6\.85/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("55%").length).toBeGreaterThan(0);
    expect(screen.getByText(/does not include recent operating results/i)).toBeInTheDocument();
    expect(screen.getByText(/valuation comparison only/i)).toBeInTheDocument();
  });

  it("does not render a direction icon for a null direction", () => {
    const { container } = renderResults(withheldResult());
    expect(container.querySelector("svg.lucide-minus")).toBeNull();
    expect(container.querySelector("svg.lucide-trending-up")).toBeNull();
    expect(container.querySelector("svg.lucide-trending-down")).toBeNull();
  });

  it("does not render a hero verdict even when empty decision blocks are present as objects", () => {
    renderResults(withheldResult({ decision_engine_v2: {}, ai_conclusion: {} }));
    expect(screen.queryByText(/why this rating/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Neutral$/)).not.toBeInTheDocument();
  });

  it("sidebar shows Not available, not a neutral or Not Applicable overall view, and no best-for", () => {
    render(<SidebarHarness result={withheldResult()} />);
    expect(screen.getByTestId("sidebar-verdict-not-available")).toHaveTextContent("Not available");
    expect(screen.queryByText(/^neutral$/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Not Applicable")).not.toBeInTheDocument();
  });

  it("a market-level engine view is labelled as such, not as the rating of the compared companies", () => {
    renderResults(withheldResult({ investment_verdict: { rating: "Not Applicable", direction: null, confidence: 55, horizon: "", top_picks: [], risks: [], catalysts: [], opportunity_score: null,
      risk_level: "", suitable_for: "", engine_verdict: { rating: "Cautious", tier: "T2" } } }));
    expect(screen.getByText("Market-level data engine view")).toBeInTheDocument();
    expect(screen.queryByText("Why this rating")).not.toBeInTheDocument();
  });
});

describe("an authorized verdict still renders normally", () => {
  const authorized = () => withheldResult({
    answer: { ...withheldResult().answer, sentiment: "bullish" },
    investment_verdict: { rating: "Constructive", direction: "bullish", confidence: 72, horizon: "6-12 months", top_picks: [], risks: [], catalysts: [], opportunity_score: null,
      risk_level: "Medium", suitable_for: "Medium-term investors", engine_verdict: null },
  });
  it("shows the rating, risk level and suitable-for", () => {
    renderResults(authorized());
    expect(screen.getByText("Constructive")).toBeInTheDocument();
    expect(screen.getByText("Risk Level")).toBeInTheDocument();
    expect(screen.getByText("Medium-term investors")).toBeInTheDocument();
    expect(screen.queryByTestId("verdict-not-available")).not.toBeInTheDocument();
  });
});
