// Directional-surface reassessment (2026-09-03) — TrendSparkline used to
// draw a deterministic Math.sin-seeded fake chart, visually
// indistinguishable from a real one. Confirms the replacement
// (TrendIndicator) only ever shows the real, honest direction -- never a
// fabricated shape/magnitude.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { AIOpportunitySection } from "./AIOpportunitySection";

function row(overrides: Partial<Parameters<typeof AIOpportunitySection>[0]["items"][0]> = {}) {
  return {
    href: "/opportunity-radar/test", score: 78, theme: "Test Theme",
    reason: "test reason", category: "Test", trend: "up" as const,
    ...overrides,
  };
}

describe("AIOpportunitySection — CD3-D reassessment fix (no fake sparkline)", () => {
  it("renders no <polyline> chart element -- the fake-chart-drawing primitive is gone", () => {
    const { container } = render(<AIOpportunitySection items={[row()]} />);
    expect(container.querySelector("polyline")).not.toBeInTheDocument();
  });

  it("shows the real trend direction honestly for up/down/stable", () => {
    render(<AIOpportunitySection items={[
      row({ href: "/a", trend: "up" }),
      row({ href: "/b", trend: "down" }),
      row({ href: "/c", trend: "stable" }),
    ]} />);
    expect(screen.getByLabelText("Trend: Up")).toBeInTheDocument();
    expect(screen.getByLabelText("Trend: Down")).toBeInTheDocument();
    expect(screen.getByLabelText("Trend: Stable")).toBeInTheDocument();
  });

  it("empty items list shows the honest empty state, not a fabricated row", () => {
    render(<AIOpportunitySection items={[]} />);
    expect(screen.getByText("No opportunities detected yet.")).toBeInTheDocument();
  });
});
