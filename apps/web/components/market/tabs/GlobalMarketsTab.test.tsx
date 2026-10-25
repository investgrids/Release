import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { GlobalMarketsTab, REGION_GROUPS } from "./GlobalMarketsTab";

const ALL_TEN = [
  "Dow Jones", "S&P 500", "Nasdaq", "FTSE 100", "DAX", "CAC 40",
  "Nikkei 225", "Hang Seng", "Shanghai Composite", "KOSPI",
];

describe("REGION_GROUPS", () => {
  it("covers all ten indices exactly once (Shanghai regression)", () => {
    const flat = REGION_GROUPS.flatMap(g => g.indices);
    expect([...flat].sort()).toEqual([...ALL_TEN].sort());               // no omissions, no extras
    expect(new Set(flat).size).toBe(flat.length);                         // no duplicates
    expect(flat).toContain("Shanghai Composite");                        // the specific regression
  });
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const INDICES = [
  { name: "Dow Jones", flag: "🇺🇸", value: "51,000.00", pct: "+0.50%", positive: true },
  { name: "Nasdaq", flag: "🇺🇸", value: "26,000.00", pct: "+1.10%", positive: true },
  { name: "FTSE 100", flag: "🇬🇧", value: "10,700.00", pct: "-1.00%", positive: false },
  { name: "Nikkei 225", flag: "🇯🇵", value: "64,000.00", pct: "-1.30%", positive: false },
];

function routeFetch(brief: unknown) {
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    const body = String(url).includes("global-brief") ? brief : { indices: INDICES };
    return Promise.resolve({ ok: true, json: async () => body });
  }));
}

describe("GlobalMarketsTab", () => {
  it("renders the index grid and NO brief when the brief is disabled", async () => {
    routeFetch({ enabled: false });
    render(<GlobalMarketsTab />);
    // index names appear in both the grid and the pre-existing regional summary,
    // so there are legitimately multiple matches — assert ≥1, not exactly one.
    await waitFor(() => expect(screen.getAllByText("Dow Jones").length).toBeGreaterThan(0));
    expect(screen.queryByText("Global Market Brief")).not.toBeInTheDocument();
  });

  it("renders every brief section when enabled", async () => {
    routeFetch({
      enabled: true,
      generated_at: "2026-10-20T07:00:00Z",
      mood: { label: "Mixed", reason: "2 advancing and 2 declining of 4 observed.", observed: 4, total: 4, positive: 2, negative: 2, coverage_by_freshness: { live: 4 } },
      regions: [
        { region: "Americas", observed: 2, leader: { name: "Nasdaq", pct: "+1.10%", session: "REGULAR" }, laggard: { name: "Dow Jones", pct: "+0.50%", session: "REGULAR" } },
        { region: "Europe", observed: 0, leader: null, laggard: null, note: "No eligible observations in this region right now." },
      ],
      india_implications: [],
      india_implications_note: "No supported transmission path is available from current data; causal links require the Phase 2 evidence workstream.",
      what_to_watch: [{ title: "India IIP", date: "Oct 28, 2026", category: "india_iip" }],
      what_to_watch_note: null,
      cannot_conclude: "Index movements alone do not establish why markets moved. A causal explanation requires verified news or macroeconomic evidence.",
    });
    render(<GlobalMarketsTab />);
    await waitFor(() => expect(screen.getByText("Global Market Brief")).toBeInTheDocument());
    // mood: count-led headline + breadth classification chip (not a definitive judgment)
    expect(screen.getByText(/2 advancing, 2 declining of 4 tracked indices/i)).toBeInTheDocument();
    expect(screen.getByText(/Breadth: Mixed/i)).toBeInTheDocument();
    // regional leader present (appears in grid too → assert ≥1) + brief-only empty-region note
    expect(screen.getAllByText("Nasdaq").length).toBeGreaterThan(0);
    expect(screen.getByText(/No eligible observations/i)).toBeInTheDocument();
    // india empty-state note (not a fabricated hypothesis)
    expect(screen.getByText(/No supported transmission path/i)).toBeInTheDocument();
    // what to watch
    expect(screen.getByText("India IIP")).toBeInTheDocument();
    // cannot-conclude honesty line
    expect(screen.getByText(/do not establish why markets moved/i)).toBeInTheDocument();
  });

  it("shows the india empty-state note and never fabricates a hypothesis", async () => {
    routeFetch({
      enabled: true, mood: { label: "Positive", reason: "r", observed: 4, total: 4, positive: 4, negative: 0, coverage_by_freshness: { live: 4 } },
      regions: [], india_implications: [], india_implications_note: "No supported transmission path from current data.",
      what_to_watch: [], what_to_watch_note: "No verified events available in the current calendar data.",
      cannot_conclude: "Index movements alone do not establish why markets moved.",
    });
    render(<GlobalMarketsTab />);
    await waitFor(() => expect(screen.getByText(/No supported transmission path/i)).toBeInTheDocument());
    expect(screen.getByText(/No verified events available/i)).toBeInTheDocument();
    expect(screen.queryByText("Hypothesis")).not.toBeInTheDocument();
  });
});
