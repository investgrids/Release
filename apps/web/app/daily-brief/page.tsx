import type { Metadata } from "next";
import Link from "next/link";
import { TrendingUp, AlertTriangle, Newspaper, Calendar, BarChart2, ArrowRight, Lightbulb } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.API_URL ?? "http://localhost:8000";

export const dynamic   = "force-dynamic";
export const revalidate = 0;

// ── Data fetching ─────────────────────────────────────────────────────────────

function timed(ms: number): AbortSignal {
  return AbortSignal.timeout ? AbortSignal.timeout(ms) : new AbortController().signal;
}

async function fetchHomeIntelligence() {
  try {
    const res = await fetch(`${API}/api/intelligence/home`, { cache: "no-store", signal: timed(10000) });
    if (res.ok) return res.json();
  } catch {}
  return null;
}

async function fetchMarketOverview() {
  try {
    const res = await fetch(`${API}/api/market/overview`, { cache: "no-store", signal: timed(10000) });
    if (res.ok) return res.json();
  } catch {}
  return null;
}

async function fetchTopEvents() {
  try {
    const res = await fetch(`${API}/api/events/?limit=5`, { cache: "no-store", signal: timed(8000) });
    if (res.ok) return res.json();
  } catch {}
  return [];
}

async function fetchTopNews() {
  try {
    const res = await fetch(`${API}/api/news/?limit=6`, { cache: "no-store", signal: timed(8000) });
    if (res.ok) {
      const d = await res.json();
      return Array.isArray(d) ? d : (d.articles ?? d.news ?? []);
    }
  } catch {}
  return [];
}

// ── Metadata ──────────────────────────────────────────────────────────────────

export async function generateMetadata(): Promise<Metadata> {
  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
  const intel = await fetchHomeIntelligence();
  const takeaway = intel?.key_takeaway?.slice(0, 100);
  const description = takeaway
    ? `${takeaway} — AI-powered daily market brief for Indian equities.`
    : `Today's AI-powered Indian market brief — ${today}. Events, opportunities, risks and sector outlook.`;

  return {
    title: `Daily Market Brief — ${today} | InvestGrids`,
    description,
    openGraph: {
      title: `Daily Market Brief — ${today}`,
      description,
      type: "article",
      siteName: "InvestGrids",
    },
    twitter: { card: "summary_large_image", title: `Daily Market Brief — ${today}`, description },
    alternates: { canonical: "/daily-brief" },
  };
}

// ── Components ────────────────────────────────────────────────────────────────

function SectionHeader({ icon, title, color }: { icon: React.ReactNode; title: string; color: string }) {
  return (
    <h2 className={`mb-4 flex items-center gap-2 text-[12px] font-bold uppercase tracking-widest ${color}`}>
      {icon} {title}
    </h2>
  );
}

