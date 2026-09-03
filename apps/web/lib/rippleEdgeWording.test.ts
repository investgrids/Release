import { describe, it, expect } from "vitest";
import { rippleEdgeDisplay } from "./rippleEdgeWording";

describe("rippleEdgeDisplay — CD3-D (D4) Ripple causality wording", () => {
  it("observed + real relationship renders the relationship as a direct claim", () => {
    expect(rippleEdgeDisplay("observed", "causes")).toEqual({ label: "causes", asserts: true });
  });

  it("supported renders a hedged mechanism phrase, not a bare relationship word", () => {
    expect(rippleEdgeDisplay("supported", "hurts")).toEqual({
      label: "may transmit through hurts", asserts: true,
    });
  });

  it("hypothesized renders a generic hedge, never the raw relationship as fact", () => {
    const result = rippleEdgeDisplay("hypothesized", "causes");
    expect(result.label).toBe("possible link");
    expect(result.asserts).toBe(false);
    expect(result.label).not.toContain("causes");
  });

  it("unavailable asserts no relationship at all", () => {
    expect(rippleEdgeDisplay("unavailable", "causes")).toEqual({
      label: "no confirmed relationship", asserts: false,
    });
  });

  it("unknown/unrecognized evidence_state fails closed the same as unavailable", () => {
    expect(rippleEdgeDisplay("unknown", "causes").asserts).toBe(false);
    expect(rippleEdgeDisplay(null, "causes").asserts).toBe(false);
    expect(rippleEdgeDisplay(undefined, "causes").asserts).toBe(false);
    expect(rippleEdgeDisplay("garbage", "causes").asserts).toBe(false);
  });

  it("THE CORE ADVERSARIAL CASE — missing relationship never defaults to 'causes', for any evidence_state", () => {
    expect(rippleEdgeDisplay("observed", undefined)).toEqual({ label: "no confirmed relationship", asserts: false });
    expect(rippleEdgeDisplay("observed", null)).toEqual({ label: "no confirmed relationship", asserts: false });
    expect(rippleEdgeDisplay("observed", "")).toEqual({ label: "no confirmed relationship", asserts: false });
    expect(rippleEdgeDisplay("supported", undefined).label).not.toBe("causes");
    expect(rippleEdgeDisplay("hypothesized", undefined).label).not.toBe("causes");
    expect(rippleEdgeDisplay("unavailable", undefined).label).not.toBe("causes");
    // No branch of this function ever returns the literal string "causes"
    // unless the real data said so via an observed/supported relationship.
    for (const state of ["observed", "supported", "hypothesized", "unavailable", "unknown", null, undefined, "garbage"]) {
      expect(rippleEdgeDisplay(state as any, undefined).label).not.toBe("causes");
    }
  });
});
