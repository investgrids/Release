import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// next/link needs no App Router context in these unit tests.
vi.mock("next/link", () => ({
  default: ({ children, href }: any) => <a href={href}>{children}</a>,
}));

import { GlobalMarketsSelectorView } from "./GlobalMarketsSelectorView";

const fresh = (name: string, flag: string, value: string, pct: string, positive: boolean) => ({
  name, flag, value, pct, positive, source: "Yahoo Finance",
  source_timestamp: "2026-10-24T20:00:00Z", session: "CLOSED",
  timezone: "America/New_York", freshness: "closed",
});

const TEN = [
  fresh("Dow Jones", "🇺🇸", "52,000.00", "-1.00%", false),
  fresh("S&P 500", "🇺🇸", "7,600.00", "-0.50%", false),
  fresh("Nasdaq", "🇺🇸", "25,900.00", "-0.20%", false),
  fresh("FTSE 100", "🇬🇧", "10,690.00", "-0.30%", false),
  fresh("DAX", "🇩🇪", "24,000.00", "+0.40%", true),
  fresh("CAC 40", "🇫🇷", "8,100.00", "+0.10%", true),
  fresh("Nikkei 225", "🇯🇵", "64,000.00", "+1.20%", true),
  fresh("Hang Seng", "🇭🇰", "26,000.00", "-0.80%", false),
  fresh("Shanghai Composite", "🇨🇳", "3,900.00", "+0.30%", true),
  fresh("KOSPI", "🇰🇷", "3,300.00", "-0.10%", false),
];

const FUTURES = {
  enabled: true, market: "US",
  futures: [
    { name: "S&P 500 Fut.", ticker: "ES=F", instrument: "future", value: "7,650.00", change: "+10.00", pct: "+0.13%", positive: true, source: "Yahoo Finance", source_timestamp: "2026-10-25T02:00:00Z", session: "REGULAR", timezone: "America/New_York", freshness: "live" },
    { name: "Nasdaq 100 Fut.", ticker: "NQ=F", instrument: "future", value: "26,000.00", change: "+30.00", pct: "+0.12%", positive: true, source: "Yahoo Finance", source_timestamp: "2026-10-25T02:00:00Z", session: "REGULAR", timezone: "America/New_York", freshness: "live" },
    { name: "Dow Futures", ticker: "YM=F", instrument: "future", value: "52,100.00", change: "+40.00", pct: "+0.08%", positive: true, source: "Yahoo Finance", source_timestamp: "2026-10-25T02:00:00Z", session: "REGULAR", timezone: "America/New_York", freshness: "live" },
  ],
};

function routeFetch() {
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    const body = String(url).includes("/futures") ? FUTURES : { indices: TEN };
    return Promise.resolve({ ok: true, json: async () => body });
  }));
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("GlobalMarketsSelectorView", () => {
  it("defaults to US: shows US cash indices + US futures, and an honest movers limitation", async () => {
    routeFetch();
    render(<GlobalMarketsSelectorView />);
    await waitFor(() => expect(screen.getByText("S&P 500")).toBeInTheDocument());
    expect(screen.getByText("Dow Jones")).toBeInTheDocument();
    expect(screen.getByText("Nasdaq")).toBeInTheDocument();
    // futures rendered separately (distinct from the cash "S&P 500")
    expect(screen.getByText("S&P 500 Fut.")).toBeInTheDocument();
    // US has no stock universe → concise movers limitation stated, not fabricated
    expect(screen.getByText(/Stock movers require a dedicated market-data source/i)).toBeInTheDocument();
    // a non-US index must NOT appear under the US selection
    expect(screen.queryByText("FTSE 100")).not.toBeInTheDocument();
  });

  it("switching to Europe updates every section and leaves no stale US rows", async () => {
    routeFetch();
    render(<GlobalMarketsSelectorView />);
    await waitFor(() => expect(screen.getByText("S&P 500")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("tab", { name: /Europe/ }));

    await waitFor(() => expect(screen.getByText("FTSE 100")).toBeInTheDocument());
    expect(screen.getByText("DAX")).toBeInTheDocument();
    expect(screen.getByText("CAC 40")).toBeInTheDocument();
    // stale US rows cleared
    expect(screen.queryByText("S&P 500")).not.toBeInTheDocument();
    expect(screen.queryByText("S&P 500 Fut.")).not.toBeInTheDocument();
    // Europe has no futures feed → limitation, not fabricated futures
    expect(screen.getByText(/No index-futures feed is wired/i)).toBeInTheDocument();
  });

  it("India routes out to existing surfaces — no native strip, no fabricated movers", async () => {
    routeFetch();
    render(<GlobalMarketsSelectorView />);
    await waitFor(() => expect(screen.getByText("S&P 500")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("tab", { name: /India/ }));

    await waitFor(() => expect(screen.getByText(/Overview & Live Market tabs/i)).toBeInTheDocument());
    // routing links out to the India hub
    expect(screen.getAllByText(/India top movers|Live Market tab/i).length).toBeGreaterThan(0);
    // no non-India index rows bled through
    expect(screen.queryByText("S&P 500")).not.toBeInTheDocument();
    expect(screen.queryByText("FTSE 100")).not.toBeInTheDocument();
  });
});
