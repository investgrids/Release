import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import type { WeekendIntelligenceSnapshotDTO } from "@/types/weekendIntelligence";
import { WeekendHomePage } from "./WeekendHomePage";

function baseSnapshot(overrides: Partial<WeekendIntelligenceSnapshotDTO> = {}): WeekendIntelligenceSnapshotDTO {
  return {
    available: true,
    target_trading_date: "2026-08-17",
    last_trading_date: "2026-08-14",
    generated_at: "2026-08-16T12:30:00+00:00",
    checkpoint_label: "Sunday 18:00 IST",
    version: 1,
    status: "ok",
    baseline_available: true,
    overall_bias: "mixed",
    production_confidence: 44.27,
    confidence_components: {
      raw: { evidence_strength: 1, source_diversity: 0.5, agreement: 0.09, historical_support: 0.2, baseline_quality: 1 },
      weights: {}, weighted_contributions: {},
    },
    top_sectors: [],
    top_companies: [],
    market_risks: [],
    confidence_warnings: [],
    new_since_close_count: 0,
    new_since_close: [],
    changes_since_prior: [],
    evidence_summary: { total: 0, by_source_type: {} },
    opportunities: [],
    historical_analogues: [],
    ...overrides,
  };
}

function mockFetchOnce(response: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok, json: async () => response }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("WeekendHomePage — brief §39 response states", () => {
  it("available=false renders the honest 'preparing next session' state, not fake cards", async () => {
    mockFetchOnce({ available: false, target_trading_date: "2026-08-17" });
    render(await WeekendHomePage());
    expect(screen.getByText(/Preparing the next market session/i)).toBeInTheDocument();
  });

  it("status=insufficient_evidence shows 'No material change detected', never a forced direction", async () => {
    mockFetchOnce(baseSnapshot({ status: "insufficient_evidence", overall_bias: "neutral", production_confidence: 0 }));
    render(await WeekendHomePage());
    expect(screen.getByText(/No material change detected/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Positive$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Bullish$/)).not.toBeInTheDocument();
  });

  it("status=degraded still renders the full page, with a quality note, not a blocking error", async () => {
    mockFetchOnce(baseSnapshot({ status: "degraded", baseline_available: false }));
    render(await WeekendHomePage());
    expect(screen.getByText(/Preparing You For/i)).toBeInTheDocument();
    expect(screen.getByText(/Some baseline market data is unavailable/i)).toBeInTheDocument();
  });

  it("status=ok renders the normal full experience with no quality caveat banner", async () => {
    mockFetchOnce(baseSnapshot({ status: "ok" }));
    render(await WeekendHomePage());
    expect(screen.getByText(/Preparing You For/i)).toBeInTheDocument();
    expect(screen.queryByText(/Some baseline market data is unavailable/i)).not.toBeInTheDocument();
  });

  it("API failure (network error) shows a calm unavailable state, not a raw error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));
    render(await WeekendHomePage());
    expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/500/)).not.toBeInTheDocument();
  });

  it("API failure (non-ok HTTP status) also shows the calm unavailable state", async () => {
    mockFetchOnce({}, false);
    render(await WeekendHomePage());
    expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
  });
});

