import { describe, expect, it } from "vitest";
import { indexSentimentScore } from "./marketSentiment";

const q = (name: string, pct: number, value = "1") => ({ name, value, pct });

describe("indexSentimentScore", () => {
  it("falls with the market and counts a rising VIX against it", () => {
    const falling = indexSentimentScore([q("NIFTY 50", -0.7), q("SENSEX", -0.76), q("BANK NIFTY", -0.9), q("INDIA VIX", 5)]);
    const rising = indexSentimentScore([q("NIFTY 50", 0.8), q("SENSEX", 0.9), q("INDIA VIX", -4)]);
    const flat = indexSentimentScore([q("NIFTY 50", 0), q("SENSEX", 0), q("INDIA VIX", 0)]);
    expect(falling!).toBeLessThan(50);
    expect(rising!).toBeGreaterThan(50);
    expect(flat).toBe(50);
  });
  it("does not treat the VIX or a flat index as a positive index", () => {
    expect(indexSentimentScore([q("NIFTY 50", -0.7), q("INDIA VIX", 5)])!).toBeLessThan(50);
  });
  it("returns null, not a neutral default, without usable data", () => {
    expect(indexSentimentScore([])).toBeNull();
    expect(indexSentimentScore([{ name: "NIFTY 50", value: "—", pct: 0 }])).toBeNull();
  });
  it("matches the backend for the October 12 closes", () => {
    // backend: mean(-0.70,-0.76,-0.61)/1.5 -> 50 - 0.45*35 - (VIX +6.23% -> 0.623*5) = 31
    expect(indexSentimentScore([q("NIFTY 50", -0.7), q("SENSEX", -0.76), q("BANK NIFTY", -0.61), q("INDIA VIX", 6.23)])).toBe(31);
  });
});
