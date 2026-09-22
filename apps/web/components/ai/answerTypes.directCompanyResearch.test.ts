// direct_company_research's minimum eligibility contract (2026-09-22).
// Exercises toDirectCompanyResearchAEV2Answer directly against
// hand-authored fixtures mirroring assemble_aev2()'s real output — there
// is no live HTTP path to this data yet (AEV2_BUILD_COMPLETE is False),
// so these fixtures ARE the test surface, not a stand-in for one.
import { describe, it, expect } from "vitest";
import { toDirectCompanyResearchAEV2Answer } from "./answerTypes";
import {
  completeAnswer, noPriceDataAnswer, noCompanyEvidenceAnswer, citationInvalidAnswer,
  advisoryLanguageAnswer, twoCompanyAnswer, synthesisIncompleteAnswer, minimalAnswer,
  entityMismatchAnswer, noEntityAnswer,
} from "./__fixtures__/directCompanyResearch";

describe("toDirectCompanyResearchAEV2Answer — eligibility contract", () => {
  it("1. accepts a complete company answer with citations and price provenance", () => {
    const answer = toDirectCompanyResearchAEV2Answer(completeAnswer.result, completeAnswer.aev2);
    expect(answer.ui_mode).toBe("direct_company_research");
  });

  it("2. accepts a partial answer with no price data (price section is a rendering concern, not an eligibility gate)", () => {
    const answer = toDirectCompanyResearchAEV2Answer(noPriceDataAnswer.result, noPriceDataAnswer.aev2);
    expect(answer.ui_mode).toBe("direct_company_research");
  });

  it("3. fails closed with no attributable company evidence", () => {
    const answer = toDirectCompanyResearchAEV2Answer(noCompanyEvidenceAnswer.result, noCompanyEvidenceAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_no_company_evidence");
  });

  it("4. fails closed on a citation-invalid conclusion", () => {
    const answer = toDirectCompanyResearchAEV2Answer(citationInvalidAnswer.result, citationInvalidAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_unvalidated_conclusion");
  });

  it("5. fails closed when advisory language was present", () => {
    const answer = toDirectCompanyResearchAEV2Answer(advisoryLanguageAnswer.result, advisoryLanguageAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_unvalidated_conclusion");
  });

  it("6. rejects a two-company query incorrectly labeled direct-company", () => {
    const answer = toDirectCompanyResearchAEV2Answer(twoCompanyAnswer.result, twoCompanyAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_multi_entity");
  });

  it("rejects when zero companies resolved", () => {
    const answer = toDirectCompanyResearchAEV2Answer(noEntityAnswer.result, noEntityAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_no_entity");
  });

  it("rejects when AEV2 attributed a different company than the one V3 resolved", () => {
    const answer = toDirectCompanyResearchAEV2Answer(entityMismatchAnswer.result, entityMismatchAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_entity_mismatch");
  });

  it("9. a degraded (synthesis_incomplete) response never reaches the successful layout", () => {
    const answer = toDirectCompanyResearchAEV2Answer(synthesisIncompleteAnswer.result, synthesisIncompleteAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("synthesis_incomplete");
  });

  it("10. accepts an answer with every optional section empty (component owns the omission, not this gate)", () => {
    const answer = toDirectCompanyResearchAEV2Answer(minimalAnswer.result, minimalAnswer.aev2);
    expect(answer.ui_mode).toBe("direct_company_research");
  });

  it("7. is a pure function — identical input twice yields deep-equal output, no fixture mutation", () => {
    const first = toDirectCompanyResearchAEV2Answer(completeAnswer.result, completeAnswer.aev2);
    const aev2Snapshot = JSON.parse(JSON.stringify(completeAnswer.aev2));
    const second = toDirectCompanyResearchAEV2Answer(completeAnswer.result, completeAnswer.aev2);
    expect(first).toEqual(second);
    expect(completeAnswer.aev2).toEqual(aev2Snapshot);
  });
});
