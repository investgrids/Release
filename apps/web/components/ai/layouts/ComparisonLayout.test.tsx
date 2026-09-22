// Component tests for ComparisonLayout (2026-09-22). Proves the neutral
// comparison layout never inherits switch vocabulary, structurally
// cannot surface a prohibited plain-V3/advisory concept, and renders
// entity order + honest missing-data handling correctly.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ComparisonLayout } from "./ComparisonLayout";
import { toComparisonAEV2Answer } from "../answerTypes";
import {
  completeComparisonAnswer, comparisonNoCompanyEvidenceAnswer, reversedOrderComparisonAnswer,
} from "../__fixtures__/comparison";
import type { AEV2ComparisonAnswer } from "../answerTypes";

function buildAnswer(fixture: typeof completeComparisonAnswer): AEV2ComparisonAnswer {
  const answer = toComparisonAEV2Answer(fixture.result, fixture.aev2);
  if (answer.ui_mode !== "company_comparison") {
    throw new Error("fixture expected to be eligible for company_comparison");
  }
  return answer;
}

const PROHIBITED_TEXT = [
  "Buy", "Sell", "Hold", "Verdict", "Recommendation",
  "Investment Watch", "Current Research",
];

// The approved spec's own prohibited-vocabulary list for standard
// comparison — matched case-insensitively against rendered text, since
// none of these phrases should appear regardless of casing.
const PROHIBITED_SWITCH_TERMS = [
  "current holding", "alternative", "switch", "stay with", "move to",
  "conditions favoring switching",
];

const PROHIBITED_KEYS = [
  "investment_verdict", "engine_verdict", "rating", "suitable_for",
  "risk_level", "top_picks", "scenarios", "confidence_self_rating", "raw",
  "current_company", "alternative_company", "switch_holding", "switch_target",
  "conditions_favoring_current", "conditions_favoring_alternative",
  "what_changes_the_comparison",
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

describe("ComparisonLayout", () => {
  it("renders the direct comparison and the dimension table for both companies", () => {
    const answer = buildAnswer(completeComparisonAnswer);
    render(<ComparisonLayout answer={answer} onNewSearch={() => {}} />);

    expect(screen.getByText("Infosys Ltd vs Tata Consultancy Services Ltd")).toBeInTheDocument();
    expect(screen.getByText(/Infosys's digital transformation win and TCS's new AI research center/)).toBeInTheDocument();
    expect(screen.getByText("Recent developments")).toBeInTheDocument();
    expect(screen.getByText("Price reaction")).toBeInTheDocument();
    expect(screen.getAllByText(/1,845\.20 \(\+0\.60%\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/4,102\.50 \(-0\.20%\)/).length).toBeGreaterThan(0);
  });

  it("1. preserves the user's entity order — the reversed-order fixture shows TCS first, not alphabetized", () => {
    const answer = buildAnswer(reversedOrderComparisonAnswer);
    render(<ComparisonLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("Tata Consultancy Services Ltd vs Infosys Ltd")).toBeInTheDocument();
  });

  it("4. shows an honest 'No data available' cell, never a disadvantage claim, when one side lacks data", () => {
    const cmp = comparisonNoCompanyEvidenceAnswer.aev2.comparison!;
    const directAnswer: AEV2ComparisonAnswer = {
      ui_mode: "company_comparison",
      query: comparisonNoCompanyEvidenceAnswer.result.query,
      aev2: comparisonNoCompanyEvidenceAnswer.aev2,
      comparison: cmp,
    };
    const { container } = render(<ComparisonLayout answer={directAnswer} onNewSearch={() => {}} />);
    expect(screen.getAllByText("No data available").length).toBeGreaterThan(0);
    expect(container.textContent ?? "").not.toMatch(/disadvantage/i);
    expect(container.textContent ?? "").not.toMatch(/weaker/i);
  });

  it("2 & 11. never renders switch terminology or a favoring/what-changes section (no leakage from switch logic)", () => {
    const answer = buildAnswer(completeComparisonAnswer);
    const { container } = render(<ComparisonLayout answer={answer} onNewSearch={() => {}} />);
    const text = (container.textContent ?? "").toLowerCase();
    for (const term of PROHIBITED_SWITCH_TERMS) {
      expect(text).not.toContain(term);
    }
    expect(screen.queryByText(/Conditions favoring/)).not.toBeInTheDocument();
    expect(screen.queryByText(/What would change this comparison/)).not.toBeInTheDocument();
  });

  it("never renders a prohibited advisory label", () => {
    const answer = buildAnswer(completeComparisonAnswer);
    const { container } = render(<ComparisonLayout answer={answer} onNewSearch={() => {}} />);
    for (const word of PROHIBITED_TEXT) {
      expect(container.textContent ?? "").not.toContain(word);
    }
  });

  it("12. the answer object graph never carries a prohibited plain-V3/switch key (recursive regression net)", () => {
    const answer = buildAnswer(completeComparisonAnswer);
    const found = new Set<string>();
    collectKeys(answer, found);
    for (const key of PROHIBITED_KEYS) {
      expect(found.has(key)).toBe(false);
    }
  });

  it("each Key Evidence row shows which claim it supports", () => {
    const answer = buildAnswer(completeComparisonAnswer);
    render(<ComparisonLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getAllByText(/Cited by: Comparison/).length).toBeGreaterThan(0);
  });
});
