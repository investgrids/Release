import { describe, it, expect } from "vitest";
import { deriveRippleStage } from "./rippleStage";

describe("deriveRippleStage — CD3-C Ripple scale-mismatch fix (2026-09-03)", () => {
  // ── The real production specimen CD3-C found ─────────────────────────────
  it("the real event_impact=0.9 specimen resolves to 'emerging', not a dead-code strong-momentum branch", () => {
    // Real specimen: /api/ripple/event/fed-b6a5befa779d returned
    // event_impact: 0.9 -- under the OLD >80 threshold this was already
    // "emerging" by accident (0.9 <= 80), but only because the threshold
    // was unreachable for ANY real value, not because the logic was
    // correct. Confirms the fix doesn't regress this specimen either way.
    expect(deriveRippleStage(0.9, null)).toBe("emerging");
  });

  // ── Boundary, both sides, on the real 0-10 scale ─────────────────────────
  it("exactly 8.0 does not trigger strong-momentum (strictly greater-than)", () => {
    expect(deriveRippleStage(8.0, null)).toBe("developing");
  });

  it("just above 8 triggers strong-momentum", () => {
    expect(deriveRippleStage(8.1, null)).toBe("strong-momentum");
  });

  it("exactly 6.0 does not trigger developing (strictly greater-than)", () => {
    expect(deriveRippleStage(6.0, null)).toBe("emerging");
  });

  it("just above 6 triggers developing", () => {
    expect(deriveRippleStage(6.1, null)).toBe("developing");
  });

  it("a real high-impact event (e.g. 9.5/10) correctly reaches strong-momentum", () => {
    expect(deriveRippleStage(9.5, null)).toBe("strong-momentum");
  });

  // ── The old (broken) 0-100-scale thresholds must not be reachable ───────
  it("no real 0-10 event_impact value can exceed 10 -- the max real magnitude is well under the old 80 threshold", () => {
    // Documents why the OLD code was dead: 10 (the ceiling of the real
    // scale) is nowhere near 80. This test exists so a future regression
    // (re-introducing a 0-100-scale threshold) fails loudly.
    expect(deriveRippleStage(10, null)).toBe("strong-momentum");
    expect(deriveRippleStage(10, null)).not.toBe("emerging");
  });

  // ── Null/undefined falls back to the qualitative ripple-strength text ───
  it("falls back to directStrength when event_impact is null", () => {
    expect(deriveRippleStage(null, "High")).toBe("strong-momentum");
    expect(deriveRippleStage(null, "Medium")).toBe("developing");
    expect(deriveRippleStage(null, "Low")).toBe("emerging");
  });

  it("falls back to emerging when both event_impact and directStrength are unavailable", () => {
    expect(deriveRippleStage(null, null)).toBe("emerging");
    expect(deriveRippleStage(undefined, undefined)).toBe("emerging");
  });

  it("a qualitative 'high' directStrength can still promote a mid-range numeric impact", () => {
    // Matches the original logic's OR semantics: either signal can trigger
    // the stronger stage, not just the numeric one.
    expect(deriveRippleStage(5, "High")).toBe("strong-momentum");
  });
});
