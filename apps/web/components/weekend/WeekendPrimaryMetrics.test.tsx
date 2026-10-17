// Opportunity Radar SEO URL fix, slug-link consumer (2026-10-17).
// WeekendPrimaryMetrics links its top opportunity into /opportunity-radar --
// confirms it prefers the real slug (now propagated from
// app/api/weekend_intelligence.py's _resolve_opportunities, radar.py can
// resolve it since the backend SEO fix) and falls back to the numeric id
// for any snapshot predating the field, never a broken/fabricated URL.
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import type { WeekendIntelligenceSnapshotDTO, WeekendOpportunity } from "@/types/weekendIntelligence";
import { WeekendPrimaryMetrics } from "./WeekendPrimaryMetrics";

function baseOpportunity(overrides: Partial<WeekendOpportunity> = {}): WeekendOpportunity {
  return {
    id: 42,
    title: "Banking sector gold-loan expansion",
    sectors: ["Banking"],
    risk_level: "Medium",
    opportunity_score: 81,
    confidence: 0.74,
    reason: "Real AI summary text.",
    companies: [],
    ...overrides,
  };
}

function baseSnapshot(opportunities: WeekendOpportunity[]): WeekendIntelligenceSnapshotDTO {
  return {
    available: true,
    target_trading_date: "2026-08-17",
    last_trading_date: "2026-08-14",
    generated_at: "2026-08-16T12:30:00+00:00",
    checkpoint_label: "Sunday 18:00 IST",
    version: 1,
    status: "ok",
    baseline_available: true,
    overall_bias: "mixed",
    production_confidence: 44.27,
    confidence_components: {
      raw: { evidence_strength: 1, source_diversity: 0.5, agreement: 0.09, historical_support: 0.2, baseline_quality: 1 },
      weights: {}, weighted_contributions: {},
    },
    top_sectors: [],
    top_companies: [],
    market_risks: [],
    confidence_warnings: [],
    new_since_close_count: 0,
    new_since_close: [],
    changes_since_prior: [],
    evidence_summary: { total: 0, by_source_type: {} },
    opportunities,
    historical_analogues: [],
  };
}

describe("WeekendPrimaryMetrics — opportunity link slug preference", () => {
  it("links to the real slug when the opportunity has one", () => {
    const snapshot = baseSnapshot([baseOpportunity({ id: 42, slug: "banking-gold-loan-expansion-ab12cd" })]);
    render(<WeekendPrimaryMetrics snapshot={snapshot} />);
    const link = screen.getByRole("link", { name: /View opportunity/i });
    expect(link).toHaveAttribute("href", "/opportunity-radar/banking-gold-loan-expansion-ab12cd");
  });

  it("falls back to the numeric id when no slug is present, never a broken URL", () => {
    const snapshot = baseSnapshot([baseOpportunity({ id: 42, slug: undefined })]);
    render(<WeekendPrimaryMetrics snapshot={snapshot} />);
    const link = screen.getByRole("link", { name: /View opportunity/i });
    expect(link).toHaveAttribute("href", "/opportunity-radar/42");
  });
});
