import type { Metadata } from "next";
import Link from "next/link";
import {
  Sparkles, TrendingUp, Building2, CalendarClock, Radio, ChevronRight, Clock,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

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
  companies_affected: { name: string; symbol: string; impact: string }[];
  published_at?: string;
}

interface OpportunityCard {
  id: number;
  slug: string;
  title: string;
  summary: string;
  opportunity_score: number;
  confidence: number;
  trend: string;
  risk_level: string;
  sectors: string[];
}

interface EventCard {
  id: string;
  title: string;
  summary: string;
  impact_score: number;
  sectors: string[];
  category: string;
  date: string;
}

interface NewsCard {
  id: string;
  headline: string;
  source: string;
  published_at: string;
  url?: string;
}

const TYPE_LABEL: Record<string, string> = {
  breaking_intelligence: "Breaking",
  morning_intelligence:  "Morning Brief",
  market_wrap:           "Market Wrap",
  company_intelligence:  "Company",
  theme_intelligence:    "Theme",
};

// ── Data fetching — parallel, each degrades to an empty array on failure so
// one slow/down endpoint never blanks the whole page. ───────────────────────

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
  const [brief, breaking, wrap, themes, companies, events, news] = await Promise.all([
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=morning_intelligence&limit=1", { items: [] }),
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=breaking_intelligence&limit=4", { items: [] }),
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=market_wrap&limit=1", { items: [] }),
    fetchJSON<{ items: OpportunityCard[] }>("/api/radar/?page=1&page_size=4", { items: [] }),
    fetchJSON<{ items: InsightCard[] }>("/api/insights/?article_type=company_intelligence&limit=4", { items: [] }),
    fetchJSON<EventCard[]>("/api/events/?limit=4&sort_by=impact_score", []),
    fetchJSON<NewsCard[]>("/api/news/", []),
  ]);

  return {
    hero: brief.items[0] ?? wrap.items[0] ?? null,
    breaking: breaking.items,
    themes: themes.items,
    companies: companies.items,
    events,
    news: news.slice(0, 6),
  };
}

// ── Page ──────────────────────────────────────────────────────────────────

export default async function NewsroomHomePage() {
  const { hero, breaking, themes, companies, events, news } = await getHomeData();

  return (
    <div className="mx-auto max-w-6xl space-y-10 px-4 py-8 sm:px-6">

      {/* Hero — Today's Market Brief */}
      <section>
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <Sparkles className="h-3 w-3 text-amber-400" /> Today&apos;s Market Brief
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
            <span className="mt-4 inline-flex items-center gap-1 text-[13px] font-medium text-sky-400">
              Read the full brief <ChevronRight className="h-3.5 w-3.5" />
            </span>
          </Link>
        ) : (
          <p className="mt-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6 text-[13px] text-slate-500">
            No brief published yet today — check back soon.
          </p>
        )}
      </section>

      {/* Breaking Intelligence */}
      <Section title="Breaking Intelligence" icon={<Radio className="h-3 w-3 text-rose-400" />} href="/newsroom/breaking">
        {breaking.length === 0 ? (
          <EmptyRow text="No breaking intelligence in the last cycle." />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {breaking.map((a) => (
              <ArticleCard key={a.slug} a={a} accent="rose" />
            ))}
          </div>
        )}
      </Section>

      {/* Themes to Watch — real opportunity scores, not AI narrative */}
      <Section title="Themes to Watch" icon={<TrendingUp className="h-3 w-3 text-emerald-400" />} href="/newsroom/themes">
        {themes.length === 0 ? (
          <EmptyRow text="No scored themes available right now." />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {themes.map((t) => (
              <Link
                key={t.id}
                href={`/newsroom/themes/${t.slug}`}
                className="block rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition hover:border-white/20 hover:bg-white/[0.05]"
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-[22px] font-black text-emerald-400">{Math.round(t.opportunity_score)}</span>
                  <span className="text-[10px] uppercase tracking-wider text-slate-500">{t.risk_level} risk</span>
                </div>
                <p className="mt-1 line-clamp-2 text-[13px] font-semibold text-white">{cleanText(t.title)}</p>
                {t.sectors.length > 0 && (
                  <p className="mt-1 text-[11px] text-slate-500">{t.sectors.slice(0, 2).join(" · ")}</p>
                )}
              </Link>
            ))}
          </div>
        )}
      </Section>

      {/* Companies in Focus */}
      <Section title="Companies in Focus" icon={<Building2 className="h-3 w-3 text-sky-400" />} href="/newsroom/companies">
        {companies.length === 0 ? (
          <EmptyRow text="No company intelligence published in the last cycle." />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {companies.map((a) => (
              <ArticleCard key={a.slug} a={a} accent="sky" />
            ))}
          </div>
        )}
      </Section>

      {/* Events Driving Markets */}
      <Section title="Events Driving Markets" icon={<CalendarClock className="h-3 w-3 text-indigo-400" />} href="/newsroom/events">
        {events.length === 0 ? (
          <EmptyRow text="No high-impact events right now." />
        ) : (
          <div className="space-y-2">
            {events.map((e) => (
              <div key={e.id} className="flex items-center justify-between rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
                <div className="min-w-0">
                  <p className="truncate text-[13.5px] font-semibold text-white">{cleanText(e.title)}</p>
                  <p className="mt-0.5 text-[11px] text-slate-500">{e.category} · impact {Math.round(e.impact_score)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Live Sources — supporting evidence, not AI narrative */}
      <Section title="Live Sources" icon={<Clock className="h-3 w-3 text-slate-400" />} href="/newsroom/sources">
        {news.length === 0 ? (
          <EmptyRow text="No live sources fetched right now." />
        ) : (
          <ul className="divide-y divide-white/[0.06] rounded-xl border border-white/[0.07] bg-white/[0.02]">
            {news.map((n) => (
              <li key={n.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                <span className="truncate text-[12.5px] text-slate-300">{n.headline}</span>
                {/* published_at from /api/news/ is already a formatted relative
                    string ("7m ago"), not ISO — do not re-parse it with Date(). */}
                <span className="shrink-0 text-[10.5px] text-slate-600">{n.source} · {n.published_at}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

    </div>
  );
}

// ── Small building blocks ────────────────────────────────────────────────────

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

function EmptyRow({ text }: { text: string }) {
  return (
    <p className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 text-[12.5px] text-slate-500">
      {text}
    </p>
  );
}

function ArticleCard({ a, accent }: { a: InsightCard; accent: "rose" | "sky" }) {
  const accentCls = accent === "rose"
    ? "border-rose-500/30 bg-rose-500/10 text-rose-400"
    : "border-sky-500/30 bg-sky-500/10 text-sky-400";
  return (
    <Link
      href={`/newsroom/article/${a.slug}`}
      className="group block rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition hover:border-white/20 hover:bg-white/[0.05]"
    >
      <span className={`rounded-full border px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider ${accentCls}`}>
        {TYPE_LABEL[a.article_type] ?? "Intelligence"}
      </span>
      <p className="mt-2 line-clamp-2 text-[13.5px] font-semibold leading-snug text-white group-hover:text-sky-200">
        {cleanText(a.headline)}
      </p>
      {a.companies_affected?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {a.companies_affected.slice(0, 3).map((c, i) => (
            <span key={i} className="rounded-full border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-400">
              {c.symbol}
            </span>
          ))}
        </div>
      )}
    </Link>
  );
}
