import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { CompanyRankingsView } from "./CompanyRankingsView";
import type { SectorRankings } from "@/lib/companyRankings";

describe("CompanyRankingsView — fixture states (2026-09-26 migration)", () => {
  it("renders a populated ranked table with real rank/score/coverage", () => {
    const data: SectorRankings = {
      sector: "Banking", supported: true, methodologyVersion: "BANKING_V1",
      ranked: [
        { symbol: "ICICIBANK", companyName: "ICICI Bank Ltd", rank: 1, score: 62.2, rating: "Positive", coveragePct: 83.3, calculatedAt: new Date().toISOString() },
        { symbol: "SBIN", companyName: "State Bank of India", rank: 2, score: 49.1, rating: "Neutral", coveragePct: 70.0, calculatedAt: new Date().toISOString() },
      ],
      partialCoverage: [], unavailable: [],
    };
    render(<CompanyRankingsView data={data} />);
    expect(screen.getByText("ICICI Bank Ltd")).toBeInTheDocument();
    expect(screen.getByText("62")).toBeInTheDocument();
    expect(screen.getByText("Positive")).toBeInTheDocument();
    expect(screen.getByText("83%")).toBeInTheDocument();
    expect(screen.queryByText("No banks qualify for a published ranking yet.")).not.toBeInTheDocument();
  });

  it("renders the partial-coverage section with each company's real reason, never mixed into the ranked table", () => {
    const data: SectorRankings = {
      sector: "Banking", supported: true,
      ranked: [],
      partialCoverage: [
        { symbol: "KOTAKBANK", companyName: "Kotak Mahindra Bank Ltd", message: "Partial coverage — 2 of 4 pillars", calculatedAt: new Date().toISOString() },
      ],
      unavailable: [],
    };
    render(<CompanyRankingsView data={data} />);
    expect(screen.getByText("No banks qualify for a published ranking yet.")).toBeInTheDocument();
    expect(screen.getByText(/Kotak Mahindra Bank Ltd/)).toBeInTheDocument();
    expect(screen.getByText("Partial coverage — 2 of 4 pillars")).toBeInTheDocument();
  });

  it("renders stale and other unavailable reasons in the collapsible section with their real labels", () => {
    const data: SectorRankings = {
      sector: "Banking", supported: true,
      ranked: [],
      partialCoverage: [],
      unavailable: [
        { symbol: "SBIN", companyName: "State Bank of India", reason: "stale", message: "Last computed more than 30 days ago.", calculatedAt: null },
        { symbol: "AXISBANK", companyName: "Axis Bank Ltd", reason: "ineligible", message: "Insufficient verified financial data.", calculatedAt: null },
      ],
    };
    render(<CompanyRankingsView data={data} />);
    const toggle = screen.getByRole("button", { name: /Not yet ranked/ });
    expect(toggle).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.getByText("Needs refresh")).toBeInTheDocument();
    expect(screen.getByText("Insufficient data")).toBeInTheDocument();
  });

  it("renders the honest unsupported-sector state for a non-Banking sector, never a fabricated ranking", () => {
    const data: SectorRankings = {
      sector: "Technology", supported: false,
      message: "MarketRipple Score is not yet available for this sector.",
      ranked: [], partialCoverage: [], unavailable: [],
    };
    render(<CompanyRankingsView data={data} />);
    expect(screen.getByText("MarketRipple Score is not yet available for this sector.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
