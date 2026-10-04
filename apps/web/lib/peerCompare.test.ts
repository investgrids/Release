import { describe, expect, it } from "vitest";
import { median, parseFigure, peerSentences } from "./peerCompare";

describe("parseFigure / median", () => {
  it("reads page figures and rejects placeholders", () => {
    expect(parseFigure("₹1,234.5")).toBe(1234.5); expect(parseFigure("47.7%")).toBe(47.7); expect(parseFigure("-3.2%")).toBe(-3.2);
    expect(parseFigure("—")).toBeNull(); expect(parseFigure("N/A")).toBeNull(); expect(parseFigure("")).toBeNull(); expect(parseFigure(undefined)).toBeNull(); expect(parseFigure("abc")).toBeNull();
  });
  it("takes the median of odd and even sets", () => {
    expect(median([3, 1, 2])).toBe(2); expect(median([1, 2, 3, 4])).toBe(2.5); expect(median([])).toBeNull();
  });
});

describe("peerSentences", () => {
  const peers = [{ symbol: "INFY", pe: "21.0", roe: "30.0%" }, { symbol: "WIPRO", pe: "18.0", roe: "16.0%" }, { symbol: "HCLTECH", pe: "24.0", roe: "24.0%" }];
  it("states the P/E and ROE position against the peer median, from the figures shown", () => {
    const s = peerSentences({ symbol: "TCS", pe: "15.1", roe: "47.7%" }, peers);
    expect(s).toEqual([
      "P/E 15.1 against a peer median of 21.0: below the median; priced lower than 3 of 3 peers.",
      "ROE 47.7% against a peer median of 24.0%: above the median; higher than 3 of 3 peers.",
    ]);
  });
  it("says nothing when fewer than two peers have a figure, or the company's own is missing or not positive (P/E)", () => {
    expect(peerSentences({ symbol: "TCS", pe: "15.1", roe: "47.7%" }, [peers[0]])).toEqual([]);
    expect(peerSentences({ symbol: "TCS", pe: "—", roe: "—" }, peers)).toEqual([]);
    expect(peerSentences({ symbol: "X", pe: "-4.0", roe: "10%" }, peers).some(l => l.startsWith("P/E"))).toBe(false);
    expect(peerSentences({ symbol: "X", pe: "20", roe: "10%" }, [{ symbol: "A", pe: "—", roe: "—" }, { symbol: "B", pe: "-3", roe: "—" }])).toEqual([]);
  });
});
