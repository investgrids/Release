// Component tests for FactualLookupLayout (2026-09-22, six-mode
// integration audit). Found during the audit: this is the ONLY ui_mode
// actually reachable today (IMPLEMENTED_UI_MODES/IntentLayout/HTTP —
// every other mode is still fixture-only, pre-activation), yet it was
// the one layout with zero test coverage. Closes that gap.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { FactualLookupLayout } from "./FactualLookupLayout";
import { toAIAnswer } from "../answerTypes";
import { baseSearchResult } from "../__fixtures__/directCompanyResearch";
import type { FactualLookupAnswer } from "../answerTypes";

function buildAnswer(overrides: Record<string, unknown> = {}): FactualLookupAnswer {
  const result = baseSearchResult({ ui_mode: "factual_lookup", ...overrides });
  const answer = toAIAnswer(result);
  if (answer.ui_mode !== "factual_lookup") {
    throw new Error("fixture expected to reach the real factual_lookup layout");
  }
  return answer;
}

describe("FactualLookupLayout", () => {
  it("renders bottom_line as the direct answer when present", () => {
    const answer = buildAnswer({
      answer: {
        summary: "", bottom_line: "TCS's Q4 FY25 revenue was ₹64,479 crore.",
        what_happened: "", why_it_happened: "", immediate_impact: "", medium_term: "",
        long_term: "", what_priced_in: "", risks: [], opportunities: [], confidence: null,
        confidence_level: "unscored", sentiment: "neutral", sources_count: 2,
      },
    });
    render(<FactualLookupLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("TCS's Q4 FY25 revenue was ₹64,479 crore.")).toBeInTheDocument();
  });

  it("falls back to summary when bottom_line is empty", () => {
    const answer = buildAnswer({
      answer: {
        summary: "TCS reported steady revenue growth in Q4 FY25.", bottom_line: "",
        what_happened: "", why_it_happened: "", immediate_impact: "", medium_term: "",
        long_term: "", what_priced_in: "", risks: [], opportunities: [], confidence: null,
        confidence_level: "unscored", sentiment: "neutral", sources_count: 1,
      },
    });
    render(<FactualLookupLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("TCS reported steady revenue growth in Q4 FY25.")).toBeInTheDocument();
  });

  it("shows elaboration only when summary differs from the direct answer", () => {
    const answer = buildAnswer({
      answer: {
        summary: "TCS's Q4 FY25 revenue was ₹64,479 crore, up 5.6% YoY.",
        bottom_line: "TCS's Q4 FY25 revenue was ₹64,479 crore.",
        what_happened: "", why_it_happened: "", immediate_impact: "", medium_term: "",
        long_term: "", what_priced_in: "", risks: [], opportunities: [], confidence: null,
        confidence_level: "unscored", sentiment: "neutral", sources_count: 2,
      },
    });
    render(<FactualLookupLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("TCS's Q4 FY25 revenue was ₹64,479 crore.")).toBeInTheDocument();
    expect(screen.getByText("TCS's Q4 FY25 revenue was ₹64,479 crore, up 5.6% YoY.")).toBeInTheDocument();
  });

  it("never renders an elaboration paragraph when summary equals the direct answer", () => {
    const same = "TCS's Q4 FY25 revenue was ₹64,479 crore.";
    const answer = buildAnswer({
      answer: {
        summary: same, bottom_line: same, what_happened: "", why_it_happened: "",
        immediate_impact: "", medium_term: "", long_term: "", what_priced_in: "",
        risks: [], opportunities: [], confidence: null, confidence_level: "unscored",
        sentiment: "neutral", sources_count: 1,
      },
    });
    render(<FactualLookupLayout answer={answer} onNewSearch={() => {}} />);
    // Rendered exactly once (the bold direct-answer line) — a second,
    // identical paragraph would mean the elaboration branch fired when
    // summary and bottom_line are the same string.
    expect(screen.getAllByText(same)).toHaveLength(1);
  });

  it("shows an honest no-answer notice, never a blank body, when neither bottom_line nor summary exist", () => {
    const answer = buildAnswer({
      answer: {
        summary: "", bottom_line: "", what_happened: "", why_it_happened: "",
        immediate_impact: "", medium_term: "", long_term: "", what_priced_in: "",
        risks: [], opportunities: [], confidence: null, confidence_level: "unscored",
        sentiment: "neutral", sources_count: 0,
      },
    });
    render(<FactualLookupLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/No direct answer was generated/)).toBeInTheDocument();
  });

  it("never shows a confidence badge or related-links section (factual lookups have neither)", () => {
    const answer = buildAnswer({
      answer: {
        summary: "", bottom_line: "TCS's Q4 FY25 revenue was ₹64,479 crore.",
        what_happened: "", why_it_happened: "", immediate_impact: "", medium_term: "",
        long_term: "", what_priced_in: "", risks: [], opportunities: [], confidence: null,
        confidence_level: "unscored", sentiment: "neutral", sources_count: 2,
      },
    });
    render(<FactualLookupLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.queryByText(/Related links/i)).not.toBeInTheDocument();
  });

  it("shows the shell's own factual_lookup ui-mode chrome, not a generic badge", () => {
    const answer = buildAnswer({
      answer: {
        summary: "", bottom_line: "TCS's Q4 FY25 revenue was ₹64,479 crore.",
        what_happened: "", why_it_happened: "", immediate_impact: "", medium_term: "",
        long_term: "", what_priced_in: "", risks: [], opportunities: [], confidence: null,
        confidence_level: "unscored", sentiment: "neutral", sources_count: 2,
      },
    });
    render(<FactualLookupLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByTestId("ai-answer-shell")).toHaveAttribute("data-ui-mode", "factual_lookup");
  });
});
