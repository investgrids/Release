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
    const note = screen.getByTestId("evidence-strength");
    expect(note).toHaveTextContent(/Evidence strength/);
    expect(note).toHaveTextContent(/not how likely the answer is to be right/);
    expect(note.textContent).not.toMatch(/confidence/i);
    expect(note).toHaveTextContent("live prices");
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
    expect(list).toHaveTextContent("Evidence reviewed (3)");
    expect(list).toHaveTextContent("Market event · NSE · 2026-10-01");
    expect(list).toHaveTextContent("Used in this answer");
  });
});

describe("follow-ups", () => {
  it("are asked on click and kept near the bottom of the answer", () => {
    const onFollowUp = vi.fn();
    render(<AnswerV2 result={research()} onFollowUp={onFollowUp} />);
    fireEvent.click(screen.getByText("Compare HDFC Bank and ICICI Bank"));
    expect(onFollowUp).toHaveBeenCalledWith("Compare HDFC Bank and ICICI Bank");
    const article = screen.getByTestId("answer-research").querySelector("article")!;
    const order = Array.from(article.children).map((c) => c.getAttribute("data-testid"));
    expect(order.indexOf("follow-ups")).toBeGreaterThan(order.indexOf("limits") >= 0 ? order.indexOf("limits") : 0);
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
  it("is absent for a non-comparison answer and for a single company", () => {
    mount(research());
    expect(screen.queryByTestId("comparison-table")).toBeNull();
    expect(screen.queryByTestId("entity-snapshot")).toBeNull();
  });
});
