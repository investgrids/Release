import type { Metadata } from "next";
import Link from "next/link";
import { Newspaper, ChevronRight, ChevronLeft, Clock } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

export const metadata: Metadata = {
  title: "Market Intelligence Insights | MarketRipple",
  description:
    "AI-generated market intelligence articles — what breaking news, policy moves, and earnings mean for Indian investors, with companies affected, risks, and what to watch next.",
  openGraph: {
    title: "Market Intelligence Insights | MarketRipple",
    description:
      "AI-generated market intelligence articles — what breaking news, policy moves, and earnings mean for Indian investors.",
    type: "website",
  },
  alternates: { canonical: "/insights" },
};

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
  breaking_intelligence:    "Breaking",
  morning_intelligence:     "Morning Brief",
  company_intelligence:     "Company",
  sector_intelligence:      "Sector",
  theme_intelligence:       "Theme",
  policy_intelligence:      "Policy",
  ripple_intelligence:      "Ripple",
  opportunity_intelligence: "Opportunity",
  market_wrap:              "Market Wrap",
  weekly_intelligence:      "Weekly",
  monthly_intelligence:     "Monthly",
  educational_intelligence: "Education",
};

const PAGE_SIZE = 20;

async function fetchInsights(offset: number): Promise<{ items: InsightCard[]; total: number }> {
  try {
    const res = await fetch(`${API}/api/insights/?limit=${PAGE_SIZE}&offset=${offset}`, { next: { revalidate: 300 } });
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

export default async function InsightsIndexPage(
  { searchParams }: { searchParams: Promise<{ page?: string }> }
) {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const offset = (page - 1) * PAGE_SIZE;

  const { items, total } = await fetchInsights(offset);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="min-h-screen bg-[#040810] text-white">
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">

        <div className="mb-8">
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <Newspaper className="h-3 w-3" /> Market Intelligence
          </p>
          <h1 className="mt-2 text-[28px] font-black leading-tight text-white md:text-[34px]">
            Insights
          </h1>
          <p className="mt-3 max-w-2xl text-[14px] leading-6 text-slate-400">
            AI-generated intelligence on what&apos;s moving Indian markets — what it means
            for investors, which companies are affected, and what to watch next.
          </p>
        </div>

        {items.length === 0 ? (
          <p className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-8 text-center text-[13px] text-slate-500">
            No published intelligence articles yet — check back soon.
          </p>
        ) : (
          <div className="space-y-3">
            {items.map((a) => (
              <Link
                key={a.slug}
                href={`/insights/${a.slug}`}
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
                  {a.headline}
                </h2>
                {(a.key_takeaway || a.executive_summary) && (
                  <p className="mt-1.5 line-clamp-2 text-[13px] leading-5 text-slate-400">
                    {a.key_takeaway ?? a.executive_summary}
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
        )}

        {totalPages > 1 && (
          <div className="mt-8 flex items-center justify-between">
            <Link
              href={`/insights?page=${page - 1}`}
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
              href={`/insights?page=${page + 1}`}
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

      </div>
    </main>
  );
}
