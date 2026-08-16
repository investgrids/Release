import { describe, expect, it } from "vitest";
import {
  baselineLabel,
  biasLabel,
  biasStyle,
  companyStateStyle,
  dataWindowLabel,
  dedupeMarketRisks,
  evidenceQualityFor,
  formatDateShort,
  sectorDirectionStyle,
  severityStyle,
  simplifyConfidenceWarnings,
  summaryTemplate,
  weekdayNameFromISODate,
} from "./weekendLabels";
import type { WeekendRisk } from "@/types/weekendIntelligence";

function risk(overrides: Partial<WeekendRisk> = {}): WeekendRisk {
  return {
    description: "test", risk_type: "conflicting_evidence", severity: "medium",
    evidence_refs: [], related_sectors: [], related_companies: [],
    ...overrides,
  };
}

/**
 * Brief §40 — truthfulness tests: the backend's semantic states must
 * render faithfully, never reinterpreted into something more certain
 * (e.g. "mixed" must never become "Positive" anywhere in the mapping).
 */
describe("sectorDirectionStyle", () => {
  it("mixed renders Mixed, never Positive or Negative", () => {
    const style = sectorDirectionStyle("mixed");
    expect(style.label).toBe("Mixed");
    expect(style.label).not.toBe("Positive");
    expect(style.label).not.toBe("Negative");
  });

  it("positive renders Positive with an up symbol, not color alone", () => {
    const style = sectorDirectionStyle("positive");
    expect(style.label).toBe("Positive");
    expect(style.symbol).toBe("↑");
  });

  it("negative renders Negative with a down symbol", () => {
    const style = sectorDirectionStyle("negative");
    expect(style.label).toBe("Negative");
    expect(style.symbol).toBe("↓");
  });

  it("neutral renders Neutral, not silently dropped or upgraded", () => {
    expect(sectorDirectionStyle("neutral").label).toBe("Neutral");
  });

  it("unrecognized direction falls back to Neutral rather than guessing", () => {
    expect(sectorDirectionStyle("something_unexpected").label).toBe("Neutral");
  });
});

describe("companyStateStyle", () => {
  it("mixed company state renders Mixed, never a directional watch label", () => {
    const style = companyStateStyle("mixed");
    expect(style.label).toBe("Mixed");
  });

  it("monitor is not upgraded to a watch state", () => {
    expect(companyStateStyle("monitor").label).toBe("Monitor");
  });

  it("high_conviction_watch and positive_watch are both directionally positive, not identical labels collapsed into one lie", () => {
    expect(companyStateStyle("high_conviction_watch").label).toBe("High Conviction Watch");
    expect(companyStateStyle("positive_watch").label).toBe("Positive Watch");
  });

  it("risk_watch renders Risk Watch, not a euphemism", () => {
    expect(companyStateStyle("risk_watch").label).toBe("Risk Watch");
  });
});

describe("biasLabel / biasStyle", () => {
  it("mixed overall bias renders Mixed, not Positive or Bullish", () => {
    expect(biasLabel("mixed")).toBe("Mixed");
    expect(biasStyle("mixed").label).toBe("Mixed");
  });

  it("strong_positive and positive both map to the positive visual family but keep distinct labels", () => {
    expect(biasLabel("strong_positive")).toBe("Strong Positive");
    expect(biasLabel("positive")).toBe("Positive");
    expect(biasStyle("strong_positive").label).toBe("Positive");
  });
});

describe("severityStyle", () => {
  it("passes through real severities without inventing a 4th tier", () => {
    expect(severityStyle("high").label).toBe("High");
    expect(severityStyle("medium").label).toBe("Medium");
    expect(severityStyle("low").label).toBe("Low");
  });
});

describe("weekdayNameFromISODate", () => {
  it("resolves a real date to its weekday name", () => {
    expect(weekdayNameFromISODate("2026-08-17")).toBe("Monday");
  });

  it("missing date falls back to a safe generic label, not a crash or a guessed date", () => {
    expect(weekdayNameFromISODate(null)).toBe("the next session");
    expect(weekdayNameFromISODate(undefined)).toBe("the next session");
    expect(weekdayNameFromISODate("")).toBe("the next session");
  });

  it("malformed date string falls back safely", () => {
    expect(weekdayNameFromISODate("not-a-date")).toBe("the next session");
  });
});

/**
 * Redesign brief (2026-08-15) §6/§7/§15 — Evidence Quality and the
 * metadata strip's baseline/data-window fields, and the Weekend
 * Intelligence Summary, are NOT real backend fields. These tests pin
 * down that every value they show is deterministically derived from
 * real fields the backend does send (status, confidence_warnings,
 * evidence_summary, last_trading_date, generated_at, top_sectors,
 * overall_bias, production_confidence, baseline_available) — never an
 * invented number, verdict, or free-text sentence.
 */
