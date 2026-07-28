import type { Metadata } from "next";
import Link from "next/link";
import { API_BASE_URL as API } from "@/lib/api";

/**
 * Comparisons hub — SEO roadmap, "surface comparison pages contextually,
 * not as a long undifferentiated list." Real published comparison_intelligence
 * articles, grouped two ways: Trending (real view counts, falls back to most
 * recent when nothing has real traffic yet) and Browse by Sector (real
 * sectors_affected on each article, from comparison_publisher.py). No
 * fabricated categories — a sector only appears here if a real published
 * comparison exists in it.
 */

export const metadata: Metadata = {
  title: "AI Company Comparisons — Trending & By Sector | MarketRipple",
  description: "Browse AI-generated, evidence-based comparisons between NSE-listed companies — trending pairs and comparisons organized by sector.",
};

interface ComparisonItem {
  slug: string; headline: string; executive_summary?: string; views?: number; published_at?: string;
  companies_affected: { name: string; symbol: string }[];
  sectors_affected: { name: string }[];
}

async function getComparisons(): Promise<ComparisonItem[]> {
  try {
    const res = await fetch(`${API}/api/insights/?article_type=comparison_intelligence&limit=100&sort_by=newest`, { next: { revalidate: 1800 } });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}

function Card({ it }: { it: ComparisonItem }) {
  const [a, b] = it.companies_affected ?? [];
  return (
    <Link href={`/research/${it.slug}`}
      className="group flex items-center justify-between rounded-[16px] border border-white/[0.08] bg-[#0c1422] px-5 py-3.5 transition hover:-translate-y-0.5 hover:border-violet-500/25">
      <span className="text-[13.5px] font-bold text-white">
        {a?.symbol ?? "?"} <span className="text-slate-500 font-medium">vs</span> {b?.symbol ?? "?"}
      </span>
      <span className="text-[11px] font-semibold text-violet-400 opacity-0 transition group-hover:opacity-100">Read →</span>
    </Link>
  );
}

export default async function ComparisonsHubPage() {
  const items = await getComparisons();

  const trending = [...items].sort((a, b) => (b.views ?? 0) - (a.views ?? 0)).slice(0, 6);

  const bySector: Record<string, ComparisonItem[]> = {};
  for (const it of items) {
    for (const s of it.sectors_affected ?? []) {
      if (!s.name) continue;
      (bySector[s.name] ??= []).push(it);
    }
  }
  const sectors = Object.entries(bySector).sort((a, b) => b[1].length - a[1].length);

  return (
    <main className="mx-auto max-w-[1100px] space-y-8 px-6 py-6 pb-16">
      <nav className="flex items-center gap-2 text-[12px] text-slate-500">
        <Link href="/research" className="hover:text-slate-300 transition">Research</Link>
        <span>/</span>
        <span className="text-slate-400">Comparisons</span>
      </nav>

      <div>
        <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-400">MarketRipple Research</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight text-white">AI Company Comparisons</h1>
        <p className="mt-1 text-sm text-slate-400">
          Real, evidence-based head-to-head comparisons between NSE-listed companies — generated and refreshed automatically as new events change the picture.
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
        <>
          {trending.length > 0 && (
            <section>
              <h2 className="mb-3 text-[13px] font-bold uppercase tracking-wide text-slate-400">🔥 Trending</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {trending.map((it) => <Card key={it.slug} it={it} />)}
              </div>
            </section>
          )}

          {sectors.length > 0 && (
            <section>
              <h2 className="mb-3 text-[13px] font-bold uppercase tracking-wide text-slate-400">Browse by Sector</h2>
              <div className="space-y-5">
                {sectors.map(([sector, list]) => (
                  <div key={sector}>
                    <p className="mb-2 text-[12px] font-semibold text-slate-300">{sector} <span className="text-slate-600">({list.length})</span></p>
                    <div className="grid gap-2.5 sm:grid-cols-2">
                      {list.slice(0, 6).map((it) => <Card key={it.slug} it={it} />)}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}
