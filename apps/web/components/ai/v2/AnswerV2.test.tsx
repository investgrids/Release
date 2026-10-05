// Step 6: the final AI Search UI is driven by answer_availability (the Step 5 contract). These tests pin what each presentation shows and, as importantly, what it must never show.
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { AnswerV2 } from "./AnswerV2";
import { authorizedVerdict, followUps, resolveKind, temporaryCopy, type V2Result } from "./contract";

const avail = (o: Record<string, unknown> = {}) => ({ state: "available", evidence_count: 3, evidence_retrieval_completed: true, kind: "research", scope: "full", conclusion_authorized: false, basis: "retrieved_evidence", reason: null, ...o });

function research(o: Partial<V2Result> & Record<string, unknown> = {}): V2Result {
  return {
    query: "How is HDFC Bank doing?",
    answer: { summary: "HDFC Bank reported steady loan growth in the latest quarter.", bottom_line: "Loan growth held; margin data is limited.", risks: ["Margin disclosure is limited."] },
    answer_availability: avail() as V2Result["answer_availability"],
    claim_sources: [{ claim: "HDFC Bank disclosed quarterly loan growth of 8%.", sources: ["ev1"], status: "ok" }],
    evidence_index: [{ id: "ev1", kind: "announcement", title: "HDFC Bank quarterly update", source: "NSE" }],
    related_events: [{ id: "1", title: "HDFC Bank quarterly update", source: "NSE", date: "2026-10-01" }],
    companies: [{ symbol: "HDFCBANK", name: "HDFC Bank", reason: "Subject of the question" }],
    evidence_score: { stars: 3, checklist: { company_filings: true, real_time_price_data: false }, source_count: 1 },
    investment_verdict: { rating: "Not Applicable", direction: null },
    follow_up_questions: ["Compare HDFC Bank and ICICI Bank"],
    ...o,
  } as V2Result;
}

const mount = (r: V2Result, extra: Record<string, unknown> = {}) => render(<AnswerV2 result={r} onFollowUp={vi.fn()} {...extra} />);

describe("no fabricated fallbacks", () => {
  const FILES = ["app/ai-search/AISearchClient.tsx", "components/ai/v2/AnswerV2.tsx", "components/ai/v2/contract.ts"];
  const src = FILES.map((f) => readFileSync(path.join(process.cwd(), f), "utf-8")).join("\n");
  it.each([
    ['horizon default "6-12 months"', /6-12 months/],
    ["opportunity_score ?? 50", /opportunity_score\s*\?\?\s*50/],
    ["stars ?? 3", /stars\s*\?\?\s*3/],
    ["confidence-derived risk", /risk_level|confidenceRisk|riskFromConfidence/],
    ["a default of 50", /\?\?\s*50\b/],
  ])("the UI source has no %s", (_n, re) => expect(src).not.toMatch(re));

  it("a research answer shows no horizon, opportunity score, percentage confidence or default stars", () => {
    const { container } = mount(research({ evidence_score: null }));
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/6-12 months|opportunity score|\d+%\s*confidence/i);
    expect(screen.queryByTestId("evidence-strength")).toBeNull();
    expect(text).not.toMatch(/confidence/i);
  });
});

describe("verdict", () => {
  it("is hidden when no conclusion is authorized, even if a rating is present", () => {
    mount(research({ investment_verdict: { rating: "Positive", direction: "up" } }));
    expect(screen.queryByTestId("verdict")).toBeNull();
    expect(screen.queryByText("Not Applicable")).toBeNull();
  });
  it("is hidden when authorized but no real rating is supplied", () => {
    mount(research({ answer_availability: avail({ conclusion_authorized: true }) as V2Result["answer_availability"] }));
    expect(screen.queryByTestId("verdict")).toBeNull();
  });
  it("is shown only when authorized and a real rating exists", () => {
    mount(research({ answer_availability: avail({ conclusion_authorized: true }) as V2Result["answer_availability"], investment_verdict: { rating: "Positive", direction: "up" } }));
    expect(screen.getByTestId("verdict")).toHaveTextContent("Positive");
    expect(authorizedVerdict(research())).toBeNull();
  });
});

