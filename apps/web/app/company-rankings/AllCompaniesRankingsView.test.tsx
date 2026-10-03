import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { AllCompaniesRankingsView } from "./AllCompaniesRankingsView";
import type { AllCompanyRankingsPage } from "@/lib/companyRankings";

describe("AllCompaniesRankingsView — insufficient market history", () => {
  it("renders an RSI-only HEG snapshot as N/A with its reason and no score or rank", () => {
    const data: AllCompanyRankingsPage = {
      total: 1,
      page: 1,
      pageSize: 50,
      totalPages: 1,
      companies: [{
        symbol: "HEG",
        companyName: "Hindustan Electro Graphite",
        sector: "Infrastructure",
        status: "insufficient_data",
        score: null,
        rating: null,
        coveragePct: null,
        rank: null,
        totalRankedInSector: null,
        calculatedAt: "2026-09-30T06:22:13.034313+00:00",
        message: "Score unavailable — insufficient market history. MarketRipple requires at least 64 completed price observations and one market or sector comparison.",
        localPreview: null,
      }],
    };

    render(<AllCompaniesRankingsView data={data} />);

    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(screen.getByText("Insufficient data")).toBeInTheDocument();
    expect(screen.getByTitle(/Score unavailable — insufficient market history/)).toBeInTheDocument();
    expect(screen.queryByText("60")).not.toBeInTheDocument();
  });
});

describe("AllCompaniesRankingsView — states and peer note (2026-10-03)", () => {
  const row = (symbol: string, status: any, message: string | null) => ({
    symbol, companyName: symbol + " Ltd", sector: "Metals", status, score: null, rating: null, coveragePct: null,
    rank: null, totalRankedInSector: null, calculatedAt: null, message, localPreview: null,
  });

  it("labels each company with its own state and reason, and explains that peer changes can move scores", () => {
    const data: AllCompanyRankingsPage = {
      total: 4, page: 1, pageSize: 50, totalPages: 1, companies: [
        row("A", "not_processed", "This company is supported, but its score hasn't been calculated yet."),
        row("B", "needs_refresh", "Last calculated on 01 Jul 2026."),
        row("C", "insufficient_data", "Financial data awaiting update"),
        row("D", "unsupported", "Bank scores need filed disclosure data."),
      ],
    };
    render(<AllCompaniesRankingsView data={data} />);
    for (const label of ["Not processed yet", "Score needs refresh", "Insufficient data", "Not supported yet"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByTitle(/hasn't been calculated yet/)).toBeInTheDocument();
    expect(screen.getByTestId("rankings-peer-note")).toHaveTextContent("can change when companies are added");
    expect(screen.getByRole("link", { name: "How scores work" })).toHaveAttribute("href", "/methodology/marketripple-score#peer-groups-heading");
  });
});
