import Link from "next/link";
import { Target } from "lucide-react";

interface OpportunityRow {
  id: string;
  score: number | null;
  theme: string;
  reason: string;
  category: string;
  trend: "up" | "down" | "stable";
}

function TrendSparkline({ trend, seed }: { trend: string; seed: number }) {
  const up = trend === "up";
  const color = up ? "#22c55e" : trend === "down" ? "#f43f5e" : "#64748b";
  const pts: number[] = [];
  let v = 50;
  for (let i = 0; i < 8; i++) {
    v += Math.sin(seed + i * 0.9) * 5 + (up ? 2 : trend === "down" ? -2 : 0);
    v = Math.max(15, Math.min(85, v));
    pts.push(v);
  }
  const svgPts = pts.map((p, i) => `${(i / 7) * 48},${90 - p}`).join(" ");
  return (
    <svg viewBox="0 0 48 100" className="h-8 w-12 shrink-0" fill="none">
      <polyline points={svgPts} stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function ScoreCircle({ score }: { score: number | null | undefined }) {
  const unscored = score === null || score === undefined;
  const color = unscored ? "text-slate-500 ring-slate-700/30 bg-slate-800/20" :
    score >= 85 ? "text-emerald-300 ring-emerald-500/30 bg-emerald-500/10" :
    score >= 70 ? "text-sky-300 ring-sky-500/30 bg-sky-500/10" :
    "text-amber-300 ring-amber-500/30 bg-amber-500/10";
  return (
    <div className={`flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-full ring-1 ${color} text-[13px] font-black`}>
      {unscored ? <span className="text-[9px]">N/A</span> : score}
    </div>
  );
}

const LEVEL_LABEL: Record<number, string> = {};
function trendLabel(score: number | null | undefined) {
  if (score === null || score === undefined) return "Unscored";
  return score >= 85 ? "Very High" : score >= 70 ? "High" : "Medium";
}

export function AIOpportunitySection({ items }: { items: OpportunityRow[] }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-5 h-full">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-500/15">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5 text-violet-400">
              <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
              <line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/>
              <line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/>
            </svg>
          </div>
          <h2 className="text-[14px] font-bold text-white">AI Opportunity Radar</h2>
        </div>
        <Link href="/opportunity-radar" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>

      {/* Table header */}
      <div className="mb-2 grid grid-cols-[1fr_48px_52px] gap-3 border-b border-white/[0.06] pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
        <span>Opportunity</span>
        <span>Score</span>
        <span>Trend</span>
      </div>

      <div className="space-y-1.5">
        {items.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8">
            <Target className="h-8 w-8 text-slate-500 mb-2" />
            <p className="text-[12px] text-slate-500">No opportunities detected yet.</p>
          </div>
        )}
        {items.slice(0, 6).map((item, i) => (
          <Link
            key={item.id}
            href={`/opportunity-radar/${item.id}`}
            className="grid grid-cols-[1fr_48px_52px] items-center gap-3 rounded-2xl border border-white/[0.04] bg-white/[0.02] px-3 py-2.5 hover:border-violet-500/15 hover:bg-white/[0.04] transition"
          >
            <div className="min-w-0">
              <p className="text-[12px] font-semibold text-white line-clamp-1">{item.theme}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="rounded-full bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-slate-500">{item.category}</span>
                <span className={`text-[9px] font-medium ${item.score === null || item.score === undefined ? "text-slate-500" : item.score >= 85 ? "text-emerald-400" : item.score >= 70 ? "text-sky-400" : "text-amber-400"}`}>
                  {trendLabel(item.score)}
                </span>
              </div>
            </div>
            <ScoreCircle score={item.score}/>
            <TrendSparkline trend={item.trend} seed={i * 7.3}/>
          </Link>
        ))}
      </div>
    </div>
  );
}
