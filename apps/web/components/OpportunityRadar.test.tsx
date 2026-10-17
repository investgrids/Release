// Opportunity Radar SEO URL fix, slug-link consumer (2026-10-17).
// No live caller of this component exists in the codebase today (confirmed
// via a repo-wide search) -- this test exists so the component is correct
// and ready the moment a real caller supplies the slug the backend already
// returns, without this component ever inventing or reconstructing one.
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { OpportunityRadar } from "./OpportunityRadar";

describe("OpportunityRadar — slug link preference", () => {
  it("links to the real slug when the item has one", () => {
    render(<OpportunityRadar items={[
      { id: "42", slug: "banking-gold-loan-expansion-ab12cd", score: 81, theme: "Banking", reason: "Real reason.", category: "Energy" },
    ]}/>);
    const link = screen.getByRole("link", { name: /Banking/i });
    expect(link).toHaveAttribute("href", "/opportunity-radar/banking-gold-loan-expansion-ab12cd");
  });

  it("falls back to the id when no slug is present, never a broken URL", () => {
    render(<OpportunityRadar items={[
      { id: "42", score: 81, theme: "Banking", reason: "Real reason.", category: "Energy" },
    ]}/>);
    const link = screen.getByRole("link", { name: /Banking/i });
    expect(link).toHaveAttribute("href", "/opportunity-radar/42");
  });
});
