"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { WeekendRisk } from "@/types/weekendIntelligence";
import { dedupeMarketRisks, severityStyle } from "./weekendLabels";

const VISIBLE_LIMIT = 4;

/**
 * "Key Risks For The Next Session" — market_risks ONLY — never mixed
 * with confidence_warnings (see WeekendConfidenceWarnings for those;
 * the two are semantically different: this section is about the
 * MARKET, that one is about how much to trust this outlook).
 *
 * Owner correction (2026-08-15): dedupeMarketRisks collapses sector-
 * level and company-level duplicates of the same real risk_type (e.g.
 * "finance: conflicting..." absorbs BAJFINANCE/LICHSGFIN/HDFCBANK's
 * individual entries of the same type) before capping to 4 — pure
 * frontend presentation logic, the real risk array is untouched.
 * "View All Risks" expands over that SAME deduped set, never
 * re-exposes the raw per-company duplicates dedup just removed.
 *
 * [contain:layout] below — defensive page-scroll leak fix, same class
 * of bug as WeekendChanges.tsx (see that file's comment for the full
 * diagnosis) — this card's default 4-item cap makes it low-risk today,
 * but "View All Risks" can render enough rows for the same leak once a
 * weekend produces many real risks.
 */
export function WeekendRisks({ risks }: { risks: WeekendRisk[] }) {
  const [expanded, setExpanded] = useState(false);
  if (risks.length === 0) return null;

  const deduped = dedupeMarketRisks(risks);
  const visible = expanded ? deduped : deduped.slice(0, VISIBLE_LIMIT);
  const hasMore = deduped.length > VISIBLE_LIMIT;

  return (
    <section className="flex min-h-[230px] max-h-[250px] flex-col overflow-hidden [contain:layout] rounded-2xl border border-surface-border/7 bg-surface-card p-5 shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]">
      <h2 className="mb-3 text-[13px] font-black text-text-primary">Key Risks For The Next Session</h2>
      <ul className="flex-1 space-y-3 overflow-y-auto">
        {visible.map((r, i) => {
          const sev = severityStyle(r.severity);
          const subject = r.related_sectors[0] ?? r.related_companies[0] ?? null;
          return (
            <li key={i} className="flex items-start gap-3">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-rose-500/10">
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
      {hasMore && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-3 w-fit rounded text-[11px] font-semibold text-violet-500 transition duration-200 hover:text-violet-400 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
        >
          {expanded ? "Show fewer" : "View All Risks"}
        </button>
      )}
    </section>
  );
}
