// Component tests for SwitchAnalysisLayout (2026-09-22). Mirrors
// DirectCompanyResearchLayout.test.tsx's structure: real content
// renders, optional sections are omitted honestly (no placeholders,
// no "disadvantage" framing for missing data), and no prohibited
// plain-V3/advisory concept can surface.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { SwitchAnalysisLayout } from "./SwitchAnalysisLayout";
import { toSwitchAnalysisAEV2Answer } from "../answerTypes";
import { completeSwitchAnswer, switchMinimalAnswer, switchNoCompanyEvidenceAnswer } from "../__fixtures__/switchAnalysis";
import type { AEV2SwitchAnswer } from "../answerTypes";

function buildAnswer(fixture: typeof completeSwitchAnswer): AEV2SwitchAnswer {
  const answer = toSwitchAnalysisAEV2Answer(fixture.result, fixture.aev2);
  if (answer.ui_mode !== "switch_analysis") {
    throw new Error("fixture expected to be eligible for switch_analysis");
  }
  return answer;
}

const PROHIBITED_TEXT = [
  "Buy", "Sell", "Hold", "Verdict", "Recommendation",
  "Investment Watch", "Current Research",
];

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

describe("SwitchAnalysisLayout", () => {
  it("renders the headline, direct comparison, dimension table, and favoring conditions", () => {
    const answer = buildAnswer(completeSwitchAnswer);
    render(<SwitchAnalysisLayout answer={answer} onNewSearch={() => {}} />);

    expect(screen.getByText(/Evidence leans toward Bharat Electronics Ltd/)).toBeInTheDocument();
    expect(screen.getByText(/BEL's recent order win and HAL's delivery milestone/)).toBeInTheDocument();
    expect(screen.getByText("Recent developments")).toBeInTheDocument();
    expect(screen.getByText("Price reaction")).toBeInTheDocument();
    // Appears twice: the dimension table AND the sidebar entity snapshot.
    expect(screen.getAllByText(/285\.40 \(\+1\.10%\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/4,512\.00 \(-0\.30%\)/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Conditions favoring Bharat Electronics Ltd/)).toBeInTheDocument();
    expect(screen.queryByText(/Conditions favoring Hindustan Aeronautics Ltd/)).not.toBeInTheDocument();
  });

  it("shows an honest 'No data available' cell, never a disadvantage claim, when one side lacks data for a dimension", () => {
    // This fixture is ineligible per the gate (no_company_evidence), so
    // exercise the layout directly against its raw switch data instead
    // of going through the gate, to test the cell-rendering behavior in
    // isolation.
    const sw = switchNoCompanyEvidenceAnswer.aev2.switch_analysis!;
    const directAnswer: AEV2SwitchAnswer = {
      ui_mode: "switch_analysis",
      query: switchNoCompanyEvidenceAnswer.result.query,
      aev2: switchNoCompanyEvidenceAnswer.aev2,
      switch: sw,
    };
    const { container } = render(<SwitchAnalysisLayout answer={directAnswer} onNewSearch={() => {}} />);
    expect(screen.getAllByText("No data available").length).toBeGreaterThan(0);
    expect(container.textContent ?? "").not.toMatch(/disadvantage/i);
    expect(container.textContent ?? "").not.toMatch(/weaker/i);
  });

  it("omits the favoring-conditions boxes and the what-changes section honestly when empty", () => {
    const answer = buildAnswer(switchMinimalAnswer);
    render(<SwitchAnalysisLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("No clear evidence advantage yet")).toBeInTheDocument();
    expect(screen.queryByText(/Conditions favoring/)).not.toBeInTheDocument();
    expect(screen.queryByText(/What would change this comparison/)).not.toBeInTheDocument();
  });

  it("never renders a prohibited advisory label", () => {
    const answer = buildAnswer(completeSwitchAnswer);
    const { container } = render(<SwitchAnalysisLayout answer={answer} onNewSearch={() => {}} />);
    for (const word of PROHIBITED_TEXT) {
      expect(container.textContent ?? "").not.toContain(word);
    }
  });

  it("the answer object graph never carries a prohibited plain-V3/advisory key (recursive regression net)", () => {
    const answer = buildAnswer(completeSwitchAnswer);
    const found = new Set<string>();
    collectKeys(answer, found);
    for (const key of PROHIBITED_KEYS) {
      expect(found.has(key)).toBe(false);
    }
  });
});
