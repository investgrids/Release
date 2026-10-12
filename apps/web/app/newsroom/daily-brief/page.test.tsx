/**
 * Daily Brief V2 release checks: the page renders for the new API shape, the old shape, sparse data and an unavailable forecast; a
 * withheld forecast never shows a direction in the page, the metadata or the structured data; a completed session is never described
 * as a bullish opening.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

import Page, { generateMetadata } from "./page";

const NIFTY = { name: "NIFTY 50", value: "22,363.35", change: "-0.70%", pct: -0.7, positive: false };
const baseSnapshot = {
  nifty: NIFTY, banknifty: null, sensex: { ...NIFTY, name: "SENSEX", value: "71,924.68", pct: -0.76 }, vix: null,
  breadth: { advances: 18, declines: 30, unchanged: 1 }, market_status: { is_open: false, status: "closed", time_ist: "05:00 PM", date: "12 Oct 2026" },
  sectors: [],
};
const emptyBlocks = {
  events: { tiers: { critical: 0, high: 0, medium: 0, other: 0 }, total: 0, top: [] },
  why_today_matters: [], stocks_to_watch: [], sector_intelligence: [], historical_context: { available: false, message: "n/a" },
  what_to_watch_next: [], questions: [], evidence: [], generated_at: "2026-10-12T11:30:00+00:00",
};
const newShape = {
  ...emptyBlocks,
  session: { state: "after_close", label: "Market Wrap", subtitle: "Market wrap, Mon 12 Oct 2026", reference_label: "Mon 12 Oct 2026" },
  market_verdict: {
    kind: "realized", headline: "Lower close", direction: "Negative", confidence: null, primary_drivers: [], risks: [], ai_generated: false,
    reasoning: "Nifty 50 closed 0.70% lower at 22,363.35, and the Sensex 0.76% lower at 71,924.68.", session_state: "after_close",
    session_date: "2026-10-12", target_date: null,
  },
  market_snapshot: baseSnapshot, summary: "Lower close on Mon 12 Oct 2026. Main risk: India VIX rose.",
  catalysts: [], risks: ["INDIA VIX"], catalyst_details: [],
  risk_details: [{ name: "INDIA VIX", explanation: "India VIX rose to 15.8 (+4.20%): expected volatility is higher.", source: "feed" }],
  questions: [{ question: "What were the key index levels at the close?", answer: "Nifty 50 22,363.35 (-0.70%).", links: [] }],
};
const withheld = {
  ...newShape,
  session: { state: "pre_open", label: "Pre-Market Outlook", subtitle: "Opening outlook for Tue 13 Oct 2026", reference_label: "Mon 12 Oct 2026" },
  market_verdict: {
    kind: "forecast", headline: "Signals disagree", direction: null, confidence: null, primary_drivers: [], risks: [], ai_generated: true,
    reasoning: "Signals disagree, so no opening direction is shown. The model read positive, the signal model reads neutral, and 3 of 3 directional signals point the other way.",
    session_state: "pre_open", session_date: "2026-10-09", target_date: "2026-10-13",
    direction_check: { status: "conflict", withheld: true, message: "Signals disagree, so no opening direction is shown." },
    forecast: { target_date: "2026-10-13", generated_at: "2026-10-13T02:00:00+00:00", method: "ai_validated_against_signals" },
  },
  summary: "No opening direction for Tue 13 Oct 2026: the signals disagree.",
};
const oldShape = {
  market_verdict: { direction: "Positive", confidence: 62, primary_drivers: ["a"], risks: ["b"], reasoning: "Upside bias.", ai_generated: true },
  market_snapshot: baseSnapshot, ...emptyBlocks, why_today_matters: [{ event: "E", consequence: "C", affected: ["Banking", "HDFCBANK"] }],
  catalysts: ["Nifty up"], risks: ["INDIA VIX"],
};

function mockApi(body: unknown, ok = true) {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok, json: async () => body })));
}
afterEach(() => vi.unstubAllGlobals());

async function renderPage() {
  const ui = await Page();
  return render(ui);
}
function jsonLd(container: HTMLElement): string {
  return Array.from(container.querySelectorAll('script[type="application/ld+json"]')).map(s => s.textContent ?? "").join("\n");
}

describe("daily brief page", () => {
  it("after the close: shows a lower close, never a bullish opening", async () => {
    mockApi(newShape);
    const { container, getByText, queryByText } = await renderPage();
    expect(getByText("Lower close")).toBeInTheDocument();
    expect(getByText("Market wrap, Mon 12 Oct 2026")).toBeInTheDocument();
    expect(queryByText(/Bullish|Bearish/)).toBeNull();
    expect(container.textContent).toContain("what happened, not a forecast");
    const md = await generateMetadata();
    expect(String(md.description)).toContain("0.70% lower");
    expect(String(md.description).toLowerCase()).not.toContain("outlook");
  });

  it("withheld forecast: no direction anywhere (page, metadata, structured data)", async () => {
    mockApi(withheld);
    const { container, getByText, queryByText } = await renderPage();
    expect(getByText("Signals disagree")).toBeInTheDocument();
    expect(queryByText(/Bullish|Bearish|Neutral/)).toBeNull();
    expect(container.textContent ?? "").not.toMatch(/\d+% confidence/);
    const md = await generateMetadata();
    const blob = `${md.title} ${md.description} ${jsonLd(container)}`.toLowerCase();
    for (const word of ["bullish", "bearish", "positive outlook", "negative outlook", "upside"]) expect(blob).not.toContain(word);
    expect(String(md.description)).not.toMatch(/: (positive|negative)/i);
  });

  it("unavailable forecast renders without a direction or confidence", async () => {
    mockApi({ ...withheld, market_verdict: { ...withheld.market_verdict, kind: "unavailable", headline: "Outlook unavailable", unavailable: true, reasoning: null, direction_check: null, forecast: null }, summary: "Market data is limited right now." });
    const { container, queryByText } = await renderPage();
    expect(container.textContent).toContain("Outlook unavailable");
    expect(queryByText(/Bullish|Bearish/)).toBeNull();
  });

  it("old API shape (no session/summary/details) still renders, as the forecast it was", async () => {
    mockApi(oldShape);
    const { container } = await renderPage();
    expect(container.textContent).toContain("Indian Stock Market Today");
    expect(container.textContent).toContain("INDIA VIX");              // risks fall back to their names
  });

  it("sparse data renders without throwing", async () => {
    mockApi({
      ...emptyBlocks, session: newShape.session, summary: "", catalyst_details: [], risk_details: [],
      market_verdict: { kind: "unavailable", headline: "Index data unavailable", direction: null, confidence: null, primary_drivers: [], risks: [], reasoning: null, ai_generated: false, unavailable: true, session_state: "after_close", session_date: null, target_date: null },
      market_snapshot: { nifty: null, banknifty: null, sensex: null, vix: null, breadth: null, market_status: null, sectors: [], unavailable: true },
    });
    const { container } = await renderPage();
    expect(container.textContent).toContain("Index data unavailable");
  });

  it("shows the fallback message when the backend is down", async () => {
    mockApi({}, false);
    const { container } = await renderPage();
    expect(container.textContent).toContain("temporarily unavailable");
  });

  it("FAQ structured data is exactly the visible questions", async () => {
    mockApi(newShape);
    const { container } = await renderPage();
    const faq = JSON.parse(Array.from(container.querySelectorAll('script[type="application/ld+json"]')).map(s => s.textContent!).find(t => t.includes("FAQPage"))!);
    expect(faq.mainEntity.map((q: { name: string }) => q.name)).toEqual(newShape.questions.map(q => q.question));
    expect(faq.mainEntity.map((q: { acceptedAnswer: { text: string } }) => q.acceptedAnswer.text)).toEqual(newShape.questions.map(q => q.answer));
  });
});

// ── Part A sections ─────────────────────────────────────────────────────────────────────────────────────────────

const driver = (over: Record<string, unknown> = {}) => ({
  id: "e1", headline: "RBI measures spark rupee rally", source: "Economic Times", published_at: "2026-10-12T14:35:00+00:00",
  evidence_label: "potential_contributor", relevance: ["Coincided with Banking -0.80% in the same session. Timing alone does not show that this caused the move."],
  sectors: [{ name: "Banking", verified_move_pct: -0.8 }], companies: [{ symbol: "HDFCBANK", relation: "mentioned" }], articles_merged: 3,
  links: { event: "/events/rbi-measures-spark-rupee-rally", article: "/newsroom/article/rbi-rupee-analysis" }, ...over,
});
const withSections = (items: ReturnType<typeof driver>[], extra: Record<string, unknown> = {}) => {
  const groups: Record<string, ReturnType<typeof driver>[]> = { confirmed_driver: [], potential_contributor: [], commentary: [] };
  items.forEach(i => groups[i.evidence_label as string].push(i));
  return {
    ...newShape,
    market_drivers: { items, groups, note: items.length ? null : "No development met the evidence threshold for this session.", method: "m" },
    investor_implications: { items: [{ sector: "Banking", verified_move_pct: -0.8, why: "Named in 1 development above. Its sector index moved -0.80% in the session.", developments: [{ id: "e1", headline: "RBI measures spark rupee rally", evidence_label: "potential_contributor" }],
      companies_mentioned: ["HDFCBANK"], companies_label: "Mentioned in these developments (not an assessment of impact)" }], note: null },
    scenarios: { available: true, target: "Tue 13 Oct 2026", generated_at: "t", gift_nifty_status: "live",
      scenarios: [{ key: "bullish", title: "Bullish scenario", condition: "If GIFT Nifty indicates a higher open.", watch: ["GIFT Nifty turning positive"] },
                  { key: "neutral", title: "Neutral scenario", condition: "If signals stay mixed.", watch: ["FII Flow staying negative"] },
                  { key: "bearish", title: "Bearish scenario", condition: "If US futures point lower.", watch: ["S&P 500 Fut. turning negative"] }],
      current_signals: [{ label: "GIFT Nifty", reading: "+0.23%", direction: "positive", detail: null }], catalysts: ["CPI inflation data (Oct 14, 2026)"] },
    takeaway: { development: { headline: "RBI measures spark rupee rally", evidence_label: "potential_contributor", text: "It coincided with the session; the data does not show that it caused the move.", id: "e1" },
      uncertainty: "No development is confirmed as the cause of the move.", monitor: ["Whether the Banking move holds in the next session"] },
    ...extra,
  };
};

describe("daily brief V2 sections", () => {
  it("renders drivers with evidence labels, verified sector moves, 'mentioned' companies and internal links only", async () => {
    mockApi(withSections([driver(), driver({ id: "e2", headline: "RBI holds repo rate", evidence_label: "confirmed_driver", relevance: ["The source itself ties this development to the move."], sectors: [], companies: [], links: { event: "/events/e2", article: null } })]));
    const { container, getByText, getAllByText } = await renderPage();
    expect(getByText("What moved the market today?")).toBeInTheDocument();
    expect(getAllByText("Confirmed").length).toBeGreaterThan(0);
    expect(getAllByText("Potential contributor").length).toBeGreaterThan(0);
    expect(container.textContent).toContain("Banking");
    expect(container.textContent).toContain("-0.80%");
    expect(container.textContent).toContain("mentioned");
    expect(container.textContent).toContain("Timing alone does not show that this caused the move");
    const hrefs = Array.from(container.querySelectorAll("a[href]")).map(a => a.getAttribute("href")!);
    expect(hrefs.every(h => h.startsWith("/"))).toBe(true);
    expect(hrefs).toContain("/newsroom/article/rbi-rupee-analysis");
    expect(container.textContent ?? "").not.toMatch(/impact score|bullish impact|bearish impact/i);
  });

  it("sparse data: fewer than five items, an honest note, no filler cards", async () => {
    mockApi(withSections([]));
    const { container } = await renderPage();
    expect(container.textContent).toContain("No development met the evidence threshold for this session.");
    expect(container.querySelectorAll("#drivers-title ~ div li, #drivers-title ~ ul li").length).toBe(0);
  });

  it("scenarios are conditional and carry no probability, target or range; the live session hides them", async () => {
    mockApi(withSections([driver()]));
    const first = await renderPage();
    expect(first.container.textContent).toContain("Next session: Tue 13 Oct 2026");
    expect(first.container.textContent).toContain("Conditional outlook");
    expect(first.container.textContent ?? "").not.toMatch(/probability|price target|support level|resistance|expected range/i);
    first.unmount();
    mockApi(withSections([driver()], { scenarios: { available: false, reason: "The session is live. Scenarios for the next session return after the close.", target: "Tue 13 Oct 2026", generated_at: "t" } }));
    const live = await renderPage();
    expect(live.container.textContent).toContain("The session is live.");
  });

  it("investor takeaway shows the development, the uncertainty and what to monitor", async () => {
    mockApi(withSections([driver()]));
    const { container } = await renderPage();
    expect(container.textContent).toContain("Investor takeaway");
    expect(container.textContent).toContain("No development is confirmed as the cause of the move.");
    expect(container.textContent).toContain("Whether the Banking move holds in the next session");
  });

  it("old API shape (no new sections) falls back to the events list instead of failing", async () => {
    mockApi({ ...newShape, events: { ...emptyBlocks.events, top: [{ id: "x", headline: "Old events list item", one_liner: "Old events list item", priority_tier: "High", priority_score: 1, sectors: [], tickers: [], sentiment: null, source: null }] } });
    const { container } = await renderPage();
    expect(container.textContent).toContain("Market-moving events");
    expect(container.textContent).toContain("Old events list item");
  });

  it("removed duplicates stay removed: no sector grid, no 'why today matters', no duplicate driver tiles", async () => {
    mockApi(withSections([driver()]));
    const { container } = await renderPage();
    for (const gone of ["Sector Intelligence", "Why Today Matters", "Strongest supportive signal", "Biggest risk signal", "What to Watch Next", "Companies named in high-priority events"]) {
      expect(container.textContent).not.toContain(gone);
    }
    expect(container.textContent).toContain("After Market");
  });
});

describe("investor implications (V2.1)", () => {
  const v21 = {
    items: [], note: null,
    sector_performance: { available: true, as_of: "Mon 12 Oct 2026 close", source: "Sector index quotes from the market data provider", note: null,
      leaders: [{ name: "Realty", pct: 0.9 }, { name: "Auto", pct: 0.5 }], laggards: [{ name: "FMCG", pct: -2.0 }, { name: "IT", pct: -1.3 }] },
    exposure: [
      { variable: "rupee_stronger", label: "Stronger rupee (USD/INR lower)", evidence: "verified", observed: "USD/INR lower at 95.76", source: "Forex market data", observed_at: "2026-10-12T16:00:00Z",
        pressured: ["IT", "Pharma"], helped: ["Aviation"], why: "Export earners translate foreign revenue into fewer rupees.", basis: "rule" },
      { variable: "yields_rising", label: "Rising bond yields (reported)", evidence: "reported", observed: "Reported: India benchmark bond posts worst day", source: "Economic Times", observed_at: null,
        pressured: ["Banking", "Realty"], helped: [], why: "Banks mark down bond holdings.", basis: "rule" },
    ],
    overlap: [
      { sector: "IT", verified_move_pct: -1.3, variable: "rupee_stronger", typical: "pressured", agrees: true, text: "IT is typically pressured by this; its index moved -1.30% in the session, in line with that typical exposure. An observation, not an attribution." },
      { sector: "Realty", verified_move_pct: 0.9, variable: "yields_rising", typical: "pressured", agrees: false, text: "Realty is typically pressured by this; its index moved +0.90% in the session, against that typical exposure. An observation, not an attribution." },
    ],
    company_links: [{ sector: "IT", companies: ["TCS"], via: ["TCS wins deal"], basis: "b" }], exposure_notes: [],
  };

  it("shows verified sector performance, typical exposure with evidence levels, overlap and company links, and never the empty message", async () => {
    mockApi(withSections([driver()], { investor_implications: v21 }));
    const { container, getByText, queryByText } = await renderPage();
    expect(getByText("Verified sector performance")).toBeInTheDocument();
    expect(container.textContent).toContain("As of Mon 12 Oct 2026 close");
    expect(container.textContent).toContain("Realty");
    expect(container.textContent).toContain("-2.00%");
    expect(getByText("Typical exposure by market variable")).toBeInTheDocument();
    expect(container.textContent).toContain("Verified");
    expect(container.textContent).toContain("Reported");
    expect((container.textContent ?? "").toLowerCase()).toContain("typically pressured");
    expect(container.textContent).toContain("USD/INR lower at 95.76");
    expect(container.textContent).toContain("against that typical exposure");
    expect(container.textContent).toContain("Companies named");
    expect(queryByText("No sector is tied to a verified development yet.")).toBeNull();
    expect(container.textContent ?? "").not.toMatch(/\b(because|due to|caused by|driven by)\b/i);
  });

  it("when nothing is available it says so once and does not crash", async () => {
    mockApi(withSections([driver()], { investor_implications: { items: [], note: "No sector information is available yet.", sector_performance: { available: false, leaders: [], laggards: [], as_of: "x", source: "s", note: "Sector index quotes are unavailable right now." } } }));
    const { container } = await renderPage();
    expect(container.textContent).toContain("Sector index quotes are unavailable right now.");
  });

  it("an older implications payload (tag rows only) still renders", async () => {
    mockApi(withSections([driver()]));
    const { container } = await renderPage();
    expect(container.textContent).toContain("Investor implications");
    expect(container.textContent).toContain("Banking");
  });
});
