import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { CompanyScoreContributors, type CompanyScoreData } from "./CompanyPageClient";
import type { StockDetail } from "./CompanyPageClient";

const stock = { symbol: "TESTCO", name: "Test Company Ltd" } as StockDetail;

function mockFetchOnce(data: CompanyScoreData | null) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: data !== null,
    json: async () => data,
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

// One-score migration regression guard (2026-09-26, owner instruction):
// this section was renamed from "AI Company Score" to "Recent Intelligence
// Evidence" and stripped of every standalone numeric score, rating,
// verdict, and score-based colour gauge — a second public company rating
// living on a different tab under a different name was still a second
// rating. These tests prove the removed elements are gone and the real,
// dated evidence content (the actual reason this section exists) survives
// untouched.
describe("CompanyScoreContributors — Recent Intelligence Evidence (2026-09-26 rename)", () => {
  it("renders the new title and never the old numeric score, risk/trend pills, or verdict text", async () => {
    const data: CompanyScoreData = {
      symbol: "TESTCO", score: 62.4, confidence: 0.71,
      signal_count: 3, contributing_signal_count: 2, sector: "Banking",
      trend: "up", risk_level: "Low",
      verdict: { label: "Bullish", tone: "positive", reasoning: "Opportunity score 62/100 · Low risk · up trend" },
      top_contributors: [],
      positive_reasons: [
        { reason: "Real published analysis found strong Q3 earnings growth.", source_type: "article", href: "/newsroom/article/real-q3-earnings", signed_magnitude: 40, signal_at: "2026-09-10T00:00:00Z" },
      ],
      risk_factors: [
        { reason: "A real opportunity flagged margin compression risk.", source_type: "opportunity", href: "/opportunity-radar/real-margin-risk", signed_magnitude: -15, signal_at: "2026-09-12T00:00:00Z" },
      ],
    };
    mockFetchOnce(data);

    render(<CompanyScoreContributors stock={stock} />);

    await waitFor(() => expect(screen.getByText("Recent intelligence evidence")).toBeInTheDocument());

    // --- REMOVED: no standalone numeric score, rating, verdict, or colour gauge ---
    expect(screen.queryByText("AI Company Score")).not.toBeInTheDocument();
    expect(screen.queryByText("62.4")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Score")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Powered")).not.toBeInTheDocument();
    expect(screen.queryByText("Evidence quality")).not.toBeInTheDocument();
    expect(screen.queryByText(/Low Risk/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Trending Up/)).not.toBeInTheDocument();
    expect(screen.queryByText("Bullish")).not.toBeInTheDocument();
    expect(screen.queryByText(/Opportunity score 62\/100/)).not.toBeInTheDocument();

    // --- RETAINED: the actual dated, sourced evidence content ---
    expect(screen.getByText("Real published analysis found strong Q3 earnings growth.")).toBeInTheDocument();
    expect(screen.getByText("A real opportunity flagged margin compression risk.")).toBeInTheDocument();
    expect(screen.getByText(/From published analysis/)).toBeInTheDocument();
    expect(screen.getByText(/From opportunity tracking/)).toBeInTheDocument();
    expect(screen.getByText(/10 Sept? 2026/)).toBeInTheDocument();
    expect(screen.getByText(/12 Sept? 2026/)).toBeInTheDocument();
    expect(screen.getByText(/2 contributing signals/)).toBeInTheDocument();
    // Explains the evidence's real relationship to the score without
    // itself being a competing rating.
    expect(screen.getByText(/Current Intelligence pillar/)).toBeInTheDocument();
  });

  it("renders the honest empty state under the new title when there is no real evidence yet", async () => {
    const data: CompanyScoreData = {
      symbol: "TESTCO", score: null, confidence: null,
      signal_count: 0, contributing_signal_count: 0, sector: null,
      top_contributors: [],
    };
    mockFetchOnce(data);

    render(<CompanyScoreContributors stock={stock} />);

    await waitFor(() => expect(screen.getByText("Recent intelligence evidence")).toBeInTheDocument());
    expect(screen.getByText(/No intelligence evidence tracked for Test Company Ltd yet/)).toBeInTheDocument();
    expect(screen.queryByText("AI Company Score")).not.toBeInTheDocument();
  });

  it("renders nothing while the fetch is pending or fails", async () => {
    mockFetchOnce(null);
    const { container } = render(<CompanyScoreContributors stock={stock} />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});


// Intelligence tab clarity pass (2026-10-04): repeated points counted once, a short list with the rest behind a button, and the impact number explained.
describe("CompanyScoreContributors — readable evidence", () => {
  const mk = (reason: string, mag: number, at = "2026-09-10T00:00:00Z") => ({ reason, source_type: "article" as const, href: null, signed_magnitude: mag, signal_at: at });
  const base = { symbol: "TESTCO", score: null, confidence: null, sector: null, top_contributors: [] as never[] };

  it("counts a repeated point once, shows the strongest copy, and explains the impact scale", async () => {
    mockFetchOnce({ ...base, signal_count: 4, contributing_signal_count: 4,
      positive_reasons: [mk("Directly exposed to Technology opportunity.", 85), mk("directly exposed to technology opportunity", 91)],
      risk_factors: [mk("Rupee appreciation compresses margins", -80)] } as CompanyScoreData);
    render(<CompanyScoreContributors stock={stock} />);
    await waitFor(() => expect(screen.getByText("What supports it")).toBeInTheDocument());
    expect(screen.getAllByText(/Directly exposed to Technology opportunity/i)).toHaveLength(1);
    expect(screen.getByText(/Impact \+91/)).toBeInTheDocument();
    expect(screen.queryByText(/Impact \+85/)).not.toBeInTheDocument();
    expect(screen.getByText(/1 point support/)).toBeInTheDocument();
    expect(screen.getByText(/1 point counter/)).toBeInTheDocument();
    expect(screen.getByText(/0–100 scale/)).toBeInTheDocument();
  });

  it("shows three points per side and reveals the rest on request", async () => {
    const many = Array.from({ length: 5 }, (_, i) => mk(`Distinct supporting point number ${i}`, 90 - i));
    mockFetchOnce({ ...base, signal_count: 5, contributing_signal_count: 5, positive_reasons: many, risk_factors: [] } as CompanyScoreData);
    render(<CompanyScoreContributors stock={stock} />);
    await waitFor(() => expect(screen.getByText("What supports it")).toBeInTheDocument());
    expect(screen.queryByText("Distinct supporting point number 3")).not.toBeInTheDocument();
    screen.getByRole("button", { name: "Show 2 more" }).click();
    await waitFor(() => expect(screen.getByText("Distinct supporting point number 4")).toBeInTheDocument());
    expect(screen.getByText("No countering points in the current evidence.")).toBeInTheDocument();
  });
});
