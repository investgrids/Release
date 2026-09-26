import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// One-score migration sweep (2026-09-26, owner instruction): this page used
// to run its own client-side "AI Score" — a hardcoded formula over real
// financial metrics, with no backend call — and declared an "AI winner"
// from it ("AI Comparison Summary", "Best Future Potential", the "AI
// Recommended Pick" banner). Replaced with the real, canonical
// MarketRipple Score projection (same endpoint the Company page itself
// reads), shown honestly per company (real score / partial coverage /
// unavailable) with no declared winner anywhere. These tests cover all
// three real states plus the real company-directory search that replaced
// the hardcoded 30-company registry.

let searchParamValues: Record<string, string> = { a: "ELIGCO", b: "PARTCO" };
vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: (k: string) => searchParamValues[k] ?? null }),
}));

function stockPayload(overrides: Record<string, unknown> = {}) {
  return {
    name: "Test Co", price: "100.00", pct_change: 1.2, change_abs: "1.20",
    market_cap: "₹1.00T", sector: "Test Sector", industry: "Test Industry",
    week52_high: "120.00", week52_low: "80.00",
    pe: "20.0", pb: "3.0", forward_pe: "18.0", eps: "5.0",
    roe: "18.0%", roa: "10.0%", roce: "—", beta: "0.9",
    dividend_yield: "1.5%", dividend_rate: "2.0",
    gross_margins: "40.0%", operating_margins: "30.0%", net_margins: "20.0%",
    debt_to_equity: "0.5", current_ratio: "1.8", free_cashflow: "₹50.0B",
    enterprise_value: "₹1.10T", recommendation: "buy",
    target_mean: "110.00", target_high: "130.00", target_low: "90.00",
    analyst_count: 10, buy_count: 6, hold_count: 3, sell_count: 1,
    held_institutions: "40.0%", held_insiders: "5.0%",
    quarterly_revenue: [], quarterly_net_income: [],
    annual_financials: [{ year: "FY25", revenue: 123456, net_income: 22222 }],
    events: [], peers: [],
    ...overrides,
  };
}

function mrScorePayload(overrides: Record<string, unknown>) {
  return { resolved: true, snapshot: true, eligible: true, score: 72, rating: "Strong", ...overrides };
}

