import Link from "next/link";

interface NewsItem {
  id: string;
  headline: string;
  source: string;
  published_at?: string;
  publishedAt?: string;
  score: number;
}

interface LatestNewsProps {
  items: NewsItem[];
}

function scoreColor(score: number) {
  if (score >= 85) return "text-emerald-300 bg-emerald-500/10";
  if (score >= 70) return "text-sky-300 bg-sky-500/10";
  return "text-slate-300 bg-slate-700/50";
}

function thumbGrad(score: number) {
  if (score >= 90) return "from-sky-900/80 via-blue-900/60 to-slate-900";
  if (score >= 80) return "from-violet-900/80 via-indigo-900/60 to-slate-900";
  if (score >= 70) return "from-teal-900/80 via-cyan-900/60 to-slate-900";
  return "from-amber-900/80 via-orange-900/60 to-slate-900";
}

export function LatestNews({ items }: LatestNewsProps) {
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4 shadow-glow">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-white">Latest News</h2>
        <Link href="/news" className="text-xs text-slate-500 transition hover:text-white">View All</Link>
      </div>
      <div className="space-y-2">
        {items.map((item) => {
          const time = item.published_at ?? item.publishedAt ?? "";
          return (
            <Link key={item.id} href={`/news/${item.id}`}
              className="flex items-start gap-2.5 rounded-[14px] border border-white/5 bg-slate-950/60 p-2.5 transition hover:bg-slate-900/60 hover:border-white/10">
              <div className={`h-10 w-10 shrink-0 rounded-[10px] bg-gradient-to-br ${thumbGrad(item.score)} border border-white/5`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-white leading-snug line-clamp-2">{item.headline}</p>
                <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-slate-500">
                  <span>{time}</span>
                  <span>·</span>
                  <span>{item.source}</span>
                </div>
              </div>
              <div className={`flex h-8 min-w-[36px] shrink-0 items-center justify-center rounded-full px-2 text-xs font-bold ${scoreColor(item.score)}`}>
                {item.score}
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
