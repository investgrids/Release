import { describe, expect, it } from "vitest";
import { confidenceWord, dedupeEvidence, distinctHeadlines, evidenceBalance, plainDate, type Evidence } from "./intelligenceView";

const ev = (reason: string | null, mag: number, at: string | null = "2026-09-01T00:00:00Z"): Evidence => ({ reason, source_type: "article", href: null, signed_magnitude: mag, signal_at: at });

describe("dedupeEvidence", () => {
  it("keeps one row per distinct reason (ignoring case and punctuation), the strongest, then the most recent", () => {
    const rows = [
      ev("Directly exposed to Technology opportunity through core operations.", 85, "2026-08-17T00:00:00Z"),
      ev("directly exposed to technology opportunity through core operations", 91, "2026-08-09T00:00:00Z"),
      ev("Weaker rupee makes exports cheaper", 80), ev("Weaker rupee makes exports cheaper!", 80, "2026-09-05T00:00:00Z"),
    ];
    const out = dedupeEvidence(rows);
    expect(out).toHaveLength(2);
    expect(out[0].signed_magnitude).toBe(91);                         // strongest copy of the repeated sentence
    expect(out[1].signal_at).toBe("2026-09-05T00:00:00Z");           // equal strength: the more recent copy
  });

  it("orders by absolute strength so counter-signals sort the same way, and drops empty reasons", () => {
    const out = dedupeEvidence([ev("a risk", -60), ev("bigger risk", -90), ev(null, 99), ev("   ", 50)]);
    expect(out.map(r => r.reason)).toEqual(["bigger risk", "a risk"]);
    expect(dedupeEvidence(undefined)).toEqual([]);
  });
});

describe("evidenceBalance / confidenceWord / plainDate / distinctHeadlines", () => {
  it("computes the support share over distinct evidence, or null when there is none", () => {
    expect(evidenceBalance([ev("a", 1), ev("b", 1), ev("c", 1)], [ev("d", -1)])).toEqual({ support: 3, counter: 1, supportPct: 75 });
    expect(evidenceBalance([], [])).toBeNull();
  });
  it("words the confidence percentage and never invents one", () => {
    expect(confidenceWord(31)).toBe("Low"); expect(confidenceWord(55)).toBe("Moderate"); expect(confidenceWord(80)).toBe("High");
    expect(confidenceWord(null)).toBeNull(); expect(confidenceWord(NaN)).toBeNull();
  });
  it("formats ISO dates plainly and leaves other text alone", () => {
    expect(plainDate("2026-08-19")).toBe("19 Aug 2026");
    expect(plainDate("not a date")).toBe("not a date");
    expect(plainDate(null)).toBe("");
  });
  it("keeps the first of repeated headlines", () => {
    const out = distinctHeadlines([{ headline: "FPI outflows hit ₹3 lakh crore" }, { headline: "fpi outflows hit ₹3 lakh crore." }, { headline: "Rupee slides" }]);
    expect(out.map(e => e.headline)).toEqual(["FPI outflows hit ₹3 lakh crore", "Rupee slides"]);
  });
});
