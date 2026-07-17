"use client";

import { useState, useEffect } from "react";
import { API_BASE_URL as API } from "@/lib/api";

interface CalibrationRow {
  level: "Low" | "Medium" | "High" | "Very High";
  total: number;
  accuracy_rate: number;
  calibration_factor: number;
  last_updated: string | null;
}

interface PredictionStats {
  total_predictions: number;
  complete_predictions: number;
  pending_predictions: number;
  overall_accuracy: number | null;
  verdicts: Record<string, number>;
  calibration: CalibrationRow[];
}

const LEVEL_COLOR: Record<string, string> = {
  "Very High": "#10b981",
  "High":      "#0ea5e9",
  "Medium":    "#f59e0b",
  "Low":       "#ef4444",
};


export function LearningEngine() {
  const [stats, setStats]     = useState<PredictionStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/predictions/stats`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { setStats(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="h-24 animate-pulse rounded-2xl bg-white/[0.03]" />
  );
  if (!stats || stats.total_predictions === 0) return null;

  const { correct = 0, partial = 0, incorrect = 0, inconclusive = 0 } = stats.verdicts;
  const conclusive = correct + partial + incorrect;

  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-500/20">
            <svg className="h-4 w-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15M14.25 3.104c.251.023.501.05.75.082M19.8 15l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.5l-1.82 6.84A2.25 2.25 0 0115.8 23H8.2a2.25 2.25 0 01-2.18-1.66L4.2 14.5" />
            </svg>
          </div>
          <div>
            <p className="text-[13px] font-semibold text-white leading-none">Learning Engine</p>
            <p className="mt-0.5 text-[11px] text-slate-500">
              {stats.total_predictions.toLocaleString()} predictions tracked
            </p>
          </div>
        </div>

        {stats.overall_accuracy !== null && (
          <div className="text-right">
            <p className="text-[22px] font-bold tabular-nums text-white leading-none">
              {stats.overall_accuracy}%
            </p>
            <p className="text-[10px] text-slate-500">overall accuracy</p>
          </div>
        )}
      </div>

      {/* Verdict bar */}
      {conclusive > 0 && (
        <div className="mb-4">
          <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
            <div className="h-full bg-emerald-500/70" style={{ width: `${(correct / conclusive) * 100}%` }} />
            <div className="h-full bg-amber-500/60"  style={{ width: `${(partial / conclusive) * 100}%` }} />
            <div className="h-full bg-rose-500/60"   style={{ width: `${(incorrect / conclusive) * 100}%` }} />
          </div>
          <div className="mt-1.5 flex items-center gap-3 text-[10px] text-slate-500">
            <span><span className="font-semibold text-emerald-400">{correct}</span> correct</span>
            <span><span className="font-semibold text-amber-400">{partial}</span> partial</span>
            <span><span className="font-semibold text-rose-400">{incorrect}</span> incorrect</span>
            {inconclusive > 0 && <span><span className="font-semibold text-slate-600">{inconclusive}</span> pending</span>}
          </div>
        </div>
      )}

      {/* Calibration table */}
      {stats.calibration.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-600">
            Calibration by confidence level
          </p>
          {stats.calibration.map(row => {
            if (row.total === 0) return null;
            const color = LEVEL_COLOR[row.level] || "#64748b";
            const acc   = row.accuracy_rate;
            const calib = row.calibration_factor;
            return (
              <div key={row.level} className="flex items-center gap-3">
                <div className="w-16 shrink-0 text-[10px] font-semibold" style={{ color }}>
                  {row.level}
                </div>
                <div className="flex-1">
                  <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                    <div className="h-full rounded-full" style={{ width: `${acc}%`, backgroundColor: color + "99" }} />
                  </div>
                </div>
                <div className="w-10 text-right text-[11px] tabular-nums text-slate-300 font-semibold">
                  {acc}%
                </div>
                <div className={`w-14 text-right text-[10px] tabular-nums ${calib < 0.9 ? "text-rose-400" : calib > 1.1 ? "text-emerald-400" : "text-slate-500"}`}>
                  {calib < 0.9 ? "↓" : calib > 1.1 ? "↑" : "≈"} {calib.toFixed(2)}×
                </div>
                <div className="w-10 text-right text-[10px] tabular-nums text-slate-600">
                  n={row.total}
                </div>
              </div>
            );
          })}
          <p className="mt-1 text-[9px] text-slate-600">
            Calibration factor auto-adjusts future confidence scores.
            Updates daily at 4:00 PM IST after market close.
          </p>
        </div>
      )}
    </div>
  );
}
