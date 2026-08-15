import { FileCheck2 } from "lucide-react";
import type { WeekendEvidenceSummary as WeekendEvidenceSummaryDTO } from "@/types/weekendIntelligence";

const SOURCE_TYPE_LABEL: Record<string, string> = {
  event: "Events",
  policy: "Policies",
  announcement: "Company Announcements",
  news: "News",
  company_signal: "Company Signals",
  opportunity: "Opportunities",
};

/**
 * "Built From Verified Evidence" — brief §19. Deliberately NOT labeled
 * "unique developments": the backend's evidence_summary.total is the
 * RAW evidence-item count (evidence_refs length, pre-deduplication —
 * 600 in the real local dataset), not the deduplicated cluster count
 * (471 in the same dataset). The backend does not currently expose a
 * unique-development count anywhere in this API response, so this
 * label says "evidence items reviewed" rather than overclaiming
 * "unique developments" for a number that isn't actually deduplicated
 * — see final report's blocker note (§M) for the tiny backend addition
 * that would let this section say what the brief's example copy wants.
 */
export function WeekendEvidenceSummary({ summary }: { summary: WeekendEvidenceSummaryDTO }) {
  if (summary.total === 0) return null;
  const breakdown = Object.entries(summary.by_source_type).sort((a, b) => b[1] - a[1]);

  return (
    <section className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <div className="flex items-center gap-2">
        <FileCheck2 className="h-4 w-4 text-text-muted" aria-hidden="true" />
        <h2 className="text-[13px] font-black text-text-primary">Built From Verified Evidence</h2>
      </div>
      <p className="mt-2 text-[12px] font-bold text-text-primary">
        {summary.total.toLocaleString("en-IN")} evidence item{summary.total === 1 ? "" : "s"} reviewed
      </p>
      {breakdown.length > 0 && (
        <p className="mt-1 text-[10px] text-text-muted">
          {breakdown.map(([type, n]) => `${SOURCE_TYPE_LABEL[type] ?? type} (${n})`).join(" · ")}
        </p>
      )}
    </section>
  );
}
