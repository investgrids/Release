import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { InvestmentWatchPanel, type WatchResponse } from "./InvestmentWatchPanel";

const subject = { subject_key: "company:TCS", subject_type: "company" as const, subject_label: "TCS" };
const base: WatchResponse = {
  available: true,
  current_verdict: { verdict_scale: "Cautious", confidence: 31, as_of: "2026-08-19", age_days: 46 },
  last_change: null,
  watching: [
    { label: "US dollar / rupee", status: "rising", detail: "₹88.23 per US$ (+0.4%)", why: "Export earnings are in dollars: a weaker rupee tends to lift margins.", scope: "sector" },
    { label: "Foreign investor (FII) flows", status: "selling", detail: "-₹9,484 Cr, previous session", why: "Heavy foreign selling tends to weigh on large, widely held stocks.", scope: "market" },
    { label: "Nasdaq", status: "flat", detail: "20,000 (+0.0%)", scope: "sector" },
  ],
  next_trigger: { label: "RBI policy decision", category: "RBI", date: "2026-10-20", days_until: 16, description: "", scope: "market" },
};

afterEach(() => vi.unstubAllGlobals());

describe("InvestmentWatchPanel", () => {
  it("uses the data it is given without making a request", () => {
    const f = vi.fn(); vi.stubGlobal("fetch", f);
    render(<InvestmentWatchPanel subject={subject} initialData={base} />);
    expect(f).not.toHaveBeenCalled();
    expect(screen.getByText("Cautious")).toBeInTheDocument();
    expect(screen.getByText(/Low/)).toBeInTheDocument();
  });

  it("warns when the verdict is older than two weeks and stays quiet when it is recent", () => {
    const { rerender } = render(<InvestmentWatchPanel subject={subject} initialData={base} />);
    expect(screen.getByText(/46 days old and may be out of date/)).toBeInTheDocument();
    rerender(<InvestmentWatchPanel subject={subject} initialData={{ ...base, current_verdict: { ...base.current_verdict!, age_days: 3 } }} />);
    expect(screen.queryByText(/days old/)).not.toBeInTheDocument();
  });

  it("explains each watched indicator, tags its scope, and uses direction arrows without implying good or bad", () => {
    render(<InvestmentWatchPanel subject={subject} initialData={base} />);
    expect(screen.getByText("What we are watching")).toBeInTheDocument();
    expect(screen.getByText(/a weaker rupee tends to lift margins/)).toBeInTheDocument();
    expect(screen.getAllByText("Sector", { selector: "span" })).toHaveLength(2);
    expect(screen.getByText("Market-wide", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("▲")).toBeInTheDocument();   // rising
    expect(screen.getByText("▼")).toBeInTheDocument();   // selling
    expect(screen.getByText("▬")).toBeInTheDocument();   // flat: a 0.0% move is not "rising"
  });

  it("labels the next trigger as market-wide or company-specific", () => {
    const { rerender } = render(<InvestmentWatchPanel subject={subject} initialData={base} />);
    expect(screen.getByText(/Next market-wide event/)).toBeInTheDocument();
    expect(screen.getByText(/20 Oct 2026 · in 16 days/)).toBeInTheDocument();
    rerender(<InvestmentWatchPanel subject={subject} initialData={{ ...base, next_trigger: { ...base.next_trigger!, scope: "company", label: "TCS Q2 results" } }} />);
    expect(screen.getByText(/Next event for TCS/)).toBeInTheDocument();
  });
});
