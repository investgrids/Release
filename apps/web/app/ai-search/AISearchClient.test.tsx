// Fail-closed degraded-mode frontend coverage (2026-09-21).
//
// Real defect found live: a synthesis_incomplete response ("Should I invest
// in HDFC Bank right now?" with every AI provider exhausted) still rendered
// a full "Neutral" verdict, a 33.6% confidence score, a "6-12 months"
// horizon, a risk level, scenarios, a monitoring checklist, and an
// "AI Reasoning" breakdown -- all either a hardcoded stub with no relation
// to the query, or real signals computed from real evidence and then glued
// onto that stub, producing a page that admitted "synthesis failed" in one
// sentence while presenting a fully-dressed analysis two sections below it.
//
// The backend fix (pipeline.py::_build_degraded_response, commit 8ca268e)
// now sends an honest, mostly-empty shape for a degraded response. These
// tests prove the frontend actually HIDES the corresponding sections given
// that shape, rather than rendering them decorated with an amber "degraded"
// badge (the previous behavior) -- and that a genuinely successful response
// is completely unaffected by this gating.
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { SearchResults, RightSidebar } from "./AISearchClient";
import { useResearchSession } from "@/lib/hooks/useResearchSession";

// InvestmentWatchPanel and ResearchWorkspace fetch real data over the
// network on mount -- stubbed so this test stays hermetic and fast, and so
// presence/absence of the *real* component is unambiguous (a marker
// data-testid, not a network response that may or may not resolve).
vi.mock("@/components/ai/InvestmentWatchPanel", () => ({
  InvestmentWatchPanel: () => <div data-testid="investment-watch-panel" />,
}));
vi.mock("@/components/ai/ResearchWorkspace", () => ({
  ResearchWorkspace: () => <div data-testid="research-workspace-stub" />,
}));

function baseResult(overrides: Record<string, unknown> = {}) {
  return {
    query: "Should I invest in HDFC Bank right now?",
    synthesis_incomplete: false,
    answer: {
      summary: "", bottom_line: "", what_happened: "", why_it_happened: "",
      immediate_impact: "", medium_term: "", long_term: "", what_priced_in: "",
      risks: [], opportunities: [], confidence: null, confidence_level: "unscored",
      sentiment: "neutral", sources_count: 0,
    },
    key_drivers: [], insights: [], companies: [], sectors: [], related_events: [],
    news: [], policies: [], timeline: [], historical_comparison: [], ripple_chain: [],
    scenarios: {}, market_impact_horizons: [], what_to_monitor: [], ai_reasoning_methods: [],
    follow_up_questions: [], follow_up_groups: [],
    investment_verdict: {
      rating: "Not Applicable", direction: "neutral", confidence: null, horizon: null,
      top_picks: [], risks: [], catalysts: [], opportunity_score: null,
      risk_level: "", suitable_for: "", engine_verdict: null,
    },
    market_chart: { labels: [], series: [] },
    graph: { nodes: [], edges: [] },
    citations: [], decision_intelligence: null,
    confidence_data: { level: "unscored", score: null, reasons: [], breakdown: {}, caveats: [] },
    decision_engine_v2: {}, ai_conclusion: {}, timeline_intelligence: {},
    evidence_score: { stars: 0, checklist: {}, source_count: 0 },
    confidence_breakdown: undefined,
    opportunity_risk_matrix: undefined,
    context_used: { companies: [], sectors: [] },
    watch_subject: null,
    ...overrides,
  } as unknown as import("./AISearchClient").SearchResult;
}

