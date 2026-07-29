import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Clock, TrendingUp, TrendingDown, BookOpen, ArrowLeft, Landmark } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText, safeJsonLd } from "@/lib/text";

/**
 * Historical Memory detail page — SEO audit's "no page, engine exists"
 * finding: historical_memory_service.py + /api/historical/ already stores
 * 52 real, richly-detailed market-pattern events (Union Budgets, RBI rate
 * cycles, market corrections, global shocks — dated back to 2008), consumed
 * only by the HistoricalMemory.tsx sidebar widget until now. These pages
 * have long organic life since a pattern (not a single day's news) stays
 * relevant long after the event itself fades from search.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://marketripple.in";

interface HistoricalWinner {
  symbol: string; name: string;
  return_1d?: number | null; return_1w?: number | null; return_1m?: number | null;
  reason: string;
}

interface HistoricalDetail {
  id: string; event_title: string; event_date: string; category: string;
  sentiment: string | null; sectors: string[]; companies: string[]; tags: string[];
  market_regime: string | null; interest_rate_trend: string | null; crude_trend: string | null;
  interest_rate_level: number | null; vix_level: number | null;
  nifty_1d: number | null; nifty_3d: number | null; nifty_1w: number | null; nifty_1m: number | null;
  sector_reactions: Record<string, number>;
  historical_winners: HistoricalWinner[];
  historical_losers: HistoricalWinner[];
  opportunity_score: number | null; risk_score: number | null; confidence: number | null;
  what_happened: string | null; key_lesson: string | null; source: string | null;
}

async function fetchEvent(id: string): Promise<HistoricalDetail | null> {
  try {
    const res = await fetch(`${API}/api/historical/${id}`, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    const raw = await res.json();
    return {
      ...raw,
      event_title: cleanText(raw.event_title),
      what_happened: raw.what_happened ? cleanText(raw.what_happened) : raw.what_happened,
      key_lesson: raw.key_lesson ? cleanText(raw.key_lesson) : raw.key_lesson,
      historical_winners: (raw.historical_winners ?? []).map((w: HistoricalWinner) => ({ ...w, reason: cleanText(w.reason) })),
      historical_losers: (raw.historical_losers ?? []).map((w: HistoricalWinner) => ({ ...w, reason: cleanText(w.reason) })),
    };
  } catch {
    return null;
  }
}

function pct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`;
}
function pctCls(v: number | null | undefined): string {
  if (v == null) return "text-slate-500";
  return v >= 0 ? "text-emerald-400" : "text-rose-400";
}
function bestReturn(w: HistoricalWinner): number {
  return w.return_1w ?? w.return_1m ?? w.return_1d ?? 0;
}
const SENTIMENT_STYLE: Record<string, string> = {
  bullish: "text-emerald-400 border-emerald-500/25 bg-emerald-500/10",
  bearish: "text-rose-400 border-rose-500/25 bg-rose-500/10",
  mixed:   "text-amber-400 border-amber-500/25 bg-amber-500/10",
  neutral: "text-slate-400 border-white/15 bg-white/5",
};

// Data has near-duplicate category casings ("Monetary Policy" / "monetary
// policy") — normalized for display without touching the stored value,
// since that's a data-entry inconsistency, not something worth a migration
// for a read-only display label.
function normalizeCategory(c: string): string {
  return c.replace(/_/g, " ").trim().split(" ").map(w => w[0]?.toUpperCase() + w.slice(1)).join(" ");
}

// Thin, auto-captured events (no real Nifty reaction or scoring data yet —
// see sitemap.ts's same filter) still render honestly rather than 404ing,
// since a widget or direct link might reach one, but they shouldn't be
// indexed as a "full analysis" page — same thin-content reasoning as the
// sitemap exclusion, applied here too since crawlers can reach a page
// through links even when it's absent from the sitemap.
function isSubstantive(d: HistoricalDetail): boolean {
  return d.nifty_1w != null || d.opportunity_score != null || d.historical_winners.length > 0;
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/historical/${id}`;
  const d = await fetchEvent(id);
  if (!d) return { title: "Historical Pattern Not Found — MarketRipple", alternates: { canonical: url } };
  const title = `${d.event_title} — What Happened & What It Means Now`;
  const description = (d.key_lesson || d.what_happened || `${d.event_title}: real historical market data on how Nifty and key sectors reacted.`).slice(0, 160);
  return {
    title,
    description,
    ...(isSubstantive(d) ? {} : { robots: { index: false, follow: true } }),
    openGraph: { type: "article", title, description, url, siteName: "MarketRipple" },
    twitter: { card: "summary_large_image", title, description },
    alternates: { canonical: url },
  };
}

export default async function HistoricalDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const d = await fetchEvent(id);
  if (!d) notFound();

  const url = `${SITE}/historical/${id}`;
  const sentimentCls = SENTIMENT_STYLE[(d.sentiment ?? "neutral").toLowerCase()] ?? SENTIMENT_STYLE.neutral;
  const category = normalizeCategory(d.category);

  // Real, honestly-derived FAQs from the same fields already on the page —
  // not a second LLM call, not invented. Only included when the
  // underlying data actually supports the answer.
  const faqs: { q: string; a: string }[] = [];
  if (d.what_happened) faqs.push({ q: `What happened during ${d.event_title}?`, a: d.what_happened });
  if (d.historical_winners.length) {
    const names = d.historical_winners.slice(0, 3).map(w => w.name || w.symbol).join(", ");
    faqs.push({ q: `Which stocks benefited most from ${d.event_title}?`, a: `Historically, ${names} were among the strongest performers in the aftermath, based on real 1-week/1-month return data.` });
  }
  if (d.nifty_1w != null) {
    faqs.push({ q: `How did the Nifty 50 react to ${d.event_title}?`, a: `The Nifty 50 moved ${pct(d.nifty_1w)} in the following week and ${pct(d.nifty_1m)} over the following month.` });
  }
  if (d.key_lesson) faqs.push({ q: `What's the investing lesson from ${d.event_title}?`, a: d.key_lesson });

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": faqs.length ? ["Article", "FAQPage"] : "Article",
    headline: d.event_title,
    description: d.key_lesson || d.what_happened || d.event_title,
    datePublished: d.event_date,
    dateModified: d.event_date,
    author: { "@type": "Organization", name: "MarketRipple AI Intelligence Engine" },
    publisher: { "@type": "Organization", name: "MarketRipple" },
    mainEntityOfPage: url,
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: SITE },
        { "@type": "ListItem", position: 2, name: "Historical Patterns", item: `${SITE}/historical` },
        { "@type": "ListItem", position: 3, name: d.event_title, item: url },
      ],
    },
    ...(faqs.length ? {
      mainEntity: faqs.map(f => ({
        "@type": "Question", name: f.q,
        acceptedAnswer: { "@type": "Answer", text: f.a },
      })),
    } : {}),
  };

  return (
    <main className="mx-auto max-w-[900px] px-5 py-8 pb-16 sm:px-6">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }} />

      <nav className="mb-5 flex items-center gap-2 text-[12px] text-slate-500">
        <Link href="/historical" className="flex items-center gap-1 hover:text-slate-300 transition">
          <ArrowLeft className="h-3 w-3" /> Historical Patterns
        </Link>
      </nav>

      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">{category}</span>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${sentimentCls}`}>{d.sentiment ?? "Neutral"}</span>
        <span className="flex items-center gap-1 text-[11px] text-slate-500"><Clock className="h-3 w-3" /> {d.event_date}</span>
      </div>

      <h1 className="text-[26px] font-black leading-tight text-white md:text-[32px]">{d.event_title}</h1>

      {d.key_lesson && (
        <p className="mt-3 max-w-[700px] text-[15px] leading-relaxed text-slate-400">{d.key_lesson}</p>
      )}

      {/* Nifty reaction strip — the real, verified data this whole page exists to surface */}
      <div className="mt-6 grid grid-cols-2 gap-3 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5 sm:grid-cols-4">
        {[["1 Day", d.nifty_1d], ["3 Days", d.nifty_3d], ["1 Week", d.nifty_1w], ["1 Month", d.nifty_1m]].map(([label, val]) => (
          <div key={label as string} className="text-center">
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Nifty {label}</p>
            <p className={`mt-1 text-[20px] font-black tabular-nums ${pctCls(val as number | null)}`}>{pct(val as number | null)}</p>
          </div>
        ))}
      </div>

      {d.what_happened && (
        <section className="mt-8">
          <h2 className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-slate-500">
            <BookOpen className="h-3.5 w-3.5" /> What Happened
          </h2>
          <p className="text-[14px] leading-relaxed text-slate-300">{d.what_happened}</p>
        </section>
      )}

      {(d.historical_winners.length > 0 || d.historical_losers.length > 0) && (
        <section className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.04] p-4">
            <h2 className="mb-3 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-emerald-500">
              <TrendingUp className="h-3.5 w-3.5" /> Historical Winners
            </h2>
            {d.historical_winners.length ? (
              <div className="space-y-2.5">
                {d.historical_winners.map((w, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between">
                      <Link href={`/companies/${w.symbol}`} className="text-[13px] font-semibold text-white hover:text-emerald-300 transition">{w.name || w.symbol}</Link>
                      <span className="text-[13px] font-bold text-emerald-400 tabular-nums">{pct(bestReturn(w))}</span>
                    </div>
                    {w.reason && <p className="mt-0.5 text-[11px] text-slate-500">{w.reason}</p>}
                  </div>
                ))}
              </div>
            ) : <p className="text-[12px] text-slate-600">No clear winners in the historical data.</p>}
          </div>
          <div className="rounded-2xl border border-rose-500/15 bg-rose-500/[0.04] p-4">
            <h2 className="mb-3 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-rose-500">
              <TrendingDown className="h-3.5 w-3.5" /> Historical Losers
            </h2>
            {d.historical_losers.length ? (
              <div className="space-y-2.5">
                {d.historical_losers.map((l, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between">
                      <Link href={`/companies/${l.symbol}`} className="text-[13px] font-semibold text-white hover:text-rose-300 transition">{l.name || l.symbol}</Link>
                      <span className="text-[13px] font-bold text-rose-400 tabular-nums">{pct(bestReturn(l))}</span>
                    </div>
                    {l.reason && <p className="mt-0.5 text-[11px] text-slate-500">{l.reason}</p>}
                  </div>
                ))}
              </div>
            ) : <p className="text-[12px] text-slate-600">No significant laggards in the historical data.</p>}
          </div>
        </section>
      )}

      {Object.keys(d.sector_reactions).length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-slate-500">Sector Reactions</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(d.sector_reactions).map(([sec, chg]) => (
              <span key={sec} className={`rounded-full px-3 py-1 text-[12px] font-semibold ${chg >= 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
                {sec} {pct(chg)}
              </span>
            ))}
          </div>
        </section>
      )}

      {faqs.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-slate-500">Frequently Asked</h2>
          <div className="space-y-2">
            {faqs.map((f, i) => (
              <details key={i} className="group rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <summary className="cursor-pointer text-[13px] font-semibold text-white">{f.q}</summary>
                <p className="mt-2 text-[13px] leading-relaxed text-slate-400">{f.a}</p>
              </details>
            ))}
          </div>
        </section>
      )}

      <section className="mt-10 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
        <h2 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">Market Context Then</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {d.market_regime && <div><p className="text-[9px] uppercase text-slate-600">Regime</p><p className="text-[12px] font-semibold text-slate-300 capitalize">{d.market_regime}</p></div>}
          {d.interest_rate_level != null && <div><p className="text-[9px] uppercase text-slate-600">Repo Rate</p><p className="text-[12px] font-semibold text-slate-300">{d.interest_rate_level}%</p></div>}
          {d.vix_level != null && <div><p className="text-[9px] uppercase text-slate-600">India VIX</p><p className="text-[12px] font-semibold text-slate-300">{d.vix_level.toFixed(1)}</p></div>}
          {d.confidence != null && <div><p className="text-[9px] uppercase text-slate-600">Data Confidence</p><p className="text-[12px] font-semibold text-slate-300">{d.confidence}%</p></div>}
        </div>
      </section>

      {d.companies.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-slate-500">
            <Landmark className="h-3.5 w-3.5" /> Companies Involved
          </h2>
          <div className="flex flex-wrap gap-2">
            {d.companies.map(sym => (
              <Link key={sym} href={`/companies/${sym}`} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[12px] font-semibold text-slate-300 hover:border-sky-500/30 hover:text-sky-300 transition">
                {sym}
              </Link>
            ))}
          </div>
        </section>
      )}

      <div className="mt-10 flex items-center justify-between border-t border-white/[0.06] pt-5">
        <Link href="/historical" className="text-[12px] font-semibold text-sky-400 hover:text-sky-300 transition">← All Historical Patterns</Link>
        <Link href="/ai-search" className="text-[12px] font-semibold text-slate-500 hover:text-slate-300 transition">Ask AI about this pattern →</Link>
      </div>
    </main>
  );
}
