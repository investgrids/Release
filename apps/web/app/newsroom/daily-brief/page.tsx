import type { Metadata } from "next";
import Link from "next/link";
import {
  TrendingUp, TrendingDown, Minus, ShieldAlert, Eye, Sparkles,
  ChevronRight, BadgeCheck, HelpCircle,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText, safeJsonLd } from "@/lib/text";
import { RefreshButton } from "./RefreshButton";
import {
  ImplicationsSection, MarketDriversSection, ScenariosSection, TakeawaySection,
  type Implications, type MarketDrivers, type Scenarios, type Takeaway,
} from "./sections";

// ── Types (subset of the real /api/daily-brief/intelligence response) ───────

interface IndexQuote { name: string; value: string; change: string; pct: number; positive: boolean }
interface Verdict {
  // realized = what the market did in the reference session; forecast = opening outlook (pre-open only)
  kind: "realized" | "forecast" | "unavailable";
  headline: string;
  direction: string | null; confidence: number | null;
  primary_drivers: string[]; risks: string[];
  reasoning: string | null; ai_generated: boolean; unavailable?: boolean;
  session_state: string; session_date: string | null; target_date: string | null;
  direction_check?: { status: string; withheld: boolean; message: string | null } | null;
  forecast?: { target_date: string; generated_at: string; method: string } | null;
}
interface SessionInfo {
  state: "pre_open" | "open" | "after_close" | "weekend" | "holiday";
  label: string; subtitle: string; reference_label: string;
}
interface Snapshot {
  nifty: IndexQuote | null; banknifty: IndexQuote | null; sensex: IndexQuote | null; vix: IndexQuote | null;
  breadth: { advances: number; declines: number; unchanged: number; note?: string } | null;
  market_status: { is_open: boolean; status: string; time_ist: string; date: string } | null;
  sectors: { id: string; name: string; value: string; positive: boolean }[];
  unavailable?: boolean;
}
interface EventItem {
  id: string; headline: string; one_liner: string | null; priority_tier: string; priority_score: number;
  sectors: string[]; tickers: string[]; sentiment: string | null; source: string | null;
}
interface EventsBlock { tiers: { critical: number; high: number; medium: number; other: number }; total: number; top: EventItem[] }
interface WhyMattersItem { event: string; consequence: string; affected: string[]; companies_named: string[]; affected_label: string }
interface StockToWatch { symbol: string; reason: string; priority_tier: string; sentiment: string | null; basis?: string }
interface HistoricalContext { available: boolean; message?: string; count?: number; success_rate_pct?: number | null; queried_sectors?: string[] }
interface Question { question: string; answer: string; links: { label: string; href: string }[] }
interface Evidence { claim: string; source: string; timestamp: string | null; confidence: number | null }
interface SignalDetail { name: string; explanation: string; source: string | null }
interface WatchNextItem { date: string | null; category: string | null; title: string | null; description: string | null }

interface DailyBriefData {
  session: SessionInfo;
  market_verdict: Verdict;
  market_snapshot: Snapshot;
  events: EventsBlock;
  why_today_matters: WhyMattersItem[];
  stocks_to_watch: StockToWatch[];
  sector_intelligence: { id: string; name: string; value: string; positive: boolean }[];
  historical_context: HistoricalContext;
  summary: string;
  // The four sections added in Part A. Optional: an older backend response has none of them.
  market_drivers?: MarketDrivers;
  investor_implications?: Implications;
  scenarios?: Scenarios;
  takeaway?: Takeaway;
  catalysts?: string[];
  risks?: string[];
  catalyst_details: SignalDetail[];
  risk_details: SignalDetail[];
  what_to_watch_next: WatchNextItem[];
  questions: Question[];
  evidence: Evidence[];
  generated_at: string;
}

