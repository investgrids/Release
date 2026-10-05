// AI Search V2 UI contract layer (Step 6). The page is driven by answer_availability (Step 5's final answer contract); nothing here infers state from legacy compatibility fields when the canonical field is present.

export type AnswerKind = "research" | "partial_research" | "education" | "product_information" | "unavailable" | "temporarily_unavailable";
export type AnswerReason =
  | "evidence_insufficient" | "retrieval_failed" | "retrieval_timeout" | "provider_capacity" | "generation_failed" | "time_budget_exhausted"
  | "claims_not_authorized" | "unsupported_subject" | "education_not_covered" | "limited_evidence";

export interface V2Availability {
  state: "available" | "limited_evidence" | "no_verified_evidence" | "temporarily_unavailable";
  evidence_retrieval_completed?: boolean;
  evidence_count: number;
  reason?: AnswerReason | null;
  basis?: "retrieved_evidence" | "market_data" | "education" | "none";
  kind?: AnswerKind;
  scope?: "full" | "partial" | "none";
  conclusion_authorized?: boolean;
}

export interface V2Claim { claim: string; sources: string[]; scope?: string | null; company?: string | null; status?: string }
export interface V2IndexEntry { id: string; kind: "event" | "news" | "policy" | "announcement" | "context" | string; title: string; date?: string | null; source?: string | null }
export interface V2Event { id: string; title: string; date?: string; source?: string; category?: string }
export interface V2News { id: string; headline: string; source?: string; published_at?: string }
export interface V2Policy { id: string | number; title: string; ministry?: string; status?: string }
export interface V2Company { symbol: string; name: string; reason?: string; price?: string | null; change?: string | null; positive?: boolean | null }
export interface V2Sector { name: string; explanation?: string }

export interface V2Result {
  query: string;
  response_id?: string | null;
  schema_version?: string | null;
  specialist?: string | null;
  degraded_reason?: string | null;
  synthesis_incomplete?: boolean;
  public_title?: string | null;
  answer_availability?: V2Availability | null;
  answer: {
    summary?: string; bottom_line?: string; what_happened?: string; why_it_happened?: string; immediate_impact?: string; medium_term?: string; long_term?: string; what_priced_in?: string;
    risks?: string[]; opportunities?: string[];
  };
  key_drivers?: { title: string; explanation: string }[];
  companies?: V2Company[];
  sectors?: V2Sector[];
  related_events?: V2Event[];
  news?: V2News[];
  policies?: V2Policy[];
  claim_sources?: V2Claim[];
  evidence_index?: V2IndexEntry[];
  evidence_score?: { stars?: number | null; checklist?: Record<string, boolean>; source_count?: number } | null;
  conclusion_scope?: { requested?: string; authorized?: string; partial?: boolean; missing?: string[]; reason?: string | null } | null;
  investment_verdict?: { rating?: string | null; direction?: string | null } | null;
  follow_up_questions?: string[];
  follow_up_groups?: { items?: { query?: string; text?: string }[] }[];
  company_suggestions?: { symbol: string; name: string }[];
  education?: { kind?: string; topic?: string; title?: string; grounding?: string; source?: string; beyond_published_detail?: boolean; advice_requested?: boolean } | null;
}

const KINDS: AnswerKind[] = ["research", "partial_research", "education", "product_information", "unavailable", "temporarily_unavailable"];

/** The canonical `kind`. Only a response that predates Step 5 (no kind at all, e.g. an old cached one) is derived, and then conservatively. */
export function resolveKind(r: V2Result): AnswerKind {
  const k = r.answer_availability?.kind;
  if (k && KINDS.includes(k)) return k;
  if (r.education) return r.education.kind === "product_knowledge" ? "product_information" : "education";
  const s = r.answer_availability?.state;
  if (s === "temporarily_unavailable") return "temporarily_unavailable";
  if (s === "no_verified_evidence" || s === "limited_evidence") return "unavailable";
  if (r.synthesis_incomplete) return "unavailable";
  return r.conclusion_scope?.partial ? "partial_research" : "research";
}

/** A verdict is shown only when the backend says a conclusion is authorized AND supplies a real rating. Anything else is absence, never a "Not Applicable" panel. */
export function authorizedVerdict(r: V2Result): { rating: string; direction: string | null } | null {
  if (r.answer_availability?.conclusion_authorized !== true) return null;
  const rating = (r.investment_verdict?.rating ?? "").trim();
  if (!rating || rating === "Not Applicable") return null;
  return { rating, direction: r.investment_verdict?.direction ?? null };
}

export const humanize = (s: string) => s.replace(/_/g, " ").replace(/\s+/g, " ").trim();

const TOKEN_TITLE = (t: string) => t.replace(/\b[A-Z0-9&]{2,}\b/g, (m) => m); // keep tickers as written

/** "operating_evidence_HDFCBANK" -> "operating results for HDFCBANK"; anything unknown is humanized, never dropped silently. */
export function missingLabel(code: string): string {
  const m = /^operating_evidence_(.+)$/.exec(code);
  if (m) return `operating results for ${m[1]}`;
  const v = /^valuation_evidence_(.+)$/.exec(code);
  if (v) return `valuation data for ${v[1]}`;
  return TOKEN_TITLE(humanize(code));
}

