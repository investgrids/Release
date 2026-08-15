import { AlertTriangle } from "lucide-react";
import type { WeekendRisk } from "@/types/weekendIntelligence";
import { severityStyle } from "./weekendLabels";

const VISIBLE_LIMIT = 5;

/**
 * "Key Risks For The Next Session" — brief §16. market_risks ONLY —
 * never mixed with confidence_warnings (see WeekendConfidenceWarnings
 * for those; the two are semantically different: this section is about
 * the MARKET, that one is about how much to trust this outlook).
 */
export function WeekendRisks({ risks }: { risks: WeekendRisk[] }) {
  if (risks.length === 0) return null;
  const visible = risks.slice(0, VISIBLE_LIMIT);

  return (
    <section className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <h2 className="mb-3 text-[13px] font-black text-text-primary">Key Risks For The Next Session</h2>
      <ul className="space-y-3">
        {visible.map((r, i) => {
          const sev = severityStyle(r.severity);
          const subject = r.related_sectors[0] ?? r.related_companies[0] ?? null;
          return (
            <li key={i} className="flex items-start gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-rose-500/10">
                <AlertTriangle className="h-3.5 w-3.5 text-rose-400" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                {subject && <p className="text-[11px] font-black text-text-primary">{subject}</p>}
                <p className="text-[11px] leading-relaxed text-text-secondary">{r.description}</p>
              </div>
              <span className={`shrink-0 text-[10px] font-black ${sev.textClass}`}>{sev.label}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
