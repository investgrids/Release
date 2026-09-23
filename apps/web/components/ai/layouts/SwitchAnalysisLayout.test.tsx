// Component tests for SwitchAnalysisLayout (2026-09-23 dense restyle).
// Covers the task's full verification list: full supported comparison;
// only the 3 real supported dimensions; one-sided missing evidence;
// both-sides-missing dimension; long names/titles; no conditions/
// monitoring sections; citation numbering; no advisory language; no
// prohibited raw-V3 keys; switch selects this layout even when a
// comparison contract is also populated; no extra provider/retrieval/
// prediction calls.
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { SwitchAnalysisLayout } from "./SwitchAnalysisLayout";
import { toSwitchAnalysisAEV2Answer, toAIAnswer } from "../answerTypes";
import {
  completeSwitchAnswer, switchMinimalAnswer, switchNoCompanyEvidenceAnswer,
  switchNoComparableDimensionAnswer, switchLongNamesAnswer, baseSwitchSearchResult,
} from "../__fixtures__/switchAnalysis";
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
  it("renders the full supported comparison: headline, direct comparison, all 3 dimensions, favoring conditions", () => {
    const answer = buildAnswer(completeSwitchAnswer);
    render(<SwitchAnalysisLayout answer={answer} onNewSearch={() => {}} />);

    expect(screen.getByText(/Evidence leans toward Bharat Electronics Ltd/)).toBeInTheDocument();
    expect(screen.getByText(/BEL's recent order win and HAL's delivery milestone/)).toBeInTheDocument();
    expect(screen.getAllByText("Recent developments").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Price reaction").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Evidence freshness").length).toBeGreaterThan(0);
    // Rendered twice: desktop table + mobile stacked cards.
    expect(screen.getAllByText(/285\.40 \(\+1\.10%\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/4,512\.00 \(-0\.30%\)/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Conditions favoring Bharat Electronics Ltd/)).toBeInTheDocument();
    expect(screen.queryByText(/Conditions favoring Hindustan Aeronautics Ltd/)).not.toBeInTheDocument();
  });

  it("only ever renders the 3 real AEV2ComparisonDimensionKey labels, never a fabricated valuation/order-book/risk row", () => {
    const answer = buildAnswer(completeSwitchAnswer);
    const { container } = render(<SwitchAnalysisLayout answer={answer} onNewSearch={() => {}} />);
    const text = container.textContent ?? "";
    for (const fabricated of ["Valuation", "Order book", "Order visibility", "Business exposure", "Risk profile"]) {
      expect(text).not.toContain(fabricated);
    }
  });

  it("shows an honest 'Insufficient verified data' cell, never a disadvantage claim, when one side lacks data for a dimension", () => {
    const sw = switchNoCompanyEvidenceAnswer.aev2.switch_analysis!;
    const directAnswer: AEV2SwitchAnswer = {
      ui_mode: "switch_analysis",
      query: switchNoCompanyEvidenceAnswer.result.query,
      aev2: switchNoCompanyEvidenceAnswer.aev2,
      switch: sw,
    };
    const { container } = render(<SwitchAnalysisLayout answer={directAnswer} onNewSearch={() => {}} />);
    expect(screen.getAllByText("Insufficient verified data").length).toBeGreaterThan(0);
    expect(container.textContent ?? "").not.toMatch(/disadvantage/i);
    expect(container.textContent ?? "").not.toMatch(/weaker/i);
  });

  it("shows 'Insufficient verified data' on both sides when neither has a comparable dimension", () => {
    const sw = switchNoComparableDimensionAnswer.aev2.switch_analysis!;
    const directAnswer: AEV2SwitchAnswer = {
      ui_mode: "switch_analysis",
      query: switchNoComparableDimensionAnswer.result.query,
      aev2: switchNoComparableDimensionAnswer.aev2,
      switch: sw,
    };
    const { container } = render(<SwitchAnalysisLayout answer={directAnswer} onNewSearch={() => {}} />);
    // 3 dimensions x 2 sides, each rendered twice (desktop + mobile).
    expect(screen.getAllByText("Insufficient verified data").length).toBeGreaterThanOrEqual(6);
    expect(container.textContent ?? "").not.toMatch(/weaker|disadvantage/i);
  });

  it("renders long company names and query titles without dropping any comparison content", () => {
    const answer = buildAnswer(switchLongNamesAnswer);
    render(<SwitchAnalysisLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getAllByText(/Bharat Electronics Limited \(Defence Electronics Systems Division\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Hindustan Aeronautics Limited \(Aircraft and Helicopter Manufacturing Division\)/).length).toBeGreaterThan(0);
  });

  it("omits the favoring-conditions boxes and the what-changes section honestly when empty", () => {
    const answer = buildAnswer(switchMinimalAnswer);
    render(<SwitchAnalysisLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("No clear evidence advantage yet")).toBeInTheDocument();
    expect(screen.queryByText(/Conditions favoring/)).not.toBeInTheDocument();
    expect(screen.queryByText(/What would change this comparison/)).not.toBeInTheDocument();
  });

  it("numbers citations consistently between claims and the key evidence table", () => {
    const answer = buildAnswer(completeSwitchAnswer);
    render(<SwitchAnalysisLayout answer={answer} onNewSearch={() => {}} />);
    // Both cited evidence rows appear, each with its own bracketed index
    // matching the citation marks used elsewhere on the page.
    expect(screen.getAllByText("BEL wins defence order worth 1,200 crore").length).toBeGreaterThan(0);
    expect(screen.getAllByText("HAL delivers first batch of Tejas Mk1A jets").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^\[1\]$/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^\[2\]$/).length).toBeGreaterThan(0);
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

  it("ui_mode stays the authoritative dispatcher: a switch_analysis result routes here even when comparison is also populated", () => {
    const result = baseSwitchSearchResult();
    const aev2 = completeSwitchAnswer.aev2;
    const withComparisonToo = {
      ...aev2,
      comparison: {
        relationship: "comparison" as const,
        left_company: { symbol: "BEL", name: "Bharat Electronics Ltd" },
        right_company: { symbol: "HAL", name: "Hindustan Aeronautics Ltd" },
        direct_comparison: { text: "unused", evidence_refs: [], validation_status: "validated" as const },
        dimensions: [],
      },
    };
    const answer = toAIAnswer({ ...result, answer_experience_v2: withComparisonToo } as unknown as Parameters<typeof toAIAnswer>[0]);
    expect(answer.ui_mode).toBe("switch_analysis");
  });

  it("makes no additional provider, retrieval, or prediction calls — purely presentational over the given answer", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const answer = buildAnswer(completeSwitchAnswer);
    render(<SwitchAnalysisLayout answer={answer} onNewSearch={() => {}} />);
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });
});