export function partialNotice(r: V2Result): { title: string; body: string; missing: string[] } {
  const cs = r.conclusion_scope ?? {};
  const authorized = cs.authorized && cs.authorized !== "not_applicable" ? humanize(cs.authorized) : null;
  const requested = cs.requested && cs.requested !== "not_applicable" ? humanize(cs.requested) : null;
  const body = authorized && requested
    ? `MarketRipple could answer the ${authorized} part of your question, but the evidence doesn't yet support a full answer on ${requested}.`
    : "MarketRipple could answer part of your question. The evidence available doesn't cover all of it.";
  return { title: "Answered in part", body, missing: (cs.missing ?? []).map(missingLabel) };
}

export interface NoticeCopy { title: string; body: string; retry: boolean }

/** Temporary failures: distinct copy per reason, no provider or technical names, and never a claim that evidence does not exist. */
export function temporaryCopy(reason: AnswerReason | null | undefined): NoticeCopy {
  switch (reason) {
    case "retrieval_failed":
      return { title: "The evidence search didn't finish", body: "MarketRipple couldn't finish searching its evidence for this question just now, so it can't tell whether supporting evidence exists. Nothing was concluded.", retry: true };
    case "retrieval_timeout":
      return { title: "The search took too long", body: "Gathering evidence for this question took longer than expected, so MarketRipple stopped before reaching an answer. That doesn't mean there is no evidence.", retry: true };
    case "provider_capacity":
      return { title: "Analysis is busy right now", body: "MarketRipple couldn't complete this analysis right now because the analysis service is at capacity. Try again in a minute.", retry: true };
    case "generation_failed":
      return { title: "The analysis didn't complete", body: "MarketRipple couldn't turn the evidence into an answer this time. Try again, or rephrase the question.", retry: true };
    case "time_budget_exhausted":
      return { title: "This took longer than expected", body: "MarketRipple ran out of time before finishing this analysis. Try again in a moment.", retry: true };
    default:
      return { title: "MarketRipple couldn't complete this analysis right now", body: "Please try again in a moment.", retry: true };
  }
}

/** Unavailable (not a temporary failure): the backend's own safe public wording is used as is; only the titles and the next-step hint have a frontend fallback. */
export function unavailableCopy(r: V2Result): NoticeCopy {
  const reason = r.answer_availability?.reason ?? null;
  const fallbackTitle: Record<string, string> = {
    evidence_insufficient: "Not enough recent evidence",
    claims_not_authorized: "This analysis couldn't be verified",
    unsupported_subject: "We couldn't match that question",
    education_not_covered: "No reviewed explanation yet",
    limited_evidence: "Only related evidence was found",
  };
  return { title: r.public_title || (reason ? fallbackTitle[reason] : undefined) || "No answer available", body: r.answer?.summary ?? "", retry: false };
}

export const EVIDENCE_TYPE_LABEL: Record<string, string> = { event: "Market event", news: "News", policy: "Policy", announcement: "Exchange filing", context: "Live market data" };

export const CHECKLIST_LABEL: Record<string, string> = {
  real_time_price_data: "live prices", live_market_events: "live market events", company_filings: "company filings", government_data: "government data", historical_precedent: "historical precedent",
};

/** Evidence strength, in plain language. It describes which kinds of evidence were found; it is not a probability and never called confidence. */
export function evidenceStrength(r: V2Result): { stars: number; found: string[]; missing: string[] } | null {
  const es = r.evidence_score;
  if (!es || typeof es.stars !== "number") return null;
  const entries = Object.entries(es.checklist ?? {});
  return {
    stars: Math.max(0, Math.min(5, Math.round(es.stars))),
    found: entries.filter(([, v]) => v).map(([k]) => CHECKLIST_LABEL[k] ?? humanize(k)),
    missing: entries.filter(([, v]) => !v).map(([k]) => CHECKLIST_LABEL[k] ?? humanize(k)),
  };
}

export function followUps(r: V2Result, max = 4): string[] {
  const direct = (r.follow_up_questions ?? []).filter((q) => typeof q === "string" && q.trim());
  const grouped = (r.follow_up_groups ?? []).flatMap((g) => (g.items ?? []).map((i) => i.query ?? i.text ?? "")).filter(Boolean);
  return Array.from(new Set(direct.length ? direct : grouped)).slice(0, max);
}

/** Internal link for a curated source ("marketripple:glossary/pe-ratio"). Plain internal paths only; nothing off-site. */
export function internalSourceLink(source?: string | null): { href: string; label: string } | null {
  const first = (source ?? "").split(",")[0].trim();
  const g = /^marketripple:glossary\/(.+)$/.exec(first);
  if (g) return { href: `/learn/glossary/${g[1]}`, label: "Read the full glossary entry" };
  const m = /^marketripple:methodology\/(.+)$/.exec(first);
  if (m) return { href: `/methodology/${m[1]}`, label: "Read the full methodology" };
  return null;
}

export const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9%.]+/g, " ").trim();
