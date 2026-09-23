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

  it("an implemented mode with no attached AEV2 payload gets its own honest aev2_unavailable copy, not the generic not-yet-implemented one (2026-09-22, activation-wiring commit)", () => {
    // direct_company_research is now wired (IMPLEMENTED_UI_MODES), but
    // baseSearchResult carries no answer_experience_v2 — exactly today's
    // real production state (AEV2_BUILD_COMPLETE stays False) — so this
    // degrades on "aev2_unavailable", never "not_yet_implemented".
    const answer = buildDegraded("direct_company_research");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/enhanced view isn't available/)).toBeInTheDocument();
    expect(screen.queryByText(/still being built/)).not.toBeInTheDocument();
  });
});

describe("DegradedAnswerLayout — never claims evidence is 'shown below' when there isn't any (2026-09-23, real browser QA finding)", () => {
  // Real query that surfaced this live: "What is the impact of RBI rate
  // cut on banking stocks?" resolved no company and matched zero
  // keyword-searched news/events/policies, yet the degraded notice still
  // said "The real evidence found is shown below" with nothing below it.
  function degradedWithEvidence(reason: "synthesis_incomplete" | "aev2_unavailable", hasEvidence: boolean): DegradedAnswer {
    const overrides: Record<string, unknown> = hasEvidence
      ? { related_events: [{ id: "e1", title: "Some real event", date: "2026-09-20", category: "Macro" }] }
      : { related_events: [], news: [], policies: [] };
    if (reason === "synthesis_incomplete") overrides.synthesis_incomplete = true;
    const answer = toAIAnswer(baseSearchResult({ ui_mode: "direct_company_research", ...overrides }));
    if (answer.ui_mode !== "degraded") throw new Error("expected a degraded answer for this fixture");
    return answer;
  }

  it("synthesis_incomplete with zero evidence says so honestly, never claiming evidence is shown below", () => {
    const answer = degradedWithEvidence("synthesis_incomplete", false);
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/No related news, events, or policy evidence was found/)).toBeInTheDocument();
    expect(screen.queryByText(/shown below/)).not.toBeInTheDocument();
  });

  it("synthesis_incomplete WITH real evidence keeps the original 'shown below' copy", () => {
    const answer = degradedWithEvidence("synthesis_incomplete", true);
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/shown below/)).toBeInTheDocument();
  });

  it("aev2_unavailable with zero evidence also says so honestly", () => {
    const answer = degradedWithEvidence("aev2_unavailable", false);
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/no related evidence was found/)).toBeInTheDocument();
    expect(screen.queryByText(/shown below/)).not.toBeInTheDocument();
  });
});

describe("DegradedAnswerLayout — answer_availability-driven copy (2026-09-23, Phase 1.2)", () => {
  function degradedWithAvailability(availability: { state: string; evidence_retrieval_completed: boolean; evidence_count: number }): DegradedAnswer {
    const answer = toAIAnswer(baseSearchResult({
      ui_mode: "direct_company_research",
      synthesis_incomplete: true,
      answer_availability: availability,
    }));
    if (answer.ui_mode !== "degraded") throw new Error("expected a degraded answer for this fixture");
    return answer;
  }

  it("temporarily_unavailable shows its own badge and never claims no evidence exists", () => {
    const answer = degradedWithAvailability({ state: "temporarily_unavailable", evidence_retrieval_completed: true, evidence_count: 0 });
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("TEMPORARILY UNAVAILABLE")).toBeInTheDocument();
    expect(screen.getByText(/couldn't complete evidence retrieval and analysis right now/)).toBeInTheDocument();
    expect(screen.queryByText(/No related verified news/)).not.toBeInTheDocument();
  });

  it("no_verified_evidence shows its own badge and message", () => {
    const answer = degradedWithAvailability({ state: "no_verified_evidence", evidence_retrieval_completed: true, evidence_count: 0 });
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("NO VERIFIED EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText("No related verified news, events, or policy evidence was found for this query.")).toBeInTheDocument();
  });

  it("limited_evidence shows its own badge and message, distinct from temporarily_unavailable", () => {
    const answer = degradedWithAvailability({ state: "limited_evidence", evidence_retrieval_completed: true, evidence_count: 3 });
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("LIMITED EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText(/verified evidence found is shown below, but the full analysis could not be completed/)).toBeInTheDocument();
    expect(screen.queryByText("TEMPORARILY UNAVAILABLE")).not.toBeInTheDocument();
  });

  it("falls back to the older evidence-length-based copy when answer_availability is absent (a response predating this contract)", () => {
    const answer = toAIAnswer(baseSearchResult({
      ui_mode: "direct_company_research", synthesis_incomplete: true,
      related_events: [], news: [], policies: [],
    }));
    if (answer.ui_mode !== "degraded") throw new Error("expected a degraded answer for this fixture");
    render(<DegradedAnswerLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/No related news, events, or policy evidence was found for this query, and the analysis itself didn't complete/)).toBeInTheDocument();
    expect(screen.queryByText("TEMPORARILY UNAVAILABLE")).not.toBeInTheDocument();
  });
});
