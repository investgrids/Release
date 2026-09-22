// switch_analysis's minimum eligibility contract (2026-09-22). Exercises
// toSwitchAnalysisAEV2Answer directly against hand-authored fixtures
// mirroring aev2/switch_analysis.py's real assemble_switch_analysis()
// output — no live HTTP path exists yet (AEV2_BUILD_COMPLETE is False),
// so these fixtures ARE the test surface.
import { describe, it, expect } from "vitest";
import { toSwitchAnalysisAEV2Answer, toAIAnswer, IMPLEMENTED_UI_MODES } from "./answerTypes";
import {
  completeSwitchAnswer, notSwitchShapedAnswer, wrongEntityCountAnswer,
  switchEntityMismatchAnswer, switchNoCompanyEvidenceAnswer, switchUnvalidatedAnswer,
  switchNoComparableDimensionAnswer, switchSynthesisIncompleteAnswer,
  switchPriceOnlyComparableAnswer, switchMinimalAnswer,
} from "./__fixtures__/switchAnalysis";

describe("toSwitchAnalysisAEV2Answer — eligibility contract", () => {
  it("accepts a complete, validated, cited switch comparison", () => {
    const answer = toSwitchAnalysisAEV2Answer(completeSwitchAnswer.result, completeSwitchAnswer.aev2);
    expect(answer.ui_mode).toBe("switch_analysis");
  });

  it("rejects when the backend never assembled a switch comparison for this query", () => {
    const answer = toSwitchAnalysisAEV2Answer(notSwitchShapedAnswer.result, notSwitchShapedAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_not_switch_shaped");
  });

  it("rejects when the query doesn't resolve to exactly two companies", () => {
    const answer = toSwitchAnalysisAEV2Answer(wrongEntityCountAnswer.result, wrongEntityCountAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_wrong_entity_count");
  });

  it("rejects when AEV2's roles don't match the companies V3 itself resolved", () => {
    const answer = toSwitchAnalysisAEV2Answer(switchEntityMismatchAnswer.result, switchEntityMismatchAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_entity_mismatch");
  });

  it("rejects when one company has no attributable evidence", () => {
    const answer = toSwitchAnalysisAEV2Answer(switchNoCompanyEvidenceAnswer.result, switchNoCompanyEvidenceAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_no_company_evidence");
  });

  it("rejects an unvalidated/uncited direct_comparison claim", () => {
    const answer = toSwitchAnalysisAEV2Answer(switchUnvalidatedAnswer.result, switchUnvalidatedAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_unvalidated_conclusion");
  });

  it("rejects when no dimension is comparable at all (via the attributable-evidence check, since recent_developments is always checked first)", () => {
    // With today's fixed 3-dimension set, recent_developments not being
    // comparable always trips ineligible_no_company_evidence before the
    // separate "any dimension comparable" check ever runs — see
    // toSwitchAnalysisAEV2Answer's own comment on why both checks stay
    // in the code even though the second is currently unreachable with
    // this exact dimension set.
    const answer = toSwitchAnalysisAEV2Answer(switchNoComparableDimensionAnswer.result, switchNoComparableDimensionAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_no_company_evidence");
  });

  it("rejects on attributable-evidence grounds even when price_reaction alone is comparable", () => {
    // recent_developments not comparable -> ineligible_no_company_evidence
    // takes priority over the more general "a comparable dimension exists"
    // check, since "both companies have attributable evidence" is its own
    // distinct requirement in the eligibility contract.
    const answer = toSwitchAnalysisAEV2Answer(switchPriceOnlyComparableAnswer.result, switchPriceOnlyComparableAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_no_company_evidence");
  });

  it("a degraded (synthesis_incomplete) response never reaches the successful layout", () => {
    const answer = toSwitchAnalysisAEV2Answer(switchSynthesisIncompleteAnswer.result, switchSynthesisIncompleteAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("synthesis_incomplete");
  });

  it("accepts an answer with every optional condition/monitoring list empty", () => {
    const answer = toSwitchAnalysisAEV2Answer(switchMinimalAnswer.result, switchMinimalAnswer.aev2);
    expect(answer.ui_mode).toBe("switch_analysis");
  });

  it("is a pure function — identical input twice yields deep-equal output, no fixture mutation", () => {
    const first = toSwitchAnalysisAEV2Answer(completeSwitchAnswer.result, completeSwitchAnswer.aev2);
    const snapshot = JSON.parse(JSON.stringify(completeSwitchAnswer.aev2));
    const second = toSwitchAnalysisAEV2Answer(completeSwitchAnswer.result, completeSwitchAnswer.aev2);
    expect(first).toEqual(second);
    expect(completeSwitchAnswer.aev2).toEqual(snapshot);
  });

  it("switch_analysis is wired through the live toAIAnswer()/SearchResults path once answer_experience_v2 is attached (2026-09-22, activation-wiring commit)", () => {
    expect(IMPLEMENTED_UI_MODES.has("switch_analysis")).toBe(true);
    const withPayload = toAIAnswer({ ...completeSwitchAnswer.result, answer_experience_v2: completeSwitchAnswer.aev2 });
    expect(withPayload.ui_mode).toBe("switch_analysis");
  });

  it("switch_analysis degrades honestly on aev2_unavailable when the backend didn't attach a payload — today's ALWAYS case in real production traffic (AEV2_BUILD_COMPLETE stays False)", () => {
    const withoutPayload = toAIAnswer(completeSwitchAnswer.result);
    expect(withoutPayload.ui_mode).toBe("degraded");
    if (withoutPayload.ui_mode === "degraded") expect(withoutPayload.reason).toBe("aev2_unavailable");
  });
});
