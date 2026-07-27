"use client";

import { useState } from "react";
import { SlidersHorizontal, RefreshCw, ChevronDown } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

const FIELDS: { key: string; label: string; options: string[] }[] = [
  { key: "horizon", label: "Horizon", options: ["Short-term (0-3mo)", "Medium-term (3-12mo)", "Long-term (1-3yr)", "Long-term (3yr+)"] },
  { key: "risk_tolerance", label: "Risk", options: ["Conservative", "Moderate", "Aggressive"] },
  { key: "investment_goal", label: "Goal", options: ["Capital Growth", "Income Generation", "Capital Preservation", "Balanced"] },
  { key: "portfolio_size", label: "Portfolio Size", options: ["Small (<5L)", "Medium (5-25L)", "Large (25L+)"] },
  { key: "style", label: "Style", options: ["Growth", "Dividend", "Value"] },
  { key: "entry_mode", label: "Entry Mode", options: ["SIP", "Lump Sum"] },
  { key: "holder_status", label: "Position", options: ["New Investor", "Existing Holder"] },
];

export interface RefinedDecision {
  investment_verdict: Record<string, any>;
  decision_engine_v2: Record<string, any>;
  ai_conclusion: Record<string, any>;
}

/**
 * Adjusts personal investment parameters and regenerates ONLY the decision
 * layer against the same already-gathered evidence — visibly faster than a
 * fresh search (see the backend's specialists/refine.py). Renders nothing
 * without a responseId — nothing to refine against yet.
 */
export function RefineAnalysisPanel({
  responseId,
  onRefined,
}: {
  responseId: string | null;
  onRefined: (result: RefinedDecision, newResponseId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [params, setParams] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");

  if (!responseId) return null;

  const activeCount = Object.values(params).filter(Boolean).length;

  async function regenerate() {
    setStatus("loading");
    try {
      const res = await fetch(`${API}/api/ai/search/refine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response_id: responseId, ...params }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Refine failed" }));
        throw new Error(err.detail || "Refine failed");
      }
      const data = await res.json();
      onRefined(
        {
          investment_verdict: data.investment_verdict,
          decision_engine_v2: data.decision_engine_v2,
          ai_conclusion: data.ai_conclusion,
        },
        data.response_id
      );
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="rounded-[14px] border border-white/[0.06] bg-white/[0.02]">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3"
      >
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-3.5 w-3.5 text-violet-400" />
          <span className="text-[12px] font-medium text-slate-300">Refine for your situation</span>
          {activeCount > 0 && (
            <span className="rounded-full bg-violet-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-violet-300">
              {activeCount}
            </span>
          )}
        </div>
        <ChevronDown className={`h-3.5 w-3.5 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="border-t border-white/[0.06] px-4 py-3">
          <p className="mb-3 text-[11px] text-slate-500">
            Adjust your situation — the AI re-derives the decision from the same evidence, without re-running the whole search.
          </p>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            {FIELDS.map(f => (
              <div key={f.key}>
                <label className="mb-1 block text-[10px] uppercase tracking-wide text-slate-600">{f.label}</label>
                <select
                  value={params[f.key] ?? ""}
                  onChange={e => setParams(p => ({ ...p, [f.key]: e.target.value }))}
                  className="w-full rounded-[8px] border border-white/10 bg-white/[0.03] px-2 py-1.5 text-[11.5px] text-slate-300 focus:border-violet-500/40 focus:outline-none"
                >
                  <option value="">Any</option>
                  {f.options.map(o => (
                    <option key={o} value={o} className="bg-[#0d1117]">
                      {o}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>

          <button
            onClick={regenerate}
            disabled={status === "loading"}
            className="mt-3 flex items-center gap-1.5 rounded-[10px] border border-violet-500/30 bg-violet-500/15 px-3 py-1.5 text-[11.5px] font-medium text-violet-300 transition hover:bg-violet-500/25 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${status === "loading" ? "animate-spin" : ""}`} />
            {status === "loading" ? "Regenerating decision…" : "Regenerate Decision"}
          </button>
          {status === "error" && (
            <p className="mt-2 text-[11px] text-rose-400">
              Couldn&apos;t refine this answer — its evidence may have expired. Try a fresh search.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
