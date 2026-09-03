import { describe, it, expect } from "vitest";
import {
  isRenderable, parseCapability, parseStrength, coerceAuthorizedClaim,
  authorizeDirection, authorizeRipple, authorizeMeasurement,
  FORECAST_UNAVAILABLE, RECOMMENDATION_UNAVAILABLE,
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

// Pins the exact same decision table as test_claim_authorization.py --
// the two implementations are mirrors, kept in sync by inspection; any
// drift between them is exactly the kind of "one new page reconstructs
// a stronger claim" bug this whole phase exists to close.
describe("claimAuthorization — decision logic (mirrors claim_authorization.py)", () => {
  it("price_sign is authorized observed_direction", () => {
    expect(authorizeDirection("price_sign")).toEqual({ capability: "observed_direction", strength: "authorized" });
  });

  it("historical_outcome is authorized historical_description", () => {
    expect(authorizeDirection("historical_outcome")).toEqual({ capability: "historical_description", strength: "authorized" });
  });

  it("analytical_hypothesis and event_direction are qualified, never authorized", () => {
    expect(authorizeDirection("analytical_hypothesis").strength).toBe("qualified");
    expect(authorizeDirection("event_direction").strength).toBe("qualified");
  });

  it("fallback/unavailable/unknown provenance is unavailable", () => {
    expect(authorizeDirection("fallback").strength).toBe("unavailable");
    expect(authorizeDirection("unavailable").strength).toBe("unavailable");
    expect(authorizeDirection("unknown").strength).toBe("unavailable");
  });

  it("any non-valid integrity collapses direction authorization to unavailable", () => {
    (["degraded", "fallback", "unavailable", "invalid"] as const).forEach(status => {
      expect(authorizeDirection("price_sign", status).strength).toBe("unavailable");
    });
  });

  it("ripple hypothesized is qualified, never authorized (the owner's named example)", () => {
    const c = authorizeRipple("hypothesized");
    expect(c.capability).toBe("causal_relationship");
    expect(c.strength).toBe("qualified");
  });

  it("ripple observed is authorized, supported is qualified, unavailable is unavailable", () => {
    expect(authorizeRipple("observed").strength).toBe("authorized");
    expect(authorizeRipple("supported").strength).toBe("qualified");
    expect(authorizeRipple("unavailable").strength).toBe("unavailable");
  });

  it("self_reported_certainty measurement is always qualified", () => {
    expect(authorizeMeasurement("self_reported_certainty", "valid").strength).toBe("qualified");
  });

  it("real composites/deterministic/calibration measurements are authorized", () => {
    for (const mt of ["evidence_composite", "hybrid_rubric", "deterministic_metric", "historical_calibration"]) {
      expect(authorizeMeasurement(mt, "valid").strength).toBe("authorized");
    }
  });

  it("forecast and recommendation are permanently unavailable constants", () => {
    expect(FORECAST_UNAVAILABLE.strength).toBe("unavailable");
    expect(RECOMMENDATION_UNAVAILABLE.strength).toBe("unavailable");
  });

  // The owner's adversarial scenario, frontend side.
  it("impact=positive + ANALYTICAL_HYPOTHESIS + HYPOTHESIZED + VALID cannot reach authorized/forecast/recommendation", () => {
    const direction = authorizeDirection("analytical_hypothesis", "valid");
    const ripple = authorizeRipple("hypothesized", "valid");
    expect(direction.strength).not.toBe("authorized");
    expect(direction.capability).not.toBe("forecast");
    expect(direction.capability).not.toBe("recommendation");
    expect(ripple.strength).not.toBe("authorized");
    // Still renderable in its qualified form -- the positive control.
    expect(direction.strength).toBe("qualified");
  });
});
