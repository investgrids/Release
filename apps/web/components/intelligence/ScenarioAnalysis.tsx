"use client";

import { useEffect, useState } from "react";
import { BarChart2, Loader2, ChevronRight, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ScenarioBranch {
  probability:         number;
  /** @deprecated use outcome */
  description?:        string;
  outcome?:            string;
  target?:             string;
  key_drivers?:        string[];
  supporting_evidence?: string;
  major_catalysts?:    string[];
  expected_evolution?: string;
  confidence?:         number;
}

export type ScenarioEntityType =
  | "event" | "company" | "story" | "opportunity" | "ripple" | "search";

export interface ScenarioAnalysisProps {
  bull?:              ScenarioBranch;
  base?:              ScenarioBranch;
  bear?:              ScenarioBranch;
  entityType?:        ScenarioEntityType;
  entityId?:          string;
  entityTitle?:       string;
  entityDescription?: string;
  entitySector?:      string;
}

// ── Config ────────────────────────────────────────────────────────────────────

type CaseKey = "bull" | "base" | "bear";

const ACCENT: Record<CaseKey, {
  label: string; bar: string; border: string; bg: string; text: string; badge: string; icon: React.ElementType;
}> = {
  bull: {
    label:  "Bull Case",
    bar:    "bg-emerald-500",
    border: "border-emerald-500/20",
    bg:     "bg-emerald-500/[0.04]",
    text:   "text-emerald-400",
    badge:  "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    icon:   TrendingUp,
  },
  base: {
    label:  "Base Case",
    bar:    "bg-sky-500",
    border: "border-sky-500/20",
    bg:     "bg-sky-500/[0.04]",
    text:   "text-sky-400",
    badge:  "border-sky-500/30 bg-sky-500/10 text-sky-300",
    icon:   Minus,
  },
  bear: {
    label:  "Bear Case",
    bar:    "bg-rose-500",
    border: "border-rose-500/20",
    bg:     "bg-rose-500/[0.04]",
    text:   "text-rose-400",
    badge:  "border-rose-500/30 bg-rose-500/10 text-rose-300",
    icon:   TrendingDown,
  },
};

// ── Sub-component ─────────────────────────────────────────────────────────────

function ScenarioCard({ caseKey, data }: { caseKey: CaseKey; data: ScenarioBranch }) {
  const [open, setOpen] = useState(false);
  const a = ACCENT[caseKey];
  const Icon = a.icon;
  const text = data.outcome ?? data.description ?? "";
  const hasDetail = !!(data.key_drivers?.length || data.supporting_evidence || data.major_catalysts?.length || data.expected_evolution);

  return (
    <div className={`flex flex-col gap-3 rounded-[16px] border ${a.border} ${a.bg} p-4`}>
      {/* Label + probability */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Icon className={`h-3.5 w-3.5 ${a.text}`} aria-hidden />
          <span className={`text-[10px] font-bold uppercase tracking-[0.12em] ${a.text}`}>{a.label}</span>
        </div>
        <span className={`rounded-full border px-2 py-0.5 text-[11px] font-black ${a.badge}`}>
          {data.probability}%
        </span>
      </div>

      {/* Bar */}
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={`h-full rounded-full transition-all duration-700 ${a.bar}`}
          style={{ width: `${data.probability}%` }}
        />
      </div>

      {/* Outcome */}
      {text && <p className="text-[12px] text-slate-400 leading-5">{text}</p>}

      {/* Target price */}
      {data.target && (
        <div className="flex items-center justify-between border-t border-white/[0.05] pt-2">
          <span className="text-[10px] text-slate-600">Target</span>
          <span className={`text-[13px] font-black ${a.text}`}>{data.target}</span>
        </div>
      )}

      {/* Confidence */}
      {data.confidence != null && (
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-slate-600">Confidence</span>
          <span className="text-[10px] text-slate-400">{data.confidence}%</span>
        </div>
      )}

      {/* Expand toggle */}
      {hasDetail && (
        <button
          onClick={() => setOpen(o => !o)}
          className={`flex items-center gap-1 text-[10px] font-medium ${a.text} opacity-70 hover:opacity-100 transition-opacity`}
        >
          <ChevronRight className={`h-3 w-3 transition-transform duration-200 ${open ? "rotate-90" : ""}`} />
          {open ? "Less" : "Details"}
        </button>
      )}

      {/* Expanded detail */}
      {open && hasDetail && (
        <div className="space-y-2 border-t border-white/[0.05] pt-3">
          {data.key_drivers?.length ? (
            <div>
              <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600 mb-1">Key Drivers</p>
              <ul className="space-y-0.5">
                {data.key_drivers.map((d, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-400">
                    <span className={`mt-[5px] h-1 w-1 shrink-0 rounded-full ${a.bar}`} />
                    {d}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {data.major_catalysts?.length ? (
            <div>
              <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600 mb-1">Catalysts</p>
              <ul className="space-y-0.5">
                {data.major_catalysts.map((c, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-400">
                    <span className="mt-[5px] h-1 w-1 shrink-0 rounded-full bg-white/20" />
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {data.supporting_evidence && (
            <p className="text-[11px] text-slate-500 italic leading-[1.55]">{data.supporting_evidence}</p>
          )}

          {data.expected_evolution && (
            <div>
              <p className="text-[9px] font-bold uppercase tracking-widest text-slate-600 mb-1">Expected Evolution</p>
              <p className="text-[11px] text-slate-400 leading-[1.55]">{data.expected_evolution}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function ScenarioAnalysis({
  bull: staticBull,
  base: staticBase,
  bear: staticBear,
  entityType,
  entityId,
  entityTitle,
  entityDescription,
  entitySector,
}: ScenarioAnalysisProps) {
  const [fetched, setFetched] = useState<{ bull?: ScenarioBranch; base?: ScenarioBranch; bear?: ScenarioBranch } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!entityType || !entityId) return;
    setLoading(true);
    const params = new URLSearchParams();
    if (entityTitle)       params.set("title",       entityTitle.slice(0, 200));
    if (entityDescription) params.set("description", entityDescription.slice(0, 800));
    if (entitySector)      params.set("sector",      entitySector.slice(0, 100));

    fetch(`${API}/api/scenario/${entityType}/${encodeURIComponent(entityId)}?${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.bull || d?.base || d?.bear) setFetched(d);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [entityType, entityId, entityTitle, entityDescription, entitySector]);

  const bull = staticBull ?? fetched?.bull;
  const base = staticBase ?? fetched?.base;
  const bear = staticBear ?? fetched?.bear;
  const hasData = !!(bull || base || bear);

  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.025] p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-sky-500/[0.08] border border-sky-500/20">
            <BarChart2 className="h-3.5 w-3.5 text-sky-400" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
            Scenario Analysis
          </span>
        </div>
        {loading && <Loader2 className="h-3 w-3 text-slate-600 animate-spin" />}
      </div>

      {/* Loading skeleton */}
      {loading && !hasData && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {(["bull", "base", "bear"] as CaseKey[]).map(k => (
            <div key={k} className={`rounded-[16px] border ${ACCENT[k].border} ${ACCENT[k].bg} p-4 space-y-3`}>
              <div className="flex justify-between">
                <span className={`text-[10px] font-bold uppercase ${ACCENT[k].text} opacity-40`}>{ACCENT[k].label}</span>
                <span className="h-5 w-8 rounded-full bg-white/[0.06] animate-pulse" />
              </div>
              <div className="h-1.5 rounded-full bg-white/[0.06] animate-pulse" />
              <div className="space-y-1.5">
                <div className="h-2.5 w-full rounded bg-white/[0.05] animate-pulse" />
                <div className="h-2.5 w-4/5 rounded bg-white/[0.05] animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && !hasData && (
        <p className="text-[12px] text-slate-400 leading-5">No data available</p>
      )}

      {/* Cards */}
      {hasData && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {bull && <ScenarioCard caseKey="bull" data={bull} />}
            {base && <ScenarioCard caseKey="base" data={base} />}
            {bear && <ScenarioCard caseKey="bear" data={bear} />}
          </div>

          {/* Probability sanity note */}
          {bull && base && bear && (
            <p className="mt-3 text-[10px] text-slate-700 text-right">
              Probabilities: {bull.probability + base.probability + bear.probability}% total · AI-generated, not financial advice
            </p>
          )}
        </>
      )}
    </div>
  );
}

export { ScenarioAnalysis as ScenarioAnalysisCard };