describe("evidence strength", () => {
  it("is plain-language evidence strength and is never labelled confidence", () => {
    mount(research());
    const note = screen.getByTestId("evidence-coverage");
    expect(note).toHaveTextContent("Evidence coverage");
    expect(note).toHaveTextContent("1 of 2 kinds of evidence found");
    expect(note).toHaveTextContent(/not how likely the answer is to be right/);
    expect(note.textContent).not.toMatch(/confidence|%|stars/i);
    expect(note).toHaveTextContent("Company filings");
  });
  it("shows source labels beside cited observations, never raw ids", () => {
    mount(research());
    expect(screen.getByTestId("source-chips")).toHaveTextContent("NSE · Exchange filing");
    expect(screen.getByTestId("observations")).not.toHaveTextContent("ev1");
  });
});

describe("partial research", () => {
  it("says it answered in part and names what is missing", () => {
    mount(research({
      answer_availability: avail({ kind: "partial_research", scope: "partial" }) as V2Result["answer_availability"],
      conclusion_scope: { requested: "investment_view", authorized: "business_update", partial: true, missing: ["operating_evidence_HDFCBANK"] },
    }));
    expect(screen.getByTestId("answer-research")).toHaveAttribute("data-kind", "partial_research");
    const note = screen.getByTestId("partial-notice");
    expect(note).toHaveTextContent("Answered in part");
    expect(note).toHaveTextContent("operating results for HDFCBANK");
  });
});

