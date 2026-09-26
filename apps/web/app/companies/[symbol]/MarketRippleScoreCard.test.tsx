import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MarketRippleScoreCard, type MarketRippleScoreData } from "./CompanyPageClient";
import type { StockDetail } from "./CompanyPageClient";

// MarketRippleScoreCard never reads `stock` today — see its own component
// body — so a minimal cast is honest here, not a shortcut around real
// coverage; this mirrors what the running app actually exercises.
const stock = {} as StockDetail;

describe("MarketRippleScoreCard — comparability interim rule (2026-09-26)", () => {
  it("shows a real headline number and rating when eligible with complete coverage", () => {
    const data: MarketRippleScoreData = {
      resolved: true, snapshot: true, eligible: true, score: 63.7, rating: "Positive",
      pillars: { financial_strength: 70, valuation: 60, market_behaviour: 55, current_intelligence: 62 },
      evidence_coverage_pct: 83.3, pillar_coverage_status: "complete",
      pillar_coverage_message: "Complete coverage — 4 of 4 pillars",
    };
    render(<MarketRippleScoreCard data={data} stock={stock} />);
    expect(screen.getByText("63")).toBeInTheDocument(); // marketRippleScoreDisplayInt floors 63.7, never rounds up
    expect(screen.getByText("Positive")).toBeInTheDocument();
    expect(screen.queryByText("Partial coverage")).not.toBeInTheDocument();
    expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
  });

  it("shows the Partial coverage state with real per-pillar values, never a fabricated headline number, when eligible but coverage is partial", () => {
    const data: MarketRippleScoreData = {
      resolved: true, snapshot: true, eligible: true, score: null, rating: null,
      pillars: { financial_strength: 68, valuation: 60, market_behaviour: null, current_intelligence: null },
      pillar_coverage_status: "partial",
      pillar_coverage_message: "Partial coverage — 2 of 4 pillars",
    };
    render(<MarketRippleScoreCard data={data} stock={stock} />);
    expect(screen.getByText("Partial coverage")).toBeInTheDocument();
    expect(screen.getByText(/Partial coverage — 2 of 4 pillars/)).toBeInTheDocument();
    // Real pillar values that DID compute must still render.
    expect(screen.getByText("68")).toBeInTheDocument();
    expect(screen.getByText("60")).toBeInTheDocument();
    // No fabricated headline number — "/ 100" only appears in the complete-coverage layout.
    expect(screen.queryByText("/ 100")).not.toBeInTheDocument();
    expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
  });

  it("shows the generic Unavailable state with the real block reason when not eligible", () => {
    const data: MarketRippleScoreData = {
      resolved: true, snapshot: true, eligible: false, score: null,
      block_headline: "Insufficient verified financial data",
      block_message: "Some financial evidence could not be verified, so MarketRipple is not publishing a score for this company yet.",
    };
    render(<MarketRippleScoreCard data={data} stock={stock} />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("Insufficient verified financial data")).toBeInTheDocument();
    expect(screen.queryByText("Partial coverage")).not.toBeInTheDocument();
  });

  it("never shows Partial coverage for an eligible symbol with a real complete score just because pillar_coverage_status is missing", () => {
    // Defensive: pillar_coverage_status is only gated True when explicitly
    // "partial" — a missing/undefined value must fall through to the
    // normal complete-score rendering, not a false "Partial coverage".
    const data: MarketRippleScoreData = {
      resolved: true, snapshot: true, eligible: true, score: 50, rating: "Neutral",
      pillars: { financial_strength: 50, valuation: 50, market_behaviour: 50, current_intelligence: 50 },
    };
    render(<MarketRippleScoreCard data={data} stock={stock} />);
    expect(screen.queryByText("Partial coverage")).not.toBeInTheDocument();
    expect(screen.getByText("Neutral")).toBeInTheDocument();
    expect(screen.getAllByText("50").length).toBeGreaterThan(0); // headline + all 4 pillars share this value
  });

  // One-score migration regression guard (2026-09-26, owner instruction):
  // CurrentIntelligenceCard/useCompanyRating (the older single-engine
  // score's own Overview-tab card) were deleted from CompanyPageClient.tsx
  // entirely — MarketRippleScoreSection now always renders this same card,
  // even when there is no snapshot at all (unsupported sector, or not yet
  // computed for this bank). These tests prove that state renders the
  // honest "Unavailable" card, never the old numeric score/rating/verdict,
  // and that nothing here depends on `stock` in a way that could suppress
  // or corrupt unrelated company data elsewhere on the page.
  describe("one-score migration — no snapshot at all never falls back to the old score", () => {
    it("renders the honest Unavailable state, not the old score/verdict, when no snapshot has ever been computed", () => {
      const data: MarketRippleScoreData = { resolved: true, snapshot: false };
      render(<MarketRippleScoreCard data={data} stock={stock} />);
      expect(screen.getByText("Unavailable")).toBeInTheDocument();
      expect(screen.getByText("Not available yet")).toBeInTheDocument();
      // The old engine's own card title/labels must never appear here —
      // that component no longer exists in this file at all.
      expect(screen.queryByText("Current Intelligence")).not.toBeInTheDocument();
      expect(screen.queryByText(/Insufficient evidence for a current-intelligence view/)).not.toBeInTheDocument();
      // No stray numeric score of any kind renders in this state.
      expect(screen.queryByText("/ 100")).not.toBeInTheDocument();
    });

    it("renders the same honest Unavailable state for the raw fetch-failure fallback shape used by MarketRippleScoreSection", () => {
      // Mirrors MarketRippleScoreSection's `data ?? { resolved: false }` —
      // the shape passed when the fetch itself failed, not just when the
      // company has no snapshot.
      const data: MarketRippleScoreData = { resolved: false };
      render(<MarketRippleScoreCard data={data} stock={stock} />);
      expect(screen.getByText("Unavailable")).toBeInTheDocument();
      expect(screen.queryByText("Current Intelligence")).not.toBeInTheDocument();
      expect(screen.queryByText(/[0-9]{2,3}\/100/)).not.toBeInTheDocument();
    });
  });
});
