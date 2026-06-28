import Link from "next/link";
import { fetchAPI } from "@/lib/api";

interface NewsArticle {
  id: string;
  headline: string;
  summary: string;
  source: string;
  published_at: string;
  publishedAt?: string;
  companies: string[];
  impact_score: number;
  url?: string;
}

async function getNews() {
  try { return await fetchAPI<NewsArticle[]>("/api/news"); }
  catch { return [] as NewsArticle[]; }
}

const SOURCE_COLORS: Record<string, string> = {
  "Economic Times":   "text-amber-300",
  "Business Standard":"text-sky-300",
  "LiveMint":         "text-emerald-300",
  "Reuters":          "text-violet-300",
  "Moneycontrol":     "text-blue-300",
  "Google News":      "text-rose-300",
  "Yahoo Finance":    "text-purple-300",
  "Mint":             "text-teal-300",
};

function impactLabel(score: number) {
  if (score >= 9) return { label: "High Impact", color: "text-emerald-300 bg-emerald-500/10 border-emerald-500/20" };
  if (score >= 7) return { label: "Medium Impact", color: "text-sky-300 bg-sky-500/10 border-sky-500/20" };
  return { label: "Low Impact", color: "text-amber-300 bg-amber-500/10 border-amber-500/20" };
}

export default async function NewsPage() {
  const articles = await getNews();
  const featured = articles[0];
  const rest = articles.slice(1);

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Newsboard</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Market News</h1>
          <p className="mt-1 text-sm text-slate-400">Live financial news from ET Markets, Moneycontrol &amp; Google News.</p>
        </div>
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.04] px-4 py-2">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[10px] text-emerald-300">Live · refreshes every 15 min</span>
        </div>
      </div>

      {/* Featured article */}
      {featured && (() => {
        const imp = impactLabel(featured.impact_score);
        const pub = featured.published_at ?? featured.publishedAt ?? "";
        return (
          <Link href={`/news/${featured.id}`}
            className="block rounded-[24px] border border-sky-500/20 bg-sky-500/[0.04] p-6 shadow-glow backdrop-blur-xl transition hover:border-sky-500/40 hover:bg-sky-500/[0.06]">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-0.5 text-xs font-medium text-sky-300">
                    Featured
                  </span>
                  <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${imp.color}`}>
                    {imp.label}
                  </span>
                  <span className={`text-[11px] font-medium ${SOURCE_COLORS[featured.source] ?? "text-slate-400"}`}>
                    {featured.source}
                  </span>
                  <span className="text-[11px] text-slate-600">{pub}</span>
                </div>
                <h2 className="mt-3 text-xl font-bold text-white leading-snug">{featured.headline}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">{featured.summary}</p>
                {featured.companies?.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {featured.companies.map((c) => (
                      <span key={c} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300">{c}</span>
                    ))}
                  </div>
                )}
                <p className="mt-4 text-xs text-sky-400">Read full story →</p>
              </div>
              <div className="text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-500/15 text-2xl font-black text-sky-300">
                  {featured.impact_score.toFixed(0)}
                </div>
                <p className="mt-1 text-[10px] text-slate-500">Score</p>
              </div>
            </div>
          </Link>
        );
      })()}

      {/* Rest of articles grid */}
      {rest.length > 0 ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {rest.map((a) => {
            const imp = impactLabel(a.impact_score);
            const pub = a.published_at ?? a.publishedAt ?? "";
            return (
              <Link key={a.id} href={`/news/${a.id}`}
                className="block rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${imp.color}`}>
                    {imp.label}
                  </span>
                  <span className={`text-[11px] font-medium ${SOURCE_COLORS[a.source] ?? "text-slate-400"}`}>
                    {a.source}
                  </span>
                  <span className="text-[11px] text-slate-600">{pub}</span>
                  <span className="ml-auto rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">
                    {a.impact_score.toFixed(1)}
                  </span>
                </div>
                <h3 className="mt-3 text-base font-semibold leading-snug text-white">{a.headline}</h3>
                <p className="mt-2 text-sm leading-5 text-slate-400 line-clamp-2">{a.summary}</p>
                {a.companies?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {a.companies.map((c) => (
                      <span key={c} className="rounded-full border border-white/8 bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">{c}</span>
                    ))}
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      ) : articles.length === 0 ? (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20">
          <p className="text-slate-500">Start the backend to load news.</p>
        </div>
      ) : null}
    </main>
  );
}
