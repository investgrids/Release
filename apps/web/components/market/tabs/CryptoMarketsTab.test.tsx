import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { CryptoMarketsTab } from "./CryptoMarketsTab";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function mockFetch(body: unknown, ok = true) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok,
    json: async () => body,
  }));
}

describe("CryptoMarketsTab", () => {
  it("shows the unavailable state when the feature is disabled", async () => {
    mockFetch({ enabled: false, assets: [] });
    render(<CryptoMarketsTab />);
    await waitFor(() => expect(screen.getByText(/Crypto market data is unavailable/i)).toBeInTheDocument());
  });

  it("renders a supported asset with price, 24h change and freshness", async () => {
    mockFetch({
      enabled: true,
      assets: [{
        name: "Bitcoin", symbol: "BTC", glyph: "₿", pair: "BTC/USD",
        value: "81,539.61", quote_currency: "USD", pct: "-0.37%", positive: false,
        change_window: "vs prior UTC-day close", volume_24h: 24143153152,
        source: "Yahoo Finance", source_timestamp: "2026-10-20T07:00:00+00:00", freshness: "live",
      }],
    });
    render(<CryptoMarketsTab />);
    await waitFor(() => expect(screen.getByText("Bitcoin")).toBeInTheDocument());
    expect(screen.getByText("81,539.61")).toBeInTheDocument();
    expect(screen.getByText("-0.37%")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText(/24h vol \$24\.1B/)).toBeInTheDocument();
  });

  it("never fabricates a value for an unavailable asset", async () => {
    mockFetch({
      enabled: true,
      assets: [{
        name: "Solana", symbol: "SOL", glyph: "◎", pair: "SOL/USD",
        value: "—", quote_currency: "USD", pct: "—", positive: true,
        change_window: "vs prior UTC-day close", volume_24h: null,
        source: "Yahoo Finance", source_timestamp: null, freshness: "unavailable",
      }],
    });
    render(<CryptoMarketsTab />);
    // enabled:true but the single asset is unavailable → still renders the asset
    // row (not a fabricated price) with the Unavailable badge and "No data".
    await waitFor(() => expect(screen.getByText("Solana")).toBeInTheDocument());
    expect(screen.getByText("No data")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });
});
