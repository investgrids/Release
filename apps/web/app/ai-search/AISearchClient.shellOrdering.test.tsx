// Real defect found live (2026-09-22, six-mode integration audit's own
// browser QA): SearchResults checked `result.synthesis_incomplete` BEFORE
// `AI_ANSWER_SHELL_ENABLED && result.ui_mode`, so a capacity-degraded
// response (synthesis_incomplete: true — the real, common case for every
// mode except market_pulse) always rendered the legacy DegradedSearchAnswer
// component, even with the shell flag on. toAIAnswer's own "synthesis_
// incomplete" handling (the universal DegradedAnswer -> DegradedAnswerLayout
// shape) never got a chance to run. Fixed by checking the shell branch
// first; these tests pin the fix directly against a real degraded fixture
// under both flag states.
//
// AI_ANSWER_SHELL_ENABLED is a module-level const read from process.env at
// import time, so the flag must be stubbed BEFORE the module is first
// evaluated — vi.resetModules() + a dynamic import inside each test, rather
// than the file's usual static import, is what makes that possible.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

vi.mock("@/components/ai/InvestmentWatchPanel", () => ({
  InvestmentWatchPanel: () => <div data-testid="investment-watch-panel" />,
}));
vi.mock("@/components/ai/ResearchWorkspace", () => ({
  ResearchWorkspace: () => <div data-testid="research-workspace-stub" />,
}));

function degradedDirectCompanyResult() {
  return {
    query: "What is happening with HDFC Bank?",
    ui_mode: "direct_company_research",
    synthesis_incomplete: true,
    degraded_reason: "capacity",
    answer: {
      summary: "There isn't enough freshly generated analysis to answer with confidence right now.",
      bottom_line: "There isn't enough freshly generated analysis to answer with confidence right now.",
      what_happened: "", why_it_happened: "", immediate_impact: "", medium_term: "",
      long_term: "", what_priced_in: "", risks: [], opportunities: [],
      confidence: null, confidence_level: "unscored", sentiment: "neutral", sources_count: 0,
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
    market_chart: { labels: [], series: [] }, graph: { nodes: [], edges: [] },
    citations: [], decision_intelligence: null,
    confidence_data: { level: "unscored", score: null, reasons: [], breakdown: {}, caveats: [] },
    context_used: { companies: [], sectors: [] }, watch_subject: null,
  } as unknown as import("./AISearchClient").SearchResult;
}

const noop = () => {};

describe("SearchResults — shell/degraded dispatch ordering", () => {
  const originalEnv = process.env.NEXT_PUBLIC_AI_ANSWER_SHELL;

  afterEach(() => {
    if (originalEnv === undefined) delete process.env.NEXT_PUBLIC_AI_ANSWER_SHELL;
    else process.env.NEXT_PUBLIC_AI_ANSWER_SHELL = originalEnv;
    vi.resetModules();
  });

  it("with the shell flag OFF (default), a degraded response still renders the legacy DegradedSearchAnswer", async () => {
    delete process.env.NEXT_PUBLIC_AI_ANSWER_SHELL;
    vi.resetModules();
    const { SearchResults } = await import("./AISearchClient");
    render(
      <SearchResults result={degradedDirectCompanyResult()} onFollowUp={noop} resultTime={new Date()} resultMeta={null} onRefined={noop} />,
    );
    expect(screen.getByTestId("degraded-search-answer")).toBeInTheDocument();
    expect(screen.queryByTestId("ai-answer-shell")).not.toBeInTheDocument();
  });

  it("with the shell flag ON, the SAME degraded response now renders the new universal shell, never the legacy one", async () => {
    process.env.NEXT_PUBLIC_AI_ANSWER_SHELL = "1";
    vi.resetModules();
    const { SearchResults } = await import("./AISearchClient");
    render(
      <SearchResults result={degradedDirectCompanyResult()} onFollowUp={noop} resultTime={new Date()} resultMeta={null} onRefined={noop} />,
    );
    expect(screen.queryByTestId("degraded-search-answer")).not.toBeInTheDocument();
    const shell = screen.getByTestId("ai-answer-shell");
    expect(shell).toBeInTheDocument();
    // The universal degraded chrome (DegradedAnswerLayout), not a real
    // direct_company_research success render — synthesis_incomplete must
    // still short-circuit toAIAnswer to the honest degraded state.
    expect(shell).toHaveAttribute("data-ui-mode", "degraded");
  });
});
