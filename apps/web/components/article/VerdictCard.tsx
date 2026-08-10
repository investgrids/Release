import { TrendingUp, TrendingDown, Activity, ChevronRight } from "lucide-react";

// Light-first, matching Daily Brief's own market-verdict card exactly
// (apps/web/app/newsroom/daily-brief/page.tsx DIRECTION_META) — same
// token pattern (colored border/bg/text triplet with a dark: pair),
// reused rather than re-invented for the article page's own verdict,
// which is a real aggregate of this article's own company/sector impact
// calls (see deriveVerdict in the article page), never a fabricated
// buy/sell rating.
const STANCE_META: Record<string, { label: string; color: string; icon: typeof TrendingUp }> = {
  Bullish: { label: "Bullish", color: "text-emerald-600 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20", icon: TrendingUp },
  Bearish: { label: "Bearish", color: "text-rose-600 dark:text-rose-300 bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20", icon: TrendingDown },
  Mixed:   { label: "Mixed",   color: "text-amber-600 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20", icon: Activity },
  Neutral: { label: "Neutral", color: "text-amber-600 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20", icon: Activity },
};

export interface VerdictCardProps {
  stance: "Bullish" | "Bearish" | "Mixed" | "Neutral";
  focus: string | null;
  confidenceScore?: number | null;
  horizons: string[];
  topAction: { title: string; description: string } | null;
  whyAffected: string[];
}

export function VerdictCard({ stance, focus, confidenceScore, horizons, topAction, whyAffected }: VerdictCardProps) {
  const meta = STANCE_META[stance] ?? STANCE_META.Neutral;
  const Icon = meta.icon;

  return (
    <div className={`rounded-2xl border p-5 ${meta.color}`}>
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-bold uppercase tracking-wide opacity-80">AI Investment Verdict</p>
        {confidenceScore != null && (
          <span className="text-[11px] font-bold tabular-nums opacity-90" title="The AI's own confidence in this article's analysis.">
            {Math.round(confidenceScore * 100)}% confidence
          </span>
        )}
      </div>
      <div className="mt-2 flex items-center gap-2">
        <Icon className="h-6 w-6" />
        <p className="text-[22px] font-black">{meta.label}</p>
      </div>
      {focus && (
        <p className="mt-1.5 text-[12.5px] leading-relaxed opacity-90">
          Current view: <span className="font-semibold">{meta.label} on {focus}</span>
        </p>
      )}

      {horizons.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {horizons.map(h => (
            <span key={h} className="rounded-full border border-current/20 bg-white/40 px-2.5 py-0.5 text-[10.5px] font-semibold dark:bg-black/10">{h}</span>
          ))}
        </div>
      )}

      {topAction && (
        <div className="mt-4 border-t border-current/15 pt-4">
          <p className="mb-1 text-[10px] font-bold uppercase tracking-wide opacity-70">Action</p>
          <p className="text-[13.5px] font-bold">{topAction.title}</p>
          <p className="mt-1 text-[12px] leading-5 opacity-90">{topAction.description}</p>
        </div>
      )}

      {whyAffected.length > 0 && (
        <div className="mt-4 border-t border-current/15 pt-4">
          <p className="mb-1.5 text-[10px] font-bold uppercase tracking-wide opacity-70">Why These Are Affected</p>
          <ul className="space-y-1">
            {whyAffected.slice(0, 3).map((r, i) => (
              <li key={i} className="flex items-start gap-1.5 text-[12px] leading-5 opacity-90">
                <ChevronRight className="mt-0.5 h-3 w-3 shrink-0" /> {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
