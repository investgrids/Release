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
});