describe("formatDateShort", () => {
  it("formats a plain Y-M-D date without any timezone-dependent Date() parsing", () => {
    expect(formatDateShort("2026-08-15")).toBe("15 Aug 2026");
  });

  it("missing/malformed date falls back safely", () => {
    expect(formatDateShort(null)).toBe("Unknown");
    expect(formatDateShort("not-a-date")).toBe("not-a-date");
  });
});

describe("baselineLabel", () => {
  it("pairs the real last_trading_date with NSE's fixed 3:30 PM IST close time", () => {
    expect(baselineLabel("2026-08-14")).toBe("14 Aug 2026, 3:30 PM IST");
  });

  it("missing baseline date is honest, not a guessed date", () => {
    expect(baselineLabel(null)).toBe("Unavailable");
  });
});

describe("dataWindowLabel", () => {
  it("computes real elapsed hours between the fixed close instant and generated_at", () => {
    // 2026-08-14 15:30 IST close = 2026-08-14T10:00:00Z; +41h -> 2026-08-16T03:00:00Z.
    expect(dataWindowLabel("2026-08-14", "2026-08-16T03:00:00Z")).toBe("~41 hours");
  });

  it("missing either real field is honest, never a fabricated window", () => {
    expect(dataWindowLabel(null, "2026-08-16T03:00:00Z")).toBe("Unavailable");
    expect(dataWindowLabel("2026-08-14", null)).toBe("Unavailable");
  });

  it("a generated_at before the close (bad data) is not shown as a negative/zero window", () => {
    expect(dataWindowLabel("2026-08-14", "2026-08-14T05:00:00Z")).toBe("Unavailable");
  });
});

describe("evidenceQualityFor", () => {
  const base = { status: "ok", confidence_warnings: [] as { severity: string }[], evidence_summary: { total: 600, by_source_type: { event: 200, news: 200, company_signal: 200 } } };

  it("status=ok with no confidence warnings -> Good, never fabricated as anything stronger", () => {
    const q = evidenceQualityFor(base);
    expect(q.label).toBe("Good");
    expect(q.tone).toBe("positive");
    expect(q.description).toBe("3 source types, no confidence caveats");
  });

  it("status=degraded downgrades to Fair, with the real caveat count named", () => {
    const q = evidenceQualityFor({ ...base, status: "degraded", confidence_warnings: [{ severity: "high" }] });
    expect(q.label).toBe("Fair");
    expect(q.description).toContain("1 confidence caveat");
  });

  it("a high-severity warning downgrades to Fair even if status still reads ok", () => {
    const q = evidenceQualityFor({ ...base, status: "ok", confidence_warnings: [{ severity: "high" }] });
    expect(q.label).toBe("Fair");
  });

  it("zero evidence -> Limited, not a fabricated Good/Fair", () => {
    const q = evidenceQualityFor({ ...base, evidence_summary: { total: 0, by_source_type: {} } });
    expect(q.label).toBe("Limited");
    expect(q.description).toContain("no sources yet");
  });
});

describe("summaryTemplate", () => {
  const base = {
    overall_bias: "mixed",
    top_sectors: [
      { sector: "Technology", direction: "positive" },
      { sector: "Banking", direction: "mixed" },
    ],
    production_confidence: 43,
    baseline_available: false,
    status: "degraded",
  };

  it("no sectors -> null, never a hollow summary card", () => {
    expect(summaryTemplate({ ...base, top_sectors: [] })).toBeNull();
  });

  it("builds a factual sentence from real bias/sector/confidence fields only", () => {
    const text = summaryTemplate(base);
    expect(text).toContain("Weekend signals remain mixed.");
    expect(text).toContain("Technology shows positive evidence while Banking is mixed.");
    expect(text).toContain("last trading session's closing baseline is unavailable");
    expect(text).not.toMatch(/\d\.\d\d/); // no raw internal confidence float leaked
  });

  it("a single dominant sector produces a single-sector sentence, not a fabricated contrast", () => {
    const text = summaryTemplate({ ...base, top_sectors: [{ sector: "Technology", direction: "positive" }] });
    expect(text).toContain("Technology carries the most evidence this weekend, trending positive.");
  });

  it("confidence word scales with the real production_confidence value", () => {
    expect(summaryTemplate({ ...base, production_confidence: 80, baseline_available: true, status: "ok" })).toContain("Confidence is high.");
    expect(summaryTemplate({ ...base, production_confidence: 50, baseline_available: true, status: "ok" })).toContain("Confidence is moderate.");
    expect(summaryTemplate({ ...base, production_confidence: 20, baseline_available: true, status: "ok" })).toContain("Confidence is low.");
  });
});

/**
 * Bottom-row simplification (owner correction, 2026-08-15) — pure
 * frontend presentation logic over the real market_risks/
 * confidence_warnings arrays. Nothing here talks to the backend or
 * changes what it returns.
 */
