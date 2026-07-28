import type { Metadata } from "next";
import Link from "next/link";
import { API_BASE_URL as API } from "@/lib/api";

export const metadata: Metadata = {
  title: "Research — AI-Powered Company Comparisons | MarketRipple",
  description: "AI-generated, research-framed comparisons between NSE-listed companies — valuation, growth drivers, risks, and a research verdict for each pair.",
};

interface ResearchItem {
  slug: string; headline: string; executive_summary?: string;
  companies_affected: { name: string; symbol: string }[];
}

async function getResearch(): Promise<ResearchItem[]> {
  try {
    const res = await fetch(`${API}/api/insights/?article_type=comparison_intelligence&limit=100`, { next: { revalidate: 1800 } });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}

export default async function ResearchListPage() {
  const items = await getResearch();

  return (
    <main className="mx-auto max-w-[1100px] space-y-6 px-6 py-6 pb-16">
      <div>
        <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-400">MarketRipple Research</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight text-white">Company Comparisons</h1>
        <p className="mt-1 text-sm text-slate-400">
          AI-powered, evidence-based comparisons between NSE-listed companies — real dimension-by-dimension analysis, not a generic screener table.
        </p>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-[24px] border border-white/[0.08] bg-white/[0.02] py-20 text-center">
          <p className="text-base font-semibold text-white">No comparisons published yet</p>
          <p className="mt-1 text-sm text-slate-500">
            Try <Link href="/ai-search" className="text-violet-400 hover:text-violet-300">AI Search</Link> for a live, personalized comparison.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {items.map((it) => (
            <Link key={it.slug} href={`/research/${it.slug}`}
              className="group rounded-[20px] border border-white/[0.08] bg-[#0c1422] p-5 transition hover:-translate-y-0.5 hover:border-white/[0.15]">
              <p className="text-[15px] font-bold text-white">{it.headline}</p>
              {it.executive_summary && (
                <p className="mt-2 text-[12.5px] leading-relaxed text-slate-400 line-clamp-3">{it.executive_summary}</p>
              )}
              <span className="mt-3 inline-block text-[11px] font-semibold text-violet-400 opacity-0 transition group-hover:opacity-100">
                Read comparison →
              </span>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
