import { describe, expect, it } from "vitest";
import { isHighConviction } from "./radarLogic";

describe("isHighConviction — V2-compatibility fix (2026-09-20)", () => {
  it("qualifies a V1 item with both a high score and a real high confidence", () => {
    expect(isHighConviction({ score: 92, confidence: 0.9 })).toBe(true);
  });

  it("disqualifies a V1 item with a high score but a real low confidence (unchanged V1 behavior)", () => {
    expect(isHighConviction({ score: 95, confidence: 0.5 })).toBe(false);
  });

  it("disqualifies a low-score item regardless of confidence", () => {
    expect(isHighConviction({ score: 40, confidence: 0.99 })).toBe(false);
  });

  it("qualifies a V2 item (confidence null, no such concept) on a high real score alone", () => {
    expect(isHighConviction({ score: 91, confidence: null })).toBe(true);
  });

  it("does not fabricate a pass for a V2 item with a low real score", () => {
    expect(isHighConviction({ score: 60, confidence: null })).toBe(false);
  });

  it("treats a missing score the same as a V1 item with no score (never qualifies)", () => {
    expect(isHighConviction({ score: null, confidence: 0.9 })).toBe(false);
    expect(isHighConviction({ score: null, confidence: null })).toBe(false);
  });
});
