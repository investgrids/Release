import { describe, expect, it, vi, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
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

  it("status=degraded still renders the full page, with a compact status indicator, not a blocking error", async () => {
    mockFetchOnce(baseSnapshot({
      status: "degraded", baseline_available: false,
      confidence_warnings: [{
        description: "Last trading session's close snapshot is missing.",
        risk_type: "stale_or_missing_baseline", severity: "high",
        evidence_refs: [], related_sectors: [], related_companies: [],
      }],
    }));
    render(await WeekendHomePage());
    expect(screen.getAllByText(/Preparing You For/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Degraded")).toBeInTheDocument();
    // Simplified copy (owner correction, 2026-08-15), not the raw backend wording.
    expect(screen.getByText("Last-session closing baseline is unavailable")).toBeInTheDocument();
  });

  it("status=ok renders the normal full experience with a Live status, not Degraded", async () => {
    mockFetchOnce(baseSnapshot({ status: "ok" }));
    render(await WeekendHomePage());
    expect(screen.getAllByText(/Preparing You For/i).length).toBeGreaterThan(0);
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.queryByText("Degraded")).not.toBeInTheDocument();
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

  it("'Since Our Last Update' is never rendered on the primary homepage, regardless of real changes_since_prior data", async () => {
    // Owner correction (2026-08-15): this section is not part of the
    // approved reference layout and exposed too much version-to-version
    // state-change noise (dozens of "X turned neutral"/"Y newly
    // appeared" rows) between the metadata strip and the primary grid.
    // changes_since_prior itself is untouched in the API/DTO — this is
    // a display-only omission, verified here with a real, populated
    // fixture (not an empty one, which would trivially pass).
    mockFetchOnce(baseSnapshot({
      version: 2,
      changes_since_prior: [
        { type: "new", entity_type: "sector", entity_id: "ETF", direction: "neutral", strength: null, reason: "irrelevant", evidence_refs: [] },
        { type: "new", entity_type: "sector", entity_id: "REIT", direction: "neutral", strength: null, reason: "irrelevant", evidence_refs: [] },
        { type: "new", entity_type: "company", entity_id: "IOC", direction: "positive", strength: null, reason: "irrelevant", evidence_refs: [] },
        { type: "new", entity_type: "company", entity_id: "SUNTV", direction: "positive", strength: null, reason: "irrelevant", evidence_refs: [] },
      ],
      new_since_close: [
        { source_type: "event", source_id: "e1", title: "RBI maintains repo rate", direction: "neutral", sectors: [], companies: [] },
      ],
      new_since_close_count: 1,
    }));
    render(await WeekendHomePage());
    expect(screen.queryByText(/Since Our Last Update/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SUNTV/)).not.toBeInTheDocument();
    expect(screen.queryByText(/turned neutral/i)).not.toBeInTheDocument();
    // The primary intelligence grid must still follow immediately —
    // "What Changed Since Market Close" (new_since_close) is the real
    // user-facing "what changed" story now.
    expect(screen.getByText(/What Changed Since Market Close/i)).toBeInTheDocument();
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

  it("baseline unavailable -> Degraded status shown; baseline available -> Live status shown", async () => {
    mockFetchOnce(baseSnapshot({ status: "degraded", baseline_available: false }));
    const { unmount } = render(await WeekendHomePage());
    expect(screen.getByText("Degraded")).toBeInTheDocument();
    unmount();

    mockFetchOnce(baseSnapshot({ status: "ok", baseline_available: true }));
    render(await WeekendHomePage());
    expect(screen.queryByText("Degraded")).not.toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
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

  it("companies renders every real backend-provided item (owner correction: scroll inside the card, not a hard 5-cap)", async () => {
    const companies = Array.from({ length: 12 }, (_, i) => ({
      symbol: `SYM${i}`, state: "monitor" as const, confidence: 0.5, evidence_count: 1, evidence_item_refs: [],
    }));
    mockFetchOnce(baseSnapshot({ top_companies: companies }));
    render(await WeekendHomePage());
    // Each symbol now appears twice (avatar initials + label) — assert
    // presence via getAllByText rather than the single-match getByText.
    for (let i = 0; i < 12; i++) expect(screen.getAllByText(`SYM${i}`).length).toBeGreaterThan(0);
  });

  it("market risks visible <= 4 even if backend returned 10", async () => {
    const risks = Array.from({ length: 10 }, (_, i) => ({
      description: `Risk number ${i}`, risk_type: "conflicting_evidence", severity: "medium" as const,
      evidence_refs: [], related_sectors: [], related_companies: [],
    }));
    mockFetchOnce(baseSnapshot({ market_risks: risks }));
    render(await WeekendHomePage());
    // The highest-ranked risk (Risk number 0, all equal severity here so
    // dedup's stable sort keeps the original first) now also appears in
    // the primary "Biggest Risk" metric card, so it matches twice —
    // getAllByText, not the single-match getByText, is correct here.
    for (let i = 0; i < 4; i++) expect(screen.getAllByText(`Risk number ${i}`).length).toBeGreaterThan(0);
    expect(screen.queryByText("Risk number 4")).not.toBeInTheDocument();
  });

  it("a sector-level risk suppresses company-level risks of the same type; expand reveals no raw duplicates", async () => {
    // Owner example: finance + BAJFINANCE/LICHSGFIN/HDFCBANK all
    // conflicting_evidence -> only the sector-level Finance risk shows.
    mockFetchOnce(baseSnapshot({
      market_risks: [
        { description: "finance: conflicting positive and negative evidence this weekend", risk_type: "conflicting_evidence", severity: "high", evidence_refs: [], related_sectors: ["finance"], related_companies: [] },
        { description: "BAJFINANCE: conflicting evidence — positive and negative signals both present", risk_type: "conflicting_evidence", severity: "high", evidence_refs: [], related_sectors: [], related_companies: ["BAJFINANCE"] },
        { description: "LICHSGFIN: conflicting evidence — positive and negative signals both present", risk_type: "conflicting_evidence", severity: "high", evidence_refs: [], related_sectors: [], related_companies: ["LICHSGFIN"] },
        { description: "HDFCBANK: conflicting evidence — positive and negative signals both present", risk_type: "conflicting_evidence", severity: "high", evidence_refs: [], related_sectors: [], related_companies: ["HDFCBANK"] },
      ],
    }));
    render(await WeekendHomePage());
    // Also now surfaced in the primary "Biggest Risk" metric card, so
    // this real, deduped risk legitimately appears twice on the page.
    expect(screen.getAllByText(/^finance:/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^BAJFINANCE:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^LICHSGFIN:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^HDFCBANK:/)).not.toBeInTheDocument();
    // Nothing left to expand into (only 1 real risk survives dedup).
    expect(screen.queryByText(/View All Risks/i)).not.toBeInTheDocument();
  });

  it("renders every real backend-provided development (owner correction: scroll inside the card, not a hard 5-cap)", async () => {
    const items = Array.from({ length: 49 }, (_, i) => ({
      source_type: "event", source_id: `e${i}`, title: `Development ${i}`,
      direction: "neutral" as const, sectors: [], companies: [],
    }));
    mockFetchOnce(baseSnapshot({ new_since_close: items, new_since_close_count: 49 }));
    render(await WeekendHomePage());
    for (let i = 0; i < 49; i++) expect(screen.getByText(`Development ${i}`)).toBeInTheDocument();
    expect(screen.getByText(/49 total/)).toBeInTheDocument();
  });

  it("a neutral-direction development shows no meaningless dash; a real direction still shows its symbol", async () => {
    mockFetchOnce(baseSnapshot({
      new_since_close: [
        { source_type: "event", source_id: "e1", title: "Neutral development", direction: "neutral", sectors: [], companies: [] },
        { source_type: "event", source_id: "e2", title: "Positive development", direction: "positive", sectors: [], companies: [] },
      ],
      new_since_close_count: 2,
    }));
    render(await WeekendHomePage());
    // The direction indicator (when present) carries a sr-only label
    // ("Positive"/"Negative"/etc) alongside its symbol — the leading
    // Newspaper icon does not, so checking for that sr-only text is a
    // reliable way to tell "no direction indicator" from "has one"
    // without also matching the row's icon.
    const neutralRow = screen.getByText("Neutral development").closest("li");
    const positiveRow = screen.getByText("Positive development").closest("li");
    expect(neutralRow?.textContent).not.toContain("Positive");
    expect(neutralRow?.textContent).not.toContain("Negative");
    expect(positiveRow?.textContent).toContain("Positive");
  });

  it("confidence warnings visible <= 4 initially, expandable via See All Warnings", async () => {
    // Distinct real risk_types so each survives simplification as its
    // own bullet (not collapsed) — five real, known types plus one
    // unrecognized type that must fall back to its own real text.
    const warnings = [
      { description: "Last trading session's close snapshot is missing — synthesis is based on weekend evidence only, without a verified price/breadth baseline", risk_type: "stale_or_missing_baseline", severity: "high" as const, evidence_refs: [], related_sectors: [], related_companies: [] },
      { description: "Evidence concentrated in news (18/20 items, 90%) — other source types are comparatively sparse this weekend", risk_type: "source_concentration", severity: "medium" as const, evidence_refs: [], related_sectors: [], related_companies: [] },
      { description: "No comparable historical analogue found for this weekend's dominant evidence", risk_type: "weak_historical_analogue", severity: "low" as const, evidence_refs: [], related_sectors: [], related_companies: [] },
      { description: "Evidence volume is thin (3 item(s)) — synthesis has lower statistical support than a typical checkpoint", risk_type: "insufficient_evidence", severity: "medium" as const, evidence_refs: [], related_sectors: [], related_companies: [] },
      { description: "Company announcement data was unavailable during this update.", risk_type: "source_unavailable", severity: "medium" as const, evidence_refs: [], related_sectors: [], related_companies: [] },
    ];
    mockFetchOnce(baseSnapshot({ confidence_warnings: warnings }));
    render(await WeekendHomePage());
    // Simplified copy shown, never the raw backend wording.
    expect(screen.getByText("Last-session closing baseline is unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/close snapshot is missing/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/18\/20 items/)).not.toBeInTheDocument();
    // 5 real warnings, capped to 4 initially, expandable to the 5th.
    expect(screen.getByText(/See All Warnings/i)).toBeInTheDocument();
  });

  it("collapses repeated per-company source_concentration warnings into one generic line", async () => {
    mockFetchOnce(baseSnapshot({
      confidence_warnings: [
        { description: "BAJFINANCE: thesis rests on a single evidence source type despite 22 clusters", risk_type: "source_concentration", severity: "low", evidence_refs: [], related_sectors: [], related_companies: ["BAJFINANCE"] },
        { description: "LICHSGFIN: thesis rests on a single evidence source type despite 20 clusters", risk_type: "source_concentration", severity: "low", evidence_refs: [], related_sectors: [], related_companies: ["LICHSGFIN"] },
        { description: "HDFCBANK: thesis rests on a single evidence source type despite 10 clusters", risk_type: "source_concentration", severity: "low", evidence_refs: [], related_sectors: [], related_companies: ["HDFCBANK"] },
      ],
    }));
    render(await WeekendHomePage());
    expect(screen.getAllByText("Some company signals rely on only one source type").length).toBe(1);
    expect(screen.queryByText(/clusters/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/BAJFINANCE:/)).not.toBeInTheDocument();
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

describe("WeekendHomePage — redesign (2026-08-15): metadata strip, evidence quality, summary", () => {
  it("metadata strip shows baseline date, data window, and snapshot version from real fields", async () => {
    mockFetchOnce(baseSnapshot({
      last_trading_date: "2026-08-14",
      generated_at: "2026-08-16T12:30:00+00:00",
      version: 3,
    }));
    render(await WeekendHomePage());
    expect(screen.getByText(/Baseline \(Market Close\)/i)).toBeInTheDocument();
    // The close date/time appears twice by design (brief's own reference
    // shows it both narratively in the hero subtitle and structurally in
    // the metadata strip) — assert it's present at least once rather than
    // assuming a single occurrence.
    expect(screen.getAllByText(/14 Aug 2026, 3:30 PM IST/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Data Window/i)).toBeInTheDocument();
    expect(screen.getByText(/Snapshot Version/i).parentElement?.textContent).toContain("v3");
  });

  it("evidence quality is Good when status is ok and there are no confidence warnings — never a fabricated verdict", async () => {
    mockFetchOnce(baseSnapshot({
      status: "ok", confidence_warnings: [],
      evidence_summary: { total: 600, by_source_type: { event: 200, news: 200, company_signal: 200 } },
    }));
    render(await WeekendHomePage());
    // Evidence quality moved inside the "How confident is this?"
    // disclosure (2026-08-22 owner correction) — collapsed by default,
    // so open it before asserting on its content.
    fireEvent.click(screen.getByText("How confident is this?"));
    expect(screen.getByText("Good")).toBeInTheDocument();
    expect(screen.getByText(/3 source types, no confidence caveats/i)).toBeInTheDocument();
  });

  it("evidence quality is Fair when degraded, and names the real caveat count", async () => {
    mockFetchOnce(baseSnapshot({
      status: "degraded",
      confidence_warnings: [
        { description: "a", risk_type: "stale_or_missing_baseline", severity: "high", evidence_refs: [], related_sectors: [], related_companies: [] },
      ],
      evidence_summary: { total: 600, by_source_type: { event: 600 } },
    }));
    render(await WeekendHomePage());
    fireEvent.click(screen.getByText("How confident is this?"));
    expect(screen.getByText("Fair")).toBeInTheDocument();
    expect(screen.getByText(/1 confidence caveat/i)).toBeInTheDocument();
  });

  it("no sparkline or trend-chart claim is ever rendered (no real time-series data exists)", async () => {
    mockFetchOnce(baseSnapshot());
    render(await WeekendHomePage());
    expect(screen.queryByText(/sparkline/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId(/sparkline/i)).not.toBeInTheDocument();
  });

  it("Weekend Intelligence Summary is built from real structured fields, contrasting two real sectors", async () => {
    mockFetchOnce(baseSnapshot({
      overall_bias: "mixed",
      top_sectors: [
        { sector: "Technology", score: 0.6, direction: "positive", evidence_count: 5 },
        { sector: "Banking", score: 0.5, direction: "mixed", evidence_count: 4 },
      ],
      production_confidence: 43,
      baseline_available: false,
    }));
    render(await WeekendHomePage());
    expect(screen.getByText(/Weekend Intelligence Summary/i)).toBeInTheDocument();
    expect(screen.getByText(/Weekend signals remain mixed\./)).toBeInTheDocument();
    expect(screen.getByText(/Technology shows positive evidence while Banking is mixed\./)).toBeInTheDocument();
    expect(screen.getByText(/last trading session's closing baseline is unavailable/i)).toBeInTheDocument();
  });

  it("Weekend Intelligence Summary is hidden entirely when there are no sectors to summarize", async () => {
    mockFetchOnce(baseSnapshot({ top_sectors: [] }));
    render(await WeekendHomePage());
    expect(screen.queryByText(/Weekend Intelligence Summary/i)).not.toBeInTheDocument();
  });

  it("'How We Generate This' links to the real, existing methodology page, not a dead control", async () => {
    mockFetchOnce(baseSnapshot({
      top_sectors: [{ sector: "Technology", score: 0.5, direction: "positive", evidence_count: 3 }],
    }));
    render(await WeekendHomePage());
    const link = screen.getByText(/How We Generate This/i).closest("a");
    expect(link).toHaveAttribute("href", "/how-marketripple-thinks");
  });
});
