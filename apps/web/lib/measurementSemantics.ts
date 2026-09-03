// CD3-C typed measurement semantics — TypeScript mirror of
// app/services/measurement_semantics.py (kept in sync by inspection, same
// convention as lib/recommendationLanguage.ts / lib/whatToWatchNext.ts's
// relationship to their backend counterparts — no shared build step
// bridges the Python backend and this Next.js frontend).
//
// Same two independent axes as the backend: `measurementType` (what kind
// of thing this number structurally is) and `integrityStatus` (is this
// specific instance trustworthy right now). A value's public wording must
// be authorized by BOTH together — never by field name alone, never by
// numeric shape alone (a 0-100 self-rating and a 0-100 evidence composite
// are not interchangeable just because they're both "a number 0-100").
//
// Hard rule: measurement type unknown -> do not infer from field name ->
// do not convert to a percentage -> do not display as "Confidence".

export type MeasurementType =
  | "self_reported_certainty"
  | "evidence_composite"
  | "hybrid_rubric"
  | "historical_calibration"
  | "deterministic_metric"
  | "derived_transform"
  | "unknown";

export type IntegrityStatus =
  | "valid"
  | "degraded"
  | "fallback"
  | "unavailable"
  | "invalid";

export interface Measurement {
  measurementType: MeasurementType;
  integrityStatus: IntegrityStatus;
  value: number | string | null;
  /** Real native scale, e.g. "0-100 evidence coverage", "0-10 impact
   * magnitude" — never assume 0-100 just because a number is present. */
  scale: string;
  /** The human-facing name for this specific value, chosen for what it
   * actually measures — never a bare, undifferentiated "Confidence". */
  label: string;
  reason?: string | null;
}

// Human-facing label per measurement type — the shared source every
// frontend consumer should pull from during the CD3-C sweep, so 67 files
// don't each invent slightly different wording for the same concept.
export const MEASUREMENT_LABEL: Record<MeasurementType, string> = {
  self_reported_certainty: "Model Self-Rating",
  evidence_composite:      "Evidence Coverage",
  hybrid_rubric:           "Evidence Score",
  historical_calibration:  "Historical Accuracy",
  deterministic_metric:    "", // real per-field name required, e.g. "Impact Magnitude" — no generic fallback on purpose
  derived_transform:       "",
  unknown:                 "",
};

const VALID: IntegrityStatus = "valid";

/**
 * The one boolean gate every consumer should check before rendering a
 * Measurement as anything confidence-shaped. False for any non-VALID
 * integrityStatus regardless of measurementType, and false for
 * unknown/derived_transform measurementType even when "valid" (a derived
 * transform's own inputs must be checked separately by its own caller —
 * this function can't see them).
 */
export function isPubliclyAuthorized(m: Measurement | null | undefined): boolean {
  if (!m) return false;
  if (m.integrityStatus !== VALID) return false;
  if (m.measurementType === "unknown" || m.measurementType === "derived_transform") return false;
  return true;
}

/** Fail-safe accessor: a missing/unrecognized value resolves to
 * "unknown", never inferred into a stronger type than the data proves. */
export function resolveMeasurementType(raw: string | null | undefined): MeasurementType {
  const known: MeasurementType[] = [
    "self_reported_certainty", "evidence_composite", "hybrid_rubric",
    "historical_calibration", "deterministic_metric", "derived_transform", "unknown",
  ];
  return (known as string[]).includes(raw ?? "") ? (raw as MeasurementType) : "unknown";
}

/** Fail-safe accessor: a missing/unrecognized value resolves to the
 * weakest status, "unavailable", never "valid" just because the field was absent. */
export function resolveIntegrityStatus(raw: string | null | undefined): IntegrityStatus {
  const known: IntegrityStatus[] = ["valid", "degraded", "fallback", "unavailable", "invalid"];
  return (known as string[]).includes(raw ?? "") ? (raw as IntegrityStatus) : "unavailable";
}
