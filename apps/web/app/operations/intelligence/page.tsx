import type { Metadata } from "next";
import Link from "next/link";
import {
  Sparkles, ArrowRight, TrendingUp, TrendingDown, Minus, Radio, Clock,
  Zap, Layers, HelpCircle, Search as SearchIcon,
  History, GraduationCap, BarChart3,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { GLOSSARY } from "@/lib/glossary-data";
import { LiveTicker } from "./LiveTicker";
import { LoadMoreInsights } from "./LoadMoreInsights";
import { TYPE_LABEL, fmtRelative, sectorName, type FeedArticle } from "./shared";

export const metadata: Metadata = {
  title: "Market Intelligence — MarketRipple's AI Newsroom",
  description:
    "Every market-moving event, transformed into investor-ready intelligence within minutes. MarketRipple's AI continuously monitors, analyzes, and publishes investment intelligence — 24×7.",
  openGraph: {
    title: "Market Intelligence — MarketRipple's AI Newsroom",
    description: "Every market-moving event, transformed into investor-ready intelligence within minutes.",
    type: "website",
  },
  alternates: { canonical: "/operations/intelligence" },
};

/* ─── Types ─────────────────────────────────────────────── */
interface Campaign {
  event_group_id: string; headline: string; article_type: string;
  article_count: number; published_count: number; failed_count: number;
  created_at: string | null; last_updated: string | null;
  articles: { slug: string; headline: string; angle: string; angle_entity: string | null; status: string }[];
}
interface ThemeScore {
  theme: string; score: number; momentum: string;
  top_stocks: { sym: string; change_pct: number }[];
}
interface FeedItem {
  id: string; headline: string; priority_tier: string; direction: string; triaged_at: string;
}
interface HistoricalEvent {
  id: string; event_title: string; event_date: string | null; category: string;
  sentiment: string; sectors: string[]; nifty_1w: number | null; nifty_1m: number | null;
  opportunity_score: number | null; risk_score: number | null;
}

/* ─── Data fetching (server-side, parallel) ────────────────── */
async function safeJson<T>(url: string, revalidate: number, fallback: T): Promise<T> {
  try {
    const r = await fetch(url, { next: { revalidate } });
    if (!r.ok) return fallback;
    return (await r.json()) as T;
  } catch {
    return fallback;
  }
}

async function getPageData() {
  const [insights, campaigns, themes, feed, historical, questions, suggestions] = await Promise.all([
    safeJson<{ items: FeedArticle[]; total: number }>(`${API}/api/insights/?limit=60`, 90, { items: [], total: 0 }),
    safeJson<{ campaigns: Campaign[] }>(`${API}/api/publishing/campaigns?limit=6`, 90, { campaigns: [] }),
    safeJson<{ themes: ThemeScore[] }>(`${API}/api/intelligence/market/themes`, 180, { themes: [] }),
    safeJson<{ feed: FeedItem[] }>(`${API}/api/intelligence/market/feed?limit=10`, 60, { feed: [] }),
    safeJson<{ events: HistoricalEvent[] }>(`${API}/api/historical/all?limit=50`, 600, { events: [] }),
    safeJson<{ items: FeedArticle[]; total: number }>(`${API}/api/insights/?article_type=question_intelligence&limit=6`, 300, { items: [], total: 0 }),
    safeJson<{ trending: string[]; categories: string[] }>(`${API}/api/ai/suggestions`, 600, { trending: [], categories: [] }),
  ]);
  return { insights, campaigns, themes, feed, historical, questions, suggestions };
}

/* ─── Derivations ───────────────────────────────────────────── */
function pickFeatured(items: FeedArticle[]): FeedArticle | null {
  if (items.length === 0) return null;
  const primary = items.filter(a => a.angle === "primary" || !a.angle_entity);
  const pool = primary.length ? primary : items;
  return [...pool].sort((a, b) => (b.confidence_score ?? 0) - (a.confidence_score ?? 0))[0];
}

interface CompanyStat { symbol: string; name: string; count: number; latestReason: string; latestAt: string | null; impact: string }
function deriveCompanies(items: FeedArticle[]): CompanyStat[] {
  const map = new Map<string, CompanyStat>();
  for (const a of items) {
    for (const c of a.companies_affected ?? []) {
      if (!c.symbol) continue;
      const existing = map.get(c.symbol);
      if (existing) {
        existing.count += 1;
        if (!existing.latestAt || (a.published_at && a.published_at > existing.latestAt)) {
          existing.latestAt = a.published_at;
          existing.latestReason = c.reason || existing.latestReason;
          existing.impact = c.impact || existing.impact;
        }
      } else {
        map.set(c.symbol, {
          symbol: c.symbol, name: c.name, count: 1,
          latestReason: c.reason || "", latestAt: a.published_at, impact: c.impact || "neutral",
        });
      }
    }
  }
  return [...map.values()].sort((a, b) => b.count - a.count).slice(0, 8);
}

interface ThemeStat extends ThemeScore { articleCount: number; companyCount: number; latestAt: string | null }
function deriveThemes(themes: ThemeScore[], items: FeedArticle[]): ThemeStat[] {
  return themes.map(t => {
    const lower = t.theme.toLowerCase();
    const matches = items.filter(a =>
      (a.sectors_affected ?? []).some(s => sectorName(s).toLowerCase().includes(lower.split(" ")[0]) || lower.includes(sectorName(s).toLowerCase()))
    );
    const companies = new Set<string>();
    matches.forEach(a => (a.companies_affected ?? []).forEach(c => c.symbol && companies.add(c.symbol)));
    const latestAt = matches.reduce<string | null>((max, a) => (a.published_at && (!max || a.published_at > max) ? a.published_at : max), null);
    return { ...t, articleCount: matches.length, companyCount: companies.size, latestAt };
  }).sort((a, b) => b.score - a.score).slice(0, 8);
}

const IMPACT_COLOR: Record<string, string> = {
  positive: "text-emerald-400", negative: "text-rose-400", neutral: "text-slate-400",
};
const MOMENTUM_ICON: Record<string, typeof TrendingUp> = { rising: TrendingUp, falling: TrendingDown, stable: Minus };

function campaignStatus(c: Campaign): { label: string; cls: string } {
  if (c.failed_count > 0) return { label: "Partial", cls: "border-amber-500/25 bg-amber-500/10 text-amber-400" };
  if (c.published_count < c.article_count) return { label: "Generating", cls: "border-violet-500/25 bg-violet-500/10 text-violet-400" };
  return { label: "Generated", cls: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" };
}

/* ─── Small presentational bits ─────────────────────────────── */
function SectionHeader({ eyebrow, title, sub, href, cta }: { eyebrow: string; title: string; sub?: string; href?: string; cta?: string }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-violet-400">{eyebrow}</p>
        <h2 className="mt-2 text-[26px] font-black text-white sm:text-[32px] tracking-tight">{title}</h2>
        {sub && <p className="mt-2 max-w-2xl text-[14px] leading-6 text-slate-400">{sub}</p>}
      </div>
      {href && cta && (
        <Link href={href as any} className="group flex shrink-0 items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-[12px] font-semibold text-slate-300 transition hover:border-violet-500/40 hover:text-white">
          {cta} <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
        </Link>
      )}
    </div>
  );
}

function GlassCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-3xl border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl ${className}`}>
      {children}
    </div>
  );
}

/* ─── Page ──────────────────────────────────────────────────── */
export default async function MarketIntelligenceShowcase() {
  const { insights, campaigns, themes, feed, historical, questions, suggestions } = await getPageData();

  const featured = pickFeatured(insights.items);
  const rest = insights.items.filter(a => a.slug !== featured?.slug);
  const timelineArticles = rest.slice(0, 8);
  const feedInitial = rest.slice(8);
  const companies = deriveCompanies(insights.items);
  const themeStats = deriveThemes(themes.themes, insights.items);
  const verifiedHistory = historical.events
    .filter(e => e.nifty_1w != null || e.nifty_1m != null)
    .sort((a, b) => Math.abs(b.nifty_1m ?? b.nifty_1w ?? 0) - Math.abs(a.nifty_1m ?? a.nifty_1w ?? 0))
    .slice(0, 5);
  const guideSlugs = ["repo-rate", "cpi-inflation", "fii", "india-vix", "pe-ratio"];
  const guides = guideSlugs.map(s => GLOSSARY.find(g => g.slug === s)).filter(Boolean) as typeof GLOSSARY;
  const nextOffset = insights.items.length;

  return (
    <main className="min-h-screen bg-[#040711] text-white overflow-x-hidden">

      {/* ══════════════════════ HERO ══════════════════════ */}
      <section className="relative isolate overflow-hidden">
        {/* Ambient background: glow blobs + grid + particles */}
        <div className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute left-1/2 top-[-12rem] h-[36rem] w-[36rem] -translate-x-1/2 rounded-full bg-violet-600/25 blur-[120px]" />
          <div className="absolute right-[-8rem] top-[8rem] h-[28rem] w-[28rem] rounded-full bg-indigo-500/15 blur-[110px]" />
          <div className="absolute left-[-6rem] top-[16rem] h-[24rem] w-[24rem] rounded-full bg-emerald-500/10 blur-[100px]" />
          <div
            className="absolute inset-0 opacity-[0.07]"
            style={{
              backgroundImage:
                "linear-gradient(to right, rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.6) 1px, transparent 1px)",
              backgroundSize: "56px 56px",
              maskImage: "radial-gradient(ellipse 60% 50% at 50% 0%, black 40%, transparent 90%)",
            }}
          />
          {[...Array(14)].map((_, i) => (
            <span
              key={i}
              className="absolute h-1 w-1 rounded-full bg-violet-300/40 animate-pulse"
              style={{
                left: `${(i * 137) % 100}%`,
                top: `${(i * 71) % 80}%`,
                animationDelay: `${(i % 6) * 0.7}s`,
                animationDuration: `${3 + (i % 4)}s`,
              }}
            />
          ))}
        </div>

        <div className="mx-auto max-w-[1200px] px-6 pt-24 pb-16 text-center sm:pt-32 sm:pb-20">
          <div className="mb-6 flex flex-wrap items-center justify-center gap-2.5">
            <span className="flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-[11px] font-bold uppercase tracking-widest text-rose-400">
              <Radio className="h-3 w-3 animate-pulse" /> Live
            </span>
            <span className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] font-semibold text-slate-300">
              <Clock className="h-3 w-3" /> Updated just now
            </span>
            <span className="flex items-center gap-1.5 rounded-full border border-violet-500/25 bg-violet-500/10 px-3 py-1.5 text-[11px] font-semibold text-violet-300">
              <Sparkles className="h-3 w-3" /> AI Powered
            </span>
            <span className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] font-semibold text-slate-300">
              <Zap className="h-3 w-3" /> 24×7 Monitoring
            </span>
          </div>

          <h1 className="text-balance text-[42px] font-black leading-[1.05] tracking-tight text-white sm:text-[64px] lg:text-[76px]">
            Market Intelligence
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-balance text-[16px] leading-8 text-slate-400 sm:text-[19px]">
            Every market-moving event is transformed into investor-ready intelligence within minutes.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="#featured"
              className="rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 px-7 py-3.5 text-[14px] font-bold text-white shadow-[0_8px_30px_rgba(124,58,237,0.35)] transition hover:shadow-[0_8px_40px_rgba(124,58,237,0.5)] hover:-translate-y-0.5"
            >
              Explore Intelligence
            </Link>
            <Link
              href="#campaigns"
              className="rounded-full border border-white/15 bg-white/[0.04] px-7 py-3.5 text-[14px] font-semibold text-slate-200 backdrop-blur transition hover:border-white/30 hover:bg-white/[0.08]"
            >
              View Latest Campaign
            </Link>
          </div>
        </div>
      </section>

      {/* ══════════════════════ LIVE TICKER ══════════════════════ */}
      <LiveTicker initial={feed.feed} />

      <div className="mx-auto max-w-[1200px] px-6">

        {/* ══════════════════════ FEATURED INTELLIGENCE ══════════════════════ */}
        {featured && (
          <section id="featured" className="pt-20 sm:pt-24">
            <SectionHeader eyebrow="Today's Featured Intelligence" title="The story moving markets right now" />
            <Link href={`/newsroom/article/${featured.slug}` as any} className="group block">
              <GlassCard className="relative overflow-hidden p-8 transition hover:border-violet-500/30 sm:p-12">
                <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-violet-600/20 blur-[100px]" />
                <div className="relative grid grid-cols-1 gap-8 lg:grid-cols-[1fr_280px]">
                  <div>
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-slate-300">
                        {TYPE_LABEL[featured.article_type] ?? "Intelligence"}
                      </span>
                      <span className="text-[11px] text-slate-500">{fmtRelative(featured.published_at)}</span>
                      {featured.update_count > 0 && (
                        <span className="flex items-center gap-1 rounded-full border border-sky-500/25 bg-sky-500/10 px-2.5 py-1 text-[10px] font-bold text-sky-400">
                          Updated {featured.update_count}×
                        </span>
                      )}
                    </div>
                    <h3 className="mt-5 text-[26px] font-black leading-tight text-white sm:text-[36px] group-hover:text-violet-100 transition">
                      {featured.headline}
                    </h3>
                    {(featured.key_takeaway || featured.executive_summary) && (
                      <p className="mt-4 text-[15px] leading-7 text-slate-400 line-clamp-3">
                        {featured.key_takeaway ?? featured.executive_summary}
                      </p>
                    )}
                    {featured.companies_affected?.length > 0 && (
                      <div className="mt-6 flex flex-wrap gap-2">
                        {featured.companies_affected.slice(0, 6).map((c, i) => (
                          <span key={i} className={`rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] font-semibold ${IMPACT_COLOR[c.impact] ?? "text-slate-300"}`}>
                            {c.symbol}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="mt-7 flex items-center gap-1.5 text-[14px] font-bold text-violet-300 group-hover:text-violet-200">
                      Read Full Article <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
                    </div>
                  </div>

                  {featured.confidence_score != null && (
                    <div className="flex flex-col items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.02] p-6">
                      <div className="relative flex h-28 w-28 items-center justify-center">
                        <svg width={112} height={112} viewBox="0 0 112 112" className="-rotate-90">
                          <circle cx={56} cy={56} r={48} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={8} />
                          <circle
                            cx={56} cy={56} r={48} fill="none" stroke="url(#g)" strokeWidth={8} strokeLinecap="round"
                            strokeDasharray={`${2 * Math.PI * 48}`}
                            strokeDashoffset={`${2 * Math.PI * 48 * (1 - featured.confidence_score)}`}
                          />
                          <defs>
                            <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
                              <stop offset="0%" stopColor="#8b5cf6" />
                              <stop offset="100%" stopColor="#6366f1" />
                            </linearGradient>
                          </defs>
                        </svg>
                        <span className="absolute text-[22px] font-black text-white">{Math.round(featured.confidence_score * 100)}%</span>
                      </div>
                      <p className="mt-3 text-[11px] font-bold uppercase tracking-widest text-slate-500">AI Confidence</p>
                      {featured.sectors_affected?.length > 0 && (
                        <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                          {featured.sectors_affected.slice(0, 3).map((s, i) => (
                            <span key={i} className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">{sectorName(s)}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </GlassCard>
            </Link>
          </section>
        )}

        {/* ══════════════════════ TODAY'S CAMPAIGNS ══════════════════════ */}
        {campaigns.campaigns.length > 0 && (
          <section id="campaigns" className="pt-20 sm:pt-24">
            <SectionHeader
              eyebrow="Multi-Angle Coverage"
              title="Today's Campaigns"
              sub="One market event, analyzed from every angle — the primary story, per-company breakdowns, sector rollups, and the questions investors are asking."
            />
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {campaigns.campaigns.map(c => {
                const st = campaignStatus(c);
                const companySet = new Set(c.articles.filter(a => a.angle === "per_company" && a.angle_entity).map(a => a.angle_entity!));
                const themeSet = new Set(c.articles.filter(a => a.angle === "theme" || a.angle === "sector_rollup").map(a => a.angle_entity || "Theme"));
                const primary = c.articles.find(a => a.angle === "primary") ?? c.articles[0];
                return (
                  <GlassCard key={c.event_group_id} className="flex flex-col p-6 transition hover:border-violet-500/25">
                    <div className="flex items-start justify-between gap-3">
                      <Layers className="h-5 w-5 shrink-0 text-violet-400" />
                      <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${st.cls}`}>{st.label}</span>
                    </div>
                    <h3 className="mt-3 text-[16px] font-bold leading-snug text-white line-clamp-2">{c.headline}</h3>
                    <p className="mt-1.5 text-[11px] text-slate-500">{c.article_count} article{c.article_count !== 1 ? "s" : ""} generated</p>

                    {companySet.size > 0 && (
                      <div className="mt-4">
                        <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600 mb-1.5">Companies</p>
                        <div className="flex flex-wrap gap-1.5">
                          {[...companySet].slice(0, 5).map(sym => (
                            <span key={sym} className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-slate-300">{sym}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {themeSet.size > 0 && (
                      <div className="mt-3">
                        <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600 mb-1.5">Themes</p>
                        <div className="flex flex-wrap gap-1.5">
                          {[...themeSet].slice(0, 4).map(t => (
                            <span key={t} className="rounded-full border border-violet-500/20 bg-violet-500/[0.06] px-2 py-0.5 text-[10px] text-violet-300">{t}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {primary && (
                      <Link href={`/newsroom/article/${primary.slug}` as any} className="mt-5 flex items-center gap-1.5 text-[12px] font-bold text-violet-300 hover:text-violet-200 transition">
                        Explore Campaign <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    )}
                  </GlassCard>
                );
              })}
            </div>
          </section>
        )}

        {/* ══════════════════════ LATEST PUBLISHED ARTICLES (TIMELINE) ══════════════════════ */}
        {timelineArticles.length > 0 && (
          <section className="pt-20 sm:pt-24">
            <SectionHeader eyebrow="As It Happens" title="Latest Published Articles" href="/newsroom" cta="View all insights" />
            <div className="relative space-y-0">
              <div className="absolute left-[15px] top-2 bottom-2 w-px bg-gradient-to-b from-violet-500/40 via-white/10 to-transparent sm:left-[19px]" />
              {timelineArticles.map((a, i) => (
                <Link key={a.slug} href={`/newsroom/article/${a.slug}` as any} className="group relative flex gap-5 pb-7 last:pb-0">
                  <div className="relative z-10 mt-1.5 flex h-[30px] w-[30px] shrink-0 items-center justify-center sm:h-[38px] sm:w-[38px]">
                    <span className={`h-3 w-3 rounded-full ${a.update_count > 0 ? "bg-sky-400" : "bg-violet-400"} ring-4 ring-[#040711]`} />
                  </div>
                  <GlassCard className="flex-1 p-5 transition group-hover:border-white/20 group-hover:bg-white/[0.05]">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-400">
                        {TYPE_LABEL[a.article_type] ?? "Intelligence"}
                      </span>
                      <span className="text-[10px] text-slate-600">{fmtRelative(a.published_at)}</span>
                      {a.confidence_score != null && (
                        <span className="text-[10px] font-bold text-emerald-400">{Math.round(a.confidence_score * 100)}% confidence</span>
                      )}
                      {a.update_count > 0 && <span className="text-[10px] font-bold text-sky-400">Live · {a.update_count} updates</span>}
                    </div>
                    <h3 className="mt-2 text-[15px] font-bold leading-snug text-white group-hover:text-violet-100 transition">{a.headline}</h3>
                    {(a.key_takeaway || a.executive_summary) && (
                      <p className="mt-1.5 line-clamp-2 text-[12.5px] leading-6 text-slate-500">{a.key_takeaway ?? a.executive_summary}</p>
                    )}
                    {a.companies_affected?.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {a.companies_affected.slice(0, 4).map((c, ci) => (
                          <span key={ci} className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">{c.symbol}</span>
                        ))}
                      </div>
                    )}
                  </GlassCard>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* ══════════════════════ MARKET THEMES ══════════════════════ */}
        {themeStats.length > 0 && (
          <section className="pt-20 sm:pt-24">
            <SectionHeader eyebrow="Thematic Intelligence" title="Market Themes" href="/newsroom/themes" cta="Explore all themes" />
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {themeStats.map(t => {
                const Icon = MOMENTUM_ICON[t.momentum] ?? Minus;
                const momentumColor = t.momentum === "rising" ? "text-emerald-400" : t.momentum === "falling" ? "text-rose-400" : "text-slate-400";
                return (
                  <GlassCard key={t.theme} className="p-5 transition hover:border-violet-500/25">
                    <div className="flex items-center justify-between">
                      <span className="text-[14px] font-bold text-white">{t.theme}</span>
                      <Icon className={`h-4 w-4 ${momentumColor}`} />
                    </div>
                    <div className="mt-3 flex items-baseline gap-1.5">
                      <span className="text-[24px] font-black text-white">{t.score.toFixed(0)}</span>
                      <span className="text-[11px] text-slate-500">momentum score</span>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-500">
                      <span>{t.articleCount} article{t.articleCount !== 1 ? "s" : ""}</span>
                      <span>{t.companyCount} companies</span>
                    </div>
                    {t.top_stocks?.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {t.top_stocks.slice(0, 3).map(s => (
                          <span key={s.sym} className={`rounded-full bg-white/5 px-2 py-0.5 text-[10px] ${s.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            {s.sym} {s.change_pct >= 0 ? "+" : ""}{s.change_pct.toFixed(1)}%
                          </span>
                        ))}
                      </div>
                    )}
                    {t.latestAt && <p className="mt-3 text-[10px] text-slate-600">Updated {fmtRelative(t.latestAt)}</p>}
                  </GlassCard>
                );
              })}
            </div>
          </section>
        )}

        {/* ══════════════════════ TOP COMPANIES IN FOCUS ══════════════════════ */}
        {companies.length > 0 && (
          <section className="pt-20 sm:pt-24">
            <SectionHeader eyebrow="Company Coverage" title="Top Companies in Focus" sub="Companies MarketRipple's AI is actively tracking right now, ranked by intelligence coverage." />
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {companies.map(c => (
                <Link key={c.symbol} href={`/companies/${c.symbol}` as any} className="group">
                  <GlassCard className="h-full p-5 transition group-hover:border-violet-500/25 group-hover:bg-white/[0.05]">
                    <div className="flex items-center justify-between">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/20 to-indigo-500/20 text-[11px] font-black text-violet-300">
                        {c.symbol.slice(0, 2)}
                      </div>
                      <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-bold text-slate-400">
                        {c.count} article{c.count !== 1 ? "s" : ""}
                      </span>
                    </div>
                    <h3 className="mt-3 text-[14px] font-bold text-white group-hover:text-violet-100 transition">{c.name || c.symbol}</h3>
                    {c.latestReason && <p className="mt-1.5 line-clamp-2 text-[11.5px] leading-5 text-slate-500">{c.latestReason}</p>}
                    <div className="mt-3 flex items-center justify-between">
                      <span className={`text-[10px] font-bold ${IMPACT_COLOR[c.impact] ?? "text-slate-400"}`}>
                        {c.impact === "positive" ? "Bullish signal" : c.impact === "negative" ? "Bearish signal" : "Neutral"}
                      </span>
                      {c.latestAt && <span className="text-[10px] text-slate-600">{fmtRelative(c.latestAt)}</span>}
                    </div>
                  </GlassCard>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* ══════════════════════ HISTORICAL INTELLIGENCE ══════════════════════ */}
        {verifiedHistory.length > 0 && (
          <section className="pt-20 sm:pt-24">
            <SectionHeader eyebrow="Pattern Recognition" title="Learn From History" sub="Real, verified market events with measured outcomes — the evidence base MarketRipple's AI draws on before making a call." />
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {verifiedHistory.map(e => {
                const move = e.nifty_1m ?? e.nifty_1w ?? 0;
                return (
                  <GlassCard key={e.id} className="p-6 transition hover:border-emerald-500/20">
                    <div className="flex items-center gap-2">
                      <History className="h-4 w-4 text-amber-400" />
                      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{e.event_date ?? e.category}</span>
                    </div>
                    <h3 className="mt-3 text-[14px] font-bold leading-snug text-white line-clamp-2">{e.event_title}</h3>
                    <div className="mt-4 flex items-center gap-2">
                      <span className={`text-[22px] font-black ${move >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {move >= 0 ? "+" : ""}{move.toFixed(1)}%
                      </span>
                      <span className="text-[11px] text-slate-500">Nifty, {e.nifty_1m != null ? "1 month" : "1 week"} after</span>
                    </div>
                    {e.sectors?.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {e.sectors.slice(0, 3).map(s => (
                          <span key={s} className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">{s}</span>
                        ))}
                      </div>
                    )}
                  </GlassCard>
                );
              })}
            </div>
          </section>
        )}

        {/* ══════════════════════ BEGINNER'S GUIDES ══════════════════════ */}
        {guides.length > 0 && (
          <section className="pt-20 sm:pt-24">
            <SectionHeader eyebrow="MarketRipple Academy" title="Beginner's Guides" href="/learn/glossary" cta="Browse full glossary" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {guides.map(g => (
                <Link key={g.slug} href={`/learn/glossary/${g.slug}` as any} className="group">
                  <GlassCard className="h-full p-5 transition group-hover:border-white/20">
                    <GraduationCap className="h-5 w-5 text-sky-400" />
                    <h3 className="mt-3 text-[14px] font-bold text-white group-hover:text-sky-200 transition">{g.term}</h3>
                    <p className="mt-1.5 line-clamp-3 text-[11.5px] leading-5 text-slate-500">{g.shortDef}</p>
                  </GlassCard>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* ══════════════════════ PEOPLE ARE ASKING ══════════════════════ */}
        {questions.items.length > 0 && (
          <section className="pt-20 sm:pt-24">
            <SectionHeader eyebrow="Investor Questions" title="People Are Asking" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {questions.items.map(q => (
                <Link key={q.slug} href={`/newsroom/article/${q.slug}` as any} className="group">
                  <GlassCard className="h-full p-5 transition group-hover:border-violet-500/25">
                    <HelpCircle className="h-4 w-4 text-violet-400" />
                    <h3 className="mt-3 text-[14px] font-bold leading-snug text-white group-hover:text-violet-100 transition">{q.headline}</h3>
                    {q.key_takeaway && <p className="mt-1.5 line-clamp-2 text-[11.5px] leading-5 text-slate-500">{q.key_takeaway}</p>}
                  </GlassCard>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* ══════════════════════ TRENDING SEARCHES ══════════════════════ */}
        {suggestions.trending.length > 0 && (
          <section className="pt-20 sm:pt-24">
            <SectionHeader eyebrow="What Investors Search" title="Trending Searches" />
            <div className="flex flex-wrap gap-3">
              {suggestions.categories.map(cat => (
                <Link
                  key={cat}
                  href={`/ai-search?q=${encodeURIComponent(cat)}` as any}
                  className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-[13px] font-semibold text-slate-300 transition hover:border-violet-500/40 hover:bg-violet-500/[0.08] hover:text-violet-200"
                >
                  {cat}
                </Link>
              ))}
            </div>
            <div className="mt-5 space-y-2.5">
              {suggestions.trending.slice(0, 4).map(q => (
                <Link key={q} href={`/ai-search?q=${encodeURIComponent(q)}` as any} className="group flex items-center gap-2.5 text-[13px] text-slate-500 transition hover:text-white">
                  <SearchIcon className="h-3.5 w-3.5 shrink-0 text-slate-600 group-hover:text-violet-400" />
                  {q}
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* ══════════════════════ LATEST INSIGHTS (INFINITE FEED) ══════════════════════ */}
        <section className="pt-20 sm:pt-24">
          <SectionHeader eyebrow="The Full Feed" title="Latest Insights" sub="Every piece of intelligence MarketRipple's AI has published — newest first." />
          <LoadMoreInsights initialItems={feedInitial} startOffset={nextOffset} total={insights.total} />
        </section>

        {/* ══════════════════════ FOOTER CTA ══════════════════════ */}
        <section className="py-24 sm:py-28">
          <GlassCard className="relative overflow-hidden p-10 text-center sm:p-16">
            <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br from-violet-600/15 via-transparent to-indigo-600/15" />
            <BarChart3 className="mx-auto h-8 w-8 text-violet-400" />
            <h2 className="mt-5 text-[28px] font-black text-white sm:text-[36px]">Never miss market-moving intelligence.</h2>
            <p className="mx-auto mt-3 max-w-xl text-[14px] leading-6 text-slate-400">
              MarketRipple's AI is monitoring markets right now — every event, every ripple, analyzed the moment it happens.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link href="/newsroom" className="rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 px-7 py-3.5 text-[14px] font-bold text-white shadow-[0_8px_30px_rgba(124,58,237,0.35)] transition hover:-translate-y-0.5">
                Explore Today's Market Intelligence
              </Link>
              <Link href="/ai-search" className="flex items-center gap-1.5 rounded-full border border-white/15 bg-white/[0.04] px-7 py-3.5 text-[14px] font-semibold text-slate-200 transition hover:border-white/30">
                Search Any Company <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </GlassCard>
        </section>
      </div>
    </main>
  );
}
