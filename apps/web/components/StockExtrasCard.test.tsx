import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StockExtrasCard, formatDay } from "./StockExtrasCard";

afterEach(() => vi.restoreAllMocks());
const mockFetch = (body: unknown, ok = true) => vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok, json: async () => body }));

describe("StockExtrasCard", () => {
  it("shows results, growth and dividends with the Yahoo label", async () => {
    mockFetch({
      earnings: { next_date: "2026-10-08", next_eps_estimate: "₹38.17", history: [{ date: "2026-07-08", estimate: "₹37.33", actual: "₹38.28", surprise_pct: "+2.5%" }] },
      growth_valuation: [{ label: "EV / EBITDA", value: "9.96" }],
      dividends: { yield: "3.13%", rate: "₹65.00", history: [{ date: "2026-07-15", amount: "₹12.00" }] },
    });
    render(<StockExtrasCard symbol="TCS" />);
    await waitFor(() => expect(screen.getByText("EV / EBITDA")).toBeInTheDocument());
    expect(screen.queryByText(/Source: Yahoo/)).toBeNull();
    expect(screen.getByText(/8 Oct 2026 · est\. ₹38\.17/)).toBeInTheDocument();
    expect(screen.getByText(/▲ 2\.5%/)).toBeInTheDocument();
    expect(screen.getByText("₹38.28").className).toMatch(/emerald/);
    expect(screen.getByText("3.13%")).toBeInTheDocument();
  });

  it("renders nothing when Yahoo has nothing or the request fails", async () => {
    mockFetch({ earnings: { next_date: null, next_eps_estimate: null, history: [] }, growth_valuation: [], dividends: { yield: null, rate: null, history: [] } });
    const { container } = render(<StockExtrasCard symbol="X" />);
    await waitFor(() => expect(container.querySelector("[aria-busy]")).toBeNull());
    expect(container).toBeEmptyDOMElement();
  });

  it("formatDay keeps an unparseable date as-is", () => expect(formatDay("soon")).toBe("soon"));
});