function Pill({ label, positive }: { label: string; positive: boolean }) {
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${
      positive
        ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400"
        : "border-rose-500/25 bg-rose-500/10 text-rose-400"
    }`}>
      {label}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function DailyBriefPage() {
  const [intel, market, events, news] = await Promise.all([
    fetchHomeIntelligence(),
    fetchMarketOverview(),
    fetchTopEvents(),
    fetchTopNews(),
  ]);

  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  const opps: any[]    = intel?.opportunities ?? [];
  const risks: any[]   = intel?.risks ?? [];
  const companies: any[]= intel?.companies ?? [];
  const sectors: any[] = intel?.sectors ?? [];
  const themes: any[]  = intel?.themes ?? [];
  const monitoring: string[] = intel?.monitoring_points ?? [];
  const indices: any[] = market?.indices ?? [];
  const topEvents: any[] = Array.isArray(events) ? events.slice(0, 5) : [];
  const topNews: any[]   = news.slice(0, 6);

  // Structured data for SEO
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": `Daily Market Brief — ${today}`,
    "description": intel?.market_story ?? "AI-powered daily market brief for Indian equities",
    "datePublished": new Date().toISOString(),
    "publisher": { "@type": "Organization", "name": "InvestGrids" },
    "about": { "@type": "Thing", "name": "Indian Stock Market" },
  };

  return (
    <main className="min-h-screen bg-[#040810] text-white">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />

      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">

        {/* Header */}
        <div className="mb-8 border-b border-white/[0.06] pb-6">
          <div className="flex items-center gap-2 mb-2">
            <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sky-400">
              Daily Brief
            </span>
            {intel?.confidence?.level && (
              <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${
                intel.confidence.score >= 75
                  ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400"
                  : "border-amber-500/25 bg-amber-500/10 text-amber-400"
              }`}>
                AI Confidence: {intel.confidence.level}
              </span>
            )}
          </div>
          <h1 className="text-[26px] font-black leading-tight text-white">{today}</h1>
          <p className="mt-1 text-[13px] text-slate-500">AI-powered market intelligence for Indian equities</p>
        </div>

        {/* Key Takeaway */}
        {intel?.key_takeaway && (
          <div className="mb-7 rounded-2xl border border-violet-500/20 bg-violet-500/[0.06] p-5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-violet-400 mb-1.5">Today's Key Insight</p>
            <p className="text-[16px] font-semibold leading-snug text-white">{intel.key_takeaway}</p>
          </div>
        )}

        {/* Market Story */}
        {intel?.market_story && (
          <section className="mb-7">
            <SectionHeader icon={<Lightbulb className="h-3.5 w-3.5" />} title="Market Story" color="text-slate-500" />
            <p className="text-[14px] leading-7 text-slate-300">{intel.market_story}</p>
          </section>
        )}

        {/* Market Indices snapshot */}
        {indices.length > 0 && (
          <section className="mb-7">
            <SectionHeader icon={<BarChart2 className="h-3.5 w-3.5" />} title="Market Snapshot" color="text-slate-500" />
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {indices.slice(0, 6).map((idx: any, i: number) => {
                const pos = (idx.change_pct ?? 0) >= 0;
                return (
                  <div key={i} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-600">{idx.name}</p>
                    <p className="mt-1 text-[18px] font-black tabular-nums text-white">{idx.value ?? "—"}</p>
                    <p className={`text-[11px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>
                      {pos ? "+" : ""}{(idx.change_pct ?? 0).toFixed(2)}%
                    </p>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Opportunities */}
        {opps.length > 0 && (
          <section className="mb-7">
            <SectionHeader icon={<TrendingUp className="h-3.5 w-3.5" />} title="Today's Opportunities" color="text-emerald-500" />
            <div className="space-y-3">
              {opps.slice(0, 4).map((o: any, i: number) => (
                <div key={i} className="rounded-xl border border-emerald-500/15 bg-emerald-500/[0.04] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-[13px] font-semibold text-emerald-300">{o.title}</h3>
                    {o.horizon && <span className="shrink-0 text-[10px] font-medium text-slate-500">{o.horizon}</span>}
                  </div>
                  <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{o.description}</p>
                  {o.companies?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {o.companies.map((c: string) => (
                        <Link key={c} href={`/companies/${c}`}
                          className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400 hover:text-sky-300 transition">
                          {c}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Risks */}
        {risks.length > 0 && (
          <section className="mb-7">
            <SectionHeader icon={<AlertTriangle className="h-3.5 w-3.5" />} title="Key Risks to Watch" color="text-amber-500" />
            <div className="space-y-3">
              {risks.slice(0, 3).map((r: any, i: number) => (
                <div key={i} className={`rounded-xl border p-4 ${
                  r.severity === "High"
                    ? "border-rose-500/20 bg-rose-500/[0.04]"
                    : "border-amber-500/15 bg-amber-500/[0.04]"
                }`}>
                  <div className="flex items-start justify-between gap-3">
                    <h3 className={`text-[13px] font-semibold ${r.severity === "High" ? "text-rose-300" : "text-amber-300"}`}>
                      {r.title}
                    </h3>
                    {r.severity && <Pill label={r.severity} positive={false} />}
                  </div>
                  <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{r.description}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Sectors + Themes */}
        {(sectors.length > 0 || themes.length > 0) && (
          <div className="mb-7 grid grid-cols-1 gap-5 sm:grid-cols-2">
            {sectors.length > 0 && (
              <section>
                <SectionHeader icon={null} title="Sector Outlook" color="text-slate-500" />
                <div className="space-y-2">
                  {sectors.slice(0, 5).map((s: any, i: number) => (
                    <div key={i} className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                      <span className="text-[12px] text-slate-300">{s.name}</span>
                      <span className={`text-[11px] font-bold ${
                        s.outlook === "Positive" ? "text-emerald-400" :
                        s.outlook === "Negative" ? "text-rose-400" : "text-slate-400"
                      }`}>{s.outlook ?? "Neutral"}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {themes.length > 0 && (
              <section>
                <SectionHeader icon={null} title="Active Themes" color="text-slate-500" />
                <div className="flex flex-wrap gap-2">
                  {themes.slice(0, 8).map((t: any, i: number) => (
                    <Link key={i} href="/themes"
                      className="rounded-full border border-violet-500/20 bg-violet-500/[0.06] px-3 py-1.5 text-[11px] font-medium text-violet-300 hover:text-violet-200 transition">
                      {t.name}
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {/* Key Events */}
        {topEvents.length > 0 && (
          <section className="mb-7">
            <SectionHeader icon={<Calendar className="h-3.5 w-3.5" />} title="Key Events" color="text-slate-500" />
            <div className="space-y-2">
              {topEvents.map((e: any, i: number) => (
                <Link key={i} href={`/events/${e.id}`}
                  className="flex items-start justify-between gap-3 rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3 hover:border-white/15 transition">
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold text-slate-200 line-clamp-1">{e.title}</p>
                    <p className="mt-0.5 text-[10px] text-slate-600">{e.category} · Impact {e.impact_score ?? "—"}</p>
                  </div>
                  <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-600" />
                </Link>
              ))}
            </div>
            <Link href="/events" className="mt-3 inline-block text-[11px] text-sky-400 hover:text-sky-300 transition">
              View all events →
            </Link>
          </section>
        )}

        {/* Top News */}
        {topNews.length > 0 && (
          <section className="mb-7">
            <SectionHeader icon={<Newspaper className="h-3.5 w-3.5" />} title="Market News" color="text-slate-500" />
            <div className="space-y-2">
              {topNews.map((n: any, i: number) => (
                <Link key={i} href={n.url || n.link || `/news/${n.id}`} target={n.url ? "_blank" : undefined}
                  className="flex items-start justify-between gap-3 rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3 hover:border-white/15 transition">
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold text-slate-200 line-clamp-2">{n.title || n.headline}</p>
                    <p className="mt-0.5 text-[10px] text-slate-600">{n.source ?? n.publisher} · {n.publishedAt ?? n.date ?? ""}</p>
                  </div>
                  <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-600" />
                </Link>
              ))}
            </div>
            <Link href="/news" className="mt-3 inline-block text-[11px] text-sky-400 hover:text-sky-300 transition">
              View all news →
            </Link>
          </section>
        )}

        {/* What to monitor */}
        {monitoring.length > 0 && (
          <section className="mb-7">
            <SectionHeader icon={null} title="What to Watch Today" color="text-slate-500" />
            <ul className="space-y-2">
              {monitoring.map((pt, i) => (
                <li key={i} className="flex items-start gap-2.5 text-[13px] text-slate-400">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500" />
                  {pt}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Companies to track */}
        {companies.length > 0 && (
          <section className="mb-7">
            <SectionHeader icon={null} title="Companies in Focus" color="text-slate-500" />
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {companies.slice(0, 6).map((c: any, i: number) => (
                <Link key={i} href={`/companies/${c.symbol}`}
                  className="flex flex-col gap-0.5 rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2.5 hover:border-white/15 transition">
                  <span className="text-[12px] font-bold text-sky-300">{c.symbol}</span>
                  <span className="text-[10px] text-slate-500 truncate">{c.name}</span>
                  <span className={`mt-1 text-[10px] font-semibold ${
                    c.stance === "Bullish" ? "text-emerald-400" :
                    c.stance === "Bearish" ? "text-rose-400" : "text-slate-500"
                  }`}>{c.stance ?? "Watch"}</span>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Footer CTA */}
        <div className="mt-8 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
          <p className="text-[13px] font-semibold text-white mb-3">Dig deeper with AI</p>
          <div className="flex flex-wrap gap-2">
            {[
              { label: "What should I buy today?", q: "What are the best stocks to buy in Indian market today?" },
              { label: "Market outlook this week", q: "What is the Indian stock market outlook for this week?" },
              { label: "Sectors to avoid", q: "Which sectors should Indian investors avoid right now and why?" },
            ].map(({ label, q }) => (
              <Link key={label} href={`/ai-search?q=${encodeURIComponent(q)}`}
                className="rounded-full border border-violet-500/25 bg-violet-500/[0.08] px-3 py-1.5 text-[11px] font-medium text-violet-300 hover:bg-violet-500/15 transition">
                {label} →
              </Link>
            ))}
          </div>
        </div>

      </div>
    </main>
  );
}
