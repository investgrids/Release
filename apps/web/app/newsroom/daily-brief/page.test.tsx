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
    expect(getByText("Market Wrap")).toBeInTheDocument();
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
