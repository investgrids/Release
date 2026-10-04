import { describe, expect, it } from "vitest";
import { labelTone, metricTone, NEUTRAL, parseMetric } from "./metricTone";

const GREEN = /emerald/, AMBER = /amber/, RED = /rose/;

describe("metricTone", () => {
  it("lower-is-better metrics: P/E, P/B, D/E", () => {
    expect(metricTone("pe", "15.1")).toMatch(GREEN);
    expect(metricTone("pe", "32")).toMatch(AMBER);
    expect(metricTone("pe", "65.4")).toMatch(RED);
    expect(metricTone("pb", "6.9")).toMatch(RED);
    expect(metricTone("pb", "2.1")).toMatch(GREEN);
    expect(metricTone("de", "0.10")).toMatch(GREEN);
    expect(metricTone("de", "1.80")).toMatch(RED);
  });

  it("higher-is-better metrics: ROE, margin, yield", () => {
    expect(metricTone("roe", "47.7%")).toMatch(GREEN);
    expect(metricTone("roe", "11%")).toMatch(AMBER);
    expect(metricTone("roe", "3.2%")).toMatch(RED);
    expect(metricTone("net_margin", "18.1%")).toMatch(GREEN);
    expect(metricTone("dividend_yield", "3.12%")).toMatch(GREEN);
    expect(metricTone("dividend_yield", "0.2%")).toMatch(RED);
  });

  it("a negative P/E (loss-making) is red, not cheap", () => {
    expect(metricTone("pe", "-12.5")).toMatch(RED);
  });

  it("missing values stay neutral", () => {
    for (const v of ["—", "", null, undefined, "N/A"]) expect(metricTone("roe", v)).toBe(NEUTRAL);
  });

  it("maps page labels, and leaves unrated labels neutral", () => {
    expect(labelTone("P/E (TTM)", "15.1")).toMatch(GREEN);
    expect(labelTone("Market cap", "₹7.53T")).toBe(NEUTRAL);
  });

  it("parses formatted numbers", () => {
    expect(parseMetric("₹1,234.5")).toBe(1234.5);
    expect(parseMetric("24.3x")).toBe(24.3);
    expect(parseMetric("abc")).toBeNull();
  });
});