describe("dedupeMarketRisks", () => {
  it("drops company-level risks when a sector-level risk of the same type exists", () => {
    const risks = [
      risk({ description: "finance: conflicting", related_sectors: ["finance"] }),
      risk({ description: "BAJFINANCE: conflicting", related_companies: ["BAJFINANCE"] }),
      risk({ description: "HDFCBANK: conflicting", related_companies: ["HDFCBANK"] }),
    ];
    const result = dedupeMarketRisks(risks);
    expect(result).toHaveLength(1);
    expect(result[0].description).toBe("finance: conflicting");
  });

  it("keeps company-level risks when no sector-level risk of that type exists", () => {
    const risks = [
      risk({ description: "BAJFINANCE: conflicting", related_companies: ["BAJFINANCE"] }),
      risk({ description: "HDFCBANK: conflicting", related_companies: ["HDFCBANK"] }),
    ];
    expect(dedupeMarketRisks(risks)).toHaveLength(2);
  });

  it("never drops sector-level risks or risks of a different type", () => {
    const risks = [
      risk({ description: "finance: conflicting", related_sectors: ["finance"], risk_type: "conflicting_evidence" }),
      risk({ description: "banking: conflicting", related_sectors: ["banking"], risk_type: "conflicting_evidence" }),
    ];
    expect(dedupeMarketRisks(risks)).toHaveLength(2);
  });

  it("ranks the surviving risks by severity, high first", () => {
    const risks = [
      risk({ description: "low one", severity: "low" }),
      risk({ description: "high one", severity: "high" }),
      risk({ description: "medium one", severity: "medium" }),
    ];
    const result = dedupeMarketRisks(risks);
    expect(result.map((r) => r.severity)).toEqual(["high", "medium", "low"]);
  });
});

describe("simplifyConfidenceWarnings", () => {
  it("replaces the raw baseline-missing wording with the simplified copy", () => {
    const result = simplifyConfidenceWarnings([
      risk({ risk_type: "stale_or_missing_baseline", description: "Last trading session's close snapshot is missing — synthesis is based on weekend evidence only, without a verified price/breadth baseline" }),
    ]);
    expect(result[0].description).toBe("Last-session closing baseline is unavailable");
  });

  it("collapses every per-company source_concentration warning into one generic line", () => {
    const result = simplifyConfidenceWarnings([
      risk({ risk_type: "source_concentration", related_companies: ["BAJFINANCE"], description: "BAJFINANCE: thesis rests on a single evidence source type despite 22 clusters" }),
      risk({ risk_type: "source_concentration", related_companies: ["LICHSGFIN"], description: "LICHSGFIN: thesis rests on a single evidence source type despite 20 clusters" }),
      risk({ risk_type: "source_concentration", related_companies: ["HDFCBANK"], description: "HDFCBANK: thesis rests on a single evidence source type despite 10 clusters" }),
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].description).toBe("Some company signals rely on only one source type");
  });

  it("keeps the whole-snapshot source_concentration warning separate from the per-company one", () => {
    const result = simplifyConfidenceWarnings([
      risk({ risk_type: "source_concentration", related_companies: [], description: "Evidence concentrated in news (18/20 items, 90%) — other source types are comparatively sparse this weekend" }),
      risk({ risk_type: "source_concentration", related_companies: ["BAJFINANCE"], description: "BAJFINANCE: thesis rests on a single evidence source type despite 22 clusters" }),
    ]);
    expect(result).toHaveLength(2);
    expect(result.some((r) => r.description === "Evidence this weekend leans heavily on one source type")).toBe(true);
    expect(result.some((r) => r.description === "Some company signals rely on only one source type")).toBe(true);
  });

  it("simplifies weak_historical_analogue and insufficient_evidence, dropping raw counts", () => {
    const result = simplifyConfidenceWarnings([
      risk({ risk_type: "weak_historical_analogue", description: "No comparable historical analogue found for this weekend's dominant evidence" }),
      risk({ risk_type: "insufficient_evidence", description: "Evidence volume is thin (3 item(s)) — synthesis has lower statistical support than a typical checkpoint" }),
    ]);
    expect(result.find((r) => r.risk_type === "weak_historical_analogue")?.description).toBe("No similar historical pattern was found this weekend");
    expect(result.find((r) => r.risk_type === "insufficient_evidence")?.description).toBe("Evidence volume is limited this cycle");
    expect(result.some((r) => /\d item\(s\)/.test(r.description))).toBe(false);
  });

  it("passes an unrecognized risk_type through with its real description, never dropping it silently", () => {
    const result = simplifyConfidenceWarnings([
      risk({ risk_type: "some_future_type", description: "A brand new warning type" }),
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].description).toBe("A brand new warning type");
  });
});
