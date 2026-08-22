"use client";

import { useState } from "react";
import { ShieldQuestion } from "lucide-react";
import type { WeekendRisk } from "@/types/weekendIntelligence";
import { simplifyConfidenceWarnings } from "./weekendLabels";

const VISIBLE_LIMIT = 4;

/**
 * "What Could Make This Outlook Wrong?" — confidence_warnings ONLY —
 * these describe data/model quality (missing baseline, source
 * concentration, weak historical support), never the market itself.
 * Deliberately not labeled "Market Risks" (see WeekendRisks for those).
 * This is the section that builds trust by being honest about limits.
 *
 * Owner correction (2026-08-15): simplifyConfidenceWarnings translates
 * every real risk_type into plain copy with no backend terminology
 * (clusters/source_type/synthesis) and collapses repeated per-company
 * "single source type" warnings into one generic line — pure frontend
 * presentation, the real warnings array is untouched. Capped at 4
 * visible; "See All Warnings" expands over that same simplified set.
 *
 * [contain:layout] below — defensive page-scroll leak fix, same class
 * of bug as WeekendChanges.tsx (see that file's comment for the full
 * diagnosis) — this card's default 4-item cap makes it low-risk today,
 * but "See All Warnings" can render enough rows for the same leak.
 */
export function WeekendConfidenceWarnings({ warnings }: { warnings: WeekendRisk[] }) {
  const [expanded, setExpanded] = useState(false);
  if (warnings.length === 0) return null;

  const simplified = simplifyConfidenceWarnings(warnings);
  const visible = expanded ? simplified : simplified.slice(0, VISIBLE_LIMIT);
  const hasMore = simplified.length > VISIBLE_LIMIT;

  return (
    <section className="flex min-h-[230px] max-h-[250px] flex-col overflow-hidden [contain:layout] rounded-2xl border border-surface-border/7 bg-surface-card p-5 shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]">
      <h2 className="mb-3 text-[13px] font-black text-text-primary">What Could Make This Outlook Wrong?</h2>
      <ul className="flex-1 space-y-2 overflow-y-auto">
        {visible.map((w, i) => (
          <li key={i} className="flex items-start gap-2.5">
            <ShieldQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" aria-hidden="true" />
            <p className="text-[11px] leading-relaxed text-text-muted">{w.description}</p>
          </li>
        ))}
      </ul>
      {hasMore && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-3 w-fit rounded text-[11px] font-semibold text-violet-500 transition duration-200 hover:text-violet-400 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
        >
          {expanded ? "Show fewer" : "See All Warnings"}
        </button>
      )}
    </section>
  );
}
