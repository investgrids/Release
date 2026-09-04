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
import { generateMetadata } from "./page";

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

function mockFetchFor(article: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/api/insights/")) {
        return { ok: true, json: async () => article };
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
