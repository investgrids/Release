// DegradedAnswerLayout — proves each explicit unsupported mode renders
// its OWN specific message (2026-09-22, intent-coverage audit), never
// the generic "Analysis unavailable"/"not supported yet" fallback, and
// that the shell chrome shows the real mode's own label rather than a
// bare "Degraded" badge.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { DegradedAnswerLayout } from "./DegradedAnswerLayout";
import { toAIAnswer, UNSUPPORTED_MODE_INFO } from "../answerTypes";
import { baseSearchResult } from "../__fixtures__/directCompanyResearch";
import type { DegradedAnswer } from "../answerTypes";
import type { UIMode } from "@/app/ai-search/AISearchClient";

function buildDegraded(mode: UIMode): DegradedAnswer {
  const answer = toAIAnswer(baseSearchResult({ ui_mode: mode }));
  if (answer.ui_mode !== "degraded") {
    throw new Error("expected a degraded answer for this fixture");
  }
  return answer;
}

describe("DegradedAnswerLayout — explicit unsupported modes", () => {
  it("renders technical_timing's own specific message", () => {
    const answer = buildDegraded("technical_timing");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(UNSUPPORTED_MODE_INFO.technical_timing)).toBeInTheDocument();
  });

  it("renders company_discovery's own specific message, distinct from technical_timing's", () => {
    const answer = buildDegraded("company_discovery");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(UNSUPPORTED_MODE_INFO.company_discovery)).toBeInTheDocument();
    expect(screen.queryByText(UNSUPPORTED_MODE_INFO.technical_timing)).not.toBeInTheDocument();
  });

  it("renders portfolio_review's own message, mentioning the Portfolio Coverage tool", () => {
    const answer = buildDegraded("portfolio_review");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/Portfolio Coverage tool/)).toBeInTheDocument();
  });

  it("renders earnings_preview's own message", () => {
    const answer = buildDegraded("earnings_preview");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(UNSUPPORTED_MODE_INFO.earnings_preview)).toBeInTheDocument();
  });

  it("renders multi_company_comparison's own message", () => {
    const answer = buildDegraded("multi_company_comparison");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(UNSUPPORTED_MODE_INFO.multi_company_comparison)).toBeInTheDocument();
  });

  it("shows the real mode's own chrome label, not the generic Degraded badge", () => {
    const answer = buildDegraded("technical_timing");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByTestId("ai-answer-shell")).toHaveAttribute("data-ui-mode", "technical_timing");
  });

  it("never shows the generic not-supported-yet fallback for a mode with its own registry entry", () => {
    const answer = buildDegraded("technical_timing");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.queryByText("This kind of question isn't supported yet. The real evidence found is shown below.")).not.toBeInTheDocument();
  });

  it("a still-unwired locally-implemented mode keeps the generic not-yet-implemented copy", () => {
    const answer = buildDegraded("direct_company_research");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/still being built/)).toBeInTheDocument();
  });
});
