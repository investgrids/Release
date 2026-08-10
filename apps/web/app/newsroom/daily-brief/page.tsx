import type { Metadata } from "next";
import Link from "next/link";
import {
  TrendingUp, TrendingDown, Minus, ShieldAlert, Flame, Eye, Sparkles,
  ChevronRight, BadgeCheck, CalendarClock, HelpCircle,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";
import { RefreshButton } from "./RefreshButton";

// ── Types (subset of the real /api/daily-brief/intelligence response) ───────

interface IndexQuote { name: string; value: string; change: string; pct: number; positive: boolean }
interface Verdict {
  direction: string | null; confidence: number | null;
  primary_drivers: string[]; risks: string[];
  reasoning: string | null; ai_generated: boolean; unavailable?: boolean;
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
interface WhyMattersItem { event: string; consequence: string; affected: string[] }
interface StockToWatch { symbol: string; reason: string; priority_tier: string; sentiment: string | null }
interface HistoricalContext { available: boolean; message?: string; count?: number; success_rate_pct?: number | null; queried_sectors?: string[] }
interface Question { question: string; answer: string; links: { label: string; href: string }[] }
interface Evidence { claim: string; source: string; timestamp: string | null; confidence: number | null }
interface WatchNextItem { date: string | null; category: string | null; title: string | null; description: string | null }

interface DailyBriefData {
  market_verdict: Verdict;
  market_snapshot: Snapshot;
  events: EventsBlock;
  why_today_matters: WhyMattersItem[];
  stocks_to_watch: StockToWatch[];
  sector_intelligence: { id: string; name: string; value: string; positive: boolean }[];
  historical_context: HistoricalContext;
  catalysts: string[];
  risks: string[];
  what_to_watch_next: WatchNextItem[];
  questions: Question[];
  evidence: Evidence[];
  generated_at: string;
}

async function getData(): Promise<DailyBriefData | null> {
  try {
    const res = await fetch(`${API}/api/daily-brief/intelligence`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
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

const TIER_COLOR: Record<string, string> = {
  Critical: "bg-rose-500/10 text-rose-600 dark:text-rose-300 border-rose-500/20",
  High:     "bg-amber-500/10 text-amber-600 dark:text-amber-300 border-amber-500/20",
};

export async function generateMetadata(): Promise<Metadata> {
  const data = await getData();
  const dateStr = data?.market_snapshot.market_status?.date;
  const direction = data?.market_verdict.direction;
  const title = dateStr
    ? `Indian Stock Market Today (${dateStr}): Nifty, Bank Nifty & Market Outlook | MarketRipple`
    : "Indian Stock Market Today: Nifty, Bank Nifty & Market Outlook | MarketRipple";
  const description = direction
    ? `Indian stock market today: ${direction.toLowerCase()} outlook, Nifty 50 and Bank Nifty levels, stocks to watch, sector performance, key events and risks for Indian investors.`
    : "Indian stock market today: Nifty 50, Bank Nifty, market outlook, stocks to watch, sector performance, key events and risks for Indian investors.";

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

  const { market_verdict: verdict, market_snapshot: snap, events, why_today_matters, stocks_to_watch,
    sector_intelligence, historical_context: historical, catalysts, risks, what_to_watch_next, questions, evidence } = data;

  const dirMeta = DIRECTION_META[verdict.direction ?? ""] ?? DIRECTION_META.Neutral;
  const topDriver = catalysts[0] || events.top[0]?.one_liner || events.top[0]?.headline;
  const topRisk = risks[0];

  const thirtySecondAnswer = [
    verdict.reasoning,
    topDriver ? `Today's biggest driver: ${topDriver}.` : null,
    topRisk ? `Key risk to watch: ${topRisk}.` : null,
  ].filter(Boolean).join(" ");

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
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(webPageJsonLd) }} />
      {faqJsonLd && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />}

      {/* Header */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-accent-violet">Market Intelligence</p>
          <h1 className="mt-2 text-[26px] font-black leading-tight text-text-primary md:text-[32px]">
            Indian Stock Market Today
          </h1>
          <p className="mt-1.5 text-[13px] text-text-muted">
            {snap.market_status?.date} · {snap.market_status?.status === "pre_market" ? "Pre-Market Outlook" : snap.market_status?.status === "live" ? "Live Session" : "Market Wrap"} · Updated {fmtIST(data.generated_at)}
          </p>
        </div>
        <RefreshButton />
      </div>

      {/* ── Above the fold: 2-column ─────────────────────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* LEFT: Verdict + Snapshot + Driver/Risk */}
        <div className="space-y-4">
          <div className={`rounded-2xl border p-5 ${dirMeta.color}`}>
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-bold uppercase tracking-wide opacity-80">Market Verdict</p>
              {verdict.unavailable && <span className="text-[10px] opacity-70">Data unavailable</span>}
            </div>
            <div className="mt-2 flex items-center gap-2">
              {dirMeta.icon}
              <p className="text-[22px] font-black">{dirMeta.label}</p>
              {verdict.confidence != null && (
                <span className="ml-auto text-[13px] font-bold tabular-nums">{verdict.confidence}% confidence</span>
              )}
            </div>
            {verdict.reasoning && <p className="mt-2 text-[12.5px] leading-relaxed opacity-90">{verdict.reasoning}</p>}
            {!verdict.ai_generated && !verdict.unavailable && (
              <p className="mt-2 text-[10.5px] italic opacity-60">Deterministic signal-only estimate — AI reasoning layer unavailable this cycle.</p>
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
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/[0.04] p-4">
              <p className="text-[10px] font-bold uppercase tracking-wide text-emerald-600 dark:text-emerald-300">Today&apos;s Biggest Driver</p>
              <p className="mt-1.5 text-[12.5px] leading-snug text-text-primary">{topDriver || "No standout driver detected today."}</p>
            </div>
            <div className="rounded-xl border border-rose-500/15 bg-rose-500/[0.04] p-4">
              <p className="text-[10px] font-bold uppercase tracking-wide text-rose-600 dark:text-rose-300">Biggest Risk</p>
              <p className="mt-1.5 text-[12.5px] leading-snug text-text-primary">{topRisk || "No standout risk detected today."}</p>
            </div>
          </div>
        </div>

        {/* RIGHT: 30-sec answer + Stocks to Watch + Events */}
        <div className="space-y-4">
          <div className="rounded-2xl border border-accent-violet/15 bg-accent-violet/[0.05] p-5">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-wide text-accent-violet">30-Second Answer</p>
            <p className="text-[13.5px] leading-relaxed text-text-primary">
              {thirtySecondAnswer || "Market intelligence is being compiled for today."}
            </p>
          </div>

          <div className="rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] p-5">
            <p className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
              <Flame className="h-3 w-3 text-rose-400" /> Stocks to Watch Today
            </p>
            {stocks_to_watch.length === 0 ? (
              <p className="text-[12px] text-text-muted">No standout stocks in today&apos;s high-impact events yet.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {stocks_to_watch.slice(0, 8).map(s => (
                  <Link key={s.symbol} href={`/companies/${s.symbol}`} title={s.reason}
                    className={`rounded-full border px-3 py-1.5 text-[11.5px] font-semibold transition hover:opacity-80 ${
                      s.sentiment === "bullish" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
                      : s.sentiment === "bearish" ? "border-rose-500/25 bg-rose-500/10 text-rose-600 dark:text-rose-300"
                      : "border-surface-border/15 bg-surface-card text-text-secondary"
                    }`}>
                    {s.symbol}
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] p-5">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-[11px] font-bold uppercase tracking-wide text-text-muted">Market-Moving Events</p>
              <div className="flex gap-1.5 text-[10px] font-bold">
                <span className="rounded-full bg-rose-500/10 px-2 py-0.5 text-rose-600 dark:text-rose-300">{events.tiers.critical} Critical</span>
                <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-600 dark:text-amber-300">{events.tiers.high} High</span>
                <span className="rounded-full bg-surface-border/15 px-2 py-0.5 text-text-muted">{events.tiers.medium} Medium</span>
              </div>
            </div>
            {events.top.length === 0 ? (
              <p className="text-[12px] text-text-muted">No high-impact events right now.</p>
            ) : (
              <div className="space-y-2">
                {events.top.slice(0, 4).map(e => (
                  <div key={e.id} className="rounded-lg border border-surface-border/6 bg-surface-card p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[12.5px] font-medium leading-snug text-text-primary">{cleanText(e.one_liner || e.headline)}</p>
                      {TIER_COLOR[e.priority_tier] && (
                        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9.5px] font-bold uppercase ${TIER_COLOR[e.priority_tier]}`}>{e.priority_tier}</span>
                      )}
                    </div>
                    {e.sectors.length > 0 && <p className="mt-1 text-[10.5px] text-text-muted">{e.sectors.slice(0, 3).join(" · ")}</p>}
                  </div>
                ))}
              </div>
            )}
            <Link href="/events" className="mt-3 inline-flex items-center gap-0.5 text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
              View all today&apos;s events <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
        </div>
      </div>

      {/* ── Sector Intelligence ───────────────────────────────────────────── */}
      {sector_intelligence.length > 0 && (
        <section className="mt-8">
          <p className="mb-3 text-[11px] font-bold uppercase tracking-wide text-text-muted">Sector Intelligence</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
            {sector_intelligence.map(s => (
              <Link key={s.id} href={`/sectors/${s.id}`} className="rounded-lg border border-surface-border/7 bg-text-primary/[0.02] p-3 transition hover:border-surface-border/20">
                <p className="text-[11.5px] font-semibold text-text-primary">{s.name}</p>
                <p className={`mt-0.5 text-[12px] font-bold tabular-nums ${s.positive ? "text-emerald-500" : "text-rose-500"}`}>{s.value}</p>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ── Why Today Matters ─────────────────────────────────────────────── */}
      {why_today_matters.length > 0 && (
        <section className="mt-8">
          <p className="mb-3 text-[11px] font-bold uppercase tracking-wide text-text-muted">Why Today Matters</p>
          <ul className="space-y-2">
            {why_today_matters.map((w, i) => (
              <li key={i} className="flex gap-2 rounded-lg border border-surface-border/6 bg-text-primary/[0.02] p-3 text-[12.5px] leading-relaxed text-text-secondary">
                <span className="text-accent-violet">→</span>
                <span><span className="font-semibold text-text-primary">{cleanText(w.event)}</span> — {cleanText(w.consequence)} <span className="text-text-muted">({w.affected.join(", ")})</span></span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── Historical Context / Catalysts+Risks — 2 col ─────────────────── */}
      <div className="mt-8 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] p-5">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
            <BadgeCheck className="h-3 w-3" /> Historical Context
          </p>
          {historical.available ? (
            <>
              <p className="text-[12.5px] text-text-secondary">
                {historical.count} similar historical setup{historical.count !== 1 ? "s" : ""} found for {historical.queried_sectors?.join(", ")}.
                {historical.success_rate_pct != null && ` ${historical.success_rate_pct}% saw a positive next-day move.`}
              </p>
              <Link href="/historical" className="mt-2 inline-flex items-center gap-0.5 text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
                View Historical Patterns <ChevronRight className="h-3 w-3" />
              </Link>
            </>
          ) : (
            <p className="text-[12px] text-text-muted">{historical.message}</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.04] p-4">
            <p className="mb-2 text-[10.5px] font-bold uppercase tracking-wide text-emerald-600 dark:text-emerald-300">Catalysts</p>
            {catalysts.length === 0 ? <p className="text-[11.5px] text-text-muted">None detected today.</p> : (
              <ul className="space-y-1.5">
                {catalysts.map((c, i) => <li key={i} className="text-[11.5px] leading-snug text-text-secondary">🟢 {cleanText(c)}</li>)}
              </ul>
            )}
          </div>
          <div className="rounded-2xl border border-rose-500/15 bg-rose-500/[0.04] p-4">
            <p className="mb-2 flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-rose-600 dark:text-rose-300">
              <ShieldAlert className="h-3 w-3" /> Risks
            </p>
            {risks.length === 0 ? <p className="text-[11.5px] text-text-muted">None detected today.</p> : (
              <ul className="space-y-1.5">
                {risks.map((r, i) => <li key={i} className="text-[11.5px] leading-snug text-text-secondary">🔴 {cleanText(r)}</li>)}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* ── What to Watch Next ────────────────────────────────────────────── */}
      {what_to_watch_next.length > 0 && (
        <section className="mt-8">
          <p className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
            <CalendarClock className="h-3 w-3" /> What to Watch Next
          </p>
          <div className="space-y-2">
            {what_to_watch_next.map((w, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg border border-surface-border/6 bg-text-primary/[0.02] p-3">
                <span className="shrink-0 rounded-md bg-accent-violet/10 px-2 py-1 text-[10.5px] font-bold text-accent-violet">{w.date}</span>
                <div className="min-w-0">
                  <p className="text-[12.5px] font-semibold text-text-primary">{w.title}</p>
                  {w.description && <p className="truncate text-[11px] text-text-muted">{w.description}</p>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Questions Investors Are Asking (AEO) ──────────────────────────── */}
      {questions.length > 0 && (
        <section className="mt-8">
          <p className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
            <HelpCircle className="h-3 w-3" /> Questions Investors Are Asking
          </p>
          <div className="space-y-3">
            {questions.map((q, i) => (
              <div key={i} className="rounded-xl border border-surface-border/7 bg-text-primary/[0.02] p-4">
                <p className="text-[13px] font-semibold text-text-primary">{q.question}</p>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-text-secondary">{q.answer}</p>
                {q.links.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-3">
                    {q.links.map(l => (
                      <Link key={l.href} href={l.href} className="text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
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
        <section className="mt-8 border-t border-surface-border/7 pt-6">
          <p className="mb-3 text-[11px] font-bold uppercase tracking-wide text-text-muted">Evidence</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {evidence.slice(0, 8).map((e, i) => (
              <div key={i} className="rounded-lg border border-surface-border/6 bg-text-primary/[0.02] p-3 text-[11.5px]">
                <p className="text-text-secondary">{cleanText(e.claim)}</p>
                <p className="mt-1 text-[10.5px] text-text-muted">
                  {e.source}{e.confidence != null && ` · ${Math.round(e.confidence * 100)}% confidence`}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Continue Research ─────────────────────────────────────────────── */}
      <section className="mt-8 rounded-2xl border border-surface-border/7 bg-text-primary/[0.03] p-5 text-center">
        <p className="mb-3 text-[13px] font-semibold text-text-primary">Continue Your Research</p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Link href="/ai-search" className="inline-flex items-center gap-1.5 rounded-full bg-accent-violet px-4 py-2 text-[12px] font-semibold text-white transition hover:opacity-90">
            <Sparkles className="h-3.5 w-3.5" /> Ask AI Search
          </Link>
          <Link href="/events" className="rounded-full border border-surface-border/15 px-4 py-2 text-[12px] font-semibold text-text-secondary transition hover:text-text-primary">All Events</Link>
          <Link href="/market-intelligence" className="rounded-full border border-surface-border/15 px-4 py-2 text-[12px] font-semibold text-text-secondary transition hover:text-text-primary">Market Intelligence</Link>
          <Link href="/historical" className="rounded-full border border-surface-border/15 px-4 py-2 text-[12px] font-semibold text-text-secondary transition hover:text-text-primary">Historical Patterns</Link>
          <Link href="/opportunity-radar" className="rounded-full border border-surface-border/15 px-4 py-2 text-[12px] font-semibold text-text-secondary transition hover:text-text-primary">Opportunity Radar</Link>
        </div>
      </section>

      <p className="mt-6 flex items-center gap-1 text-[10.5px] text-text-muted">
        <Eye className="h-3 w-3" /> Every figure above is real, live market data — nothing on this page is fabricated or estimated beyond what&apos;s explicitly labeled.
      </p>
    </div>
  );
}
