/**
 * Server-rendered breadcrumb regression (2026-09-20) — real production
 * finding during the Adani V2 canary review: an editorial-override title
 * only ever reached the visible breadcrumb AFTER client hydration, so the
 * initial server-rendered HTML/BreadcrumbList JSON-LD (what a crawler or
 * "view source" actually sees) kept showing the raw humanized URL slug —
 * including already-rejected interpretive title language ("Execution
 * Catalyst") a human editor had specifically replaced, plus the trailing
 * id suffix. Fixed by rendering <StaticBreadcrumbs> directly in this
 * server component with the real, already-effective-title-resolved
 * `title` value, and suppressing the global auto-derived breadcrumb for
 * this route (Breadcrumbs.tsx's SERVER_RENDERED_BREADCRUMB_ROUTES).
 *
 * These tests render the raw server HTML output (no hydration, no
 * client-side effects) — exactly what the earlier, broken version would
 * have gotten wrong.
 */
import { describe, expect, it, vi, afterEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import OpportunityPage from "./page";

vi.mock("./OpportunityPageClient", () => ({ default: () => null }));

function v2Detail(overrides: Record<string, unknown> = {}) {
  return {
    id: "96b5d32b-23ad-4456-b0df-b66d906ab58c",
    slug: "adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b",
    title: "Adani Energy Solutions’ 2,500 MW RTC Power Award and PPA",
    thesis_anchor: "company:adaniensol",
    direction: "positive",
    current_strength: 47.6,
    evidence_count: 1,
    candidate_status: "formed",
    narrative_status: "generated",
    public_status: "public",
    why_this_exists: "Adani Energy Solutions Limited disclosed that it received a Letter of Award and executed a Power Purchase Agreement for the supply of 2,500 MW of Round-the-Clock power.",
    what_changed: null,
    companies_connected: [{ symbol: "ADANIENSOL", company_name: "ADANIENSOL", real_score: 59.1, real_direction: "positive", confirms_thesis: true, contradicts_thesis: false }],
    sectors_themes: [],
    ripple: { anchor: "company:adaniensol", nodes: [], edges: [] },
    supporting_evidence: [],
    development_impacts: [],
    contradictions_risks: [],
    created_at: "2026-09-09T02:00:51.666671",
    updated_at: "2026-09-09T02:00:00.037844",
    ...overrides,
  };
}

function v1Detail(overrides: Record<string, unknown> = {}) {
  return {
    id: 406, slug: "real-opportunity-406", title: "A Real V1 Opportunity", summary: "Real V1 summary.",
    opportunity_score: 72, confidence: 0.65, trend: "positive", risk_level: "Medium", time_horizon: "3-6 months",
    sectors: ["Banking"], ai_summary: null, metrics: null, timeline: [], events: [], companies: [], news: [],
    sector_distribution: [], graph_nodes: [], graph_edges: [], primary_event: null, investment_verdict: null,
    historical_similarity: null, catalysts: [],
    ...overrides,
  };
}

function mockFetchFor(detail: Record<string, unknown> | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/api/radar/meta")) return { ok: true, json: async () => ({ opportunity_v2_promoted: false }) };
      if (url.includes("/api/radar/")) return detail ? { ok: true, json: async () => detail } : { ok: false, json: async () => ({}) };
      if (url.includes("/api/related/")) return { ok: true, json: async () => null };
      return { ok: false, json: async () => ({}) };
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("opportunity-radar/[id] page — server-rendered breadcrumb", () => {
  it("initial HTML contains the effective editorial title", async () => {
    mockFetchFor(v2Detail());
    const html = renderToStaticMarkup(await OpportunityPage({ params: Promise.resolve({ id: "adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b" }) }));
    expect(html).toContain("Adani Energy Solutions’ 2,500 MW RTC Power Award and PPA");
  });

  it("initial HTML does NOT contain the rejected 'Execution Catalyst' language", async () => {
    mockFetchFor(v2Detail());
    const html = renderToStaticMarkup(await OpportunityPage({ params: Promise.resolve({ id: "adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b" }) }));
    expect(html).not.toContain("Execution Catalyst");
  });

  it("initial HTML does NOT contain the raw id suffix humanized into the breadcrumb", async () => {
    mockFetchFor(v2Detail());
    const html = renderToStaticMarkup(await OpportunityPage({ params: Promise.resolve({ id: "adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b" }) }));
    // The real bug put "...96b5d32b" into the BreadcrumbList's own item
    // name and into the visible <nav> crumb text -- the slug legitimately
    // (and correctly) still appears elsewhere on the page, e.g. inside the
    // JSON-LD Article schema's "url" field, so this scopes narrowly to
    // just those two breadcrumb-owned strings rather than the whole page.
    const breadcrumbJsonLdMatch = html.match(/"@type":"BreadcrumbList".*?<\/script>/);
    expect(breadcrumbJsonLdMatch?.[0] ?? "").not.toContain("96b5d32b");
    const navMatch = html.match(/<nav aria-label="Breadcrumb">.*?<\/nav>|<nav aria-label="Breadcrumb"[^>]*>.*?<\/nav>/);
    expect(navMatch?.[0] ?? "").not.toContain("96b5d32b");
  });

  it("emits exactly one BreadcrumbList JSON-LD schema", async () => {
    mockFetchFor(v2Detail());
    const html = renderToStaticMarkup(await OpportunityPage({ params: Promise.resolve({ id: "adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b" }) }));
    const matches = html.match(/"@type":"BreadcrumbList"/g) ?? [];
    expect(matches.length).toBe(1);
  });

  it("preserves the correct canonical URL in the breadcrumb's own item link", async () => {
    mockFetchFor(v2Detail());
    const html = renderToStaticMarkup(await OpportunityPage({ params: Promise.resolve({ id: "adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b" }) }));
    expect(html).toContain('href="/opportunity-radar"');
  });

  it("works for a V2 row with no editorial override (falls back to the generated title)", async () => {
    mockFetchFor(v2Detail({ title: "A Generated V2 Title With No Override", slug: "a-generated-v2-title-abc123", id: "abc123" }));
    const html = renderToStaticMarkup(await OpportunityPage({ params: Promise.resolve({ id: "a-generated-v2-title-abc123" }) }));
    expect(html).toContain("A Generated V2 Title With No Override");
  });

  it("still works for a V1 numeric route", async () => {
    mockFetchFor(v1Detail());
    const html = renderToStaticMarkup(await OpportunityPage({ params: Promise.resolve({ id: "406" }) }));
    expect(html).toContain("A Real V1 Opportunity");
    const matches = html.match(/"@type":"BreadcrumbList"/g) ?? [];
    expect(matches.length).toBe(1);
  });
});