function degradedHdfcResult() {
  return baseResult({
    synthesis_incomplete: true,
    degraded_reason: "capacity",
    answer: {
      summary: "There isn't enough freshly generated analysis to answer with confidence right now.",
      bottom_line: "There isn't enough freshly generated analysis to answer “Should I invest in HDFC Bank right now?” with confidence right now — the underlying event and news data is available below, but the synthesis step didn't complete. Try rephrasing the question or checking back shortly.",
      what_happened: "", why_it_happened: "", immediate_impact: "", medium_term: "",
      long_term: "", what_priced_in: "", risks: [], opportunities: [],
      confidence: null, confidence_level: "unscored", sentiment: "neutral", sources_count: 1,
    },
    related_events: [{
      id: "evt-rbi-june-2026", slug: "evt-rbi-june-2026",
      title: "RBI holds repo rate at 6.5% for seventh consecutive meeting",
      date: "Sep 19, 2026", impact_score: 60, confidence: 65, category: "Market",
    }],
    watch_subject: { subject_key: "company:HDFCBANK", subject_type: "company", subject_label: "HDFCBANK", company_name: "HDFCBANK" },
  });
}

function successfulResult() {
  return baseResult({
    synthesis_incomplete: false,
    answer: {
      summary: "HDFC Bank shows resilient fundamentals.",
      bottom_line: "HDFC Bank's asset quality and NIM trends support a constructive near-term view.",
      what_happened: "Q1 results beat estimates.", why_it_happened: "Strong loan growth.",
      immediate_impact: "Positive.", medium_term: "Stable.", long_term: "Constructive.",
      what_priced_in: "Partially priced in.",
      risks: ["Rate cut compression", "Asset quality in unsecured retail"],
      opportunities: ["Market share gains"],
      confidence: 72, confidence_level: "High", sentiment: "bullish", sources_count: 9,
    },
    companies: [{
      symbol: "HDFCBANK", name: "HDFC Bank", price: "1,680.50", change: "+1.2%",
      positive: true, impact_type: "direct", impact_score: 78, confidence: 72,
      reason: "Direct subject of the query.", chart: [1, 2, 3], why_it_matters: "Direct subject of the query.",
    }],
    related_events: [{
      id: "evt-1", slug: "evt-1", title: "HDFC Bank Q1 results beat estimates",
      date: "Sep 19, 2026", impact_score: 70, confidence: 70, category: "Market",
    }],
    scenarios: {
      bull: { probability: 40, outcome: "Rerating on NIM stability.", key_drivers: [], confidence: 65 },
      base: { probability: 45, outcome: "In line with sector.", key_drivers: [], confidence: 70 },
      bear: { probability: 15, outcome: "Margin compression.", key_drivers: [], confidence: 55 },
    },
    what_to_monitor: [{ title: "Quarterly NIM trend", why_it_matters: "Core profitability driver", importance: "critical", frequency: "Quarterly" }],
    ai_reasoning_methods: [{ label: "Evidence-based scoring", used: true }],
    investment_verdict: {
      rating: "Positive", direction: "bullish", confidence: 72, horizon: "6-12 months",
      top_picks: [], risks: ["Rate cut compression"], catalysts: ["NIM stabilization"],
      opportunity_score: 65, risk_level: "Medium", suitable_for: "Medium-term investors", engine_verdict: null,
    },
    confidence_data: { level: "High", score: 72, reasons: ["9 trusted sources"], breakdown: { evidence_quality: 80, market_confirmation: 60, historical_similarity: 50, data_freshness: 90, reasoning_confidence: 70 }, caveats: [] },
    watch_subject: { subject_key: "company:HDFCBANK", subject_type: "company", subject_label: "HDFCBANK", company_name: "HDFC Bank" },
  });
}

const noop = () => {};

function renderResults(result: ReturnType<typeof baseResult>) {
  return render(
    <SearchResults result={result} onFollowUp={noop} resultTime={new Date()} resultMeta={null} onRefined={noop} />
  );
}

function RightSidebarHarness({ result }: { result: ReturnType<typeof baseResult> | null }) {
  const session = useResearchSession();
  return <RightSidebar result={result} onAction={noop} onReopenSearch={noop} activeQuery={undefined} session={session} />;
}

