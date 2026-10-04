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
    const urls = fetchMock.mock.calls.map(c => String(c[0]));
    expect(urls.filter(u => u.includes("/api/company-intelligence/TCS"))).toHaveLength(1);   // one intelligence request ...
    expect(urls.some(u => u.includes("investment-watch"))).toBe(false);                      // ... and the verdict comes with it: no investment-watch request
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

  it("shows the company next to its peers with real figures and a plain comparison sentence", async () => {
    const peers: Record<string, unknown> = {
      INFY: { name: "Infosys Ltd", price: "1,500.00", pct_change: -0.4, pe: "21.0", roe: "30.0%" },
      WIPRO: { name: "Wipro Ltd", price: "250.00", pct_change: 0.8, pe: "18.0", roe: "16.0%" },
    };
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      const m = /\/api\/stocks\/(\w+)/.exec(url);
      return Promise.resolve({ ok: true, json: async () => (m ? (peers[m[1]] ?? null) : payload) });
    }));
    render(<CompanyIntelligenceSection symbol="TCS" self={{ name: "Tata Consultancy Services", price: "2,075.00", pct_change: 1.19, pe: "15.1", roe: "47.7%" }} />);
    await waitFor(() => expect(screen.getByText("Where TCS sits")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("₹1,500.00")).toBeInTheDocument());
    expect(screen.getByText("This company")).toBeInTheDocument();
    expect(screen.getByText("₹2,075.00")).toBeInTheDocument();
    expect(screen.getByText("+1.19%")).toBeInTheDocument();
    expect(screen.getByText("-0.40%")).toBeInTheDocument();
    expect(screen.getByText("+0.80%")).toBeInTheDocument();
    expect(screen.getByText(/P\/E 15\.1 against a peer median of 19\.5: below the median; priced lower than 2 of 2 peers\./)).toBeInTheDocument();
    expect(screen.getByText(/ROE 47\.7% against a peer median of 23\.0%: above the median; higher than 2 of 2 peers\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "INFY" })).toHaveAttribute("href", "/companies/INFY");
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
