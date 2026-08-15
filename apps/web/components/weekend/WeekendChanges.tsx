import { Newspaper } from "lucide-react";
import type { WeekendNewSinceCloseItem } from "@/types/weekendIntelligence";
import { sectorDirectionStyle } from "./weekendLabels";

const VISIBLE_LIMIT = 8;

const SOURCE_TYPE_LABEL: Record<string, string> = {
  event: "Event",
  policy: "Policy",
  announcement: "Announcement",
  news: "News",
  company_signal: "Company Signal",
  opportunity: "Opportunity",
};

/**
 * "What Changed Since Market Close" — brief §11, one of the most
 * important sections. Uses new_since_close (already materiality-
 * filtered by the backend), NOT changes_since_prior — see
 * WeekendChangesSincePrior for that separate, secondary concept.
 * Capped at 8 even though the backend may return more (real local data
 * returned 49 — this section shows the highest-value ones the backend
 * already ranked first, not all of them).
 */
export function WeekendChanges({ items, count }: { items: WeekendNewSinceCloseItem[]; count: number }) {
  if (items.length === 0) return null;
  const visible = items.slice(0, VISIBLE_LIMIT);

  return (
    <section className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-[13px] font-black text-text-primary">What Changed Since Market Close</h2>
        <span className="text-[10px] font-bold text-text-muted">{count} total</span>
      </div>
      <ul className="space-y-3">
        {visible.map((item, i) => {
          const style = sectorDirectionStyle(item.direction);
          const affected = [...item.sectors, ...item.companies].slice(0, 2).join(" · ");
          return (
            <li key={`${item.source_type}-${item.source_id}-${i}`} className="flex items-start gap-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-surface-border/10">
                <Newspaper className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-bold leading-snug text-text-primary line-clamp-2">{item.title}</p>
                <p className="mt-0.5 text-[10px] text-text-muted">
                  {SOURCE_TYPE_LABEL[item.source_type] ?? item.source_type}
                  {affected && ` · ${affected}`}
                </p>
              </div>
              <span className={`shrink-0 text-[11px] font-black ${style.textClass}`} aria-hidden="false">
                <span aria-hidden="true">{style.symbol}</span>
                <span className="sr-only"> {style.label}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
