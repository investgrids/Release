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

  it("never renders update_history free text anywhere — Intelligence Timeline and AI Opinion Evolution are removed entirely (Article V2-F2, 2026-09-14)", async () => {
    // Article V2 Final Product Completion audit (2026-09-14) found the
    // 2026-09-06 retirement decision for both sections was recorded but
    // never implemented — both were still live, still tested, while
    // "Story Updates" (their intended replacement) existed nowhere in
    // the repo. F2 removes both outright rather than building Story
    // Updates prematurely. This test now proves the STRONGER guarantee:
    // update_history's reason/summary/takeaway fields have no display
    // surface left on this page at all, safe or not — not merely gated.
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
    // The sections themselves are gone, not merely their unsafe content.
    expect(screen.queryByText("Intelligence Timeline")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Opinion Evolution")).not.toBeInTheDocument();
    // Their own safe meta-descriptions (previously re-displayed twice)
    // are gone too — there is no surface left to show them on.
    expect(screen.queryByText("Market narrative updated: Bearish")).not.toBeInTheDocument();
    expect(screen.queryByText("2 high-urgency development(s)")).not.toBeInTheDocument();
    expect(screen.queryByText("Current")).not.toBeInTheDocument();
  });

  it("update_history's own reason field has no remaining display surface, safe or contaminated (Article V2-F2)", async () => {
    // Real historical bug this test family locked in: u.reason was
    // assumed to be a safe meta-description, but a real article's
    // stored reason carried the same recommendation-language
    // contamination as the free-text fields. Now moot at the
    // presentation layer -- Intelligence Timeline (the only renderer of
    // u.reason) is gone, so this is a stronger guarantee than gating.
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
    expect(screen.queryByText("Intelligence Timeline")).not.toBeInTheDocument();
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

  it("does not leak an unsafe meta_description itself into meta/og/twitter description (2026-09-03 gap)", async () => {
    // Real gap: meta_description was the FIRST value tried and was never
    // gated at all -- only its fallbacks (executive_summary/key_takeaway)
    // were. Found via the identical bug on research/[slug]/page.tsx.
    const insight = baseInsight("market_wrap", {
      key_takeaway: "Grounded, evidence-based summary of the quarter.",
      meta_description: UNSAFE_TAKEAWAY,
      executive_summary: "",
    });
    mockFetchFor(insight);

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: "test-slug" }) });

    expect(metadata.description ?? "").not.toMatch(/Consider shorting/i);
    // Falls through to the next safe candidate rather than an empty string.
    expect(metadata.description).toBe("Grounded, evidence-based summary of the quarter.");
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

describe("Newsroom article page — Article V2-F2 Public Article Experience (2026-09-14)", () => {
  // A minimal, realistic V2 article: one company (no impact/reason/
  // timeframe — see publication_translator.py's own field disposition),
  // structured sources, key_facts, a real what_to_watch entry, no
  // opportunities/risks/historical_events/faqs/ripple_effect/sectors,
  // no update_history, no angle_entity fan-out.
  function v2Insight(overrides: Record<string, unknown> = {}) {
    return baseInsight("company_intelligence", {
      companies_affected: [{ name: "Test Co", symbol: "TESTCO" }],
      sectors_affected: [],
      opportunities: [],
      risks: [],
      historical_events: [],
      ripple_effect: [],
      what_to_watch_next: [],
      faqs: [],
      sources: [
        { title: "A real NSE filing", source_type: "nse", source_url: "https://nse.example/filing", published_at: "2026-09-14T09:00:00Z", evidence_id: "ev-1" },
      ],
      key_facts: [],
      update_history: [],
      update_count: 0,
      parent_event_group_id: null,
      angle: "primary",
      angle_entity: null,
      ...overrides,
    });
  }

  it("renders V2's structured source objects without crashing", async () => {
    const insight = v2Insight();
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("A real NSE filing")).toBeInTheDocument();
  });

  it("still renders V1's legacy plain-string sources unchanged", async () => {
    const insight = v2Insight({ sources: ["Reuters", "Economic Times"] });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("Reuters")).toBeInTheDocument();
    expect(screen.getByText("Economic Times")).toBeInTheDocument();
  });

  it("renders no clickable link for a structured source, even with a real source_url", async () => {
    // Standing rule: this app never links users off-site to a third-party
    // source. A real, legitimate source_url must not become an <a href>.
    const insight = v2Insight();
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    const sourceEl = screen.getByText("A real NSE filing");
    expect(sourceEl.closest("a")).toBeNull();
  });

  it("shows no EvidenceList card when there is nothing substantive (V2's typical empty shape)", async () => {
    // Real gap the audit found: EvidenceList rendered unconditionally,
    // showing a thin "Sources: 0 / Historical Data: 0 events" shell.
    // published_at is deliberately unset here too -- a real article
    // always has one, and it legitimately becomes a "Published: <date>"
    // fact (real, useful, not the bug), so isolating the true
    // zero-substance case requires removing it explicitly, not just
    // zeroing sources/historical/risks/watch.
    const insight = v2Insight({ sources: [], published_at: undefined, update_count: 0, last_updated: undefined });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText("Evidence")).not.toBeInTheDocument();
    expect(screen.queryByText("Historical Data")).not.toBeInTheDocument();
  });

  it("renders key_facts as Key Numbers, with financial facts and observed market reaction", async () => {
    const insight = v2Insight({
      key_facts: [
        { kind: "financial_fact", label: "Revenue", value: "Rs 500 crore", period: "FY27 Q1", metric_code: "REVENUE" },
        { kind: "market_reaction", label: "Market reaction", value: "+2.40%", period: "observed" },
      ],
    });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("Key Numbers")).toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("Rs 500 crore")).toBeInTheDocument();
    expect(screen.getByText("Market reaction")).toBeInTheDocument();
    expect(screen.getByText("+2.40%")).toBeInTheDocument();
  });

  it("shows no Key Numbers section at all when key_facts is empty — no filler card", async () => {
    const insight = v2Insight({ key_facts: [] });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText("Key Numbers")).not.toBeInTheDocument();
  });

  it("renders observed market reaction as a plain observation, never a claimed impact direction", async () => {
    // The exact CD3 semantics the owner locked: "+2.40%" is a real,
    // observed fact; it must never be paired with words claiming a
    // positive/negative impact interpretation of that number.
    const insight = v2Insight({
      key_facts: [{ kind: "market_reaction", label: "Market reaction", value: "+2.40%", period: "observed" }],
    });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("+2.40%")).toBeInTheDocument();
    expect(screen.queryByText(/positive impact/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/negative impact/i)).not.toBeInTheDocument();
  });

  it("renders What to Watch Next only when present, with no fallback text", async () => {
    const withWatch = v2Insight({ what_to_watch_next: ["A real, already-scheduled date of September 20, 2026."] });
    mockFetchFor(withWatch);
    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));
    expect(screen.getByText("What to Watch Next")).toBeInTheDocument();
    // Appears twice by design (its own section plus EvidenceList's
    // derived "AI Interpretation" bullet) — same established pattern as
    // every other multi-surface field on this page (see e.g. "Rate
    // sensitivity" below).
    expect(screen.getAllByText(/September 20, 2026/).length).toBeGreaterThan(0);
  });

  it("shows no What to Watch Next section when empty — no synthetic fallback block", async () => {
    const insight = v2Insight({ what_to_watch_next: [] });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText("What to Watch Next")).not.toBeInTheDocument();
  });

  it("shows the Company Impact table without em-dash placeholders when reason/timeframe are absent (V2 shape)", async () => {
    const insight = v2Insight();
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("TESTCO")).toBeInTheDocument();
    // Why/Expected Horizon column headers must not appear at all when no
    // company in the set has real data for them -- not shown as "—".
    expect(screen.queryByText("Why")).not.toBeInTheDocument();
    expect(screen.queryByText("Expected Horizon")).not.toBeInTheDocument();
  });

  it("still shows Why/Expected Horizon columns for a real V1 batch that has that data", async () => {
    const insight = v2Insight({
      companies_affected: [
        { name: "HDFC Bank", symbol: "HDFCBANK", impact: "positive", reason: "A real, grounded reason.", timeframe: "short" },
      ],
    });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("Why")).toBeInTheDocument();
    expect(screen.getByText("A real, grounded reason.")).toBeInTheDocument();
  });

  it("shows only one takeaway surface on the page (30-Second Answer, now that Intelligence Timeline is removed)", async () => {
    const insight = v2Insight({ key_takeaway: "A single, grounded takeaway." });
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("30-Second Answer")).toBeInTheDocument();
    expect(screen.getAllByText("A single, grounded takeaway.").length).toBe(1);
  });

  it("emits the JSON-LD <script> tag for a V2 article using the backend-provided json_ld", async () => {
    const insight = v2Insight({
      json_ld: {
        "@context": "https://schema.org", "@type": "NewsArticle",
        headline: "Test Headline For Containment Coverage",
        datePublished: "2026-09-14T09:00:00Z", dateModified: "2026-09-14T09:00:00Z",
      },
    });
    mockFetchFor(insight);

    const { container } = render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    const script = container.querySelector('script[type="application/ld+json"]');
    expect(script).not.toBeNull();
    expect(script?.innerHTML ?? "").toContain("NewsArticle");
  });

  it("renders no JSON-LD script when the backend provides none (e.g. a legacy row predating this field)", async () => {
    const insight = v2Insight({ json_ld: undefined });
    mockFetchFor(insight);

    const { container } = render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(container.querySelector('script[type="application/ld+json"]')).toBeNull();
  });

  it("a real V1 article (multiple companies, sectors, risks, historical events, faqs, update_history) still renders every section correctly — full backward compatibility", async () => {
    const insight = baseInsight("market_wrap"); // the full, rich V1 fixture used throughout this file
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByText("HDFCBANK")).toBeInTheDocument();
    expect(screen.getByText("Why")).toBeInTheDocument();
    expect(screen.getByText("Expected Horizon")).toBeInTheDocument();
    expect(screen.getAllByText("Rate sensitivity").length).toBeGreaterThan(0);
    expect(screen.getByText("+4.2%")).toBeInTheDocument();
    expect(screen.getByText("Reuters")).toBeInTheDocument();
    expect(screen.getByText("Evidence")).toBeInTheDocument();
    // Removed sections must not reappear for V1 either.
    expect(screen.queryByText("Intelligence Timeline")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Opinion Evolution")).not.toBeInTheDocument();
  });
});