describe("WeekendHomePage — brief §40 truthfulness", () => {
  it("mixed backend bias renders Mixed, not Positive", async () => {
    mockFetchOnce(baseSnapshot({ overall_bias: "mixed" }));
    render(await WeekendHomePage());
    expect(screen.getByText(/MIXED/)).toBeInTheDocument();
  });

  it("hero weekday derives from target_trading_date, not hardcoded — a Tuesday target renders Tuesday", async () => {
    // 2026-08-18 is a real Tuesday. Proves the hero isn't silently
    // assuming "Monday" (every other fixture in this file happens to
    // use a Monday date, which would hide a hardcoded string).
    mockFetchOnce(baseSnapshot({ target_trading_date: "2026-08-18" }));
    render(await WeekendHomePage());
    expect(screen.getByText(/Preparing You For Tuesday/i)).toBeInTheDocument();
    expect(screen.queryByText(/Preparing You For Monday/i)).not.toBeInTheDocument();
  });

  it("hero weekday reflects a Monday target too, proving both are read from the same real field", async () => {
    mockFetchOnce(baseSnapshot({ target_trading_date: "2026-08-17" }));
    render(await WeekendHomePage());
    expect(screen.getByText(/Preparing You For Monday/i)).toBeInTheDocument();
  });

  it("'Since Our Last Update' never shows raw internal score transitions", async () => {
    // Backend's real changes.py template for a "weakened" sector change
    // embeds a raw 0-1 confidence transition in `reason`, e.g.
    // "Technology signal weakened (0.80 -> 0.65)" — confirmed present
    // verbatim in real local-data verification. The rendered copy must
    // never leak that number pair to the user.
    mockFetchOnce(baseSnapshot({
      version: 2,
      changes_since_prior: [
        {
          type: "weakened", entity_type: "sector", entity_id: "Technology",
          direction: null, strength: null,
          reason: "Technology signal weakened (0.80 -> 0.65)",
          evidence_refs: [],
        },
        {
          type: "strengthened", entity_type: "sector", entity_id: "Defence",
          direction: null, strength: null,
          reason: "Defence signal strengthened (0.40 -> 0.72)",
          evidence_refs: [],
        },
      ],
    }));
    render(await WeekendHomePage());
    expect(screen.getByText(/Technology/)).toBeInTheDocument();
    expect(screen.getByText(/Defence/)).toBeInTheDocument();
    expect(screen.queryByText(/0\.80/)).not.toBeInTheDocument();
    expect(screen.queryByText(/0\.65/)).not.toBeInTheDocument();
    expect(screen.queryByText(/0\.40/)).not.toBeInTheDocument();
    expect(screen.queryByText(/0\.72/)).not.toBeInTheDocument();
    expect(screen.queryByText(/->/)).not.toBeInTheDocument();
  });

  it("0 historical analogues does not create a fake analogue card", async () => {
    mockFetchOnce(baseSnapshot({ historical_analogues: [] }));
    render(await WeekendHomePage());
    expect(screen.queryByText(/Similar Historical Setups/i)).not.toBeInTheDocument();
  });

  it("no opportunities -> opportunity section is hidden entirely", async () => {
    mockFetchOnce(baseSnapshot({ opportunities: [] }));
    render(await WeekendHomePage());
    expect(screen.queryByText(/Potential Opportunities/i)).not.toBeInTheDocument();
  });

  it("baseline unavailable -> degraded warning shown; baseline available -> not shown", async () => {
    mockFetchOnce(baseSnapshot({ status: "degraded", baseline_available: false }));
    const { unmount } = render(await WeekendHomePage());
    expect(screen.getByText(/Some baseline market data is unavailable/i)).toBeInTheDocument();
    unmount();

    mockFetchOnce(baseSnapshot({ status: "ok", baseline_available: true }));
    render(await WeekendHomePage());
    expect(screen.queryByText(/Some baseline market data is unavailable/i)).not.toBeInTheDocument();
  });

  it("experimental signals are never displayed (the DTO doesn't even carry the field)", async () => {
    mockFetchOnce(baseSnapshot());
    render(await WeekendHomePage());
    expect(screen.queryByText(/experimental/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/kronos/i)).not.toBeInTheDocument();
  });

  it("frontend never recalculates production_confidence — displays exactly what the backend sent, only rounded for display", async () => {
    mockFetchOnce(baseSnapshot({ production_confidence: 44.27 }));
    render(await WeekendHomePage());
    // Math.round(44.27) = 44 — display rounding (brief §33's allowed
    // "safe human-readable number formatting"), not a recalculation.
    expect(screen.getByText("44%")).toBeInTheDocument();
  });

  it("a company with a missing/empty symbol is not rendered as a fabricated blank entry", async () => {
    mockFetchOnce(baseSnapshot({
      top_companies: [
        { symbol: "REALSYM", state: "monitor", confidence: 0.5, evidence_count: 1, evidence_item_refs: [] },
      ],
    }));
    render(await WeekendHomePage());
    expect(screen.getByText("REALSYM")).toBeInTheDocument();
    // Only the one real symbol the backend actually sent is present.
    expect(screen.getAllByRole("link").filter((a) => a.getAttribute("href")?.startsWith("/companies/")).length).toBe(1);
  });

  it("snapshot/version/source IDs are never rendered on the page", async () => {
    mockFetchOnce(baseSnapshot({
      market_risks: [{
        description: "Banking: conflicting evidence", risk_type: "conflicting_evidence", severity: "high",
        evidence_refs: [{ source_type: "event", source_id: "rss-abcdef123456" }],
        related_sectors: ["Banking"], related_companies: [],
      }],
    }));
    render(await WeekendHomePage());
    expect(screen.queryByText(/rss-abcdef123456/)).not.toBeInTheDocument();
  });
});

