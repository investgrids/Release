import { describe, it, expect } from "vitest";
import { containsRecommendationLanguage } from "./recommendationLanguage";

describe("containsRecommendationLanguage — P0-CD1 legacy-history patch", () => {
  it("flags the real live specimen that motivated this patch", () => {
    expect(containsRecommendationLanguage(
      "Consider shorting over-valued circuit-climbed names like Hy-Tech Engineers and TBZ, while watching for potential rebound in the banking sector."
    )).toBe(true);
  });

  it("flags plain buy/sell/short/accumulate/target/stop-loss language", () => {
    expect(containsRecommendationLanguage("Buy HDFC Bank now")).toBe(true);
    expect(containsRecommendationLanguage("Investors should sell into strength")).toBe(true);
    expect(containsRecommendationLanguage("Short Nifty into resistance")).toBe(true);
    expect(containsRecommendationLanguage("Accumulate on every dip")).toBe(true);
    expect(containsRecommendationLanguage("Target price of 1,850 looks achievable")).toBe(true);
    expect(containsRecommendationLanguage("Set a stop-loss below the recent low")).toBe(true);
  });

  it("does not flag the factual word buyback", () => {
    expect(containsRecommendationLanguage("Company announced a share buyback")).toBe(false);
  });

  it("does not flag short-term (space or hyphen)", () => {
    expect(containsRecommendationLanguage("A short-term catalyst is worth watching")).toBe(false);
    expect(containsRecommendationLanguage("short term momentum may continue")).toBe(false);
  });

  it("does not flag clean, grounded takeaway text", () => {
    expect(containsRecommendationLanguage(
      "The evidence points to margin stability for private banks this quarter."
    )).toBe(false);
  });

  it("handles null/undefined/empty safely", () => {
    expect(containsRecommendationLanguage(null)).toBe(false);
    expect(containsRecommendationLanguage(undefined)).toBe(false);
    expect(containsRecommendationLanguage("")).toBe(false);
  });

  it("flags the real live comparison-article specimen (2026-09-03 reassessment)", () => {
    expect(containsRecommendationLanguage(
      "Favor GAIL India Ltd for 12-month capital appreciation... preferred choice over Oil & Natural Gas Corporation"
    )).toBe(true);
  });

  it("flags comparative recommendation phrasing", () => {
    expect(containsRecommendationLanguage("We favor Company A over Company B")).toBe(true);
    expect(containsRecommendationLanguage("Company A is our preferred choice for growth investors")).toBe(true);
    expect(containsRecommendationLanguage("This makes Company A the better investment right now")).toBe(true);
    expect(containsRecommendationLanguage("Most investors would choose Company A here")).toBe(true);
  });

  it("flags all conjugations of favor, including 'favored' (past participle)", () => {
    // Real gap found live in production after the first version of this
    // fix deployed -- /\bfavor(?:s|ing)?\b/i did not match "favored" at
    // all, so a real already-published sentence kept rendering through
    // the new defense-in-depth gate unnoticed.
    expect(containsRecommendationLanguage("Company A is favor here.")).toBe(true);
    expect(containsRecommendationLanguage("Company A is favors here.")).toBe(true);
    expect(containsRecommendationLanguage("Company A is favored here.")).toBe(true);
    expect(containsRecommendationLanguage("Company A is favoring here.")).toBe(true);
  });

  it("flags the real live specimen with 'favored' (past participle)", () => {
    expect(containsRecommendationLanguage(
      "ICICI Bank Ltd is favored for 12-month tactical outperformance due to operational momentum, while HDFC Bank Ltd remains a core holding."
    )).toBe(true);
  });

  it("does not flag preferred stock/shares", () => {
    expect(containsRecommendationLanguage("The company issued new preferred stock last quarter.")).toBe(false);
    expect(containsRecommendationLanguage("Preferred shares carry a fixed dividend.")).toBe(false);
  });
});
