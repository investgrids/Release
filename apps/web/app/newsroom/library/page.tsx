import type { Metadata } from "next";
import Link from "next/link";
import { BookOpen, Search, Clock, ChevronLeft, ChevronRight } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

export const metadata: Metadata = {
  title: "AI Intelligence Library",
  description: "The complete, searchable archive of every AI-generated market intelligence article — no raw feeds, no external content, just MarketRipple's own analysis.",
  alternates: { canonical: "/newsroom/library" },
};

interface InsightCard {
  slug: string;
  article_type: string;
  headline: string;
  key_takeaway?: string;
  executive_summary?: string;
  confidence_score?: number;
  read_time_minutes?: number;
  views?: number;
  companies_affected: { name: string; symbol: string; impact: string }[];
  published_at?: string;
}

interface LibraryStats {
  total_articles?: number;
  today_articles?: number;
  this_week_articles?: number;
  companies_covered?: number;
  events_covered?: number;
  themes_covered?: number;
  avg_confidence?: number | null;
  last_updated?: string | null;
}

const TYPE_LABEL: Record<string, string> = {
  breaking_intelligence: "Breaking",
  morning_intelligence:  "Morning Brief",
  market_wrap:           "Market Wrap",
  company_intelligence:  "Company",
  sector_intelligence:   "Sector",
  theme_intelligence:    "Theme",
  policy_intelligence:   "Policy",
  ripple_intelligence:   "Ripple",
  opportunity_intelligence: "Opportunity",
  question_intelligence: "Q&A",
  historical_intelligence: "Historical",
};

const PAGE_SIZE = 20;

async function fetchJSON<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API}${path}`, { next: { revalidate: 120 } });
    if (!res.ok) return fallback;
    return res.json();
  } catch {
    return fallback;
  }
}

function fmtRelative(iso?: string): string {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return `${Math.floor(mins / 1440)}d ago`;
}

export default async function LibraryPage(
  { searchParams }: { searchParams: Promise<{ page?: string }> }
) {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const offset = (page - 1) * PAGE_SIZE;

  const [stats, list] = await Promise.all([
    fetchJSON<LibraryStats>("/api/insights/stats", {}),
    fetchJSON<{ items: InsightCard[]; total: number }>(`/api/insights/?limit=${PAGE_SIZE}&offset=${offset}`, { items: [], total: 0 }),
  ]);

  const totalPages = Math.max(1, Math.ceil(list.total / PAGE_SIZE));

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">

      {/* Hero */}
      <div className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <BookOpen className="h-3 w-3 text-violet-400" /> AI Newsroom
        </p>
        <h1 className="mt-2 text-[28px] font-black leading-tight text-white md:text-[32px]">
          AI Intelligence Library
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-slate-400">
          AI-generated investment intelligence powered by MarketRipple. Every article here is
          written by our AI Publishing Engine from real market data — no raw news feeds, no
          syndicated content.
        </p>
        <form action="/search" method="get" className="mt-4 max-w-lg">
          <div className="flex items-center gap-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] px-3.5 py-2 focus-within:border-violet-500/40">
            <Search className="h-4 w-4 shrink-0 text-slate-500" />
            <input
              type="text"
              name="q"
              placeholder="Search companies, sectors, themes, articles…"
              className="flex-1 bg-transparent text-[13px] text-white outline-none placeholder:text-slate-500"
            />
          </div>
        </form>
      </div>

      {/* Real stats — every value a live query */}
      <div className="mb-10 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <StatTile label="Total AI Articles" value={stats.total_articles} />
        <StatTile label="Today's Articles" value={stats.today_articles} />
        <StatTile label="This Week" value={stats.this_week_articles} />
        <StatTile label="Companies Covered" value={stats.companies_covered} />
        <StatTile label="Events Covered" value={stats.events_covered} />
        <StatTile label="Themes Covered" value={stats.themes_covered} />
        <StatTile label="Avg AI Confidence" value={stats.avg_confidence != null ? `${Math.round(stats.avg_confidence * 100)}%` : undefined} />
      </div>
      {stats.last_updated && (
        <p className="-mt-8 mb-8 text-[11px] text-slate-500">Last updated {fmtRelative(stats.last_updated)}</p>
      )}

      {/* Article list — server-side paginated, 20/page */}
      {list.items.length === 0 ? (
        <p className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-8 text-center text-[13px] text-slate-500">
          No articles published yet — check back soon.
        </p>
      ) : (
        <>
          <div className="space-y-3">
            {list.items.map((a) => (
              <Link
                key={a.slug}
                href={`/newsroom/article/${a.slug}`}
                className="group block rounded-xl border border-white/[0.07] bg-white/[0.03] p-5 transition-colors hover:border-white/20 hover:bg-white/[0.05]"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    {TYPE_LABEL[a.article_type] ?? "Intelligence"}
                  </span>
                  {a.published_at && (
                    <span className="flex items-center gap-1 text-[10px] text-slate-600">
                      <Clock className="h-2.5 w-2.5" /> {fmtRelative(a.published_at)}
                    </span>
                  )}
                  {a.confidence_score != null && (
                    <span className="text-[10px] text-slate-600">{Math.round(a.confidence_score * 100)}% confidence</span>
                  )}
                  {a.read_time_minutes && (
                    <span className="text-[10px] text-slate-600">{a.read_time_minutes} min read</span>
                  )}
                </div>
                <h2 className="mt-2 text-[16px] font-bold leading-snug text-white group-hover:text-sky-200 transition">
                  {cleanText(a.headline)}
                </h2>
                {(a.key_takeaway || a.executive_summary) && (
                  <p className="mt-1.5 line-clamp-2 text-[13px] leading-5 text-slate-400">
                    {cleanText(a.key_takeaway ?? a.executive_summary ?? "")}
                  </p>
                )}
                {a.companies_affected?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {a.companies_affected.slice(0, 4).map((c, i) => (
                      <span key={i} className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">
                        {c.symbol}
                      </span>
                    ))}
                  </div>
                )}
              </Link>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="mt-8 flex items-center justify-between">
              <Link
                href={`/newsroom/library?page=${page - 1}`}
                aria-disabled={page <= 1}
                className={`flex items-center gap-1 rounded-full border px-4 py-2 text-[12px] font-medium transition ${
                  page <= 1
                    ? "pointer-events-none border-white/5 text-slate-700"
                    : "border-white/10 bg-white/5 text-slate-300 hover:text-white"
                }`}
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Previous
              </Link>
              <span className="text-[12px] text-slate-500">Page {page} of {totalPages} · {list.total} articles</span>
              <Link
                href={`/newsroom/library?page=${page + 1}`}
                aria-disabled={page >= totalPages}
                className={`flex items-center gap-1 rounded-full border px-4 py-2 text-[12px] font-medium transition ${
                  page >= totalPages
                    ? "pointer-events-none border-white/5 text-slate-700"
                    : "border-white/10 bg-white/5 text-slate-300 hover:text-white"
                }`}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatTile({ label, value }: { label: string; value?: number | string }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-3 py-2.5 text-center">
      <p className="text-[18px] font-black leading-none text-white">{value ?? "—"}</p>
      <p className="mt-1 text-[9px] uppercase tracking-wider text-slate-500">{label}</p>
    </div>
  );
}
