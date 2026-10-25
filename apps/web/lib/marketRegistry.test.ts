import { describe, expect, it } from "vitest";
import { MARKETS, getMarket, hasOwnIndexStrip, type SectionKey } from "./marketRegistry";

describe("marketRegistry", () => {
  it("defines exactly the four approved markets with unique ids", () => {
    expect(MARKETS.map((m) => m.id).sort()).toEqual(["APAC", "EU", "IN", "US"]);
    expect(new Set(MARKETS.map((m) => m.id)).size).toBe(MARKETS.length);
  });

  it("non-India markets have a native index strip; India routes out", () => {
    for (const id of ["US", "EU", "APAC"]) {
      const m = getMarket(id)!;
      expect(m.sections.indexStrip.status).toBe("available");
      expect(m.indexNames.length).toBeGreaterThan(0);
      expect(hasOwnIndexStrip(m)).toBe(true);
    }
    const india = getMarket("IN")!;
    expect(india.indexNames).toEqual([]);
    expect(india.sections.indexStrip.status).toBe("external");
    expect(hasOwnIndexStrip(india)).toBe(false);
  });

  it("only the US has a wired futures feed", () => {
    expect(getMarket("US")!.sections.futures.status).toBe("available");
    expect(getMarket("EU")!.sections.futures.status).toBe("unavailable");
    expect(getMarket("APAC")!.sections.futures.status).toBe("unavailable");
  });

  it("data-blocked sections for non-India markets are unavailable WITH code/title/detail (never fabricated)", () => {
    const blocked: SectionKey[] = ["movers", "sectorHeatmap", "news"];
    for (const id of ["US", "EU", "APAC"]) {
      const m = getMarket(id)!;
      for (const key of blocked) {
        const s = m.sections[key];
        expect(s.status).toBe("unavailable");
        if (s.status === "unavailable") {
          expect(s.code.trim().length).toBeGreaterThan(0);   // internal diagnostic tag kept
          expect(s.title.trim().length).toBeGreaterThan(0);  // concise user-facing title
          expect(s.detail.trim().length).toBeGreaterThan(0); // section-specific detail
        }
      }
    }
  });

  it("India's blocked sections route out to real surfaces with an href", () => {
    const india = getMarket("IN")!;
    for (const key of ["movers", "sectorHeatmap", "news"] as SectionKey[]) {
      const s = india.sections[key];
      expect(s.status).toBe("external");
      if (s.status === "external") {
        expect(s.href).toBe("/market-intelligence");
        expect(s.label.trim().length).toBeGreaterThan(0);
      }
    }
  });

  it("index names reference only known global benchmarks", () => {
    const known = new Set([
      "S&P 500", "Dow Jones", "Nasdaq", "FTSE 100", "DAX", "CAC 40",
      "Nikkei 225", "Hang Seng", "Shanghai Composite", "KOSPI",
    ]);
    for (const m of MARKETS) for (const n of m.indexNames) expect(known.has(n)).toBe(true);
  });
});