describe("Degraded response — fail-closed frontend gate", () => {
  it("shows only the honest unavailable message and the deterministically linked event", () => {
    renderResults(degradedHdfcResult());
    expect(screen.getByText(/synthesis step didn't complete/i)).toBeInTheDocument();
    expect(screen.getByText("RBI holds repo rate at 6.5% for seventh consecutive meeting")).toBeInTheDocument();
  });

  it("hides the Research Outlook verdict/confidence/horizon/risk/suitability block", () => {
    renderResults(degradedHdfcResult());
    expect(screen.queryByText("Research Outlook")).not.toBeInTheDocument();
    expect(screen.queryByText("Not Applicable")).not.toBeInTheDocument();
    expect(screen.queryByText("Suitable For")).not.toBeInTheDocument();
    expect(screen.queryByText("Time Horizon")).not.toBeInTheDocument();
    expect(screen.queryByText("Risk Level")).not.toBeInTheDocument();
  });

  it("hides scenarios (bull/base/bear) even if scenario data were somehow present", () => {
    // Degraded responses never carry real scenario data — but this test
    // asserts the frontend GATE itself (keyed on synthesis_incomplete), not
    // just that empty data happens to render nothing. A stale cache entry
    // or a future backend regression that still populates `scenarios` on a
    // degraded response must not resurrect this section.
    const result = degradedHdfcResult();
    result.scenarios = {
      bull: { probability: 40, outcome: "x", key_drivers: [], confidence: 60 },
      base: { probability: 40, outcome: "y", key_drivers: [], confidence: 60 },
      bear: { probability: 20, outcome: "z", key_drivers: [], confidence: 60 },
    };
    renderResults(result);
    expect(screen.queryByText("Scenarios")).not.toBeInTheDocument();
    expect(screen.queryByText("Bull Case")).not.toBeInTheDocument();
  });

  it("hides risks, the monitoring checklist, and the AI Reasoning breakdown", () => {
    renderResults(degradedHdfcResult());
    expect(screen.queryByText("Risks & Counterarguments")).not.toBeInTheDocument();
    expect(screen.queryByText("What To Monitor")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Reasoning")).not.toBeInTheDocument();
    expect(screen.queryByText(/No reasoning-source breakdown available/i)).not.toBeInTheDocument();
  });

  it("hides Investment Watch", () => {
    render(<RightSidebarHarness result={degradedHdfcResult()} />);
    expect(screen.queryByTestId("investment-watch-panel")).not.toBeInTheDocument();
  });

  it("handles zero eligible events without crashing, and says so honestly", () => {
    const result = degradedHdfcResult();
    result.related_events = [];
    result.answer.sources_count = 0;
    expect(() => renderResults(result)).not.toThrow();
    expect(screen.getByText(/synthesis step didn't complete/i)).toBeInTheDocument();
  });
});

describe("Successful response — unaffected by the degraded-mode gate", () => {
  it("still shows the Research Outlook verdict, confidence, horizon, risk and suitability", () => {
    renderResults(successfulResult());
    expect(screen.getByText("Research Outlook")).toBeInTheDocument();
    expect(screen.getByText("Positive")).toBeInTheDocument();
    expect(screen.getAllByText("72%").length).toBeGreaterThan(0);
    expect(screen.getByText("6-12 months")).toBeInTheDocument();
    expect(screen.getByText("Medium-term investors")).toBeInTheDocument();
  });

  it("still shows scenarios", () => {
    renderResults(successfulResult());
    expect(screen.getByText("Scenarios")).toBeInTheDocument();
    expect(screen.getByText("Bull Case")).toBeInTheDocument();
  });

  it("still shows risks, the monitoring checklist, and AI Reasoning", () => {
    renderResults(successfulResult());
    expect(screen.getByText("Risks & Counterarguments")).toBeInTheDocument();
    expect(screen.getByText("What To Monitor")).toBeInTheDocument();
    expect(screen.getByText("AI Reasoning")).toBeInTheDocument();
  });

  it("still shows Investment Watch", () => {
    render(<RightSidebarHarness result={successfulResult()} />);
    expect(screen.getByTestId("investment-watch-panel")).toBeInTheDocument();
  });

  it("does not show the degraded-synthesis notice", () => {
    renderResults(successfulResult());
    expect(screen.queryByText(/Full AI analysis wasn.t available/i)).not.toBeInTheDocument();
  });
});
