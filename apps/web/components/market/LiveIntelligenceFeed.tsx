"use client";

/**
 * Live Intelligence — homepage widget answering "what happened just now?".
 * A real consumer of the app-wide SSE connection (AlertProvider ->
 * /api/stream/events), not mocked or simulated: every row here is a real
 * `alert`/`update` (TriagedEvent) the backend's Intelligence Orchestrator
 * broadcast when it happened, filtered to Critical/High priority only so
 * this stays a short, high-signal list — routine/medium-priority triage
 * noise belongs on the Live Market tab's richer feed, not here. The
 * merge/format/filter logic lives in hooks/useMarketIntelligence.ts
 * (useLiveFeed) so every consumer gets identical entries — this component
 * is presentation only.
 */

import Link from "next/link";
import { Radio, Sparkles } from "lucide-react";
import { useLiveFeed } from "@/hooks/useMarketIntelligence";
import { scoreToColor } from "@/lib/scoring";

function timeLabel(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true });
  } catch {
    return "";
  }
}

export function LiveIntelligenceFeed({ compact = false, limit = 20 }: { compact?: boolean; limit?: number }) {
  const entries = useLiveFeed(limit, { criticalHighOnly: true });

  return (
    <div className={`flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] ${compact ? "p-4" : "p-5"}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-y-1">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 shrink-0 text-violet-400" />
          <h3 className="whitespace-nowrap text-[11px] font-black uppercase tracking-[0.04em] text-white">Live Intelligence</h3>
        </div>
        <span className="flex items-center gap-1.5 text-[10px] font-semibold text-slate-500">
          <Radio className="h-3 w-3 text-emerald-400" />
          Live
        </span>
      </div>

      {entries.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center py-10 text-center">
          <p className="text-[12px] text-slate-500">Watching for the next real-time signal…</p>
          <p className="mt-1 text-[10px] text-slate-600">Every new event, score change, and alert appears here as it happens — nothing simulated.</p>
        </div>
      ) : (
        // flex-1 + min-h-0 so this fills whatever height the grid row
        // stretches the card to (siblings can be much taller) instead of a
        // fixed max-h that either clips the last row or leaves dead space
        // below it depending on sibling height.
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
          {entries.map(entry => (
            <div key={entry.key} className="flex items-start gap-3 rounded-xl border border-white/[0.04] bg-white/[0.02] p-2.5 hover:border-white/[0.1] transition">
              <span className="w-11 shrink-0 pt-0.5 text-[10px] tabular-nums text-slate-600">{timeLabel(entry.ts)}</span>
              <div className="min-w-0 flex-1">
                <div className="mb-0.5 flex items-center gap-1.5">
                  <span className={`rounded-full border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wider ${entry.badge.cls}`}>
                    {entry.badge.label}
                  </span>
                  {entry.kind === "score_update" && entry.score !== null && entry.score !== undefined && (
                    <span className="text-[9px] font-bold tabular-nums" style={{ color: scoreToColor(entry.score) }}>
                      {entry.scoreLabel}
                    </span>
                  )}
                </div>
                {entry.href ? (
                  <Link href={entry.href} className="text-[12px] font-medium text-slate-200 hover:text-sky-300 transition line-clamp-2">
                    {entry.headline}
                  </Link>
                ) : (
                  <p className="text-[12px] font-medium text-slate-200 line-clamp-2">{entry.headline}</p>
                )}
                {entry.sub && <p className="mt-0.5 text-[10px] text-slate-600 line-clamp-1">{entry.sub}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