// Tolerates an older backend response (rollout order, or a page cached before the backend changed): missing blocks get safe
// defaults and a verdict without `kind` is treated as the forecast it was.
function normalise(raw: Partial<DailyBriefData>): DailyBriefData {
  const d = raw as DailyBriefData;
  return {
    ...d,
    session: d.session ?? { state: "after_close", label: "Market Brief", subtitle: "", reference_label: "" },
    summary: d.summary ?? "",
    catalyst_details: d.catalyst_details ?? (d.catalysts ?? []).map(name => ({ name, explanation: name, source: null })),
    risk_details: d.risk_details ?? (d.risks ?? []).map(name => ({ name, explanation: name, source: null })),
    why_today_matters: (d.why_today_matters ?? []).map(w => ({ ...w, companies_named: w.companies_named ?? [], affected_label: w.affected_label ?? "Affected" })),
    market_verdict: { ...d.market_verdict, kind: d.market_verdict?.kind ?? "forecast", headline: d.market_verdict?.headline ?? "" },
  };
}

async function getData(): Promise<DailyBriefData | null> {
  try {
    const res = await fetch(`${API}/api/daily-brief/intelligence`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return normalise(await res.json());
  } catch {
    return null;
  }
}

function fmtDay(isoDate: string): string {
  try {
    return new Date(`${isoDate}T00:00:00+05:30`).toLocaleDateString("en-IN", {
      timeZone: "Asia/Kolkata", weekday: "short", day: "numeric", month: "short", year: "numeric",
    });
  } catch {
    return isoDate;
  }
}

function fmtIST(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata", day: "numeric", month: "short",
      hour: "numeric", minute: "2-digit", hour12: true,
    }) + " IST";
  } catch {
    return "";
  }
}

const DIRECTION_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  Positive: { label: "Bullish", color: "text-emerald-600 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20", icon: <TrendingUp className="h-4 w-4" /> },
  Negative: { label: "Bearish", color: "text-rose-600 dark:text-rose-300 bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20", icon: <TrendingDown className="h-4 w-4" /> },
  Neutral:  { label: "Neutral", color: "text-amber-600 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20", icon: <Minus className="h-4 w-4" /> },
};

export async function generateMetadata(): Promise<Metadata> {
  const data = await getData();
  const dateStr = data?.market_snapshot.market_status?.date;
  const verdictNow = data?.market_verdict;
  const title = dateStr
    ? `Indian Stock Market Today (${dateStr}): Nifty, Bank Nifty & Market Outlook | MarketRipple`
    : "Indian Stock Market Today: Nifty, Bank Nifty & Market Outlook | MarketRipple";
  const description = verdictNow?.kind === "realized" && verdictNow.reasoning
    ? `${verdictNow.reasoning} Sector performance, key events and risks for Indian investors.`
    : verdictNow?.kind === "forecast" && verdictNow.direction
      ? `Indian stock market opening outlook: Nifty 50 and Bank Nifty levels, stocks to watch, sector performance, key events and risks for Indian investors.`
      : "Indian stock market today: Nifty 50, Bank Nifty, stocks to watch, sector performance, key events and risks for Indian investors.";

  return {
    title,
    description,
    alternates: { canonical: "/newsroom/daily-brief" },
    openGraph: { type: "website", title, description, siteName: "MarketRipple" },
    twitter: { card: "summary_large_image", title, description },
  };
}

// ── Page ──────────────────────────────────────────────────────────────────

