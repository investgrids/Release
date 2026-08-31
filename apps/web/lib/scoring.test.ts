import { describe, expect, it } from "vitest";
import { marketRippleScoreDisplayInt } from "./scoring";

/**
 * Company Page release audit fix, 2026-08-31 — the real, confirmed bug:
 * engine.py::_label_for computes the published rating from the raw,
 * unrounded score (score >= 60 -> "Positive", etc. — that threshold
 * logic is unchanged, tested backend-side in
 * test_marketripple_score.py::test_label_thresholds). Math.round() on
 * the DISPLAY integer could show a number that has visually crossed a
 * boundary (45/60/75) the raw score never actually reached (a real
 * historical case: ICICIBANK at 59.7 rendered "60/100 · Neutral",
 * contradicting the published "Positive >= 60" methodology).
 * Math.floor() cannot do this — a floored integer is always <= the raw
 * score, so it can never display as having crossed a threshold the raw
 * value hasn't reached. These tests exercise exactly the three real
 * boundaries named in the audit (45, 60, 75), one tick below and at
 * each, plus the null-safety contract every score helper in this file
 * follows.
 */
describe("marketRippleScoreDisplayInt", () => {
  it("returns null for a null/undefined score (never fabricates 0)", () => {
    expect(marketRippleScoreDisplayInt(null)).toBeNull();
    expect(marketRippleScoreDisplayInt(undefined)).toBeNull();
  });

  it("44.9 displays as 44, never 45 -- stays visually below the Neutral/Cautious boundary", () => {
    expect(marketRippleScoreDisplayInt(44.9)).toBe(44);
  });

  it("exactly 45 displays as 45 -- correctly at the boundary", () => {
    expect(marketRippleScoreDisplayInt(45)).toBe(45);
  });

  it("59.9 displays as 59, never 60 -- the exact real ICICIBANK-shaped case (59.7 in production)", () => {
    expect(marketRippleScoreDisplayInt(59.9)).toBe(59);
    expect(marketRippleScoreDisplayInt(59.7)).toBe(59);
  });

  it("exactly 60 displays as 60 -- correctly at the Positive boundary", () => {
    expect(marketRippleScoreDisplayInt(60)).toBe(60);
  });

  it("74.9 displays as 74, never 75 -- stays visually below the Strong boundary", () => {
    expect(marketRippleScoreDisplayInt(74.9)).toBe(74);
  });

  it("exactly 75 displays as 75 -- correctly at the Strong boundary", () => {
    expect(marketRippleScoreDisplayInt(75)).toBe(75);
  });
});
