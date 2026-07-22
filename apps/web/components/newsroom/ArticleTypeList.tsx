import Link from "next/link";
import { ChevronRight, ChevronLeft, Clock } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

export interface InsightCard {
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
};

const PAGE_SIZE = 20;

async function fetchArticles(articleType: string, offset: number): Promise<{ items: InsightCard[]; total: number }> {
  try {
    const res = await fetch(
      `${API}/api/insights/?article_type=${articleType}&limit=${PAGE_SIZE}&offset=${offset}`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return { items: [], total: 0 };
    return res.json();
  } catch {
    return { items: [], total: 0 };
  }
}

function fmtDate(iso?: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/**
 * Shared list view for a single AIPE article_type — used by /newsroom/breaking
 * and /newsroom/companies (and any future type-filtered Newsroom section).
 * Same "view over one IntelligenceArticle model" principle as the rest of
 * the Newsroom: no separate content system per section.
 */
export async function ArticleTypeList({
  articleType, basePath, page, emptyText,
}: {
  articleType: string;
  basePath: string;
  page: number;
  emptyText: string;
}) {
  const offset = (page - 1) * PAGE_SIZE;
  const { items, total } = await fetchArticles(articleType, offset);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (items.length === 0) {
    return (
      <p className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-8 text-center text-[13px] text-slate-500">
        {emptyText}
      </p>
    );
  }

  return (
    <>
      <div className="space-y-3">
        {items.map((a) => (
          <Link
            key={a.slug}
            href={`/newsroom/article/${a.slug}`}
            className="group block rounded-xl border border-white/[0.07] bg-white/[0.03] p-5 transition-colors hover:border-white/20 hover:bg-white/[0.05]"
          >
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                {TYPE_LABEL[a.article_type] ?? "Intelligence"}
              </span>
              {a.published_at && (
                <span className="flex items-center gap-1 text-[10px] text-slate-600">
                  <Clock className="h-2.5 w-2.5" /> {fmtDate(a.published_at)}
                </span>
              )}
            </div>
            <h2 className="mt-2 text-[16px] font-bold leading-snug text-white group-hover:text-sky-200 transition">
              {cleanText(a.headline)}
            </h2>
            {(a.key_takeaway || a.executive_summary) && (
              <p className="mt-1.5 line-clamp-2 text-[13px] leading-5 text-slate-400">
                {cleanText(a.key_takeaway ?? a.executive_summary)}
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
            href={`${basePath}?page=${page - 1}`}
            aria-disabled={page <= 1}
            className={`flex items-center gap-1 rounded-full border px-4 py-2 text-[12px] font-medium transition ${
              page <= 1
                ? "pointer-events-none border-white/5 text-slate-700"
                : "border-white/10 bg-white/5 text-slate-300 hover:text-white"
            }`}
          >
            <ChevronLeft className="h-3.5 w-3.5" /> Previous
          </Link>
          <span className="text-[12px] text-slate-500">Page {page} of {totalPages}</span>
          <Link
            href={`${basePath}?page=${page + 1}`}
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
  );
}
