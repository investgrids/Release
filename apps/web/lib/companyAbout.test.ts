import { describe, expect, it } from "vitest";
import { aboutHeading, aboutSummary } from "./companyAbout";

const tcs = { name: "Tata Consultancy Services Limited", symbol: "tcs", sector: "Technology", industry: "Information Technology Services", price: "2,075.00", pct_change: 1.19, market_cap: "₹7.51T", pe: "15.1" };

describe("about text", () => {
  it("names the company and ticker in the heading", () => {
    expect(aboutHeading(tcs)).toBe("About Tata Consultancy Services Limited (TCS)");
  });
  it("builds natural sentences with the searchable terms from the live fields", () => {
    const t = aboutSummary(tcs);
    expect(t).toContain("Tata Consultancy Services Limited (TCS) is listed on the NSE in the Technology sector, Information Technology Services industry.");
    expect(t).toContain("The TCS share price is ₹2,075.00 (+1.19% today), with a market capitalisation of ₹7.51T and a price-to-earnings (P/E) ratio of 15.1.");
    expect(t).toContain("MarketRipple tracks the TCS investment thesis, the ripple-chain impact of market events on Tata Consultancy Services Limited, and the Technology sector outlook.");
  });
  it("leaves out anything the page does not have rather than printing a placeholder", () => {
    const t = aboutSummary({ ...tcs, market_cap: "—", pe: undefined, industry: "Technology", pct_change: null });
    expect(t).toContain("The TCS share price is ₹2,075.00.");
    expect(t).not.toMatch(/market capitalisation|P\/E|—|undefined|null/);
    expect(t).toContain("in the Technology sector.");
    expect(aboutSummary({ name: "X Ltd", symbol: "x" })).toBe("X Ltd (X) is listed on the NSE. MarketRipple tracks the X investment thesis, the ripple-chain impact of market events on X Ltd.");
  });
  it("handles a P/E without a market cap and a market cap without a P/E", () => {
    expect(aboutSummary({ ...tcs, market_cap: null })).toContain("with a price-to-earnings (P/E) ratio of 15.1.");
    expect(aboutSummary({ ...tcs, pe: "" })).toContain("with a market capitalisation of ₹7.51T.");
  });
});
