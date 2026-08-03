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
  if (score >= 85) return "text-emerald-600 dark:text-emerald-300 bg-emerald-500/10";
  if (score >= 70) return "text-sky-600 dark:text-sky-300 bg-sky-500/10";
  return "text-text-secondary bg-text-primary/[0.10]";
}

function thumbGrad(score: number) {
  if (score >= 90) return "from-sky-900/80 via-blue-900/60 to-slate-900";
  if (score >= 80) return "from-violet-900/80 via-indigo-900/60 to-slate-900";
  if (score >= 70) return "from-teal-900/80 via-cyan-900/60 to-slate-900";
  return "from-amber-900/80 via-orange-900/60 to-slate-900";
}

export function LatestNews({ items }: LatestNewsProps) {
  return (
    <section className="rounded-[24px] border border-surface-border/10 bg-text-primary/[0.03] p-4 shadow-glow">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary">Latest News</h2>
        <Link href="/news" className="text-xs text-text-muted transition hover:text-text-primary">View All</Link>
      </div>
      <div className="space-y-2">
        {items.map((item) => {
          const time = item.published_at ?? item.publishedAt ?? "";
          return (
            <Link key={item.id} href={`/news/${item.id}`}
              className="flex items-start gap-2.5 rounded-[14px] border border-surface-border/5 bg-bg/60 p-2.5 transition hover:bg-surface-card hover:border-surface-border/10">
              <div className={`h-10 w-10 shrink-0 rounded-[10px] bg-gradient-to-br ${thumbGrad(item.score)} border border-surface-border/5`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-text-primary leading-snug line-clamp-2">{item.headline}</p>
                <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-text-muted">
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