function mockFetch(handlers: Record<string, any>) {
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    for (const [pattern, payload] of Object.entries(handlers)) {
      if (url.includes(pattern)) {
        return Promise.resolve({ ok: true, json: async () => payload });
      }
    }
    if (url.includes("/chart")) return Promise.resolve({ ok: true, json: async () => [] });
    return Promise.resolve({ ok: false, json: async () => null });
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("CompareContent — one-score migration (2026-09-26 sweep)", () => {
  it("shows a real, populated MarketRipple Score and a real 'Partial coverage' state honestly, with no fabricated AI score or declared winner", async () => {
    searchParamValues = { a: "ELIGCO", b: "PARTCO" };
    mockFetch({
      "/api/stocks/ELIGCO": stockPayload({ name: "Eligible Co", roe: "25.0%", beta: "0.5", annual_financials: [{ year: "FY26", revenue: 123456, net_income: 22222 }] }),
      "/api/stocks/PARTCO": stockPayload({ name: "Partial Co", roe: "10.0%", beta: "1.5", annual_financials: [{ year: "FY25", revenue: 987654, net_income: 11111 }] }),
      "/api/companies/ELIGCO/marketripple-score": mrScorePayload({ score: 72, rating: "Strong" }),
      "/api/companies/PARTCO/marketripple-score": {
        resolved: true, snapshot: true, eligible: true, score: null,
        pillar_coverage_status: "partial", pillar_coverage_message: "2 of 4 pillars available.",
      },
    });

    const { CompareContent } = await import("./CompareContent");
    render(<CompareContent />);

    await waitFor(() => expect(screen.getAllByText("Eligible Co").length).toBeGreaterThan(0));

    // Real revenue/profit fix (2026-09-26): /api/stocks/{symbol} never
    // actually returns top-level revenue/profit fields — this used to
    // always render "—". Confirms it now derives from the real
    // annual_financials figure instead.
    expect(screen.getByText("1,23,456")).toBeInTheDocument();

    // Real per-company fiscal-year label (2026-09-26, owner instruction:
    // "show the actual fiscal year-end"). ELIGCO and PARTCO are given
    // DIFFERENT real years here specifically to prove a generic "Latest
    // FY" placeholder was replaced by each company's own real year, not
    // just relabeled.
    expect(screen.getAllByText("FY26").length).toBeGreaterThan(0);
    expect(screen.getAllByText("FY25").length).toBeGreaterThan(0);

    // Honest period-label disclosure (2026-09-26, owner instruction:
    // labels need verified definitions) — TTM figures are the data
    // provider's own convention, not independently recomputed here.
    expect(screen.getAllByText(/trailing-twelve-month calculation/).length).toBeGreaterThan(0);

    // Real, single-metric Comparison Summary — never an overall "winner".
    expect(screen.getByText("Comparison Summary")).toBeInTheDocument();
    expect(screen.getByText("Highest ROE")).toBeInTheDocument();
    expect(screen.getByText("Lowest Beta")).toBeInTheDocument();
    // "Eligible Co" (roe 25%) should be named as the highest-ROE company —
    // appears at least in that summary row alongside its other mentions.
    expect(screen.getAllByText("Eligible Co").length).toBeGreaterThan(1);

    // Switch to the Valuation tab to reach the real MarketRipple Score tiles.
    fireEvent.click(screen.getByText("Valuation"));
    await waitFor(() => expect(screen.getByText("MarketRipple Score")).toBeInTheDocument());
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("Partial")).toBeInTheDocument();

    // Switch to AI Analysis — the old fabricated banner must be gone.
    fireEvent.click(screen.getByText("AI Analysis"));
    await waitFor(() => expect(screen.getAllByText("MarketRipple Score").length).toBeGreaterThan(0));
    expect(screen.queryByText("AI Score")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Powered")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Recommended Pick")).not.toBeInTheDocument();
    expect(screen.queryByText("Best Future Potential")).not.toBeInTheDocument();
    expect(screen.queryByText(/Scores highest/)).not.toBeInTheDocument();
    expect(screen.queryByText(/leads on risk-adjusted return metrics/)).not.toBeInTheDocument();
    expect(screen.queryByText("Score Comparison")).not.toBeInTheDocument();
  });

  it("shows the honest 'Unavailable' state for a company with no MarketRipple Score methodology or snapshot", async () => {
    searchParamValues = { a: "ELIGCO", b: "NOSCORECO" };
    mockFetch({
      "/api/stocks/ELIGCO": stockPayload({ name: "Eligible Co" }),
      "/api/stocks/NOSCORECO": stockPayload({ name: "No Score Co" }),
      "/api/companies/ELIGCO/marketripple-score": mrScorePayload({ score: 61, rating: "Neutral" }),
      "/api/companies/NOSCORECO/marketripple-score": { resolved: false },
    });

    const { CompareContent } = await import("./CompareContent");
    render(<CompareContent />);
    await waitFor(() => expect(screen.getAllByText("Eligible Co").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByText("AI Analysis"));
    await waitFor(() => expect(screen.getByText("61")).toBeInTheDocument());
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("searches the real company directory instead of a hardcoded list, and adds a company found there", async () => {
    searchParamValues = { a: "ELIGCO", b: "PARTCO" };
    mockFetch({
      "/api/stocks/ELIGCO": stockPayload({ name: "Eligible Co" }),
      "/api/stocks/PARTCO": stockPayload({ name: "Partial Co" }),
      "/api/stocks/REALCO": stockPayload({ name: "Real Directory Co" }),
      "/api/companies/ELIGCO/marketripple-score": mrScorePayload({}),
      "/api/companies/PARTCO/marketripple-score": mrScorePayload({}),
      "/api/companies/REALCO/marketripple-score": mrScorePayload({}),
      "/api/companies/search": { count: 1, companies: [{ symbol: "REALCO", name: "Real Directory Co", sector: "Test Sector", industry: "Test", cap: "large" }] },
    });

    const { CompareContent } = await import("./CompareContent");
    render(<CompareContent />);
    await waitFor(() => expect(screen.getAllByText("Eligible Co").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole("button", { name: /add company/i }));
    fireEvent.change(screen.getByPlaceholderText("Search company or symbol…"), { target: { value: "Real Dir" } });

    await waitFor(() => expect(screen.getByText("Real Directory Co")).toBeInTheDocument());
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    expect(fetchMock.mock.calls.some((call: any[]) => call[0].includes("/api/companies/search") && call[0].includes("Real+Dir"))).toBe(true);

    fireEvent.click(screen.getByText("Real Directory Co"));
    await waitFor(() => expect(screen.getAllByText("Real Directory Co").length).toBeGreaterThan(0));
  });
});
