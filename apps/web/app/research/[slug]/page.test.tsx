/**
 * Directional-surface reassessment (2026-09-03) regression coverage,
 * scoped narrowly to generateMetadata()'s safeText() gate -- the real
 * leak found live: a comparison article's meta_description ("GAIL India
 * Ltd is the preferred choice over Oil & Natural Gas Corporation...")
 * reached <meta name="description">, og:description, twitter:description,
 * and jsonLd.description completely unguarded, even after the page's
 * visible-body defense-in-depth gate (executive_summary/ai_stance) was
 * already in place -- generateMetadata() is a separate function with its
 * own independent fallback chain that was never touched by that fix.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import ResearchPage, { generateMetadata } from "./page";

const UNSAFE_DESCRIPTION = "GAIL India Ltd is the preferred choice over Oil & Natural Gas Corporation for a 12-month horizon.";

function baseArticle(overrides: Record<string, unknown> = {}) {
  return {
    slug: "test-slug",
    headline: "GAIL vs ONGC: Which Is The Better Investment?",
    seo_title: "GAIL vs ONGC: Which Is The Better Investment?",
    meta_description: "",
    executive_summary: "",
    companies_affected: [],
    market_context: { kind: "comparison", decision_intelligence: {}, investment_verdict: {} },
    ...overrides,
  };
}

function baseComparisonArticle(diOverrides: Record<string, unknown> = {}) {
  const di = {
    decision_summary: "A grounded comparison of two energy companies.",
    holding_analysis: {
      entity: "GAIL India Ltd", symbol: "GAIL", sector: "Energy",
      thesis: "GAIL has diversified gas transmission infrastructure.",
      strengths: ["Diversified pipeline network"], risks: ["Regulatory tariff risk"],
      catalysts: [], near_term_outlook: "neutral", confidence: 60,
    },
    target_analysis: {
      entity: "Oil & Natural Gas Corporation", symbol: "ONGC", sector: "Energy",
      thesis: "ONGC benefits from upstream crude realisations.",
      strengths: ["Upstream crude exposure"], risks: ["Crude price volatility"],
      catalysts: [], near_term_outlook: "neutral", confidence: 58,
    },
    comparison: [{ dimension: "Valuation", holding: "12x P/E", target: "10x P/E", advantage: "target" }],
    tradeoff: {
      reasons_to_switch: ["ONGC offers higher dividend yield"],
      reasons_to_hold: ["GAIL has more stable cash flows"],
      risks_of_switching: [], risks_of_holding: [], when_to_wait: "",
    },
    decision_framework: {
      supports_switch: [], argues_against: [], key_unknowns: ["Global crude price trajectory"],
      ai_stance: "Both companies offer real, if different, energy-sector exposure.",
    },
    ...diOverrides,
  };
  return baseArticle({
    market_context: { kind: "comparison", decision_intelligence: di, investment_verdict: {} },
  });
}

function mockFetchFor(article: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/api/insights/")) {
        return { ok: true, json: async () => article };
      }
      if (url.includes("/api/related/")) {
        return { ok: true, json: async () => null };
      }
      return { ok: false, json: async () => ({}) };
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("research/[slug] generateMetadata — meta_description leak (2026-09-03)", () => {
  it("does not leak an unsafe meta_description into description/og/twitter", async () => {
    mockFetchFor(baseArticle({ meta_description: UNSAFE_DESCRIPTION }));

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "test-slug" }) });

    expect(metadata.description ?? "").not.toMatch(/preferred choice/i);
    expect((metadata.openGraph as { description?: string } | undefined)?.description ?? "").not.toMatch(/preferred choice/i);
    expect((metadata.twitter as { description?: string } | undefined)?.description ?? "").not.toMatch(/preferred choice/i);
  });

  it("falls through to a safe executive_summary when meta_description is unsafe", async () => {
    mockFetchFor(baseArticle({
      meta_description: UNSAFE_DESCRIPTION,
      executive_summary: "A grounded, evidence-based comparison of two energy companies.",
    }));

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "test-slug" }) });

    expect(metadata.description).toBe("A grounded, evidence-based comparison of two energy companies.");
  });

  it("falls through to the headline when both meta_description and executive_summary are unsafe or absent", async () => {
    mockFetchFor(baseArticle({ meta_description: UNSAFE_DESCRIPTION, executive_summary: UNSAFE_DESCRIPTION }));

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "test-slug" }) });

    expect(metadata.description).toBe("GAIL vs ONGC: Which Is The Better Investment?");
  });

  it("still uses a clean meta_description normally", async () => {
    mockFetchFor(baseArticle({ meta_description: "A real, grounded comparison summary." }));

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "test-slug" }) });

    expect(metadata.description).toBe("A real, grounded comparison summary.");
  });
});

describe("research/[slug] body — bullet-list/thesis recommendation-language leak (2026-09-03)", () => {
  it("filters an unsafe strengths bullet, keeps the clean ones", async () => {
    mockFetchFor(baseComparisonArticle({
      holding_analysis: {
        entity: "Adani Energy Solutions Ltd", symbol: "ADANIENSOL", sector: "Energy",
        thesis: "Real thesis text.",
        // Real live specimen: "Long-term structural tailwinds favor
        // renewable energy evacuation grids."
        strengths: ["Long-term structural tailwinds favor renewable energy evacuation grids.", "Real clean strength."],
        risks: [], catalysts: [], near_term_outlook: "neutral", confidence: 60,
      },
    }));

    render(await ResearchPage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText(/tailwinds favor/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Real clean strength\./)).toBeInTheDocument();
  });

  it("filters an unsafe thesis sentence entirely (never rewrites)", async () => {
    mockFetchFor(baseComparisonArticle({
      target_analysis: {
        entity: "Page Industries Ltd", symbol: "PAGEIND", sector: "Consumer",
        // Real live specimen: "Page Industries' stability makes it a
        // better choice for investors prioritizing dividend income."
        thesis: "Page Industries' stability makes it a better choice for investors prioritizing dividend income.",
        strengths: [], risks: [], catalysts: [], near_term_outlook: "neutral", confidence: 55,
      },
    }));

    render(await ResearchPage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText(/better choice/i)).not.toBeInTheDocument();
  });

  it("filters unsafe reasons_to_switch/reasons_to_hold bullets, keeps clean ones", async () => {
    mockFetchFor(baseComparisonArticle({
      tradeoff: {
        reasons_to_switch: ["We favor switching to the target for growth upside.", "Real clean reason to switch."],
        reasons_to_hold: ["Real clean reason to hold."],
        risks_of_switching: [], risks_of_holding: [], when_to_wait: "",
      },
    }));

    render(await ResearchPage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText(/we favor switching/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Real clean reason to switch\./)).toBeInTheDocument();
    expect(screen.getByText(/Real clean reason to hold\./)).toBeInTheDocument();
  });

  it("a fully clean article renders every section normally", async () => {
    mockFetchFor(baseComparisonArticle());

    render(await ResearchPage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("GAIL has diversified gas transmission infrastructure.")).toBeInTheDocument();
    expect(screen.getByText(/Diversified pipeline network/)).toBeInTheDocument();
    expect(screen.getByText(/ONGC offers higher dividend yield/)).toBeInTheDocument();
    expect(screen.getByText("Both companies offer real, if different, energy-sector exposure.")).toBeInTheDocument();
  });
});