describe("Newsroom article page — Article V2-F3 End-to-End Release Gate (2026-09-14)", () => {
  // These fixtures mirror the EXACT field names/values the real backend
  // pipeline produced in the matching backend specimen
  // (apps/backend/tests/services/test_article_v2_release_gate_end_to_end.py
  // ::test_full_article_specimen_survives_backend_to_api_to_frontend_contract) --
  // proving this page's assumed shape and the real
  // translate_composed_article()/publish_v2_article()/GET-/api/insights/{slug}
  // output actually agree, not just that a hand-typed F2 fixture renders.
  function fullArticleSpecimen(overrides: Record<string, unknown> = {}) {
    return baseInsight("company_intelligence", {
      headline: "RGATE1 Wins Rs 500 Crore Order",
      key_takeaway: "This order materially expands RGATE1's order book.",
      why_it_matters: "This order materially expands RGATE1's order book.",
      what_happened: "On 14 September 2026, RGATE1 Industries Ltd won a Rs 500 crore order.",
      companies_affected: [{ name: "RGATE1 Industries Ltd", symbol: "RGATE1" }],
      sectors_affected: [],
      opportunities: [],
      risks: [],
      historical_events: [],
      ripple_effect: [],
      what_to_watch_next: ["A board meeting is scheduled for 30 September 2026 to consider fund raising."],
      faqs: [],
      sources: [
        { title: "RGATE1 wins Rs 500 crore order", source_type: "nse", source_url: null, published_at: "2026-09-14T09:00:00Z", evidence_id: "ev-primary" },
        { title: "RGATE1 Q2 results filing", source_type: "nse", source_url: null, published_at: "2026-09-14T09:00:00Z", evidence_id: "ev-supporting" },
      ],
      key_facts: [
        { kind: "financial_fact", label: "Revenue", value: "Rs 500 crore", period: "FY26 Q2", metric_code: "REVENUE", prior_value: "Rs 420 crore", prior_period: "FY25 Q2" },
        { kind: "market_reaction", label: "Market reaction", value: "+3.25%", period: "observed" },
      ],
      canonical_url: "https://www.marketripple.in/newsroom/article/rgate1-wins-rs-500-crore-order-abc123",
      json_ld: {
        "@context": "https://schema.org", "@type": "NewsArticle",
        headline: "RGATE1 Wins Rs 500 Crore Order",
        datePublished: "2026-09-20T08:30:00+00:00", dateModified: "2026-09-20T08:30:00+00:00",
      },
      update_history: [],
      update_count: 0,
      parent_event_group_id: null,
      angle: "primary",
      angle_entity: null,
      ...overrides,
    });
  }

  // Mirrors the backend's thin/EVENT_ONLY-shaped specimen
  // (test_thin_specimen_publishes_and_reads_back_without_fabricated_placeholders):
  // only what_happened + one source, everything else genuinely empty.
  function thinSpecimen(overrides: Record<string, unknown> = {}) {
    return baseInsight("company_intelligence", {
      headline: "RGATE2 Files Board Meeting Notice",
      key_takeaway: "On 14 September 2026, RGATE2 Industries Ltd filed a board meeting notice.",
      why_it_matters: undefined,
      what_happened: "On 14 September 2026, RGATE2 Industries Ltd filed a board meeting notice.",
      companies_affected: [{ name: "RGATE2 Industries Ltd", symbol: "RGATE2" }],
      sectors_affected: [],
      opportunities: [],
      risks: [],
      historical_events: [],
      ripple_effect: [],
      what_to_watch_next: [],
      faqs: [],
      sources: [
        { title: "RGATE2 board meeting notice", source_type: "nse", source_url: null, published_at: "2026-09-14T09:00:00Z", evidence_id: "ev-primary-2" },
      ],
      key_facts: [],
      update_history: [],
      update_count: 0,
      parent_event_group_id: null,
      angle: "primary",
      angle_entity: null,
      ...overrides,
    });
  }

  it("full specimen: key_facts render as Key Numbers with financial fact + market reaction, including prior-period comparison", async () => {
    const insight = fullArticleSpecimen();
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("Key Numbers")).toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("Rs 500 crore")).toBeInTheDocument();
    expect(screen.getByText(/vs Rs 420 crore \(FY25 Q2\)/)).toBeInTheDocument();
    expect(screen.getByText("Market reaction")).toBeInTheDocument();
    expect(screen.getByText("+3.25%")).toBeInTheDocument();
  });

  it("full specimen: what_to_watch_next survives end-to-end and renders under What to Watch Next", async () => {
    const insight = fullArticleSpecimen();
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("What to Watch Next")).toBeInTheDocument();
    expect(screen.getByText("A board meeting is scheduled for 30 September 2026 to consider fund raising.")).toBeInTheDocument();
  });

  it("full specimen: both structured sources render as plain text, with no external link for either", async () => {
    const insight = fullArticleSpecimen();
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    const s1 = screen.getByText("RGATE1 wins Rs 500 crore order");
    const s2 = screen.getByText("RGATE1 Q2 results filing");
    expect(s1).toBeInTheDocument();
    expect(s2).toBeInTheDocument();
    expect(s1.closest("a")).toBeNull();
    expect(s2.closest("a")).toBeNull();
  });

  it("full specimen: canonical metadata and JSON-LD survive the full path", async () => {
    const insight = fullArticleSpecimen();
    mockFetchFor(insight);

    const { container } = render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    const script = container.querySelector('script[type="application/ld+json"]');
    expect(script).not.toBeNull();
    expect(script?.innerHTML ?? "").toContain("RGATE1 Wins Rs 500 Crore Order");
    expect(script?.innerHTML ?? "").toContain("2026-09-20T08:30:00");
  });

  it("full specimen: Timeline/Opinion Evolution stay absent and the takeaway is a single surface", async () => {
    const insight = fullArticleSpecimen();
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.queryByText("Intelligence Timeline")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Opinion Evolution")).not.toBeInTheDocument();
    expect(screen.getAllByText("This order materially expands RGATE1's order book.").length).toBeGreaterThanOrEqual(1);
  });

  it("thin specimen: publishes end-to-end with no fabricated placeholders — absent sections simply disappear", async () => {
    const insight = thinSpecimen();
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getAllByText(/RGATE2 Industries Ltd filed a board meeting notice/).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Key Numbers")).not.toBeInTheDocument();
    expect(screen.queryByText("What to Watch Next")).not.toBeInTheDocument();
    expect(screen.queryByText("Investment Opportunities")).not.toBeInTheDocument();
    expect(screen.getByText("RGATE2 board meeting notice")).toBeInTheDocument();
  });

  it("thin specimen: EvidenceList still shows real substance (one source, a real published date) without a filler shell", async () => {
    const insight = thinSpecimen();
    mockFetchFor(insight);

    render(await ArticlePage({ params: Promise.resolve({ slug: "test-slug" }) }));

    expect(screen.getByText("Evidence")).toBeInTheDocument();
  });
});
