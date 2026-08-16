import { CalendarClock, CircleCheck, CircleAlert, History, Layers } from "lucide-react";
import type { WeekendIntelligenceSnapshotDTO } from "@/types/weekendIntelligence";
import { baselineLabel, dataWindowLabel, formatDateFromISO, formatTimeIST } from "./weekendLabels";

const STATUS_LABEL: Record<string, { label: string; className: string; icon: typeof CircleCheck }> = {
  ok: { label: "Live", className: "text-emerald-500", icon: CircleCheck },
  degraded: { label: "Degraded", className: "text-amber-500", icon: CircleAlert },
  insufficient_evidence: { label: "Building", className: "text-text-muted", icon: CircleAlert },
};

/**
 * Compact status strip — redesign brief §7/§26: a quiet, always-visible
 * summary of what this snapshot is anchored to and how fresh/trustworthy
 * it is, WITHOUT a giant warning banner. Snapshot version is shown (the
 * brief says only if user-useful; kept small/secondary here — it lets a
 * user notice "this updated" across a weekend without exposing a raw
 * snapshot ID). No internal IDs are ever rendered.
 */
export function WeekendMetadataStrip({ snapshot }: { snapshot: WeekendIntelligenceSnapshotDTO }) {
  const status = STATUS_LABEL[snapshot.status] ?? STATUS_LABEL.degraded;
  const StatusIcon = status.icon;
  const generatedDate = formatDateFromISO(snapshot.generated_at);
  const generatedTime = formatTimeIST(snapshot.generated_at);

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1.5 rounded-xl border border-surface-border/7 bg-surface-card px-4 py-3 text-[12px] sm:px-5">
      <span className="flex items-center gap-1.5 text-text-muted">
        <CalendarClock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        Baseline (Market Close): <span className="font-semibold text-text-primary">{baselineLabel(snapshot.last_trading_date)}</span>
      </span>
      <span className="flex items-center gap-1.5 text-text-muted">
        <History className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        Data Window: <span className="font-semibold text-text-primary">{dataWindowLabel(snapshot.last_trading_date, snapshot.generated_at)}</span>
      </span>
      <span className="flex items-center gap-1.5 text-text-muted">
        <Layers className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        Snapshot Version:{" "}
        <span className="font-semibold text-text-primary">
          v{snapshot.version}
          {generatedDate && generatedTime && ` (${generatedDate}, ${generatedTime})`}
        </span>
        {/* GET /current is, by definition, always the current snapshot —
            "Latest" is implied by which endpoint returned this data, not
            a separate field the backend needs to add. */}
        <span className="rounded-full bg-violet-500/10 px-2 py-0.5 text-[10px] font-bold text-violet-600">Latest</span>
      </span>
      <span className={`ml-auto flex items-center gap-1.5 text-text-muted`}>
        <StatusIcon className={`h-3.5 w-3.5 shrink-0 ${status.className}`} aria-hidden="true" />
        Status: <span className={`font-semibold ${status.className}`}>{status.label}</span>
      </span>
    </div>
  );
}
