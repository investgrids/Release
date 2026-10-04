import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { CompanyIntelligenceSection } from "./CompanyIntelligenceSection";

const payload = {
  available: true, symbol: "TCS", name: "Tata Consultancy Services",
  active_events: [
    { id: "1", slug: "fpi-outflows", headline: "Record FPI outflows signal pressure", urgency: 8, sentiment: "negative", lifecycle: "LIVE", active_score: 9, direct: false },
    { id: "2", slug: "fpi-outflows-2", headline: "record fpi outflows signal pressure.", urgency: 8, sentiment: "negative", lifecycle: "LIVE", active_score: 8, direct: false },
    { id: "3", slug: "tcs-deal", headline: "TCS wins a large deal", urgency: 6, sentiment: "positive", lifecycle: "Developing", active_score: 7, direct: true },
  ],
  ripple_position: { upstream: ["Technology"], company: "TCS", downstream: ["INFY", "WIPRO"] },
  historical: null,
  related_opportunities: [{ title: "Some bank opportunity", href: "/opportunity-radar/x", score: 90 }],
  investment_watch: { current_verdict: { verdict_scale: "Cautious", confidence: 31, as_of: "2026-08-19" }, last_change: { from: "Positive", to: "Cautious", from_date: "2026-08-18", to_date: "2026-08-19", why: "Margin pressure widens." }, watching: [], next_trigger: null },
};

afterEach(() => vi.unstubAllGlobals());

describe("CompanyIntelligenceSection", () => {
  it("makes one request, shows the verdict once from that response, and lists repeated headlines once", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => payload });
    vi.stubGlobal("fetch", fetchMock);
    render(<CompanyIntelligenceSection symbol="TCS" govScore={30} pricePositive />);
    await waitFor(() => expect(screen.getByText("Investment Watch")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(1);                                   // the verdict comes with the intelligence payload: no investment-watch request
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/company-intelligence/TCS");
    expect(screen.getAllByText("Cautious").length).toBeGreaterThan(0);
    expect(screen.getByText(/Low/)).toBeInTheDocument();                           // confidence in words
    expect(screen.getAllByText(/Record FPI outflows signal pressure/i)).toHaveLength(1);
    expect(screen.getByText(/Developing · Mentions TCS/)).toBeInTheDocument();
    expect(screen.getByText(/Live · Sector-wide/)).toBeInTheDocument();
    expect(screen.getByText("Where TCS sits")).toBeInTheDocument();
    expect(screen.getByText("INFY")).toBeInTheDocument();
    // the old duplicates are gone: no second verdict card, no related-opportunity chips (Related Intelligence below covers them)
    expect(screen.queryByText(/Why TCS Matters Today/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Some bank opportunity")).not.toBeInTheDocument();
  });

  it("shows a loading placeholder first and nothing at all for an unavailable company", async () => {
    let resolve!: (v: unknown) => void;
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(r => { resolve = r; })));
    const { container } = render(<CompanyIntelligenceSection symbol="XYZ" />);
    expect(screen.getByLabelText("Loading intelligence")).toBeInTheDocument();
    resolve({ ok: true, json: async () => ({ available: false }) });
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
