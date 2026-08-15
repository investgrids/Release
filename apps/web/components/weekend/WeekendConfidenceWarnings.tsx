import { ShieldQuestion } from "lucide-react";
import type { WeekendRisk } from "@/types/weekendIntelligence";

/**
 * "What Could Make This Outlook Wrong?" — brief §17. confidence_warnings
 * ONLY — these describe data/model quality (missing baseline, source
 * concentration, weak historical support), never the market itself.
 * Deliberately not labeled "Market Risks" (see WeekendRisks for those).
 * This is the section that builds trust by being honest about limits.
 */
export function WeekendConfidenceWarnings({ warnings }: { warnings: WeekendRisk[] }) {
  if (warnings.length === 0) return null;

  return (
    <section className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <h2 className="mb-3 text-[13px] font-black text-text-primary">What Could Make This Outlook Wrong?</h2>
      <ul className="space-y-2">
        {warnings.map((w, i) => (
          <li key={i} className="flex items-start gap-2.5">
            <ShieldQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" aria-hidden="true" />
            <p className="text-[11px] leading-relaxed text-text-muted">{w.description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
