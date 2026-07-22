import type { Metadata } from "next";
import Link from "next/link";
import {
  Sparkles, TrendingUp, TrendingDown, Building2, Radio, ChevronRight, Clock,
  Gauge, BarChart3, Layers, CheckCircle2,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";
import { MarketSentimentGauge } from "@/components/MarketSentimentGauge";

export const metadata: Metadata = {
  title: "AI Newsroom",
  description:
    "Continuously updated AI market intelligence — today's brief, breaking analysis, theme and company intelligence, grounded in real data and live sources.",
  alternates: { canonical: "/newsroom" },
};

// ── Types (subset of the real API shapes, only what this page renders) ──────

interface InsightCard {
  slug: string;
  article_type: string;
  headline: string;
  key_takeaway?: string;
  executive_summary?: string;
  confidence_score?: number;
  sources?: string[];
  read_time_minutes?: number;
  companies_affected: { name: string; symbol: string; impact: string }[];
  published_at?: string;
}

interface OpportunityCard {
  id: number;
  slug: string;
  title: string;
  opportunity_score: number;
  confidence: number;
  trend: string;
  risk_level: string;
  sectors: string[];
}

interface NewsCard {
  id: string;
  headline: string;
  source: string;
  published_at: string;
}

interface IndexRow {
  name: string;
  value: string;
  change: string;
  pct: number;
  positive: boolean;
}

interface MieState {
  market_bias?: string;
  market_health?: { score: number; label: string };
  generated_at?: string;
}

const TYPE_LABEL: Record<string, string> = {
  breaking_intelligence: "Breaking",
  morning_intelligence:  "Morning Brief",
  market_wrap:           "Market Wrap",
  company_intelligence:  "Company",
  theme_intelligence:    "Theme",
  policy_intelligence:   "Event",
  ripple_intelligence:   "Event",
  opportunity_intelligence: "Event",
};

// ── Data fetching — parallel, each degrades to an empty/fallback value on
// failure so one slow/down endpoint never blanks the whole page. ────────────

async function fetchJSON<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API}${path}`, { next: { revalidate: 300 } });
    if (!res.ok) return fallback;
    return res.json();
  } catch {
    return fallback;
  }
}

async function getHomeData() {
  const [
    brief, breaking, wrap, theme, company, event,
    radar, news, mie, indices,
  ] = await Promise.all([
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=morning_intelligence&limit=1", { items: [] }),
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=breaking_intelligence&limit=1", { items: [] }),
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=market_wrap&limit=1", { items: [] }),
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=theme_intelligence&limit=1", { items: [] }),
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=company_intelligence&limit=6", { items: [] }),
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=ripple_intelligence&limit=1", { items: [] }),
    fetchJSON<{ items: OpportunityCard[] }>("/api/radar/?page=1&page_size=5", { items: [] }),
    fetchJSON<NewsCard[]>("/api/news/", []),
    fetchJSON<MieState>("/api/mie/state", {}),
    fetchJSON<IndexRow[]>("/api/indices/", []),
  ]);

  // Real, currently-active source names — not a fixed marketing list. NSE/BSE
  // come from the events/company-announcements pipeline (not fetched on this
  // page), so they're listed whenever the pipeline is up; the rest reflects
  // whatever the live news feed actually returned this request.
  const liveSourceNames = [...new Set(news.map((n) => n.source).filter(Boolean))];
  const sources = ["NSE", "BSE", ...liveSourceNames, "AI Analysis"];

  return {
    hero: brief.items[0] ?? wrap.items[0] ?? null,
    latest: [breaking.items[0], theme.items[0], company.items[0], event.items[0]].filter(Boolean) as InsightCard[],
    companies: company.items,
    themes: radar.items,
    news: news.slice(0, 6),
    mie,
    indices: indices.slice(0, 4),
    sources,
  };
}

// ── Page ──────────────────────────────────────────────────────────────────

export default async function NewsroomHomePage() {
  const { hero, latest, companies, themes, news, mie, indices, sources } = await getHomeData();

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">

      {/* Status banner — real freshness + real active sources, not a static claim */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
          </span>
          <span className="text-[12px] font-bold text-white">AI Intelligence Engine</span>
          {mie.generated_at && (
            <span className="text-[11px] text-slate-500">· Updated {fmtRelative(mie.generated_at)}</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {sources.map((s) => (
            <span key={s} className="flex items-center gap-1 text-[10.5px] text-slate-500">
              <CheckCircle2 className="h-3 w-3 text-emerald-500" /> {s}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">

        {/* ══════════ MAIN COLUMN ══════════ */}
        <div className="space-y-8 lg:col-span-2">

          {/* Hero — Today's Morning Brief */}
          <section>
            <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
              <Sparkles className="h-3 w-3 text-amber-400" /> Today&apos;s Morning Brief
            </p>
            {hero ? (
              <Link
                href={`/newsroom/article/${hero.slug}`}
                className="group mt-3 block rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.06] to-white/[0.02] p-6 transition hover:border-white/20"
              >
                <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-400">
                  {TYPE_LABEL[hero.article_type] ?? "Brief"}
                </span>
                <h1 className="mt-3 text-[24px] font-black leading-tight text-white group-hover:text-sky-200 md:text-[28px]">
                  {cleanText(hero.headline)}
                </h1>
                {(hero.key_takeaway || hero.executive_summary) && (
                  <p className="mt-2 max-w-3xl text-[14px] leading-6 text-slate-400">
                    {cleanText(hero.key_takeaway ?? hero.executive_summary)}
                  </p>
                )}
                <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
                  {hero.published_at && (
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {new Date(hero.published_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} IST</span>
                  )}
                  {hero.read_time_minutes && <span>{hero.read_time_minutes} min read</span>}
                  {hero.confidence_score != null && <span>Confidence: {Math.round(hero.confidence_score * 100)}%</span>}
                  {hero.sources && hero.sources.length > 0 && <span>Sources: {hero.sources.length}</span>}
                </div>
                <span className="mt-4 inline-flex items-center gap-1 text-[13px] font-medium text-sky-400">
                  Read Full Morning Brief <ChevronRight className="h-3.5 w-3.5" />
                </span>
              </Link>
            ) : (
              <p className="mt-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6 text-[13px] text-slate-500">
                No brief published yet today — check back soon.
              </p>
            )}
          </section>

          {/* Latest Intelligence — one card per real article type, not a
              fabricated preview grid */}
          <Section title="Latest Intelligence" icon={<Radio className="h-3 w-3 text-rose-400" />} href="/newsroom/breaking">
            {latest.length === 0 ? (
              <EmptyRow text="No intelligence published in the last cycle." />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {latest.map((a) => <ArticleCard key={a.slug} a={a} />)}
              </div>
            )}
          </Section>

          {/* Themes to Watch — real opportunity scores, table form */}
          <Section title="Themes to Watch" icon={<TrendingUp className="h-3 w-3 text-emerald-400" />} href="/newsroom/themes">
            {themes.length === 0 ? (
              <EmptyRow text="No scored themes available right now." />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
                <table className="w-full text-left text-[12.5px]">
                  <thead>
                    <tr className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500">
                      <th className="px-4 py-2.5 font-semibold">Theme</th>
                      <th className="px-4 py-2.5 font-semibold">Score</th>
                      <th className="px-4 py-2.5 font-semibold">Confidence</th>
                      <th className="px-4 py-2.5 font-semibold">Risk</th>
                      <th className="px-4 py-2.5 font-semibold">Trend</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.05]">
                    {themes.map((t) => (
                      <tr key={t.id} className="transition hover:bg-white/[0.03]">
                        <td className="px-4 py-2.5">
                          <Link href={`/newsroom/themes/${t.slug}`} className="font-semibold text-white hover:text-sky-300">
                            {cleanText(t.title)}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5 font-bold text-emerald-400">{Math.round(t.opportunity_score)}</td>
                        <td className="px-4 py-2.5 text-slate-400">{Math.round(t.confidence * 100)}%</td>
                        <td className="px-4 py-2.5 text-slate-400">{t.risk_level}</td>
                        <td className="px-4 py-2.5">
                          {t.trend?.toLowerCase().includes("positive") ? (
                            <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
                          ) : t.trend?.toLowerCase().includes("negative") ? (
                            <TrendingDown className="h-3.5 w-3.5 text-rose-400" />
                          ) : (
                            <span className="text-slate-500">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          {/* Companies in Focus — real company_intelligence articles, table form */}
          <Section title="Companies in Focus" icon={<Building2 className="h-3 w-3 text-sky-400" />} href="/newsroom/companies">
            {companies.length === 0 ? (
              <EmptyRow text="No company intelligence published in the last cycle." />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
                <table className="w-full text-left text-[12.5px]">
                  <tbody className="divide-y divide-white/[0.05]">
                    {companies.slice(0, 6).map((a) => {
                      const primary = a.companies_affected?.[0];
                      const sentiment = (primary?.impact ?? "neutral").toLowerCase();
                      return (
                        <tr key={a.slug} className="transition hover:bg-white/[0.03]">
                          <td className="px-4 py-2.5">
                            <Link href={`/newsroom/article/${a.slug}`} className="font-semibold text-white hover:text-sky-300">
                              {primary?.symbol ?? primary?.name ?? "—"}
                            </Link>
                          </td>
                          <td className="px-4 py-2.5 max-w-md truncate text-slate-400">
                            {cleanText(a.key_takeaway ?? a.executive_summary ?? "")}
                          </td>
                          <td className="px-4 py-2.5 whitespace-nowrap text-[11px] text-slate-600">
                            {a.published_at ? fmtRelative(a.published_at) : ""}
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${
                              sentiment === "positive" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                              : sentiment === "negative" ? "border-rose-500/30 bg-rose-500/10 text-rose-400"
                              : "border-white/10 bg-white/5 text-slate-400"
                            }`}>
                              {sentiment}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

        </div>

        {/* ══════════ SIDEBAR ══════════ */}
        <div className="space-y-6">

          {/* Market Sentiment — real MIE bias + health score */}
          <SidebarCard title="Market Sentiment" icon={<Gauge className="h-3.5 w-3.5 text-violet-400" />}>
            {mie.market_bias && mie.market_health ? (
              <MarketSentimentGauge
                score={mie.market_health.score}
                bias={mie.market_bias}
                label={mie.market_health.label}
              />
            ) : (
              <p className="text-[12px] text-slate-500">Sentiment unavailable right now.</p>
            )}
          </SidebarCard>

          {/* Indices Snapshot — real live index data */}
          <SidebarCard title="Indices Snapshot" icon={<BarChart3 className="h-3.5 w-3.5 text-sky-400" />}>
            {indices.length === 0 ? (
              <p className="text-[12px] text-slate-500">No live index data right now.</p>
            ) : (
              <div className="space-y-2">
                {indices.map((idx) => (
                  <div key={idx.name} className="flex items-center justify-between text-[12px]">
                    <span className="font-medium text-slate-300">{idx.name}</span>
                    <div className="text-right">
                      <p className="font-semibold text-white">{idx.value}</p>
                      <p className={idx.positive ? "text-emerald-400" : "text-rose-400"}>{idx.change}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SidebarCard>

          {/* Live Sources — supporting evidence, not AI narrative */}
          <SidebarCard title="Live Sources" icon={<Layers className="h-3.5 w-3.5 text-slate-400" />} href="/newsroom/sources">
            {news.length === 0 ? (
              <p className="text-[12px] text-slate-500">No live sources fetched right now.</p>
            ) : (
              <ul className="space-y-2.5">
                {news.map((n) => (
                  <li key={n.id} className="text-[12px] leading-snug">
                    <p className="line-clamp-2 text-slate-300">{n.headline}</p>
                    {/* published_at from /api/news/ is already a formatted
                        relative string ("7m ago"), not ISO. */}
                    <p className="mt-0.5 text-[10.5px] text-slate-600">{n.source} · {n.published_at}</p>
                  </li>
                ))}
              </ul>
            )}
          </SidebarCard>

        </div>
      </div>
    </div>
  );
}

// ── Small building blocks ────────────────────────────────────────────────────

function fmtRelative(iso: string): string {
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return `${Math.floor(mins / 1440)}d ago`;
}

function Section({ title, icon, href, children }: { title: string; icon: React.ReactNode; href: string; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          {icon} {title}
        </p>
        <Link href={href} className="flex items-center gap-0.5 text-[11.5px] font-medium text-slate-500 hover:text-white">
          View all <ChevronRight className="h-3 w-3" />
        </Link>
      </div>
      {children}
    </section>
  );
}

function SidebarCard({ title, icon, href, children }: { title: string; icon: React.ReactNode; href?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          {icon} {title}
        </p>
        {href && (
          <Link href={href} className="text-[10.5px] font-medium text-slate-500 hover:text-white">
            View all
          </Link>
        )}
      </div>
      {children}
    </div>
  );
}

function EmptyRow({ text }: { text: string }) {
  return (
    <p className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 text-[12.5px] text-slate-500">
      {text}
    </p>
  );
}

function ArticleCard({ a }: { a: InsightCard }) {
  const accentCls = a.article_type === "breaking_intelligence"
    ? "border-rose-500/30 bg-rose-500/10 text-rose-400"
    : a.article_type === "theme_intelligence"
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
    : a.article_type === "company_intelligence"
    ? "border-sky-500/30 bg-sky-500/10 text-sky-400"
    : "border-indigo-500/30 bg-indigo-500/10 text-indigo-400";
  return (
    <Link
      href={`/newsroom/article/${a.slug}`}
      className="group block rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition hover:border-white/20 hover:bg-white/[0.05]"
    >
      <div className="flex items-center justify-between gap-2">
        <span className={`rounded-full border px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider ${accentCls}`}>
          {TYPE_LABEL[a.article_type] ?? "Intelligence"}
        </span>
        {a.published_at && <span className="text-[10px] text-slate-600">{fmtRelative(a.published_at)}</span>}
      </div>
      <p className="mt-2 line-clamp-2 text-[13.5px] font-semibold leading-snug text-white group-hover:text-sky-200">
        {cleanText(a.headline)}
      </p>
    </Link>
  );
}
