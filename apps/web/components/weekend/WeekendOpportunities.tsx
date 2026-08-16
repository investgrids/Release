import { Rocket } from "lucide-react";
import type { WeekendOpportunity } from "@/types/weekendIntelligence";

/**
 * "Potential Opportunities" — brief §15. Only rendered when the backend
 * actually returns opportunities (empty section is hidden entirely, not
 * shown as an empty card). The backend's opportunity_score is labeled
 * explicitly as "Opportunity Activity Score" — never "Success
 * Probability", since that is not what this number measures
 * (opportunity_generator's own count-based heuristic formula, per the
 * Phase 1B evidence-quality audit — not a win-probability model).
 */
export function WeekendOpportunities({ opportunities }: { opportunities: WeekendOpportunity[] }) {
  if (opportunities.length === 0) return null;

  return (
    <section className="rounded-2xl border border-surface-border/7 bg-surface-card p-5 shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]">
      <h2 className="mb-3 text-[13px] font-black text-text-primary">Potential Opportunities</h2>
      <ul className="space-y-3">
        {opportunities.slice(0, 5).map((o) => (
          <li key={o.id} className="flex items-start gap-3">
            <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-emerald-500/15">
              <Rocket className="h-4 w-4 text-emerald-400" aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[12px] font-bold leading-snug text-text-primary line-clamp-2">{o.title}</p>
              {o.sectors.length > 0 && (
                <p className="mt-0.5 text-[10px] text-text-muted">{o.sectors.slice(0, 3).join(" · ")}</p>
              )}
            </div>
            <div className="shrink-0 text-right">
              <span className="block rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-2 py-1 text-[11px] font-black tabular-nums text-emerald-400">
                {Math.round(o.opportunity_score)}
              </span>
              <span className="mt-0.5 block text-[8px] font-semibold uppercase tracking-wide text-text-muted">
                Opportunity Activity Score
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
