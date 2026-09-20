import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ImpactMap } from "./ImpactMap";
import type { DevelopmentImpactV2 } from "@/app/opportunity-radar/[id]/types";

function row(overrides: Partial<DevelopmentImpactV2> = {}): DevelopmentImpactV2 {
  return {
    development_id: "dev-1",
    canonical_title: "RBI cuts repo rate by 25bps",
    evidence_count: 4,
    first_observed_at: "2026-09-18T00:00:00Z",
    source_types: ["announcement", "news"],
    sector_impacts: [],
    company_impacts: [],
    ...overrides,
  };
}

describe("ImpactMap — renders the server-computed per-Development contract (2026-09-20)", () => {
  it("renders a real catalyst row with real sector and company impact chips, direction-labeled from the real server field", () => {
    render(
      <ImpactMap
        developmentImpacts={[
          row({
            sector_impacts: [{ sector: "Banking", direction: "benefits" }],
            company_impacts: [
              { symbol: "HDFCBANK", company_name: "HDFC Bank", direction: "benefits", confirms_thesis: true, contradicts_thesis: false },
              { symbol: "ICICIBANK", company_name: "ICICI Bank", direction: "hurts", confirms_thesis: false, contradicts_thesis: true },
            ],
          }),
        ]}
      />
    );
    expect(screen.getByText(/RBI cuts repo rate by 25bps/i)).toBeInTheDocument();
    expect(screen.getByText(/Banking · Positive/i)).toBeInTheDocument();
    expect(screen.getByText(/HDFCBANK · Benefits/i)).toBeInTheDocument();
    expect(screen.getByText(/ICICIBANK · At Risk/i)).toBeInTheDocument();
  });

  it("shows a contradiction indicator only for the company whose real signal disagrees with the thesis", () => {
    render(
      <ImpactMap
        developmentImpacts={[
          row({
            company_impacts: [
              { symbol: "HDFCBANK", company_name: "HDFC Bank", direction: "benefits", confirms_thesis: true, contradicts_thesis: false },
              { symbol: "ICICIBANK", company_name: "ICICI Bank", direction: "hurts", confirms_thesis: false, contradicts_thesis: true },
            ],
          }),
        ]}
      />
    );
    const contradictingLink = screen.getByText(/ICICIBANK · At Risk/i).closest("a");
    expect(contradictingLink).toHaveAttribute("href", "/companies/ICICIBANK");
    const confirmingLink = screen.getByText(/HDFCBANK · Benefits/i).closest("a");
    expect(confirmingLink?.textContent).not.toMatch(/At Risk/);
  });

  it("renders each Development as its own row, never merging distinct developments' sectors together", () => {
    render(
      <ImpactMap
        developmentImpacts={[
          row({ development_id: "dev-a", canonical_title: "Dev A real title", sector_impacts: [{ sector: "Banking", direction: "benefits" }] }),
          row({ development_id: "dev-b", canonical_title: "Dev B real title", sector_impacts: [{ sector: "Pharma", direction: "hurts" }] }),
        ]}
      />
    );
    expect(screen.getByText(/Dev A real title/i)).toBeInTheDocument();
    expect(screen.getByText(/Dev B real title/i)).toBeInTheDocument();
    expect(screen.getByText(/Banking · Positive/i)).toBeInTheDocument();
    expect(screen.getByText(/Pharma · Negative/i)).toBeInTheDocument();
  });

  it("omits the whole section when there are no development impact rows at all", () => {
    const { container } = render(<ImpactMap developmentImpacts={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows an em dash, never fabricated content, for a row with no real sector or company impacts", () => {
    render(<ImpactMap developmentImpacts={[row({ sector_impacts: [], company_impacts: [] })]} />);
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBe(2); // one for the empty sector column, one for the empty company column
  });

  it("marks an unconfirmed, non-contradicting company as Monitor -- never a fabricated Benefits/At Risk label", () => {
    render(
      <ImpactMap
        developmentImpacts={[
          row({ company_impacts: [{ symbol: "UNKNOWNCO", company_name: "Unknown Co", direction: "influences", confirms_thesis: false, contradicts_thesis: false }] }),
        ]}
      />
    );
    expect(screen.getByText(/UNKNOWNCO · Monitor/i)).toBeInTheDocument();
  });

  it("falls back to 'influences' styling defensively for an unexpected direction value, never crashing", () => {
    render(
      <ImpactMap
        developmentImpacts={[
          row({ sector_impacts: [{ sector: "Banking", direction: "some_unexpected_value" }] }),
        ]}
      />
    );
    expect(screen.getByText(/Banking · Neutral/i)).toBeInTheDocument();
  });
});
