// event_impact's minimum eligibility contract (2026-09-22). Exercises
// toEventImpactAEV2Answer directly against hand-authored fixtures
// mirroring aev2/event_impact.py's real assemble_event_impact() output
// — no live HTTP path exists yet (AEV2_BUILD_COMPLETE is False), so
// these fixtures ARE the test surface.
import { describe, it, expect } from "vitest";
import { toEventImpactAEV2Answer, toAIAnswer, IMPLEMENTED_UI_MODES } from "./answerTypes";
import {
  completeEventImpactAnswer, notEventShapedAnswer, eventImpactWrongEventCountAnswer,
  eventImpactEntityMismatchAnswer, eventImpactNoCompanyEvidenceAnswer, eventImpactUnvalidatedAnswer,
  eventImpactSynthesisIncompleteAnswer, eventImpactNoSectorsAnswer, eventImpactNoPriceDataAnswer,
} from "./__fixtures__/eventImpact";

describe("toEventImpactAEV2Answer — eligibility contract", () => {
  it("accepts a complete, validated, cited single-event answer", () => {
    const answer = toEventImpactAEV2Answer(completeEventImpactAnswer.result, completeEventImpactAnswer.aev2);
    expect(answer.ui_mode).toBe("event_impact");
    if (answer.ui_mode === "event_impact") {
      expect(answer.eventImpact.event.id).toBe("e-reliance-1");
    }
  });

  it("rejects when the backend never assembled an event_impact object at all", () => {
    const answer = toEventImpactAEV2Answer(notEventShapedAnswer.result, notEventShapedAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_not_event_shaped");
  });

  it("two resolved Events fail honestly", () => {
    const answer = toEventImpactAEV2Answer(
      eventImpactWrongEventCountAnswer.result, eventImpactWrongEventCountAnswer.aev2,
    );
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_wrong_event_count");
  });

  it("rejects when AEV2 cited a different Event than the one V3 itself resolved", () => {
    const answer = toEventImpactAEV2Answer(
      eventImpactEntityMismatchAnswer.result, eventImpactEntityMismatchAnswer.aev2,
    );
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_entity_mismatch");
  });

  it("rejects when there is no company attribution", () => {
    const answer = toEventImpactAEV2Answer(
      eventImpactNoCompanyEvidenceAnswer.result, eventImpactNoCompanyEvidenceAnswer.aev2,
    );
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_no_company_evidence");
  });

  it("rejects an unvalidated/uncited direct_conclusion claim (advisory language fails closed)", () => {
    const answer = toEventImpactAEV2Answer(eventImpactUnvalidatedAnswer.result, eventImpactUnvalidatedAnswer.aev2);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_unvalidated_conclusion");
  });

  it("a degraded (synthesis_incomplete) response never reaches the successful layout", () => {
    const answer = toEventImpactAEV2Answer(
      eventImpactSynthesisIncompleteAnswer.result, eventImpactSynthesisIncompleteAnswer.aev2,
    );
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("synthesis_incomplete");
  });

  it("optional sectors are omitted cleanly, never a rejection", () => {
    const answer = toEventImpactAEV2Answer(eventImpactNoSectorsAnswer.result, eventImpactNoSectorsAnswer.aev2);
    expect(answer.ui_mode).toBe("event_impact");
    if (answer.ui_mode === "event_impact") expect(answer.eventImpact.linked_sectors).toEqual([]);
  });

  it("missing price data still succeeds", () => {
    const answer = toEventImpactAEV2Answer(eventImpactNoPriceDataAnswer.result, eventImpactNoPriceDataAnswer.aev2);
    expect(answer.ui_mode).toBe("event_impact");
    if (answer.ui_mode === "event_impact") expect(answer.eventImpact.observed_reactions).toEqual([]);
  });

  it("event_impact stays unavailable through the live toAIAnswer()/SearchResults path — no HTTP or SearchResults exposure", () => {
    expect(IMPLEMENTED_UI_MODES.has("event_impact")).toBe(false);
    const liveAnswer = toAIAnswer(completeEventImpactAnswer.result);
    expect(liveAnswer.ui_mode).toBe("degraded");
    if (liveAnswer.ui_mode === "degraded") expect(liveAnswer.reason).toBe("not_yet_implemented");
  });

  it("is a pure function — identical input twice yields deep-equal output, no fixture mutation", () => {
    const first = toEventImpactAEV2Answer(completeEventImpactAnswer.result, completeEventImpactAnswer.aev2);
    const snapshot = JSON.parse(JSON.stringify(completeEventImpactAnswer.aev2));
    const second = toEventImpactAEV2Answer(completeEventImpactAnswer.result, completeEventImpactAnswer.aev2);
    expect(first).toEqual(second);
    expect(completeEventImpactAnswer.aev2).toEqual(snapshot);
  });
});
