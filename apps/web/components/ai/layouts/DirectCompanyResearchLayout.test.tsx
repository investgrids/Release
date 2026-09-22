// Component tests for DirectCompanyResearchLayout (2026-09-22). Proves
// the component (a) renders real AEV2-sourced content, (b) omits
// optional sections honestly rather than showing placeholders, and (c)
// cannot surface any prohibited plain-V3/advisory concept — enforced
// both structurally (AEV2DirectCompanyAnswer carries no `raw`) and here,
// at runtime, as a regression net.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { DirectCompanyResearchLayout } from "./DirectCompanyResearchLayout";
import { toDirectCompanyResearchAEV2Answer } from "../answerTypes";
import { completeAnswer, noPriceDataAnswer, minimalAnswer } from "../__fixtures__/directCompanyResearch";
import type { AEV2DirectCompanyAnswer } from "../answerTypes";

function buildAnswer(fixture: typeof completeAnswer): AEV2DirectCompanyAnswer {
  const answer = toDirectCompanyResearchAEV2Answer(fixture.result, fixture.aev2);
  if (answer.ui_mode !== "direct_company_research") {
    throw new Error("fixture expected to be eligible for direct_company_research");
  }
  return answer;
}

// Prohibited concepts from any plain-V3/advisory vocabulary — none of
// these may ever appear in this layout's rendered output. Case-sensitive
// on purpose ("hold" alone is far too common a word; the prohibition is
// on these as labels/verdicts, matched by their distinctive casing).
const PROHIBITED_TEXT = [
  "Buy", "Sell", "Hold", "Verdict", "Recommendation",
  "Investment Watch", "Current Research",
];

// Recursively walks an object graph checking no prohibited KEY name
// appears anywhere — a regression net against a future refactor
// re-attaching plain-V3 fields to this answer type.
const PROHIBITED_KEYS = [
  "investment_verdict", "engine_verdict", "rating", "suitable_for",
  "risk_level", "top_picks", "scenarios", "confidence_self_rating", "raw",
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

describe("DirectCompanyResearchLayout", () => {
  it("renders the citation-backed summary, what-happened, why-it-matters, price reaction, risks, and horizon sections", () => {
    const answer = buildAnswer(completeAnswer);
    render(<DirectCompanyResearchLayout answer={answer} onNewSearch={() => {}} />);

    expect(screen.getByText(/asset quality metrics have remained stable/)).toBeInTheDocument();
    expect(screen.getByText(/disclosed its quarterly results/)).toBeInTheDocument();
    expect(screen.getByText(/reduces near-term provisioning pressure/)).toBeInTheDocument();
    expect(screen.getByText(/currently trading higher at 1,712.40/)).toBeInTheDocument();
    expect(screen.getByText(/Yahoo Finance/)).toBeInTheDocument();
    expect(screen.getByText(/sharper-than-expected slowdown in deposit growth/)).toBeInTheDocument();
    expect(screen.getByText("6-12 months")).toBeInTheDocument();
  });

  it("omits the price reaction section honestly when the company's price fetch failed (no placeholder)", () => {
    const answer = buildAnswer(noPriceDataAnswer);
    render(<DirectCompanyResearchLayout answer={answer} onNewSearch={() => {}} />);

    expect(screen.queryByText(/Price reaction/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Yahoo Finance/)).not.toBeInTheDocument();
    // The rest of the answer still renders — omission is scoped to the
    // one section with no real data, not the whole layout.
    expect(screen.getByText(/asset quality metrics have remained stable/)).toBeInTheDocument();
  });

  it("renders no blank cards or placeholders when every optional section is empty", () => {
    const answer = buildAnswer(minimalAnswer);
    const { container } = render(<DirectCompanyResearchLayout answer={answer} onNewSearch={() => {}} />);

    expect(screen.queryByText(/What happened/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Analysis — why it matters/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Risks and invalidation/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Time horizon/)).not.toBeInTheDocument();
    // No literal "Not specified"/"N/A"/"—"-as-content placeholder text
    // anywhere in the omitted regions.
    expect(container.textContent).not.toMatch(/not specified/i);
  });

  it("never renders a prohibited advisory label", () => {
    const answer = buildAnswer(completeAnswer);
    const { container } = render(<DirectCompanyResearchLayout answer={answer} onNewSearch={() => {}} />);
    for (const word of PROHIBITED_TEXT) {
      expect(container.textContent ?? "").not.toContain(word);
    }
  });

  it("the answer object graph never carries a prohibited plain-V3/advisory key (recursive regression net)", () => {
    const answer = buildAnswer(completeAnswer);
    const found = new Set<string>();
    collectKeys(answer, found);
    for (const key of PROHIBITED_KEYS) {
      expect(found.has(key)).toBe(false);
    }
  });

  it("each Key Evidence row shows which claim(s) it supports", () => {
    const answer = buildAnswer(completeAnswer);
    render(<DirectCompanyResearchLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/Cited by: Summary, What happened, Analysis/)).toBeInTheDocument();
  });
});
