import type { Metadata } from "next";
import Link from "next/link";
import { CalendarClock, Clock } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

export const metadata: Metadata = {
  title: "Event Intelligence | AI Newsroom",
  description: "AI analysis of policy moves, ripple effects, and opportunities driven by real events — why they matter and who's affected.",
  alternates: { canonical: "/newsroom/events" },
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
  policy_intelligence:      "Policy",
  ripple_intelligence:      "Ripple Effect",
  opportunity_intelligence: "Opportunity",
};

// Event Intelligence = AI narrative on event-driven developments — the
// AIPE article types that explain WHY an event matters, not the raw event
// feed itself (that's real_events on the Home page / Daily Brief, sourced
// from the Event table directly, a different real data layer).
const EVENT_TYPES = ["policy_intelligence", "ripple_intelligence", "opportunity_intelligence"];

async function fetchType(articleType: string): Promise<InsightCard[]> {
  try {
    const res = await fetch(`${API}/api/insights/?article_type=${articleType}&limit=10`, { next: { revalidate: 300 } });
    if (!res.ok) return [];
    const d = await res.json();
    return d.items ?? [];
  } catch {
    return [];
  }
}

async function getEventArticles(): Promise<InsightCard[]> {
  const lists = await Promise.all(EVENT_TYPES.map(fetchType));
  const merged = lists.flat();
  merged.sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? ""));
  return merged;
}

function fmtDate(iso?: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default async function EventIntelligencePage() {
  const articles = await getEventArticles();

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <CalendarClock className="h-3 w-3 text-indigo-400" /> AI Newsroom
        </p>
        <h1 className="mt-2 text-[26px] font-black leading-tight text-white md:text-[30px]">
          Event Intelligence
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-slate-400">
          AI analysis of policy moves, ripple effects, and opportunities driven by real events —
          why they matter and who's affected.
        </p>
      </div>

      {articles.length === 0 ? (
        <p className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-8 text-center text-[13px] text-slate-500">
          No event intelligence published in the last cycle — check back soon.
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
      )}
    </div>
  );
}
