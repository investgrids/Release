import Link from "next/link";

interface OpportunityItem {
  id: string;
  score: number;
  theme: string;
  reason: string;
  category: string;
}

interface OpportunityRadarProps {
  items: OpportunityItem[];
}

function scoreBg(score: number) {
  if (score >= 80) return "from-emerald-500/30 to-sky-500/10 text-emerald-300";
  if (score >= 60) return "from-sky-500/30     to-sky-500/10 text-sky-300";
  return                   "from-amber-500/30   to-amber-500/10 text-amber-300";
}

export function OpportunityRadar({ items }: OpportunityRadarProps) {
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl h-full">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">✦</span>
          <h2 className="text-sm font-semibold text-white">Opportunity Radar</h2>
        </div>
        <Link href="/radar" className="text-xs text-slate-500 transition hover:text-white">
          View All
        </Link>
      </div>

      <div className="space-y-2.5">
        {items.length === 0 && (
          <p className="py-6 text-center text-sm text-slate-500">No opportunities yet</p>
        )}
        {items.map((item) => (
          <Link
            key={item.id}
            href={`/radar/${item.id}`}
            className="flex items-center gap-3 rounded-[16px] border border-white/5 bg-slate-950/60 p-3 hover:border-white/10 hover:bg-white/[0.03] transition"
          >
            <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] bg-gradient-to-br text-lg font-bold ${scoreBg(item.score)}`}>
              {item.score}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-white leading-snug line-clamp-1">{item.theme}</p>
              <p className="mt-0.5 text-[11px] text-slate-500 truncate">{item.reason}</p>
            </div>
            <span className="shrink-0 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">
              {item.category}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
