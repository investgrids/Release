import { describe, expect, it } from "vitest";
import { bankFilingOverlay, MarketRippleScoreCard, type MarketRippleScoreData } from "./[symbol]/CompanyPageClient";

const base: MarketRippleScoreData = { resolved: true, snapshot: true, eligible: false, score: null, coverage_state: "unsupported", coverage_label: "Not supported yet", sector: "Banking" };

describe("bankFilingOverlay", () => {
  it("turns a scored filing row into an eligible three-pillar score", () => {
    const d = bankFilingOverlay(base, {
      state: "scored", score: 47.7, rating: "Neutral", pillars: { financial_strength: 53.9, valuation: 12.8, market_behaviour: 77.6 },
      coverage_pct: 80, metrics_used: 5, labels: ["[Loss-making: valuation ranked worst]"], unavailable: null, source: { period_end: "2026-03-31", scope: "Consolidated" },
    });
    expect(d.eligible).toBe(true);
    expect(d.score).toBe(47.7);
    expect(d.coverage_state).toBe("scored");
    expect(d.pillars?.current_intelligence).toBeNull();
    expect(d.filing).toMatchObject({ period_end: "2026-03-31", scope: "Consolidated", metrics_used: 5 });
  });

  it("shows the reason for a withheld bank and never a number", () => {
    const d = bankFilingOverlay(base, { state: "withheld", score: null, rating: null, pillars: null, coverage_pct: null, metrics_used: null, unavailable: { reason: "VALUATION_DATA_DISCREPANCY", label: null } });
    expect(d.eligible).toBe(false);
    expect(d.score).toBeNull();
    expect(d.coverage_label).toBe("Valuation data under review");
  });
  it("falls back to a generic label for an unknown reason", () => {
    const d = bankFilingOverlay(base, { state: "withheld", score: null, rating: null, pillars: null, coverage_pct: null, metrics_used: null, unavailable: { reason: "SOMETHING_NEW", label: null } });
    expect(d.coverage_label).toBe("Score withheld");
  });
  it("exports the card so the filing variant can render", () => expect(typeof MarketRippleScoreCard).toBe("function"));
});
