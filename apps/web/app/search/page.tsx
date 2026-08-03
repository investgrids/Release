import type { Metadata } from "next";
import Link from "next/link";
import { Search, Clock, Sparkles } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText, isRealSymbol } from "@/lib/text";

export async function generateMetadata(
  { searchParams }: { searchParams: Promise<{ q?: string }> }
): Promise<Metadata> {
  const { q } = await searchParams;
  return {
    title: q ? `"${q}" — Search` : "Search",
    description: "Search MarketRipple's AI-generated market intelligence — articles, companies, sectors, and themes.",
  };
}

interface InsightCard {
  slug: string;
  article_type: string;
  headline: string;
  key_takeaway?: string;
  executive_summary?: string;
  companies_affected: { name: string; symbol: string; impact: string }[];
  published_at?: string;
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
};

async function searchArticles(q: string): Promise<InsightCard[]> {
  if (!q || q.trim().length < 2) return [];
  try {
    const res = await fetch(`${API}/api/insights/search?q=${encodeURIComponent(q)}&limit=30`, { cache: "no-store" });
    if (!res.ok) return [];
    const d = await res.json();
    return d.items ?? [];
  } catch {
    return [];
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

export default async function SearchPage(
  { searchParams }: { searchParams: Promise<{ q?: string }> }
) {
  const { q } = await searchParams;
  const query = (q ?? "").trim();
  const results = await searchArticles(query);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          <Search className="h-3 w-3 text-sky-400" /> Search
        </p>
        <h1 className="mt-2 text-[24px] font-black leading-tight text-text-primary md:text-[28px]">
          {query ? <>Results for &quot;{query}&quot;</> : "Search MarketRipple"}
        </h1>
        {query && (
          <p className="mt-2 text-[13px] text-text-muted">
            {results.length} {results.length === 1 ? "article" : "articles"} found across headlines,
            summaries, companies, sectors, and themes.
          </p>
        )}
      </div>

      {!query ? (
        <p className="rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-8 text-center text-[13px] text-text-muted">
          Type a company, sector, theme, or topic in the search bar above.
        </p>
      ) : results.length === 0 ? (
        <div className="rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-8 text-center">
          <p className="text-[13px] text-text-muted">No articles matched &quot;{query}&quot; yet.</p>
          <Link
            href={`/ai-search?q=${encodeURIComponent(query)}`}
            className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-accent-violet px-4 py-2 text-[12px] font-bold text-white transition hover:opacity-90"
          >
            <Sparkles className="h-3.5 w-3.5" /> Ask MarketRipple AI instead
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {results.map((a) => (
            <Link
              key={a.slug}
              href={`/newsroom/article/${a.slug}`}
              className="group block rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-5 transition-colors hover:border-surface-border/20 hover:bg-text-primary/[0.05]"
            >
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-surface-border/10 bg-text-primary/5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-text-secondary">
                  {TYPE_LABEL[a.article_type] ?? "Intelligence"}
                </span>
                {a.published_at && (
                  <span className="flex items-center gap-1 text-[10px] text-text-muted">
                    <Clock className="h-2.5 w-2.5" /> {fmtRelative(a.published_at)}
                  </span>
                )}
              </div>
              <h2 className="mt-2 text-[16px] font-bold leading-snug text-text-primary group-hover:text-sky-700 dark:text-sky-200 transition">
                {cleanText(a.headline)}
              </h2>
              {(a.key_takeaway || a.executive_summary) && (
                <p className="mt-1.5 line-clamp-2 text-[13px] leading-5 text-text-secondary">
                  {cleanText(a.key_takeaway ?? a.executive_summary ?? "")}
                </p>
              )}
              {a.companies_affected?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {a.companies_affected.filter(c => isRealSymbol(c.symbol)).slice(0, 4).map((c, i) => (
                    <span key={i} className="rounded-full border border-surface-border/10 bg-text-primary/5 px-2 py-0.5 text-[10px] text-text-secondary">
                      {c.symbol}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
