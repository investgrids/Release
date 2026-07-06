"use client";

import { useState } from "react";
import Link from "next/link";
import { useAlerts, BreakingAlert } from "./AlertProvider";
import { AlertOctagon, Zap, AlertTriangle } from "lucide-react";

/* ── Helpers ─────────────────────────────────────────────── */
const URGENCY_STYLE = {
  critical: "border-rose-500/50 shadow-[0_0_30px_rgba(239,68,68,0.15)]",
  high:     "border-amber-500/40 shadow-[0_0_24px_rgba(245,158,11,0.12)]",
};
const URGENCY_BADGE = {
  critical: "bg-rose-500/20 text-rose-300 border border-rose-500/30",
  high:     "bg-amber-500/15 text-amber-300 border border-amber-500/30",
};

/* ── Single alert card ───────────────────────────────────── */
function AlertCard({ alert, onDismiss }: { alert: BreakingAlert; onDismiss: () => void }) {
  const [expanded, setExpanded] = useState(true);
  const urgency = alert.urgency ?? "high";

  return (
    <div className={`relative w-full overflow-hidden rounded-[20px] border bg-[#08090E]/95 backdrop-blur-2xl transition-all duration-300 ${URGENCY_STYLE[urgency]}`}>
      {/* Pulsing top accent bar */}
      <div className={`h-0.5 w-full ${urgency === "critical" ? "bg-gradient-to-r from-rose-600 via-rose-400 to-transparent animate-pulse" : "bg-gradient-to-r from-amber-500 via-amber-400 to-transparent"}`} />

      {/* Header — always visible */}
      <div className="flex items-start gap-3 p-4">
        {/* Icon */}
        <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${urgency === "critical" ? "bg-rose-500/20 text-rose-400" : "bg-amber-500/15 text-amber-400"}`}>
          <AlertOctagon className="h-4 w-4" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${URGENCY_BADGE[urgency]}`}>
              <span className="flex items-center gap-1">
                {urgency === "critical" ? <><Zap className="h-2.5 w-2.5" /> Breaking</> : <><AlertTriangle className="h-2.5 w-2.5" /> Alert</>}
              </span>
            </span>
            {urgency === "critical" && (
              <span className="h-1.5 w-1.5 rounded-full bg-rose-400 animate-pulse" />
            )}
          </div>
          <p className="text-sm font-semibold text-white leading-snug line-clamp-2">{alert.headline}</p>
        </div>

        {/* Controls */}
        <div className="flex shrink-0 items-center gap-1">
          <button onClick={() => setExpanded(e => !e)}
            className="flex h-7 w-7 items-center justify-center rounded-full bg-white/5 text-slate-400 hover:text-white transition text-xs">
            {expanded ? "▲" : "▼"}
          </button>
          <button onClick={onDismiss}
            className="flex h-7 w-7 items-center justify-center rounded-full bg-white/5 text-slate-400 hover:text-white transition">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="border-t border-white/8 px-4 pb-4 pt-3 space-y-3">
          {/* AI Summary */}
          <p className="text-xs leading-5 text-slate-300">{alert.summary}</p>

          {/* Stock impacts */}
          {alert.stocks?.length > 0 && (
            <div>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                Stocks Impacted
              </p>
              <div className="space-y-1.5">
                {alert.stocks.map((s, i) => (
                  <div key={i} className={`flex items-center gap-2.5 rounded-[10px] px-3 py-2 ${
                    s.direction === "up" ? "bg-emerald-500/[0.07]" : "bg-rose-500/[0.07]"
                  }`}>
                    <span className={`text-base font-bold leading-none ${s.direction === "up" ? "text-emerald-400" : "text-rose-400"}`}>
                      {s.direction === "up" ? "▲" : "▼"}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-xs font-semibold text-white">{s.symbol}</span>
                        <span className="text-[10px] text-slate-500 truncate">{s.name}</span>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-4 truncate">{s.reason}</p>
                    </div>
                    <span className={`shrink-0 text-[10px] font-medium capitalize ${
                      s.magnitude === "high" ? "text-rose-300" : s.magnitude === "medium" ? "text-amber-300" : "text-slate-400"
                    }`}>{s.magnitude}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sectors */}
          {alert.sectors?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {alert.sectors.map(s => (
                <span key={s} className="rounded-full bg-white/5 border border-white/8 px-2.5 py-0.5 text-[10px] text-slate-400">
                  {s}
                </span>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-1">
            <Link
              href={`/ai-search?q=${encodeURIComponent(alert.query ?? alert.headline)}`}
              className="flex-1 rounded-[12px] bg-gradient-to-r from-violet-600 to-sky-500 px-3 py-2 text-center text-xs font-semibold text-white hover:opacity-90 transition"
            >
              View Full AI Analysis →
            </Link>
            <button onClick={onDismiss}
              className="rounded-[12px] border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-white/10 transition">
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Container — stacks multiple alerts ──────────────────── */
export function BreakingNewsAlert() {
  const { alerts, dismiss } = useAlerts();
  if (alerts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[60] flex flex-col gap-3 w-[min(92vw,420px)]">
      {alerts.slice(0, 3).map(a => (
        <AlertCard key={a.id} alert={a} onDismiss={() => dismiss(a.id)} />
      ))}
    </div>
  );
}
