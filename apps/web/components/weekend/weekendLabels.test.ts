import { describe, expect, it } from "vitest";
import {
  biasLabel,
  biasStyle,
  companyStateStyle,
  sectorDirectionStyle,
  severityStyle,
  weekdayNameFromISODate,
} from "./weekendLabels";

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
