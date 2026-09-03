import { describe, it, expect } from "vitest";
import {
  isPubliclyAuthorized, resolveMeasurementType, resolveIntegrityStatus,
  MEASUREMENT_LABEL, type Measurement,
} from "./measurementSemantics";

function m(overrides: Partial<Measurement> = {}): Measurement {
  return {
    measurementType: "evidence_composite", integrityStatus: "valid",
    value: 72, scale: "0-100", label: "Evidence Coverage",
    ...overrides,
  };
}

describe("measurementSemantics — CD3-C typed measurement gate", () => {
  it("authorizes a valid evidence_composite", () => {
    expect(isPubliclyAuthorized(m())).toBe(true);
  });

  it("authorizes a valid self_reported_certainty (as itself, not as a probability)", () => {
    expect(isPubliclyAuthorized(m({ measurementType: "self_reported_certainty" }))).toBe(true);
  });

  (["fallback", "unavailable", "degraded", "invalid"] as const).forEach(status => {
    it(`never authorizes integrityStatus=${status} regardless of measurementType`, () => {
      expect(isPubliclyAuthorized(m({ integrityStatus: status }))).toBe(false);
    });
  });

  it("never authorizes measurementType=unknown even when marked valid", () => {
    expect(isPubliclyAuthorized(m({ measurementType: "unknown" }))).toBe(false);
  });

  it("never authorizes measurementType=derived_transform even when marked valid", () => {
    expect(isPubliclyAuthorized(m({ measurementType: "derived_transform" }))).toBe(false);
  });

  it("never authorizes null/undefined", () => {
    expect(isPubliclyAuthorized(null)).toBe(false);
    expect(isPubliclyAuthorized(undefined)).toBe(false);
  });

  it("resolveMeasurementType fails closed to unknown on missing/unrecognized values", () => {
    expect(resolveMeasurementType(null)).toBe("unknown");
    expect(resolveMeasurementType(undefined)).toBe("unknown");
    expect(resolveMeasurementType("some_future_type")).toBe("unknown");
  });

  it("resolveMeasurementType reads a real value", () => {
    expect(resolveMeasurementType("hybrid_rubric")).toBe("hybrid_rubric");
  });

  it("resolveIntegrityStatus fails closed to unavailable, never valid, on missing/unrecognized values", () => {
    expect(resolveIntegrityStatus(null)).toBe("unavailable");
    expect(resolveIntegrityStatus("some_legacy_status")).toBe("unavailable");
  });

  it("resolveIntegrityStatus reads a real value", () => {
    expect(resolveIntegrityStatus("invalid")).toBe("invalid");
  });

  it("a legacy record with no typed fields fails closed end to end", () => {
    const legacy: Record<string, unknown> = { confidence: 0.8 }; // no typed fields, real pre-CD3-C shape
    const measurement: Measurement = {
      measurementType: resolveMeasurementType(legacy.measurement_type as string | undefined),
      integrityStatus: resolveIntegrityStatus(legacy.integrity_status as string | undefined),
      value: legacy.confidence as number,
      scale: "unknown",
      label: "unknown",
    };
    expect(isPubliclyAuthorized(measurement)).toBe(false);
  });

  it("MEASUREMENT_LABEL gives a real name for the three primary computed types", () => {
    expect(MEASUREMENT_LABEL.evidence_composite).toBe("Evidence Coverage");
    expect(MEASUREMENT_LABEL.self_reported_certainty).toBe("Model Self-Rating");
    expect(MEASUREMENT_LABEL.historical_calibration).toBe("Historical Accuracy");
  });

  it("MEASUREMENT_LABEL deliberately has no generic fallback for deterministic_metric/derived_transform/unknown", () => {
    // Each real deterministic_metric needs its own real name (e.g. "Impact
    // Magnitude") -- a shared generic label here would just reproduce the
    // bare-"Confidence" problem this vocabulary exists to fix.
    expect(MEASUREMENT_LABEL.deterministic_metric).toBe("");
    expect(MEASUREMENT_LABEL.derived_transform).toBe("");
    expect(MEASUREMENT_LABEL.unknown).toBe("");
  });
});
