import type { Metadata } from "next";
import Link from "next/link";
import { Radio, Clock } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

export const metadata: Metadata = {
  title: "Breaking Intelligence | AI Newsroom",
  description: "Real-time AI analysis as market-moving developments happen.",
  alternates: { canonical: "/newsroom/breaking" },
};

interface InsightCard {
  slug: string;
  article_type: string;
  headline: string;
  key_takeaway?: string;
  executive_summary?: string;
  impact_score?: number;
  companies_affected: { name: string; symbol: string; impact: string }[];
  published_at?: string;
}

const TYPE_LABEL: Record<string, string> = {
  breaking_intelligence: "Breaking",
  sector_intelligence:   "Sector",
  ripple_intelligence:   "Ripple",
  company_intelligence:  "Company",
  policy_intelligence:   "Policy",
  opportunity_intelligence: "Opportunity",
};

// "Breaking" here means what actually happened in the AI pipeline: a
// literal breaking_intelligence article is one possible outcome, but a
// genuinely urgent event more often lands as a more specific type
// (sector/ripple/company/policy) since the classifier prefers the sharper
// category when one applies. Filtering this view to article_type ===
// "breaking_intelligence" alone left it empty even during real high-urgency
// news, because the urgent coverage existed under those other types instead.
//
// impact_score isn't a useful filter here — it's just urgency*10 and every
// event-driven article clears 60+ by construction (min_urgency=6 gates
// generation at all), so it doesn't separate "breaking" from routine. What
// actually makes something breaking is being event-driven AND recent — so
// this excludes the two scheduled digest types (morning brief / market
// wrap, which run on a clock, not a trigger) and shows the rest within a
// rolling window, newest first.
const BREAKING_WINDOW_HOURS = 12;
const DIGEST_TYPES = new Set(["morning_intelligence", "market_wrap"]);

async function getBreakingArticles(): Promise<InsightCard[]> {
  try {
    // Short window on purpose — this page is specifically about "what's
    // recent," so a 3-minute-stale cache showing a gap right as a real
    // burst of coverage lands (confirmed happening) undercuts the point.
    const res = await fetch(`${API}/api/insights/?limit=40`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    const d = await res.json();
    const items: InsightCard[] = d.items ?? [];
    const cutoff = Date.now() - BREAKING_WINDOW_HOURS * 3600_000;
    return items
      .filter((a) => !DIGEST_TYPES.has(a.article_type) && a.published_at && new Date(a.published_at).getTime() >= cutoff)
      .sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? ""));
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

export default async function BreakingIntelligencePage() {
  const articles = await getBreakingArticles();

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <Radio className="h-3 w-3 text-rose-400" /> AI Newsroom
        </p>
        <h1 className="mt-2 text-[26px] font-black leading-tight text-white md:text-[30px]">
          Breaking Intelligence
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-slate-400">
          High-impact AI analysis as market-moving developments happen — any article
          type, ranked by real impact, not just ones literally tagged &quot;breaking.&quot;
        </p>
      </div>

      {articles.length === 0 ? (
        <p className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-8 text-center text-[13px] text-slate-500">
          No high-impact intelligence in the last cycle — check back soon.
        </p>
      ) : (
        <div className="space-y-3">
          {articles.map((a) => (
            <Link
              key={a.slug}
              href={`/newsroom/article/${a.slug}`}
              className="group block rounded-xl border border-white/[0.07] bg-white/[0.03] p-5 transition-colors hover:border-white/20 hover:bg-white/[0.05]"
            >
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-400">
                  {TYPE_LABEL[a.article_type] ?? "Intelligence"}
                </span>
                {a.published_at && (
                  <span className="flex items-center gap-1 text-[10px] text-slate-600">
                    <Clock className="h-2.5 w-2.5" /> {fmtRelative(a.published_at)}
                  </span>
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
      )}
    </div>
  );
}
