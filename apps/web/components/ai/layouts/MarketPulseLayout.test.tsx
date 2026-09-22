// Component tests for MarketPulseLayout (2026-09-22, canonical-core
// audit). Proves structured data always renders, tracked/AI risk are
// never shown with the same label, self-rated confidence is
// unreachable, and no prohibited research-verdict concept can leak.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MarketPulseLayout } from "./MarketPulseLayout";
import { toMarketPulseAEV2Answer } from "../answerTypes";
import {
  completeMarketPulseAnswer, synthesisUnavailableMarketPulseAnswer, aiSynthesisRiskMarketPulseAnswer,
  noRiskMarketPulseAnswer, noOpportunityMarketPulseAnswer, noDriversMarketPulseAnswer,
} from "../__fixtures__/marketPulse";
import type { AEV2MarketPulseAnswer } from "../answerTypes";

function buildAnswer(fixture: typeof completeMarketPulseAnswer): AEV2MarketPulseAnswer {
  const answer = toMarketPulseAEV2Answer(fixture.result, fixture.aev2);
  if (answer.ui_mode !== "market_pulse") {
    throw new Error("fixture expected to be eligible for market_pulse");
  }
  return answer;
}

const PROHIBITED_TEXT = [
  "Buy", "Sell", "Hold", "Verdict", "Recommendation", "Research Outlook",
  "Suitability", "Time Horizon", "Confidence Score",
];

function collectKeys(value: unknown, found: Set<string>, seen = new Set<unknown>()) {
  if (value == null || typeof value !== "object") return;
  if (seen.has(value)) return;
  seen.add(value);
  for (const key of Object.keys(value as Record<string, unknown>)) {
    found.add(key);
    collectKeys((value as Record<string, unknown>)[key], found, seen);
  }
}

describe("MarketPulseLayout", () => {
  it("renders market state, indices, sectors, movers, themes, opportunity, risk, and calendar", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);

    expect(screen.getByText("NIFTY 50")).toBeInTheDocument();
    expect(screen.getByText("Realty")).toBeInTheDocument();
    expect(screen.getByText("Coal India")).toBeInTheDocument();
    expect(screen.getByText("Reliance Industries")).toBeInTheDocument();
    expect(screen.getByText("Banking")).toBeInTheDocument();
    expect(screen.getByText(/IPO rush/)).toBeInTheDocument();
    expect(screen.getByText("FII outflows accelerate on global risk-off sentiment")).toBeInTheDocument();
    expect(screen.getByText("RBI Policy Meeting")).toBeInTheDocument();
  });

  it("renders the generated summary and conclusion when synthesis is complete", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/Markets traded mixed today/)).toBeInTheDocument();
    expect(screen.getByText(/Today's move looks narrow/)).toBeInTheDocument();
  });

  it("omits generated prose honestly when synthesis is unavailable, but keeps structured data", () => {
    const answer = buildAnswer(synthesisUnavailableMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.queryByText(/Markets traded mixed today/)).not.toBeInTheDocument();
    expect(screen.getByText(/couldn't be shown/)).toBeInTheDocument();
    expect(screen.getByText("NIFTY 50")).toBeInTheDocument();
    expect(screen.getByText("Coal India")).toBeInTheDocument();
  });

  it("labels tracked-event risk as Verified market risk", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("Verified market risk")).toBeInTheDocument();
    expect(screen.queryByText("AI-identified consideration")).not.toBeInTheDocument();
  });

  it("labels AI-synthesis risk as AI-identified consideration — never the same label as a tracked event", () => {
    const answer = buildAnswer(aiSynthesisRiskMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("AI-identified consideration")).toBeInTheDocument();
    expect(screen.queryByText("Verified market risk")).not.toBeInTheDocument();
  });

  it("omits the risk section entirely when none exists — never a filled-in placeholder", () => {
    const answer = buildAnswer(noRiskMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.queryByText("Verified market risk")).not.toBeInTheDocument();
    expect(screen.queryByText("AI-identified consideration")).not.toBeInTheDocument();
  });

  it("never renders a self-rated confidence number for risk", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    const { container } = render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(container.textContent ?? "").not.toContain("70");
  });

  it("omits the opportunity card entirely when none resolves", () => {
    const answer = buildAnswer(noOpportunityMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.queryByText("Biggest Opportunity")).not.toBeInTheDocument();
  });

  it("labels the opportunity score explicitly as an Opportunity score", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/Opportunity score:/)).toBeInTheDocument();
    expect(screen.queryByText(/probability/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/forecast/i)).not.toBeInTheDocument();
  });

  it("renders an honest 'no verified driver' state for movers with no drivers", () => {
    const answer = buildAnswer(noDriversMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getAllByText("No verified driver identified for this move.").length).toBeGreaterThan(0);
  });

  it("shows a real verified driver with its confidence tier", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("Weak Results")).toBeInTheDocument();
    expect(screen.getByText(/High confidence/)).toBeInTheDocument();
  });

  it("labels theme momentum as a computed score, distinct from verified drivers", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/Computed score/)).toBeInTheDocument();
  });

  it("shows Evidence Coverage, never a standard research confidence score", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("Evidence Coverage")).toBeInTheDocument();
    expect(screen.getByText(/movers have a verified driver/)).toBeInTheDocument();
  });

  it("never renders a prohibited research-verdict concept", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    const { container } = render(<MarketPulseLayout answer={answer} onNewSearch={() => {}} />);
    for (const word of PROHIBITED_TEXT) {
      expect(container.textContent ?? "").not.toContain(word);
    }
  });

  it("the answer object graph never carries a prohibited plain-V3/confidence-formula key", () => {
    const answer = buildAnswer(completeMarketPulseAnswer);
    const found = new Set<string>();
    collectKeys(answer, found);
    for (const key of [
      "investment_verdict", "engine_verdict", "rating", "suitable_for", "risk_level",
      "top_picks", "scenarios", "raw", "confidence_breakdown", "historical_similarity",
    ]) {
      expect(found.has(key)).toBe(false);
    }
  });
});
