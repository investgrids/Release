// Honest-classification fix (2026-10-17): isHighConviction must never treat
// a V1 item whose AI classification failed ("unclassified") as eligible for
// High Conviction, even when its score clears the 90 threshold -- missing/
// failed evidence must not silently produce maximum conviction. The
// pre-existing V2 "no confidence concept at all" bypass (confidence === null,
// classification_status undefined) must stay exactly as it was.
import { describe, expect, it } from "vitest";
import { isHighConviction } from "./radarLogic";

describe("isHighConviction — honest-classification fix", () => {
  it("rejects a V1 item with a high score whose classification is unclassified, even with confidence present", () => {
    expect(
      isHighConviction({ score: 98, confidence: 0.89, classification_status: "unclassified" })
    ).toBe(false);
  });

  it("rejects an unclassified item regardless of a null confidence value", () => {
    expect(
      isHighConviction({ score: 95, confidence: null, classification_status: "unclassified" })
    ).toBe(false);
  });

  it("still accepts a real V1 classified item with score >= 90 and confidence >= 0.85", () => {
    expect(
      isHighConviction({ score: 92, confidence: 0.88, classification_status: "classified" })
    ).toBe(true);
  });

  it("still rejects a real V1 classified item whose confidence is below 0.85", () => {
    expect(
      isHighConviction({ score: 92, confidence: 0.5, classification_status: "classified" })
    ).toBe(false);
  });

  it("V2 items (no classification_status field, null confidence) still qualify on score alone -- unchanged from before this fix", () => {
    expect(
      isHighConviction({ score: 91, confidence: null, classification_status: undefined })
    ).toBe(true);
  });

  it("rejects any item, classified or not, with a score below 90", () => {
    expect(isHighConviction({ score: 85, confidence: 0.95, classification_status: "classified" })).toBe(false);
    expect(isHighConviction({ score: 85, confidence: null, classification_status: undefined })).toBe(false);
  });
});