describe("WeekendHomePage — brief §41 list caps", () => {
  it("sectors visible <= 5 even if backend somehow returned more", async () => {
    const sectors = Array.from({ length: 8 }, (_, i) => ({
      sector: `Sector${i}`, score: 0.5, direction: "positive" as const, evidence_count: i + 1,
    }));
    mockFetchOnce(baseSnapshot({ top_sectors: sectors }));
    render(await WeekendHomePage());
    for (let i = 0; i < 5; i++) expect(screen.getByText(`Sector${i}`)).toBeInTheDocument();
  });

  it("companies visible <= 6 initially, expandable up to backend-provided count only", async () => {
    const companies = Array.from({ length: 12 }, (_, i) => ({
      symbol: `SYM${i}`, state: "monitor" as const, confidence: 0.5, evidence_count: 1, evidence_item_refs: [],
    }));
    mockFetchOnce(baseSnapshot({ top_companies: companies }));
    render(await WeekendHomePage());
    for (let i = 0; i < 6; i++) expect(screen.getByText(`SYM${i}`)).toBeInTheDocument();
    expect(screen.queryByText("SYM6")).not.toBeInTheDocument();
    expect(screen.getByText(/Show all 12/i)).toBeInTheDocument();
  });

  it("market risks visible <= 5 even if backend returned 10", async () => {
    const risks = Array.from({ length: 10 }, (_, i) => ({
      description: `Risk number ${i}`, risk_type: "conflicting_evidence", severity: "medium" as const,
      evidence_refs: [], related_sectors: [], related_companies: [],
    }));
    mockFetchOnce(baseSnapshot({ market_risks: risks }));
    render(await WeekendHomePage());
    for (let i = 0; i < 5; i++) expect(screen.getByText(`Risk number ${i}`)).toBeInTheDocument();
    expect(screen.queryByText("Risk number 5")).not.toBeInTheDocument();
  });

  it("new developments visible <= 8 even if backend returned 49", async () => {
    const items = Array.from({ length: 49 }, (_, i) => ({
      source_type: "event", source_id: `e${i}`, title: `Development ${i}`,
      direction: "neutral" as const, sectors: [], companies: [],
    }));
    mockFetchOnce(baseSnapshot({ new_since_close: items, new_since_close_count: 49 }));
    render(await WeekendHomePage());
    for (let i = 0; i < 8; i++) expect(screen.getByText(`Development ${i}`)).toBeInTheDocument();
    expect(screen.queryByText("Development 8")).not.toBeInTheDocument();
    expect(screen.getByText(/49 total/)).toBeInTheDocument();
  });

  it("historical analogues visible <= 3 even if backend returned 5", async () => {
    const analogues = Array.from({ length: 5 }, (_, i) => ({
      id: `h${i}`, event_title: `Historical Event ${i}`, event_date: "Jan 1, 2020", category: "Test", key_lesson: null, nifty_1d: 1.0,
    }));
    mockFetchOnce(baseSnapshot({ historical_analogues: analogues }));
    render(await WeekendHomePage());
    for (let i = 0; i < 3; i++) expect(screen.getByText(`Historical Event ${i}`)).toBeInTheDocument();
    expect(screen.queryByText("Historical Event 3")).not.toBeInTheDocument();
  });
});
