// comparison's minimum eligibility contract (2026-09-22). Exercises
// toComparisonAEV2Answer directly against hand-authored fixtures
// mirroring aev2/comparison.py's real assemble_comparison() output — no
// live HTTP path exists yet (AEV2_BUILD_COMPLETE is False), so these
// fixtures ARE the test surface.
import { describe, it, expect } from "vitest";
import { toComparisonAEV2Answer, toAIAnswer, IMPLEMENTED_UI_MODES } from "./answerTypes";
import {
  completeComparisonAnswer, notComparisonShapedAnswer, comparisonWrongEntityCountAnswer,
  comparisonEntityMismatchAnswer, comparisonNoCompanyEvidenceAnswer, comparisonUnvalidatedAnswer,
  comparisonSynthesisIncompleteAnswer, reversedOrderComparisonAnswer,
} from "./__fixtures__/comparison";

describe("toComparisonAEV2Answer — eligibility contract", () => {
  it("9. accepts a complete, validated, cited two-company comparison", () => {
    const answer = toComparisonAEV2Answer(completeComparisonAnswer.result, completeComparisonAnswer.aev2);
    expect(answer.ui_mode).toBe("company_comparison");
  });

  it("1. preserves the query's own entity order (left_company is whatever the backend resolved first, never re-sorted here)", () => {
    const answer = toComparisonAEV2Answer(reversedOrderComparisonAnswer.result, reversedOrderComparisonAnswer.aev2);
    expect(answer.ui_mode).toBe("company_comparison");
    if (answer.ui_mode === "company_comparison") {
      expect(answer.comparison.left_company.symbol).toBe("TCS");
      expect(answer.comparison.right_company.symbol).toBe("INFY");
    }
  });

  it("rejects when the backend never assembled a comparison for this query", () => {
    const answer = toComparisonAEV2Answer(notComparisonShapedAnswer.result, notComparisonShapedAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_not_comparison_shaped");
  });

  it("10. fails honestly when the query doesn't resolve to exactly two companies", () => {
    const answer = toComparisonAEV2Answer(comparisonWrongEntityCountAnswer.result, comparisonWrongEntityCountAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_wrong_entity_count");
  });

  it("rejects when AEV2's roles don't match the companies V3 itself resolved", () => {
    const answer = toComparisonAEV2Answer(comparisonEntityMismatchAnswer.result, comparisonEntityMismatchAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_entity_mismatch");
  });

  it("6. rejects when one company has no attributable evidence", () => {
    const answer = toComparisonAEV2Answer(comparisonNoCompanyEvidenceAnswer.result, comparisonNoCompanyEvidenceAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_no_company_evidence");
  });

  it("8. rejects an unvalidated/uncited direct_comparison claim (advisory language fails closed)", () => {
    const answer = toComparisonAEV2Answer(comparisonUnvalidatedAnswer.result, comparisonUnvalidatedAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_unvalidated_conclusion");
  });

  it("a degraded (synthesis_incomplete) response never reaches the successful layout", () => {
    const answer = toComparisonAEV2Answer(comparisonSynthesisIncompleteAnswer.result, comparisonSynthesisIncompleteAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("synthesis_incomplete");
  });

  it("14. company_comparison is wired through the live toAIAnswer()/SearchResults path once answer_experience_v2 is attached (2026-09-22, activation-wiring commit)", () => {
    expect(IMPLEMENTED_UI_MODES.has("company_comparison")).toBe(true);
    const withPayload = toAIAnswer({ ...completeComparisonAnswer.result, answer_experience_v2: completeComparisonAnswer.aev2 });
    expect(withPayload.ui_mode).toBe("company_comparison");
  });

  it("company_comparison degrades honestly on aev2_unavailable when the backend didn't attach a payload — today's ALWAYS case in real production traffic (AEV2_BUILD_COMPLETE stays False)", () => {
    const withoutPayload = toAIAnswer(completeComparisonAnswer.result);
    expect(withoutPayload.ui_mode).toBe("degraded");
    if (withoutPayload.ui_mode === "degraded") expect(withoutPayload.reason).toBe("aev2_unavailable");
  });

  it("13. is a pure function — identical input twice yields deep-equal output, no fixture mutation", () => {
    const first = toComparisonAEV2Answer(completeComparisonAnswer.result, completeComparisonAnswer.aev2);
    const snapshot = JSON.parse(JSON.stringify(completeComparisonAnswer.aev2));
    const second = toComparisonAEV2Answer(completeComparisonAnswer.result, completeComparisonAnswer.aev2);
    expect(first).toEqual(second);
    expect(completeComparisonAnswer.aev2).toEqual(snapshot);
  });
});