export default async function DailyBriefPage() {
  const data = await getData();

  if (!data) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
        <p className="rounded-2xl border border-surface-border/7 bg-text-primary/[0.03] p-8 text-center text-[13px] text-text-muted">
          Market intelligence is temporarily unavailable — check back shortly.
        </p>
      </div>
    );
  }

  const { session, market_verdict: verdict, market_snapshot: snap, events, historical_context: historical, questions, evidence } = data;

  const isForecast = verdict.kind === "forecast";
  const baseMeta = DIRECTION_META[verdict.direction ?? ""] ?? DIRECTION_META.Neutral;
  // A realized session is named by what happened (Lower close), a forecast keeps the Bullish/Bearish wording.
  const dirMeta = isForecast && verdict.direction ? baseMeta : { ...baseMeta, label: verdict.headline || baseMeta.label };
  const targetLabel = verdict.target_date ? fmtDay(verdict.target_date) : null;
  // One source for the visible answer and the structured data: the backend's summary and questions are used verbatim.
  const thirtySecondAnswer = data.summary;
  const hasNewSections = !!(data.market_drivers && data.investor_implications && data.scenarios && data.takeaway);

  const faqJsonLd = questions.length > 0 ? {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: questions.map(q => ({
      "@type": "Question",
      name: q.question,
      acceptedAnswer: { "@type": "Answer", text: q.answer },
    })),
  } : null;

  const webPageJsonLd = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: "Indian Stock Market Today — Market Outlook, Nifty, Bank Nifty & Stocks",
    description: thirtySecondAnswer || "Real-time Indian stock market intelligence.",
    url: "https://www.marketripple.in/newsroom/daily-brief",
    dateModified: data.generated_at,
    about: [
      { "@type": "Thing", name: "Nifty 50" }, { "@type": "Thing", name: "Bank Nifty" },
      { "@type": "Thing", name: "Indian Stock Market" },
    ],
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(webPageJsonLd) }} />
      {faqJsonLd && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(faqJsonLd) }} />}

      {/* Header */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[26px] font-black leading-tight text-text-primary md:text-[32px]">
            Indian Stock Market Today
          </h1>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-text-muted">
            <span className="rounded-md border border-surface-border/15 bg-text-primary/[0.04] px-2 py-0.5 text-[11.5px] font-semibold text-text-secondary">{session.label}</span>
            <span>{session.subtitle}</span>
            <span aria-hidden="true">·</span>
            <span>Updated {fmtIST(data.generated_at)}</span>
          </p>
        </div>
        <RefreshButton />
      </div>

      {/* ── Above the fold: the result and the short answer ─────────────────── */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <div className={`rounded-2xl border p-5 ${dirMeta.color}`}>
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] font-bold uppercase tracking-wide opacity-80">
                {isForecast ? `Opening outlook${targetLabel ? ` for ${targetLabel}` : ""}` : `Session result · ${session.reference_label}`}
              </p>
              {verdict.unavailable && <span className="text-[10px] opacity-70">Data unavailable</span>}
              {isForecast && !verdict.unavailable && (
                <span className="rounded-full border border-current/30 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wide opacity-80">Forecast</span>
              )}
            </div>
            <div className="mt-2 flex items-center gap-2">
              {dirMeta.icon}
              <p className="text-[22px] font-black">{dirMeta.label}</p>
              {/* CD3-C: this verdict is built the same way as opening_prediction_service.py's opening prediction (same
                  ai_generated flag + fallback wording) -- confidence blends a bounded LLM self-report with deterministic
                  signal adjustments, a HYBRID_RUBRIC. */}
              {verdict.confidence != null && (
                <span className="ml-auto text-[13px] font-bold tabular-nums" title="A blend of signal-based analysis and the model's own self-assessed certainty -- not a fully computed score">{verdict.confidence}% confidence</span>
              )}
            </div>
            {verdict.reasoning && <p className="mt-2 text-[12.5px] leading-relaxed opacity-90">{verdict.reasoning}</p>}
            {isForecast && verdict.direction_check?.message && verdict.direction_check.status !== "aligned" && !verdict.direction_check.withheld && (
              <p className="mt-2 text-[11.5px] leading-snug opacity-80">{verdict.direction_check.message}</p>
            )}
            {isForecast && verdict.forecast && (
              <p className="mt-2 text-[10.5px] opacity-60">
                Forecast for {fmtDay(verdict.forecast.target_date)} · generated {fmtIST(verdict.forecast.generated_at)} ·{" "}
                {verdict.forecast.method === "deterministic_signals" ? "signal formula" : "AI checked against the signals"}
              </p>
            )}
            {isForecast && !verdict.ai_generated && !verdict.unavailable && (
              <p className="mt-2 text-[10.5px] italic opacity-60">Deterministic signal-only estimate — AI reasoning layer unavailable this cycle.</p>
            )}
            {!isForecast && !verdict.unavailable && (
              <p className="mt-2 text-[10.5px] opacity-60">Reported from index levels and market breadth. This is what happened, not a forecast.</p>
            )}
          </div>

          <div className="rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] p-5">
            <p className="mb-3 text-[11px] font-bold uppercase tracking-wide text-text-muted">Market Snapshot</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {([["Nifty 50", snap.nifty], ["Bank Nifty", snap.banknifty], ["Sensex", snap.sensex], ["India VIX", snap.vix]] as const).map(([label, q]) => (
                <div key={label}>
                  <p className="text-[10px] font-semibold uppercase text-text-muted">{label}</p>
                  <p className="mt-0.5 text-[15px] font-bold tabular-nums text-text-primary">{q?.value ?? "—"}</p>
                  {q && <p className={`text-[11px] font-medium tabular-nums ${q.positive ? "text-emerald-500" : "text-rose-500"}`}>{q.change}</p>}
                </div>
              ))}
            </div>
            {snap.breadth && (
              <p className="mt-3 border-t border-surface-border/6 pt-2.5 text-[11px] text-text-muted">
                Breadth: <span className="text-emerald-500 font-semibold">{snap.breadth.advances} advancing</span> · <span className="text-rose-500 font-semibold">{snap.breadth.declines} declining</span>
                {snap.breadth.note && <span className="ml-1 opacity-70">({snap.breadth.note})</span>}
              </p>
            )}
            <Link href="/market-intelligence?tab=after-market" className="mt-3 inline-flex items-center gap-0.5 text-[11.5px] font-semibold text-[#6366F1] hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6366F1]">
              Sector performance and top movers in After Market <ChevronRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-[#6366F1]/20 bg-[#6366F1]/[0.05] p-5">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-wide text-[#6366F1]">30-Second Answer</p>
            <p className="text-[13.5px] leading-relaxed text-text-primary">
              {thirtySecondAnswer || "Market intelligence is being compiled for today."}
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.04] p-4">
              <p className="mb-2 flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-emerald-600 dark:text-emerald-300"><TrendingUp className="h-3 w-3" aria-hidden="true" /> Supportive signals</p>
              {data.catalyst_details.length === 0 ? <p className="text-[11.5px] text-text-muted">No supportive signal stands out.</p> : (
                <ul className="space-y-2">
                  {data.catalyst_details.map((c, i) => (
                    <li key={i} className="text-[11.5px] leading-snug text-text-secondary"><span className="font-semibold text-text-primary">{cleanText(c.name)}.</span> {cleanText(c.explanation)}</li>
                  ))}
                </ul>
              )}
            </div>
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.05] p-4">
              <p className="mb-2 flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-amber-700 dark:text-amber-300"><ShieldAlert className="h-3 w-3" aria-hidden="true" /> Risk signals</p>
              {data.risk_details.length === 0 ? <p className="text-[11.5px] text-text-muted">No risk signal stands out.</p> : (
                <ul className="space-y-2">
                  {data.risk_details.map((r, i) => (
                    <li key={i} className="text-[11.5px] leading-snug text-text-secondary"><span className="font-semibold text-text-primary">{cleanText(r.name)}.</span> {cleanText(r.explanation)}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>

      {hasNewSections ? (
        <>
          <MarketDriversSection drivers={data.market_drivers!} sessionLabel="Window: from the previous session's close" />

          <div className="mt-10 grid gap-8 lg:grid-cols-2">
            <ImplicationsSection implications={data.investor_implications!} />
            <ScenariosSection scenarios={data.scenarios!} />
          </div>

          <TakeawaySection takeaway={data.takeaway!} />
        </>
      ) : (
        /* An older backend response has none of the four sections: keep the page useful with the event tiers it does have. */
        events.top.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-3 text-[19px] font-bold tracking-tight text-text-primary">Market-moving events</h2>
            <ul className="space-y-2">
              {events.top.slice(0, 4).map(e => (
                <li key={e.id} className="rounded-xl border border-surface-border/10 p-3 text-[13px] font-medium text-text-primary">{cleanText(e.one_liner || e.headline)}</li>
              ))}
            </ul>
            <Link href="/events" className="mt-3 inline-flex items-center gap-0.5 text-[12px] font-semibold text-[#6366F1]">View all events <ChevronRight className="h-3 w-3" aria-hidden="true" /></Link>
          </section>
        )
      )}

      {historical.available && (
        <section className="mt-10 rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] p-5">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
            <BadgeCheck className="h-3 w-3" aria-hidden="true" /> Historical Context
          </p>
          <p className="text-[12.5px] text-text-secondary">
            {historical.count} similar historical setup{historical.count !== 1 ? "s" : ""} found for {historical.queried_sectors?.join(", ")}.
            {historical.success_rate_pct != null && ` ${historical.success_rate_pct}% saw a positive next-day move.`}
          </p>
          <Link href="/historical" className="mt-2 inline-flex items-center gap-0.5 text-[11.5px] font-semibold text-[#6366F1] hover:opacity-80">
            View Historical Patterns <ChevronRight className="h-3 w-3" aria-hidden="true" />
          </Link>
        </section>
      )}

      {/* ── Questions Investors Are Asking (AEO) ──────────────────────────── */}
      {questions.length > 0 && (
        <section className="mt-10">
          <p className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
            <HelpCircle className="h-3 w-3" aria-hidden="true" /> Questions Investors Are Asking
          </p>
          <div className="space-y-3">
            {questions.map((q, i) => (
              <div key={i} className="rounded-xl border border-surface-border/7 bg-text-primary/[0.02] p-4">
                <p className="text-[13px] font-semibold text-text-primary">{q.question}</p>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-text-secondary">{q.answer}</p>
                {q.links.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-3">
                    {q.links.map(l => (
                      <Link key={l.href} href={l.href} className="text-[11.5px] font-semibold text-[#6366F1] hover:opacity-80">
                        {l.label} →
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Evidence ───────────────────────────────────────────────────────── */}
      {evidence.length > 0 && (
        <section className="mt-10 border-t border-surface-border/7 pt-6">
          <p className="mb-3 text-[11px] font-bold uppercase tracking-wide text-text-muted">Evidence</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {evidence.slice(0, 8).map((e, i) => (
              <div key={i} className="rounded-lg border border-surface-border/6 bg-text-primary/[0.02] p-3 text-[11.5px]">
                <p className="text-text-secondary">{cleanText(e.claim)}</p>
                {/* CD3-C: fact_registry.py folds several genuinely different producers (opening-prediction HYBRID_RUBRIC,
                    EventTriage, raw market data with no confidence at all) into one per-fact `confidence` field -- mixed
                    provenance, disclosed via tooltip rather than asserted as one clean measurement. */}
                <p className="mt-1 text-[10.5px] text-text-muted" title={e.confidence != null ? "Confidence provenance varies by fact source -- not a single uniform measurement" : undefined}>
                  {e.source}{e.confidence != null && ` · ${Math.round(e.confidence * 100)}% confidence`}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Continue Research ─────────────────────────────────────────────── */}
      <section className="mt-10 rounded-2xl border border-surface-border/7 bg-text-primary/[0.03] p-5 text-center">
        <p className="mb-3 text-[13px] font-semibold text-text-primary">Continue Your Research</p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Link href="/ai-search" className="inline-flex items-center gap-1.5 rounded-full bg-[#6366F1] px-4 py-2 text-[12px] font-semibold text-white transition hover:opacity-90">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Ask AI Search
          </Link>
          <Link href="/events" className="rounded-full border border-surface-border/15 px-4 py-2 text-[12px] font-semibold text-text-secondary transition hover:text-text-primary">All Events</Link>
          <Link href="/market-intelligence" className="rounded-full border border-surface-border/15 px-4 py-2 text-[12px] font-semibold text-text-secondary transition hover:text-text-primary">Market Intelligence</Link>
          <Link href="/historical" className="rounded-full border border-surface-border/15 px-4 py-2 text-[12px] font-semibold text-text-secondary transition hover:text-text-primary">Historical Patterns</Link>
          <Link href="/opportunity-radar" className="rounded-full border border-surface-border/15 px-4 py-2 text-[12px] font-semibold text-text-secondary transition hover:text-text-primary">Opportunity Radar</Link>
        </div>
      </section>

      <p className="mt-6 flex items-center gap-1 text-[10.5px] text-text-muted">
        <Eye className="h-3 w-3" aria-hidden="true" /> Figures come from market data feeds and MarketRipple&apos;s event scoring. Completed sessions are reported, not predicted; forecasts are labelled with their target date.
      </p>
    </div>
  );
}