describe("education and product information", () => {
  const edu = (kind: string, extra: Record<string, unknown> = {}): V2Result => ({
    query: "What is a P/E ratio?",
    answer: { summary: "A P/E ratio compares a share price with its earnings per share." },
    answer_availability: avail({ kind: kind === "product_knowledge" ? "product_information" : "education", basis: "education", evidence_count: 0, state: "available" }) as V2Result["answer_availability"],
    education: { kind, topic: "pe_ratio", title: "P/E ratio", source: "marketripple:glossary/pe-ratio", ...extra },
    key_drivers: [{ title: "How to read it", explanation: "A higher P/E means investors pay more per rupee of earnings." }],
    evidence_score: { stars: 3, checklist: {}, source_count: 0 },
    investment_verdict: { rating: "Not Applicable", direction: null },
  } as V2Result);

  it("education carries no verdict, stars, confidence, opportunity, horizon or failure language", () => {
    const { container } = mount(edu("glossary"));
    const t = container.textContent ?? "";
    expect(screen.getByTestId("answer-education")).toBeInTheDocument();
    expect(t).not.toMatch(/confidence|opportunity|horizon|couldn't|unavailable|not enough|evidence strength|No verified/i);
    expect(screen.queryByTestId("verdict")).toBeNull();
    expect(screen.queryByTestId("evidence-strength")).toBeNull();
    expect(screen.getByTestId("explainer-basis")).toHaveTextContent("not live market evidence");
  });
  it("product information distinguishes methodology from live evidence", () => {
    mount(edu("product_knowledge", { topic: "marketripple_score", source: "marketripple:methodology/score" }));
    expect(screen.getByTestId("answer-product")).toBeInTheDocument();
    expect(screen.getByTestId("explainer-basis")).toHaveTextContent(/methodology.*not live market data/s);
  });
  it("offers suggested next questions and an internal link only", () => {
    mount(edu("glossary"));
    expect(screen.getByTestId("follow-ups")).toHaveTextContent("What is TCS's current P/E?");
    for (const a of Array.from(document.querySelectorAll("a"))) expect(a.getAttribute("href")).toMatch(/^\//);
  });
});

describe("unavailable vs temporarily unavailable", () => {
  const unavailable = (): V2Result => ({
    query: "Will XYZ rise?",
    answer: { summary: "There isn't enough recent evidence to answer this reliably." },
    public_title: "Not enough recent evidence",
    answer_availability: avail({ state: "no_verified_evidence", kind: "unavailable", scope: "none", evidence_count: 0, reason: "evidence_insufficient", basis: "none" }) as V2Result["answer_availability"],
  } as V2Result);
  const temporary = (reason: string): V2Result => ({
    query: "How is HDFC Bank doing?",
    answer: { summary: "" },
    answer_availability: avail({ state: "temporarily_unavailable", kind: "temporarily_unavailable", scope: "none", evidence_count: 0, reason, basis: "none", evidence_retrieval_completed: false }) as V2Result["answer_availability"],
  } as V2Result);

  it("unavailable: a simple title and explanation, no research cards, no retry", () => {
    mount(unavailable());
    expect(screen.getByTestId("notice-title")).toHaveTextContent("Not enough recent evidence");
    expect(screen.getByTestId("notice-body")).toHaveTextContent("isn't enough recent evidence");
    for (const id of ["evidence-strength", "involves", "verdict", "observations", "retry"]) expect(screen.queryByTestId(id)).toBeNull();
  });
  it("temporary failure uses different copy from insufficiency and never implies evidence is absent", () => {
    const u = render(<AnswerV2 result={unavailable()} onFollowUp={vi.fn()} />).container.textContent;
    document.body.innerHTML = "";
    const { container } = render(<AnswerV2 result={temporary("retrieval_failed")} onFollowUp={vi.fn()} onRetry={vi.fn()} />);
    const t = container.textContent ?? "";
    expect(t).not.toBe(u);
    expect(t).toMatch(/can't tell whether supporting evidence exists/);
    expect(t).not.toMatch(/no evidence|not enough|insufficient/i);
    expect(screen.getByTestId("retry")).toBeInTheDocument();
  });
  it.each(["retrieval_failed", "retrieval_timeout", "provider_capacity", "generation_failed", "time_budget_exhausted"])("%s has its own wording with no provider or technical names", (reason) => {
    const c = temporaryCopy(reason as never);
    expect(`${c.title} ${c.body}`).not.toMatch(/groq|mistral|openai|gemini|openrouter|cerebras|deepseek|llm|api|500|timeout error|exception/i);
    expect(c.retry).toBe(true);
  });
  it("the five reasons give five different titles", () => {
    const titles = ["retrieval_failed", "retrieval_timeout", "provider_capacity", "generation_failed", "time_budget_exhausted"].map((r) => temporaryCopy(r as never).title);
    expect(new Set(titles).size).toBe(5);
  });
  it("retry calls back", () => {
    const onRetry = vi.fn();
    render(<AnswerV2 result={temporary("provider_capacity")} onFollowUp={vi.fn()} onRetry={onRetry} />);
    fireEvent.click(screen.getByTestId("retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe("rejected generated content (Gate B)", () => {
  it("never renders the generated answer when claims were not authorized", () => {
    const r = {
      query: "Is HDFC Bank a buy?",
      answer: { summary: "We could not verify the claims in the generated analysis for this question." },
      public_title: "This analysis couldn't be verified",
      answer_availability: avail({ state: "no_verified_evidence", kind: "unavailable", scope: "none", reason: "claims_not_authorized", evidence_count: 0 }),
      key_drivers: [{ title: "REJECTED_DRIVER", explanation: "REJECTED generated explanation" }],
      claim_sources: [{ claim: "REJECTED_CLAIM", sources: [], status: "rejected" }],
    } as unknown as V2Result;
    const { container } = mount(r);
    expect(container.textContent).not.toMatch(/REJECTED/);
    expect(screen.getByTestId("notice-title")).toHaveTextContent("couldn't be verified");
  });
});

describe("empty compatibility blocks and null fields", () => {
  it("renders cleanly with every optional field null or empty", () => {
    const r = { query: "q", answer: { summary: "Only a summary." }, answer_availability: avail(), companies: [], sectors: [], related_events: [], news: [], policies: [], key_drivers: [], claim_sources: [], evidence_index: [], evidence_score: null, investment_verdict: null, follow_up_questions: [], follow_up_groups: [] } as unknown as V2Result;
    mount(r);
    expect(screen.getByTestId("lead")).toHaveTextContent("Only a summary.");
    for (const id of ["observations", "meaning", "limits", "involves", "evidence-list", "evidence-strength", "follow-ups", "verdict"]) expect(screen.queryByTestId(id)).toBeNull();
  });
  it("tolerates a missing answer object and missing availability", () => {
    const r = { query: "q" } as unknown as V2Result;
    expect(() => mount(r)).not.toThrow();
  });
  it("hides legacy blocks the contract no longer feeds (scenarios, decision engine, matrix, timeline)", () => {
    const r = research({ scenarios: { bull: { probability: 0, outcome: "LEGACY_SCENARIO" } }, decision_engine_v2: { x: "LEGACY_ENGINE" }, opportunity_risk_matrix: { x: "LEGACY_MATRIX" }, timeline_intelligence: { x: "LEGACY_TIMELINE" }, market_impact_horizons: [{ horizon: "LEGACY_HORIZON" }] });
    const { container } = mount(r);
    expect(container.textContent).not.toMatch(/LEGACY_/);
  });
  it("does not render internal diagnostics if they leak", () => {
    const r = research({ answer_authorization: { x: "INTERNAL_AUTH" }, claim_validation: { x: "INTERNAL_CV" }, timing: { x: "INTERNAL_TIMING" }, evidence_sufficiency: { x: "INTERNAL_SUFF" }, premise_check: { x: "INTERNAL_PREMISE" } });
    expect(mount(r).container.textContent).not.toMatch(/INTERNAL_/);
  });
});

describe("evidence listing", () => {
  it("lists reviewed evidence with type, source and date, and marks what the answer used", () => {
    mount(research());
    const list = screen.getByTestId("evidence-list");
    expect(list).toHaveTextContent("Key evidence and sources (3)");
    const row = list.querySelector("tbody tr")!;
    expect(row).toHaveTextContent("[1]");
    expect(row).toHaveTextContent("01 Oct 2026");
    expect(row).toHaveTextContent("NSE");
    expect(row).toHaveTextContent("HDFC Bank quarterly update");
    expect(row).toHaveTextContent("Used in this answer");
  });
});

describe("follow-ups", () => {
  it("are asked on click and kept near the bottom of the answer", () => {
    const onFollowUp = vi.fn();
    render(<AnswerV2 result={research()} onFollowUp={onFollowUp} />);
    fireEvent.click(screen.getByText("Compare HDFC Bank and ICICI Bank"));
    expect(onFollowUp).toHaveBeenCalledWith("Compare HDFC Bank and ICICI Bank");
    const col = screen.getByTestId("answer-card").parentElement!;
    const order = Array.from(col.children).map((c) => c.getAttribute("data-testid"));
    expect(order.indexOf("answer-card")).toBeLessThan(order.indexOf("follow-ups"));
    expect(order.indexOf("follow-ups")).toBeLessThan(order.indexOf("evidence-list"));
  });
  it("de-duplicates and caps", () => {
    expect(followUps({ ...research(), follow_up_questions: ["a", "a", "b", "c", "d", "e"] }).length).toBe(4);
  });
});

describe("kind resolution", () => {
  it("reads the canonical kind and does not infer from legacy fields when kind exists", () => {
    expect(resolveKind({ ...research(), synthesis_incomplete: true })).toBe("research");
    expect(resolveKind({ ...research(), answer_availability: avail({ kind: "education" }) as never })).toBe("education");
  });
});

describe("comparison layout (validated against the design mockup, truthful fields only)", () => {
  const cmp = (): V2Result => research({
    query: "Compare HDFC Bank and ICICI Bank", specialist: "comparison",
    answer_availability: avail({ kind: "partial_research", scope: "partial" }) as V2Result["answer_availability"],
    conclusion_scope: { requested: "overall_strength", authorized: "valuation_comparison", partial: true, missing: ["operating_evidence_HDFCBANK"], coverage: { HDFCBANK: { valuation: true, operating: false }, ICICIBANK: { valuation: true, operating: false } } },
    companies: [
      { symbol: "HDFCBANK", name: "HDFC Bank", price: "714.50", change: "-0.93%", positive: false },
      { symbol: "ICICIBANK", name: "ICICI Bank", price: "1,420.10", change: "+0.40%", positive: true },
    ],
  } as never);

  it("shows breadcrumb, the question as the title, and a side-by-side table from real fields", () => {
    mount(cmp());
    expect(screen.getByTestId("crumb")).toHaveTextContent("Comparison");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Compare HDFC Bank and ICICI Bank");
    const t = screen.getByTestId("comparison-table");
    expect(t).toHaveTextContent("Latest price");
    expect(t).toHaveTextContent("₹714.50");
    expect(t).toHaveTextContent("Valuation evidence");
    expect(t).toHaveTextContent("Not yet available");
    expect(screen.getByTestId("entity-snapshot")).toHaveTextContent("NSE: ICICIBANK");
  });
  it("never invents market cap, analyst coverage, source-integrity grades or confidence", () => {
    const { container } = mount(cmp());
    expect(container.textContent).not.toMatch(/market cap|analyst coverage|source integrity|evidence confidence|\d+%\s*confidence/i);
  });
  it("has no comparison table for a non-comparison answer, and no entity snapshot when there are no companies", () => {
    mount(research({ companies: [] }));
    expect(screen.queryByTestId("comparison-table")).toBeNull();
    expect(screen.queryByTestId("entity-snapshot")).toBeNull();
  });
});

describe("mockup layout, real fields only", () => {
  const withSnapshot = (): V2Result => research({
    query: "Compare HDFC Bank and ICICI Bank", specialist: "comparison",
    companies: [
      { symbol: "HDFCBANK", name: "HDFC Bank", price: "714.50", change: "-0.93%", positive: false, snapshot: { pe: 15.6, pb: 1.81, week52_low: 681.9, week52_high: 1020.5 } },
      { symbol: "ICICIBANK", name: "ICICI Bank", price: "1,315.40", change: "+0.37%", positive: true, snapshot: { pe: 17.0 } },
    ],
  } as never);

  it("shows the valuation figures the answer was given, in the table and the entity card, and only where present", () => {
    mount(withSnapshot());
    const t = screen.getByTestId("comparison-table");
    expect(t).toHaveTextContent("P/E");
    expect(t).toHaveTextContent("15.6");
    expect(t).toHaveTextContent("₹681.9 – ₹1,020.5");
    expect(t).toHaveTextContent("17.0");                      // one decimal for P/E, never "17"
    expect(t).toHaveTextContent("1.81");
    expect(t).not.toHaveTextContent("P/B2");                 // ICICI has no P/B: a dash, never a placeholder number
    const card = screen.getByTestId("entity-snapshot");
    expect(card).toHaveTextContent("52-week range");
    expect(card).toHaveTextContent("NSE: ICICIBANK");
  });
  it("has the page head: breadcrumb, title, answered-at stamp, and New search that calls back", () => {
    const onNew = vi.fn();
    render(<AnswerV2 result={withSnapshot()} onFollowUp={vi.fn()} onNewSearch={onNew} />);
    expect(screen.getByTestId("crumb")).toHaveTextContent("Comparison");
    expect(screen.getByTestId("answered-at")).toHaveTextContent(/Answered .* IST/);
    fireEvent.click(screen.getByTestId("new-search"));
    expect(onNew).toHaveBeenCalledTimes(1);
  });
  it("puts chips on the answer card: kind, sources reviewed, not investment advice", () => {
    mount(withSnapshot());
    const card = screen.getByTestId("answer-card");
    expect(card).toHaveTextContent("Evidence-based comparison");
    expect(card).toHaveTextContent("3 sources reviewed");
    expect(card).toHaveTextContent("Not investment advice");
  });
  it("lists sources by kind without grading them, and offers the methodology page", () => {
    mount(research());
    const src = screen.getByTestId("sources-summary");
    expect(src).toHaveTextContent(/market event/i);
    expect(src.textContent).not.toMatch(/newss|events?s/i);
    expect(src.textContent).not.toMatch(/(High|Medium|Low)/);
    expect(screen.getByTestId("methodology-link")).toHaveAttribute("href", "/ai-methodology");
  });
  it("never renders the mockup items the contract cannot support", () => {
    const { container } = mount(withSnapshot());
    expect(container.textContent).not.toMatch(/Evidence Confidence|Source Integrity|Market Cap|Analyst coverage|\d+%\s*confidence/i);
  });
  it("numbers the next steps and caps the evidence table with a toggle", () => {
    const many = research({ related_events: Array.from({ length: 9 }, (_, i) => ({ id: String(i), title: `Event ${i}`, source: "NSE", date: "2026-10-01" })) } as never);
    mount(many);
    expect(screen.getByTestId("follow-ups").querySelectorAll("ol > li").length).toBeGreaterThan(0);
    const list = screen.getByTestId("evidence-list");
    expect(list.querySelectorAll("tbody tr").length).toBe(6);
    fireEvent.click(screen.getByTestId("evidence-toggle"));
    expect(list.querySelectorAll("tbody tr").length).toBe(9);
  });
});

describe("comparison table rows from the mockup, real data only", () => {
  const cmp = (): V2Result => research({
    query: "Compare HDFC Bank and ICICI Bank", specialist: "comparison",
    companies: [
      { symbol: "HDFCBANK", name: "HDFC Bank", price: "714.50", change: "-0.93%", positive: false, chart: [700, 705, 710, 720, 735] },
      { symbol: "ICICIBANK", name: "ICICI Bank", price: "1,315.40", change: "+0.37%", positive: true, chart: [] },
    ],
    evidence_index: [
      { id: "N1", kind: "news", title: "HDFC Bank shares rise 2% after appointing a new CEO", source: "Economic Times" },
      { id: "C1", kind: "context", title: "Live market data", source: "MarketRipple data" },
    ],
    news: [{ id: "n1", headline: "HDFC Bank shares rise 2% after appointing a new CEO", source: "Economic Times", published_at: "2026-10-04" }],
    related_events: [],
    claim_sources: [
      { claim: "HDFC Bank shares rose 2% after it appointed a new CEO.", sources: ["N1"], company: "HDFCBANK", status: "ok" },
      { claim: "HDFC Bank is at P/E 15.6 versus ICICI Bank at P/E 17.0.", sources: ["C1"], company: "HDFCBANK", status: "ok" },
    ],
  } as never);

  it("shows each company's own sourced development with the [n] of its row in the evidence table", () => {
    mount(cmp());
    const t = screen.getByTestId("comparison-table");
    expect(t).toHaveTextContent("Latest development");
    expect(t).toHaveTextContent("HDFC Bank shares rose 2% after it appointed a new CEO.");
    expect(t).toHaveTextContent("[1]");
    expect(screen.getByTestId("evidence-list").querySelector("tbody tr")).toHaveTextContent("[1]");
  });
  it("never files a claim that names the other bank, or one resting only on live market data, under a company", () => {
    mount(cmp());
    const t = screen.getByTestId("comparison-table");
    expect(t).not.toHaveTextContent("P/E 15.6 versus ICICI");
  });
  it("computes the 5-day reaction from the closes it has and shows a dash where it has none", () => {
    mount(cmp());
    const row = Array.from(screen.getByTestId("comparison-table").querySelectorAll("tbody tr")).find((r) => r.textContent?.startsWith("Price reaction"))!;
    expect(row).toHaveTextContent("+5.0%");
    expect(row).toHaveTextContent("5-day");          // 735 / 700
    expect(row.querySelectorAll("td")[1]).toHaveTextContent("—");
  });
  it("uses initials tiles, not logos it does not have", () => {
    const { container } = mount(cmp());
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByTestId("comparison-table")).toHaveTextContent("HB");
  });
});

describe("visual elements draw only numbers the answer carries", () => {
  const rich = (): V2Result => research({
    query: "What is happening with Wipro?", specialist: "company",
    companies: [{ symbol: "WIPRO", name: "Wipro", price: "248.30", change: "+0.20%", positive: true, chart: [244, 245.1, 246.9, 247.2, 248.3], snapshot: { pe: 21.4, pb: 3.6, week52_low: 205.1, week52_high: 289.9 } }],
  } as never);

  it("draws a sparkline from the closes and a range bar with the price marker", () => {
    mount(rich());
    const card = screen.getByTestId("entity-snapshot");
    expect(card.querySelector('[data-testid="sparkline"]')).not.toBeNull();
    expect(card.querySelector('[data-testid="range-bar"]')).not.toBeNull();
    expect(card).toHaveTextContent("₹205.1");
    expect(card).toHaveTextContent("₹289.9");
    expect(card).toHaveTextContent("+0.20%");
  });
  it("draws no sparkline without two closes and no range bar without a 52-week range", () => {
    mount(research({ companies: [{ symbol: "WIPRO", name: "Wipro", price: "248.30", change: "+0.20%", positive: true, chart: [248.3] }] } as never));
    const card = screen.getByTestId("entity-snapshot");
    expect(card.querySelector('[data-testid="sparkline"]')).toBeNull();
    expect(card.querySelector('[data-testid="range-bar"]')).toBeNull();
  });
  it("colours evidence by kind and keeps the type as text, not colour alone", () => {
    mount(research());
    const badge = screen.getByTestId("evidence-list").querySelector("tbody tr span.rounded-md");
    expect(badge?.textContent).toMatch(/Market event|News|Exchange filing/);
  });
  it("keeps the sign on a change pill", () => {
    mount(rich());
    expect(screen.getByTestId("entity-snapshot").textContent).toContain("+0.20%");
  });
});

describe("market cap, sector and relative P/E and P/B colour", () => {
  const pair = (): V2Result => research({
    query: "Compare HDFC Bank and ICICI Bank", specialist: "comparison",
    companies: [
      { symbol: "HDFCBANK", name: "HDFC Bank", price: "714.50", change: "-0.93%", positive: false, snapshot: { pe: 15.6, pb: 2.48, market_cap_cr: 1380000.5, sector: "Financial Services" } },
      { symbol: "ICICIBANK", name: "ICICI Bank", price: "1,315.40", change: "+0.37%", positive: true, snapshot: { pe: 17.0, pb: 2.48, market_cap_cr: 940000, sector: "Financial Services" } },
    ],
  } as never);

  it("shows sector and market cap in the entity card and the table, in lakh crore above one lakh crore", () => {
    mount(pair());
    const card = screen.getByTestId("entity-snapshot");
    expect(card.querySelectorAll('[data-testid="sector-chip"]').length).toBe(2);
    expect(card).toHaveTextContent("₹13.80 lakh Cr");
    expect(card).toHaveTextContent("₹9.40 lakh Cr");
    const t = screen.getByTestId("comparison-table");
    expect(t).toHaveTextContent("Sector");
    expect(t).toHaveTextContent("Market cap");
  });
  it("colours each multiple against the other company, and writes the word as well as the colour", () => {
    mount(pair());
    const pes = Array.from(screen.getByTestId("entity-snapshot").querySelectorAll("[data-rel]")).map((e) => [e.textContent, e.getAttribute("data-rel")]);
    expect(pes[0]).toEqual([expect.stringContaining("P/E 15.6"), "lower"]);
    expect(pes[0][0]).toContain("lower");
    expect(pes[2]).toEqual([expect.stringContaining("P/E 17.0"), "higher"]);
    expect(pes[2][0]).toContain("higher");
  });
  it("says nothing relative when the values are equal (P/B 2.48 on both), and explains the colours", () => {
    mount(pair());
    const pbs = Array.from(screen.getByTestId("entity-snapshot").querySelectorAll("[data-rel]")).filter((e) => e.textContent?.includes("P/B"));
    expect(pbs.length).toBe(2);
    pbs.forEach((e) => expect(e.getAttribute("data-rel")).toBe("none"));
    expect(screen.getByTestId("multiple-legend")).toHaveTextContent(/not automatically a better company/);
  });
  it("a single company gets neutral multiples and no legend: there is nothing to compare against", () => {
    mount(research({ companies: [{ symbol: "WIPRO", name: "Wipro", price: "248.30", change: "+0.20%", positive: true, snapshot: { pe: 21.4, pb: 3.6, sector: "Technology" } }] } as never));
    const card = screen.getByTestId("entity-snapshot");
    card.querySelectorAll("[data-rel]").forEach((e) => expect(e.getAttribute("data-rel")).toBe("none"));
    expect(screen.queryByTestId("multiple-legend")).toBeNull();
    expect(card).toHaveTextContent("Technology");
    expect(card.textContent).not.toMatch(/·\s*(lower|higher)/);
  });
  it("shows no market cap or sector when they were not fetched", () => {
    mount(research({ companies: [{ symbol: "WIPRO", name: "Wipro", price: "248.30", snapshot: { pe: 21.4 } }] } as never));
    expect(screen.queryByTestId("market-cap")).toBeNull();
    expect(screen.queryByTestId("sector-chip")).toBeNull();
  });
});
