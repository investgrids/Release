import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ImpactMap } from "./ImpactMap";
import type { RippleV2, SupportingEvidenceV2, CompanyConnectedV2 } from "@/app/opportunity-radar/[id]/types";

const baseSupportingEvidence: SupportingEvidenceV2 = {
  development_id: "dev-1", canonical_title: "RBI cuts repo rate by 25bps",
  evidence_count: 4, current_confidence: 0.8, current_impact_tier: "High",
  first_observed_at: "2026-09-18T00:00:00Z", source_types: ["announcement", "news"],
};

const baseCompaniesConnected: CompanyConnectedV2[] = [
  { symbol: "HDFCBANK", company_name: "HDFC Bank", real_score: 60, real_direction: "positive", confirms_thesis: true, contradicts_thesis: false },
  { symbol: "ICICIBANK", company_name: "ICICI Bank", real_score: -40, real_direction: "negative", confirms_thesis: false, contradicts_thesis: true },
];

function realRipple(overrides: Partial<RippleV2> = {}): RippleV2 {
  return {
    anchor: "development:dev-1",
    nodes: [
      { id: "development:dev-1", node_type: "development", label: "RBI cuts repo rate by 25bps", ticker: null },
      { id: "sector:Banking", node_type: "sector", label: "Banking", ticker: null },
      { id: "company:HDFCBANK", node_type: "company", label: "HDFC Bank", ticker: "HDFCBANK" },
      { id: "company:ICICIBANK", node_type: "company", label: "ICICI Bank", ticker: "ICICIBANK" },
      { id: "policy:some-policy", node_type: "policy", label: "Some Policy", ticker: null },
    ],
    edges: [
      { id: "e1", source: "development:dev-1", target: "sector:Banking", edge_type: "benefits", weight: 1 },
      { id: "e2", source: "development:dev-1", target: "company:HDFCBANK", edge_type: "benefits", weight: 1 },
      { id: "e3", source: "development:dev-1", target: "company:ICICIBANK", edge_type: "hurts", weight: 1 },
      // Reversed policy -> development edge -- must never be treated as an outgoing impact.
      { id: "e4", source: "policy:some-policy", target: "development:dev-1", edge_type: "influences", weight: 1 },
    ],
    ...overrides,
  };
}

describe("ImpactMap — evidence-backed replacement for the bubble graph (2026-09-20)", () => {
  it("renders a real catalyst row with real sector and company impact chips, direction-labeled from real edge_type", () => {
    render(
      <ImpactMap
        ripple={realRipple()}
        supportingEvidence={[baseSupportingEvidence]}
        companiesConnected={baseCompaniesConnected}
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
        ripple={realRipple()}
        supportingEvidence={[baseSupportingEvidence]}
        companiesConnected={baseCompaniesConnected}
      />
    );
    const contradictingLink = screen.getByText(/ICICIBANK · At Risk/i).closest("a");
    expect(contradictingLink).toHaveAttribute("href", "/companies/ICICIBANK");
    const confirmingLink = screen.getByText(/HDFCBANK · Benefits/i).closest("a");
    expect(confirmingLink?.textContent).not.toMatch(/At Risk/);
  });

  it("never treats the reversed policy->development edge as an outgoing sector/company impact", () => {
    render(
      <ImpactMap
        ripple={realRipple()}
        supportingEvidence={[baseSupportingEvidence]}
        companiesConnected={baseCompaniesConnected}
      />
    );
    expect(screen.queryByText(/Some Policy/i)).not.toBeInTheDocument();
  });

  it("omits the whole section when the Development has no real graph presence at all", () => {
    const { container } = render(
      <ImpactMap
        ripple={{ anchor: null, nodes: [], edges: [] }}
        supportingEvidence={[baseSupportingEvidence]}
        companiesConnected={baseCompaniesConnected}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("never generates a row for a Development with a real graph node but zero real outgoing sector/company edges", () => {
    const ripple: RippleV2 = {
      anchor: "development:dev-1",
      nodes: [{ id: "development:dev-1", node_type: "development", label: "Isolated development", ticker: null }],
      edges: [],
    };
    const { container } = render(
      <ImpactMap ripple={ripple} supportingEvidence={[baseSupportingEvidence]} companiesConnected={[]} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("marks an unconfirmed, non-contradicting company as Monitor -- never a fabricated Benefits/At Risk label", () => {
    const ripple = realRipple({
      edges: [
        { id: "e1", source: "development:dev-1", target: "company:UNKNOWNCO", edge_type: "influences", weight: 1 },
      ],
      nodes: [
        { id: "development:dev-1", node_type: "development", label: "RBI cuts repo rate by 25bps", ticker: null },
        { id: "company:UNKNOWNCO", node_type: "company", label: "Unknown Co", ticker: "UNKNOWNCO" },
      ],
    });
    render(<ImpactMap ripple={ripple} supportingEvidence={[baseSupportingEvidence]} companiesConnected={[]} />);
    expect(screen.getByText(/UNKNOWNCO · Monitor/i)).toBeInTheDocument();
  });
});
