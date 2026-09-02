/**
 * P0-CD1 — Public Claim Containment (2026-09-01) regression coverage.
 *
 * The P0-D audit (recommendation provenance) found that this page renders
 * AI Investment Verdict / Bullish-Bearish / "Current view: X on Y" /
 * Likely Winners / Likely Losers / opportunities[0] as "Action" / public
 * confidence percentages unconditionally, for every article type, off a
 * `companies_affected[].impact` field with 5 semantically incompatible
 * real producers. Per owner authorization this page now fails closed:
 * those elements are suppressed at the presentation layer (see page.tsx's
 * own P0-CD1 header comment). These tests prove the suppression holds
 * across article-type variation, not just for one sample article — a
 * conditional-suppression bug (vs. this page's actual structural removal)
 * is exactly the kind of thing that could silently regress per type.
 *
 * Underlying data (impact, opportunities, confidence_score) is still
 * fetched and still present in every fixture below — these tests assert
 * it isn't *rendered* as a public claim, not that it's gone from the API.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import ArticlePage, { generateMetadata } from "./page";

interface Fixture {
  article_type: string;
  overrides?: Record<string, unknown>;
}

// The exact shape of P0-D's live "theme-defence" specimen: a positive-
// impact company plus a Buy-style opportunity title. Used as the default
// so every fixture below carries a real recommendation string that must
// never leak, in any of its forms (Action, Investment Opportunities,
// AI Interpretation evidence).
function baseInsight(articleType: string, overrides: Record<string, unknown> = {}) {
  return {
    id: "test-id",
    slug: "test-slug",
    article_type: articleType,
    headline: "Test Headline For Containment Coverage",
    key_takeaway: "A 30-second answer that must always stay visible.",
    why_it_matters: "This is why it matters, grounded descriptive text.",
    what_happened: "This is what happened, grounded descriptive text.",
    companies_affected: [
      { name: "HDFC Bank", symbol: "HDFCBANK", impact: "positive", reason: "Positive USFDA-style catalyst reason text.", timeframe: "short" },
      { name: "Yes Bank", symbol: "YESBANK", impact: "negative", reason: "Negative catalyst reason text.", timeframe: "short" },
    ],
    sectors_affected: [
      { name: "Banking", impact: "positive", magnitude: "high", reason: "Sector-level reason text." },
    ],
    opportunities: [
      { title: "Buy HDFC Bank now to capture short-term upside", description: "Recommendation description text.", timeframe: "weeks", risk: "medium" },
    ],
    risks: [
      { title: "Rate sensitivity", description: "A grounded risk description.", severity: "high", mitigation: "Watch RBI policy." },
    ],
    historical_events: [
      { event: "Similar rate move, 2022", date: "2022-04-01", category: "macro", outcome: 4.2 },
    ],
    ripple_effect: [],
    what_to_watch_next: ["Watch the RBI policy statement."],
    faqs: [],
    sources: ["Reuters"],
    related_companies: [],
    related_themes: [],
    related_articles: [],
    angle: "primary",
    angle_entity: null,
    is_evergreen: false,
    confidence_score: 0.91,
    published_at: "2026-08-30T09:00:00Z",
    last_updated: "2026-08-30T09:00:00Z",
    created_at: "2026-08-30T09:00:00Z",
    story_version: 2,
    update_count: 1,
    views: 100,
    share_count: 0,
    update_history: [
      { at: "2026-08-30T10:00:00Z", version: 2, reason: "Reassessed after new data", summary: "Updated.", previous_takeaway: "Old takeaway.", new_takeaway: "New takeaway.", confidence: 0.75 },
    ],
    parent_event_group_id: null,
    ...overrides,
  };
}

function mockFetchFor(insight: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.includes("/api/insights/")) {
        return { ok: true, json: async () => insight };
      }
      if (url.includes("/api/data/quotes")) {
        return { ok: true, json: async () => ({ quotes: [] }) };
      }
      return { ok: false, json: async () => ({}) };
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const ARTICLE_TYPES: Fixture[] = [
  { article_type: "market_wrap" },
  { article_type: "theme_intelligence" },
  { article_type: "historical_intelligence" },
  { article_type: "company_intelligence" },
  { article_type: "some_unmapped_future_type" }, // hits DEFAULT_TYPE_META
];

describe.each(ARTICLE_TYPES)("Newsroom article page — P0-CD1 containment ($article_type)", ({ article_type, overrides }) => {
  it("never renders the suppressed verdict/winner-loser/action/confidence elements", async () => {
    const insight = baseInsight(article_type, overrides);
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    // AI Investment Verdict card and its parts
    expect(screen.queryByText("AI Investment Verdict")).not.toBeInTheDocument();
    expect(screen.queryByText(/Current view:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Bullish$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Bearish$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Mixed$/)).not.toBeInTheDocument();

    // Likely Winners / Likely Losers
    expect(screen.queryByText("Likely Winners")).not.toBeInTheDocument();
    expect(screen.queryByText("Likely Losers")).not.toBeInTheDocument();

    // opportunities[] as a public recommendation, in any of its 3 leak
    // paths: VerdictCard's "Action", the "Investment Opportunities"
    // section, and the AI Interpretation evidence list.
    expect(screen.queryByText("Investment Opportunities")).not.toBeInTheDocument();
    expect(screen.queryByText("Recommendation")).not.toBeInTheDocument();
    expect(screen.queryByText(/Buy HDFC Bank now/i)).not.toBeInTheDocument();

    // Public confidence percentages — VerdictCard badge, stat-grid cell,
    // EvidenceList's "AI Confidence" stat, and the update-history delta.
    expect(screen.queryByText("AI Confidence")).not.toBeInTheDocument();
    expect(screen.queryByText(/91% confidence/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/75%.*91%|91%.*75%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Confidence$/)).not.toBeInTheDocument();

    // Per-company/per-sector "AI Impact" pill (the same unprovenanced
    // `impact` field, suppressed everywhere it appears on this page).
    expect(screen.queryByText("AI Impact")).not.toBeInTheDocument();
  });

  it("still renders the grounded, allowed content for the same article", async () => {
    const insight = baseInsight(article_type, overrides);
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByRole("heading", { level: 1, name: "Test Headline For Containment Coverage" })).toBeInTheDocument();
    expect(screen.getByText(/This is why it matters/)).toBeInTheDocument();
    expect(screen.getByText(/This is what happened/)).toBeInTheDocument();
    expect(screen.getByText("HDFCBANK")).toBeInTheDocument();
    expect(screen.getAllByText("Rate sensitivity").length).toBeGreaterThan(0);
    expect(screen.getByText("A grounded risk description.")).toBeInTheDocument();
    // Historical outcome stays — dated, measured, not a forward "Likely
    // Winner" prediction. This is the /ripple-style pattern P0-D called
    // out as already correct; it's explicitly not touched by P0-CD1.
    expect(screen.getByText("+4.2%")).toBeInTheDocument();
  });
});

describe("Newsroom article page — P0-CD1 containment, edge shapes", () => {
  it("suppresses even when every unsafe field is maximally populated (multiple opportunities, long update history)", async () => {
    const insight = baseInsight("live_signal", {
      opportunities: [
        { title: "Short Nifty into resistance", description: "desc", timeframe: "days", risk: "high" },
        { title: "Accumulate on dips below 1200", description: "desc2", timeframe: "months", risk: "low" },
      ],
      update_history: [
        { at: "2026-08-29T10:00:00Z", version: 2, reason: "r1", summary: "s1", previous_takeaway: "t0", new_takeaway: "t1", confidence: 0.6 },
        { at: "2026-08-30T10:00:00Z", version: 3, reason: "r2", summary: "s2", previous_takeaway: "t1", new_takeaway: "t2", confidence: 0.95 },
      ],
    });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText(/Short Nifty into resistance/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Accumulate on dips/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/60%.*95%|95%.*60%/)).not.toBeInTheDocument();
    expect(screen.queryByText("AI Investment Verdict")).not.toBeInTheDocument();
  });

  it("suppresses even when companies_affected is entirely negative (would previously render only 'Likely Losers')", async () => {
    const insight = baseInsight("anomaly", {
      companies_affected: [
        { name: "Yes Bank", symbol: "YESBANK", impact: "negative", reason: "Negative reason.", timeframe: "immediate" },
      ],
    });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText("Likely Losers")).not.toBeInTheDocument();
    expect(screen.queryByText("Likely Winners")).not.toBeInTheDocument();
    expect(screen.getByText("YESBANK")).toBeInTheDocument();
  });

  it("renders correctly with zero companies/opportunities/risks — no crash, no phantom claims", async () => {
    const insight = baseInsight("educational_intelligence", {
      companies_affected: [], sectors_affected: [], opportunities: [], risks: [], historical_events: [],
    });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByRole("heading", { level: 1, name: "Test Headline For Containment Coverage" })).toBeInTheDocument();
    expect(screen.queryByText("AI Investment Verdict")).not.toBeInTheDocument();
    expect(screen.queryByText("Likely Winners")).not.toBeInTheDocument();
  });
});

describe("Newsroom article page — legacy-history containment patch (2026-09-01)", () => {
  // The real live specimen that motivated this patch: CD1's structural
  // suppression removed the dedicated verdict/opportunities UI, but this
  // exact pre-CD2 key_takeaway and update_history text was still visible
  // through the 30-Second Answer, Intelligence Timeline, and AI Opinion
  // Evolution sections.
  const UNSAFE_TAKEAWAY = "Consider shorting over-valued circuit-climbed names like Hy-Tech Engineers and TBZ, while watching for potential rebound in the banking sector.";

  it("omits the 30-Second Answer when key_takeaway contains recommendation language", async () => {
    const insight = baseInsight("market_wrap", { key_takeaway: UNSAFE_TAKEAWAY });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText("30-Second Answer")).not.toBeInTheDocument();
    expect(screen.queryByText(/Consider shorting/i)).not.toBeInTheDocument();
  });

  it("still shows the 30-Second Answer when key_takeaway is clean", async () => {
    const insight = baseInsight("market_wrap", { key_takeaway: "Grounded, evidence-based summary of the quarter." });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("30-Second Answer")).toBeInTheDocument();
    expect(screen.getAllByText("Grounded, evidence-based summary of the quarter.").length).toBeGreaterThan(0);
  });

  it("never renders update_history free text (previous_takeaway/new_takeaway/summary) in Intelligence Timeline or AI Opinion Evolution", async () => {
    const insight = baseInsight("market_wrap", {
      key_takeaway: UNSAFE_TAKEAWAY,
      update_history: [
        {
          at: "2026-08-30T10:00:00Z", version: 2, reason: "Market narrative updated: Bearish",
          summary: "Updated: Bearish", previous_takeaway: UNSAFE_TAKEAWAY,
          new_takeaway: "Auto moved -2.2% today, unrelated to this Signet story.", confidence: 0.85,
        },
        {
          at: "2026-08-30T16:00:00Z", version: 3, reason: "2 high-urgency development(s)",
          summary: "Updated: Bearish", previous_takeaway: "Auto moved -2.2% today, unrelated to this Signet story.",
          new_takeaway: UNSAFE_TAKEAWAY, confidence: 0.85,
        },
      ],
    });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText(/Consider shorting/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Auto moved -2\.2%/i)).not.toBeInTheDocument();
    // The safe meta-description (why the update happened) still renders —
    // once in Intelligence Timeline, once in AI Opinion Evolution.
    expect(screen.getAllByText("Market narrative updated: Bearish").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2 high-urgency development(s)").length).toBeGreaterThan(0);
    // AI Opinion Evolution is metadata-only now — "Current"/"Updated
    // (vN)" labels, not the replayed opinion text.
    expect(screen.getByText("Current")).toBeInTheDocument();
  });

  it("gates u.reason itself, not just new_takeaway/summary — real bug: reason can carry the same contamination", async () => {
    // The real gap this test locks in: u.reason was assumed to be a safe
    // meta-description ("Market narrative updated: X"), but a real
    // article's stored reason was literally "Auto moved -2.2% today |
    // Market narrative updated: Cautious..." — the exact unrelated-sector
    // contamination shape, just inside the field this patch's first pass
    // treated as always-safe.
    const CONTAMINATED_REASON = "Auto moved -2.2% today | Market narrative updated: Cautious Bear. | Consider shorting over-valued names.";
    const insight = baseInsight("market_wrap", {
      key_takeaway: "Grounded, clean takeaway.",
      update_history: [
        { at: "2026-08-30T10:00:00Z", version: 2, reason: CONTAMINATED_REASON, summary: "s", previous_takeaway: "p", new_takeaway: "n", confidence: 0.85 },
      ],
    });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText(/Auto moved/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Consider shorting/i)).not.toBeInTheDocument();
    // Falls back to a generic, safe label instead of omitting the line
    // entirely — still shows the "something happened" without the
    // contaminated specifics.
    expect(screen.getAllByText("Article updated").length).toBeGreaterThan(0);
  });

  it("does not leak an unsafe key_takeaway into the page's meta description / og:description / twitter:description", async () => {
    const insight = baseInsight("market_wrap", {
      key_takeaway: UNSAFE_TAKEAWAY,
      meta_description: "",
      executive_summary: "",
    });
    mockFetchFor(insight);

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "test-slug" }) });

    expect(metadata.description ?? "").not.toMatch(/Consider shorting/i);
    expect((metadata.openGraph as { description?: string } | undefined)?.description ?? "").not.toMatch(/Consider shorting/i);
    expect((metadata.twitter as { description?: string } | undefined)?.description ?? "").not.toMatch(/Consider shorting/i);
  });

  it("still uses a clean key_takeaway as the meta-description fallback when nothing else is available", async () => {
    const insight = baseInsight("market_wrap", {
      key_takeaway: "Grounded, evidence-based summary of the quarter.",
      meta_description: "",
      executive_summary: "",
    });
    mockFetchFor(insight);

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "test-slug" }) });

    expect(metadata.description).toBe("Grounded, evidence-based summary of the quarter.");
  });
});
