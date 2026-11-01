import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { BrentMacroCard } from "./BrentMacroCard";
import { __resetBrentObservationCache } from "@/lib/brent";

// A realistic /api/commodities/ payload (shape from app/api/commodities.py) with
// the EIA Brent item carrying source / as_of / stale.
function commoditiesBody(overrides: Record<string, unknown> = {}) {
  return {
    metals: [{ id: "gold", name: "Gold", unit: "USD / oz", price: "4,100.00", change: "+10", pct: 0.2, positive: true, high: "—", low: "—", chart: [] }],
    energy: [{
      id: "brent", name: "Crude Oil (Brent)", unit: "USD / bbl",
      price: "123.10", change: "-5.02", pct: -3.92, positive: false,
      high: "—", low: "—", chart: [],
      source: "U.S. Energy Information Administration", as_of: "2026-10-27", stale: false,
      ...overrides,
    }],
  };
}

function stubFetch(body: unknown, ok = true) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok,
    json: () => Promise.resolve(body),
  }));
}

beforeEach(() => { __resetBrentObservationCache(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); __resetBrentObservationCache(); });

describe("BrentMacroCard (Global-only)", () => {
  it("renders the EIA observation with source, observation date and freshness", async () => {
    stubFetch(commoditiesBody());
    render(<BrentMacroCard />);
    expect(await screen.findByText("Brent Crude")).toBeInTheDocument();
    expect(screen.getByText("$123.10")).toBeInTheDocument();
    expect(screen.getByText(/U\.S\. Energy Information Administration/)).toBeInTheDocument();
    expect(screen.getByText(/Series RBRTE/)).toBeInTheDocument();
    expect(screen.getByText(/As of October 27, 2026/)).toBeInTheDocument();
    expect(screen.getByText("Delayed")).toBeInTheDocument();
  });

  it("marks a stale observation as Stale", async () => {
    stubFetch(commoditiesBody({ stale: true }));
    render(<BrentMacroCard />);
    expect(await screen.findByText("Stale")).toBeInTheDocument();
  });

  it("has no crypto presentation (no 'Macro Context', no crypto wording)", async () => {
    stubFetch(commoditiesBody());
    const { container } = render(<BrentMacroCard />);
    await screen.findByText("Brent Crude");
    expect(screen.queryByText("Macro Context")).toBeNull();
    expect(container.textContent ?? "").not.toMatch(/crypto|trading signal/i);
  });

  it("uses the shared /api/commodities/ endpoint, not a bespoke or crypto EIA call", async () => {
    const f = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(commoditiesBody()) });
    vi.stubGlobal("fetch", f);
    render(<BrentMacroCard />);
    await screen.findByText("Brent Crude");
    const urls = f.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes("/api/commodities/"))).toBe(true);
    expect(urls.some((u) => /eia|brent|crypto/i.test(u))).toBe(false);
  });

  it("renders an explicit unavailable state when no Brent observation exists", async () => {
    stubFetch({ metals: [], energy: [] });
    render(<BrentMacroCard />);
    await waitFor(() => expect(screen.getByText(/Brent crude \(EIA\) is unavailable/i)).toBeInTheDocument());
  });
});
