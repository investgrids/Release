import { describe, it, expect } from "vitest";
import {
  isRenderable, parseCapability, parseStrength, coerceAuthorizedClaim,
  type AuthorizedClaim,
} from "./claimAuthorization";

describe("claimAuthorization — CD3-D fail-closed frontend gate", () => {
  it("renders an authorized claim", () => {
    const claim: AuthorizedClaim = { capability: "observed_direction", strength: "authorized" };
    expect(isRenderable(claim)).toBe(true);
  });

  it("renders a qualified claim", () => {
    const claim: AuthorizedClaim = { capability: "analytical_hypothesis", strength: "qualified" };
    expect(isRenderable(claim)).toBe(true);
  });

  it("never renders an unavailable claim", () => {
    const claim: AuthorizedClaim = { capability: "observed_direction", strength: "unavailable" };
    expect(isRenderable(claim)).toBe(false);
  });

  it("never renders a missing claim", () => {
    expect(isRenderable(null)).toBe(false);
    expect(isRenderable(undefined)).toBe(false);
  });

  it("never renders a claim with an unrecognized capability", () => {
    const claim = { capability: "some_future_capability", strength: "authorized" } as unknown as AuthorizedClaim;
    expect(isRenderable(claim)).toBe(false);
  });

  it("parseStrength fails closed to unavailable on missing/unrecognized values", () => {
    expect(parseStrength(null)).toBe("unavailable");
    expect(parseStrength(undefined)).toBe("unavailable");
    expect(parseStrength("some_future_strength")).toBe("unavailable");
  });

  it("parseCapability returns null on missing/unrecognized values, never a guessed capability", () => {
    expect(parseCapability(null)).toBeNull();
    expect(parseCapability("bullish")).toBeNull();
  });

  it("coerceAuthorizedClaim never upgrades untyped legacy data into authorized", () => {
    expect(coerceAuthorizedClaim(null).strength).toBe("unavailable");
    expect(coerceAuthorizedClaim(undefined).strength).toBe("unavailable");
    expect(coerceAuthorizedClaim({}).strength).toBe("unavailable");
    expect(coerceAuthorizedClaim({ confidence: 0.8 }).strength).toBe("unavailable"); // real legacy shape
    expect(coerceAuthorizedClaim("positive").strength).toBe("unavailable");
  });

  it("coerceAuthorizedClaim reads a real, well-formed claim", () => {
    const c = coerceAuthorizedClaim({ capability: "observed_direction", strength: "authorized", reason: null });
    expect(c).toEqual({ capability: "observed_direction", strength: "authorized", reason: null });
  });

  // The owner's adversarial scenario, frontend side: even if a
  // malformed/legacy API response tried to smuggle through
  // "capability: analytical_hypothesis, strength: authorized" for data
  // that a correctly-implemented backend would only ever mark
  // "qualified", this module cannot itself upgrade anything -- it only
  // ever narrows toward unavailable. The real guarantee lives in the
  // backend's authorize_direction() test suite; this suite guarantees
  // the frontend parser never accidentally widens what it's given.
  it("never invents authorized/qualified strength for a capability the payload didn't actually claim", () => {
    const bare = coerceAuthorizedClaim({ strength: "authorized" }); // no capability field at all
    expect(bare.strength).toBe("unavailable");
  });
});
