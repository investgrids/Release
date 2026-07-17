"use client";

import { useState, useEffect } from "react";
import { ClipboardList, Loader2, RefreshCw, ChevronRight } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ChecklistImportance = "critical" | "high" | "medium";
export type ChecklistStatus     = "pending" | "watch" | "ok";

export interface ChecklistItem {
  label:          string;
  status?:        ChecklistStatus;
  importance?:    ChecklistImportance;
  /** @deprecated use importance */
  priority?:      ChecklistImportance;
  why_it_matters?: string;
  frequency?:     string;
}

export type MonitoringChecklistEntityType =
  | "event" | "company" | "story" | "opportunity" | "ripple" | "search";

export interface MonitoringChecklistProps {
  items?:            ChecklistItem[];
  entityType?:       MonitoringChecklistEntityType;
  entityId?:         string;
  entityTitle?:      string;
  entityDescription?: string;
  entitySector?:     string;
}

// ── Styles ────────────────────────────────────────────────────────────────────

const IMP_STYLES: Record<ChecklistImportance, { dot: string; badge: string }> = {
  critical: {
    dot:   "bg-rose-400",
    badge: "text-rose-400 border-rose-500/30 bg-rose-500/10",
  },
  high: {
    dot:   "bg-amber-400",
    badge: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  },
  medium: {
    dot:   "bg-sky-400",
    badge: "text-sky-400 border-sky-500/30 bg-sky-500/10",
  },
};

const STATUS_STYLES: Record<ChecklistStatus, string> = {
  pending: "text-slate-400",
  watch:   "text-amber-400",
  ok:      "text-emerald-400",
};

const STATUS_DOT: Record<ChecklistStatus, string> = {
  pending: "bg-slate-600",
  watch:   "bg-amber-400 animate-pulse",
  ok:      "bg-emerald-400",
};

// ── Skeleton ─────────────────────────────────────────────────────────────────

function Skel({ w }: { w: string }) {
  return <span className={`inline-block h-2.5 rounded ${w} bg-white/[0.06] animate-pulse`} />;
}

// ── Main Component ────────────────────────────────────────────────────────────

export function MonitoringChecklist({
  items: staticItems,
  entityType,
  entityId,
  entityTitle,
  entityDescription,
  entitySector,
}: MonitoringChecklistProps) {
  const [checked,  setChecked]  = useState<number[]>([]);
  const [expanded, setExpanded] = useState<number[]>([]);
  const [fetched,  setFetched]  = useState<ChecklistItem[] | null>(null);
  const [loading,  setLoading]  = useState(false);

  useEffect(() => {
    if (!entityType || !entityId) return;
    setLoading(true);
    const params = new URLSearchParams();
    if (entityTitle)       params.set("title",       entityTitle.slice(0, 200));
    if (entityDescription) params.set("description", entityDescription.slice(0, 800));
    if (entitySector)      params.set("sector",      entitySector.slice(0, 100));

    fetch(`${API}/api/checklist/${entityType}/${encodeURIComponent(entityId)}?${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.items) setFetched(d.items);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [entityType, entityId, entityTitle, entityDescription, entitySector]);

  const items = staticItems?.length ? staticItems : (fetched ?? []);

  const toggle = (i: number) =>
    setChecked(p => p.includes(i) ? p.filter(x => x !== i) : [...p, i]);

  const toggleExpand = (i: number) =>
    setExpanded(p => p.includes(i) ? p.filter(x => x !== i) : [...p, i]);

  const doneCount = checked.length;

  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.025] p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-sky-500/[0.08] border border-sky-500/20">
            <ClipboardList className="h-3.5 w-3.5 text-sky-400" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
            Monitoring Checklist
          </span>
        </div>
        <div className="flex items-center gap-2">
          {loading && <Loader2 className="h-3 w-3 text-slate-600 animate-spin" />}
          {items.length > 0 && (
            <span className="text-[10px] text-slate-600">
              {doneCount}/{items.length} done
            </span>
          )}
        </div>
      </div>

      {/* Loading skeleton */}
      {loading && !items.length && (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 rounded-[14px] border border-white/[0.05] px-3 py-2.5">
              <span className="h-4 w-4 shrink-0 rounded border border-white/20 bg-white/[0.03]" />
              <span className="h-2 w-2 shrink-0 rounded-full bg-white/10" />
              <Skel w={`w-${["48", "40", "56", "44", "52"][i % 5]}`} />
            </div>
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && items.length === 0 && (
        <p className="text-[12px] text-slate-400 leading-5">No data available</p>
      )}

      {/* List */}
      {items.length > 0 && (
        <ul className="space-y-2">
          {items.map((item, i) => {
            const importance = item.importance ?? item.priority ?? "medium";
            const status     = item.status ?? "pending";
            const isDone     = checked.includes(i);
            const isOpen     = expanded.includes(i);
            const impStyles  = IMP_STYLES[importance] ?? IMP_STYLES.medium;

            return (
              <li key={i} className="group">
                <div
                  className={`rounded-[14px] border px-3 py-2.5 transition-all ${
                    isDone
                      ? "border-white/[0.04] bg-white/[0.01] opacity-60"
                      : "border-white/[0.07] bg-white/[0.02] hover:border-sky-400/20 hover:bg-white/[0.04]"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    {/* Checkbox */}
                    <button
                      onClick={() => toggle(i)}
                      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-all ${
                        isDone ? "border-sky-500 bg-sky-500" : "border-white/20 bg-transparent"
                      }`}
                      aria-label={isDone ? "Mark incomplete" : "Mark done"}
                    >
                      {isDone && (
                        <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 10 10" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M1.5 5l2.5 2.5 4.5-4.5" />
                        </svg>
                      )}
                    </button>

                    {/* Status dot */}
                    <span className={`h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[status]}`} title={status} />

                    {/* Label */}
                    <span className={`flex-1 text-[12px] leading-5 ${isDone ? "line-through text-slate-600" : "text-slate-300"}`}>
                      {item.label}
                    </span>

                    {/* Frequency */}
                    {item.frequency && (
                      <span className="shrink-0 text-[9px] text-slate-600 hidden sm:inline">
                        {item.frequency}
                      </span>
                    )}

                    {/* Importance badge */}
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${impStyles.badge}`}>
                      {importance}
                    </span>

                    {/* Expand toggle (only if why_it_matters) */}
                    {item.why_it_matters && (
                      <button
                        onClick={() => toggleExpand(i)}
                        className="shrink-0 text-slate-600 hover:text-slate-400 transition-colors"
                        aria-label="Toggle details"
                      >
                        <ChevronRight
                          className={`h-3.5 w-3.5 transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}
                        />
                      </button>
                    )}
                  </div>

                  {/* Expanded detail */}
                  {isOpen && item.why_it_matters && (
                    <p className="mt-2 ml-7 text-[11px] text-slate-500 leading-[1.55]">
                      {item.why_it_matters}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {/* Progress bar */}
      {items.length > 0 && (
        <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/[0.06]">
          <div
            className="h-full rounded-full bg-sky-500 transition-all duration-500"
            style={{ width: `${(doneCount / items.length) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}

export { MonitoringChecklist as MonitoringChecklistCard };
