import Link from "next/link";
import { fetchAPI } from "@/lib/api";

interface NewsArticle {
  id: string;
  headline: string;
  summary: string;
  source: string;
  published_at: string;
  companies: string[];
  impact_score: number;
  url?: string;
}

interface PageProps {
  params: Promise<{ id: string }>;
}

async function getArticle(id: string): Promise<NewsArticle | null> {
  try {
    return await fetchAPI<NewsArticle>(`/api/news/${id}`);
  } catch {
    return null;
  }
}

async function getAllNews(): Promise<NewsArticle[]> {
  try {
    return await fetchAPI<NewsArticle[]>("/api/news");
  } catch {
    return [];
  }
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
  if (score >= 9) return { label: "High Impact", color: "text-emerald-300 bg-emerald-500/10 border-emerald-500/20", bar: "from-emerald-500 to-teal-400" };
  if (score >= 7) return { label: "Medium Impact", color: "text-sky-300 bg-sky-500/10 border-sky-500/20", bar: "from-sky-500 to-cyan-400" };
  return { label: "Low Impact", color: "text-amber-300 bg-amber-500/10 border-amber-500/20", bar: "from-amber-500 to-yellow-400" };
}

const MARKET_CONTEXT: Record<string, { sectors: string[]; tags: string[] }> = {
  "nifty":    { sectors: ["Equity", "Index"], tags: ["Broad Market", "Technical"] },
  "sensex":   { sectors: ["Equity", "Index"], tags: ["Broad Market", "BSE"] },
  "rbi":      { sectors: ["Banking", "NBFC"], tags: ["Monetary Policy", "Rates"] },
  "sebi":     { sectors: ["Capital Markets"], tags: ["Regulation", "Compliance"] },
  "defence":  { sectors: ["Defence", "Aerospace"], tags: ["Government", "Capex"] },
  "inflation":{ sectors: ["All Sectors"], tags: ["Macro", "CPI", "WPI"] },
  "fii":      { sectors: ["Equity"], tags: ["Institutional Flow", "Global"] },
  "oil":      { sectors: ["Energy", "FMCG"], tags: ["Commodity", "Crude"] },
  "ipo":      { sectors: ["Capital Markets"], tags: ["Primary Market", "Listing"] },
  "results":  { sectors: ["Earnings"], tags: ["Quarterly", "Corporate"] },
  "profit":   { sectors: ["Earnings"], tags: ["Corporate Results"] },
};

function deriveContext(headline: string) {
  const h = headline.toLowerCase();
  for (const [kw, ctx] of Object.entries(MARKET_CONTEXT)) {
    if (h.includes(kw)) return ctx;
  }
  return { sectors: ["Indian Markets"], tags: ["Market News"] };
}

export default async function NewsDetailPage({ params }: PageProps) {
  const { id } = await params;
  const [article, allNews] = await Promise.all([getArticle(id), getAllNews()]);

  if (!article) {
    return (
      <main className="min-w-0 flex flex-col items-center justify-center gap-4 py-24 text-center">
        <span className="text-5xl">📰</span>
        <h1 className="text-2xl font-semibold text-white">Article not found</h1>
        <p className="text-slate-400">This article may have expired from the live feed.</p>
        <Link href="/news" className="mt-2 rounded-full bg-sky-500/15 px-5 py-2 text-sm text-sky-300 hover:bg-sky-500/25">
          ← Back to News
        </Link>
      </main>
    );
  }

  const imp = impactLabel(article.impact_score);
  const ctx = deriveContext(article.headline);
  const related = allNews.filter((a) => a.id !== article.id).slice(0, 4);

  return (
    <main className="min-w-0 space-y-6 pb-10">
      {/* Back */}
      <Link href="/news" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 transition">
        ← News
      </Link>

      {/* Main article card */}
      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6 shadow-glow backdrop-blur-xl">
        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full border px-3 py-0.5 text-[11px] font-medium ${imp.color}`}>
            {imp.label}
          </span>
          <span className={`text-sm font-semibold ${SOURCE_COLORS[article.source] ?? "text-slate-400"}`}>
            {article.source}
          </span>
          <span className="text-sm text-slate-600">{article.published_at}</span>
        </div>

        {/* Headline */}
        <h1 className="mt-4 text-2xl font-bold leading-snug text-white sm:text-3xl">
          {article.headline}
        </h1>

        {/* Impact score bar */}
        <div className="mt-5">
          <div className="mb-1.5 flex items-center justify-between text-xs text-slate-500">
            <span>Market Impact Score</span>
            <span className={`font-bold ${imp.color.split(" ")[0]}`}>{article.impact_score.toFixed(1)} / 10</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/5">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${imp.bar}`}
              style={{ width: `${(article.impact_score / 10) * 100}%` }}
            />
          </div>
        </div>

        {/* Summary */}
        <div className="mt-6 rounded-2xl border border-white/8 bg-white/[0.02] p-5">
          <p className="text-[11px] uppercase tracking-widest text-slate-500 mb-3">Summary</p>
          <p className="text-base leading-7 text-slate-200">{article.summary}</p>
        </div>

        {/* Companies mentioned */}
        {article.companies?.length > 0 && (
          <div className="mt-5">
            <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Companies Mentioned</p>
            <div className="flex flex-wrap gap-2">
              {article.companies.map((c) => (
                <Link key={c} href={`/stocks/${c.replace(/\s+/g, "").toUpperCase()}`}
                  className="rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-xs text-sky-300 transition hover:border-sky-500/40">
                  {c} →
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Market context tags */}
        <div className="mt-5">
          <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Market Context</p>
          <div className="flex flex-wrap gap-2">
            {ctx.sectors.map((s) => (
              <span key={s} className="rounded-full border border-violet-500/20 bg-violet-500/10 px-3 py-1 text-[11px] text-violet-300">{s}</span>
            ))}
            {ctx.tags.map((t) => (
              <span key={t} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-400">{t}</span>
            ))}
          </div>
        </div>

        {/* Read full article CTA */}
        {article.url && (
          <div className="mt-6">
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-2xl bg-sky-500/15 px-5 py-3 text-sm font-semibold text-sky-300 transition hover:bg-sky-500/25"
            >
              Read full article on {article.source}
              <span className="text-base">↗</span>
            </a>
          </div>
        )}
      </div>

      {/* Related news */}
      {related.length > 0 && (
        <div>
          <p className="mb-3 text-[10px] uppercase tracking-widest text-slate-500">More market news</p>
          <div className="grid gap-3 xl:grid-cols-2">
            {related.map((a) => {
              const ri = impactLabel(a.impact_score);
              return (
                <Link key={a.id} href={`/news/${a.id}`}
                  className="group rounded-[18px] border border-white/10 bg-white/[0.03] p-4 shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${ri.color}`}>
                      {ri.label}
                    </span>
                    <span className={`text-[11px] font-medium ${SOURCE_COLORS[a.source] ?? "text-slate-400"}`}>
                      {a.source}
                    </span>
                    <span className="text-[11px] text-slate-600">{a.published_at}</span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-white leading-snug group-hover:text-sky-300 transition line-clamp-2">
                    {a.headline}
                  </p>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </main>
  );
}
