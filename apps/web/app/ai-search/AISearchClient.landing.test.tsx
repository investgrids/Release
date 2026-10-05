// Step 6: the landing's example questions follow the live market (GET /api/ai/search/suggestions), fall back to the static examples, and a search renders through AnswerV2.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(), useRouter: () => ({ push: vi.fn() }) }));

import AISearchClient from "./AISearchClient";

const live = { as_of: "2026-10-05T04:00:00Z", live_count: 1, items: [
  { query: "What is driving the Banking sector today?", kind: "sector", note: "Banking -1.2% today" },
  { query: "Compare HDFC Bank and ICICI Bank", kind: "evergreen", note: null },
] };

describe("landing", () => {
  beforeEach(() => { vi.restoreAllMocks(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("shows today's live questions with the live fact each came from", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => live })));
    render(<AISearchClient />);
    expect(await screen.findByText("What is driving the Banking sector today?")).toBeInTheDocument();
    expect(screen.getByText("Banking -1.2% today")).toBeInTheDocument();
    expect(screen.getByText(/Today in the market/)).toBeInTheDocument();
  });

  it("falls back to the static examples when the suggestions cannot be fetched", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    render(<AISearchClient />);
    await waitFor(() => expect(screen.getByTestId("suggestions")).toBeInTheDocument());
    expect(screen.getByText(/Try asking/)).toBeInTheDocument();
    expect(screen.getByTestId("suggestions").querySelectorAll("button").length).toBeGreaterThan(0);
  });

  it("a search renders the answer through the contract (research view, no confidence)", async () => {
    const result = {
      query: "q", answer: { summary: "A grounded answer." },
      answer_availability: { state: "available", kind: "research", evidence_count: 0, conclusion_authorized: false },
      investment_verdict: { rating: "Not Applicable", direction: null },
    };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (String(url).includes("/suggestions")) return { ok: true, json: async () => live };
      return { ok: true, json: async () => ({ cached: false, result }) };
    }));
    render(<AISearchClient />);
    fireEvent.change(screen.getByLabelText("Ask a market question"), { target: { value: "q" } });
    fireEvent.click(screen.getByText("Ask"));
    expect(await screen.findByTestId("answer-research")).toHaveTextContent("A grounded answer.");
    expect(document.body.textContent).not.toMatch(/confidence|6-12 months|Not Applicable/i);
  });

  it("shows the temporary-failure wording, not the insufficiency wording, on a retrieval failure", async () => {
    const result = { query: "q", answer: { summary: "" }, answer_availability: { state: "temporarily_unavailable", kind: "temporarily_unavailable", reason: "retrieval_failed", evidence_count: 0 } };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => String(url).includes("/suggestions") ? { ok: true, json: async () => live } : { ok: true, json: async () => ({ cached: false, result }) }));
    render(<AISearchClient />);
    fireEvent.change(screen.getByLabelText("Ask a market question"), { target: { value: "q" } });
    fireEvent.click(screen.getByText("Ask"));
    expect(await screen.findByTestId("answer-temporary")).toHaveTextContent(/can't tell whether supporting evidence exists/);
    expect(screen.getByTestId("retry")).toBeInTheDocument();
  });
});
