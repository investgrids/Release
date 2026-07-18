"use client";

/**
 * Live Intelligence Feed — a real consumer of the app-wide SSE connection
 * (AlertProvider -> /api/stream/events), not mocked or simulated: every
 * row here is a real `alert`/`update` (TriagedEvent) or `score_update`
 * (ScoreUpdate) the backend's Intelligence Orchestrator broadcast when it
 * happened. Reuses the single shared connection AlertProvider already
 * maintains app-wide instead of opening a second EventSource.
 */

import { useMemo } from "react";
import Link from "next/link";
import { Radio, Sparkles } from "lucide-react";
import { useAlerts, type IntelligenceEvent, type ScoreUpdateEvent } from "@/components/AlertProvider";
import { scoreToColor } from "@/lib/scoring";

type FeedKind = "alert" | "update" | "score_update";

interface FeedEntry {
  key: string;
  kind: FeedKind;
  ts: string;
  headline: string;
  sub?: string;
  href?: string;
  badge: { label: string; cls: string };
  score?: number | null;
  scoreLabel?: string;
}

function timeLabel(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true });
  } catch {
    return "";
  }
}

function triagedToEntry(evt: IntelligenceEvent): FeedEntry {
  const isAlert = evt.urgency >= 7;
  return {
    key: `triaged-${evt.id}-${evt.ts}`,
    kind: isAlert ? "alert" : "update",
    ts: evt.ts,
    headline: evt.one_liner || evt.headline,
    sub: [...(evt.sectors ?? []), ...(evt.tickers ?? [])].slice(0, 3).join(" · ") || evt.source,
    href: evt.tickers?.[0] ? `/companies/${evt.tickers[0]}` : undefined,
    badge: isAlert
      ? { label: "ALERT", cls: "bg-rose-500/15 text-rose-300 border-rose-500/30" }
      : { label: "UPDATE", cls: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  };
}

const STATUS_CLS: Record<string, string> = {
  preliminary: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  verified: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  live: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
};

function scoreUpdateToEntry(evt: ScoreUpdateEvent): FeedEntry {
  const entityLabel = evt.entity_type ? evt.entity_type.charAt(0).toUpperCase() + evt.entity_type.slice(1) : "Entity";
  const unscored = evt.score === null || evt.score === undefined;
  const delta = !unscored && evt.previous_score !== null && evt.previous_score !== undefined
    ? (evt.score as number) - evt.previous_score
    : null;
  return {
    key: `score-${evt.entity_type}-${evt.entity_id}-${evt.ts}`,
    kind: "score_update",
    ts: evt.ts,
    headline: `${entityLabel} score ${unscored ? "unscored" : delta !== null ? (delta >= 0 ? "increased" : "decreased") : "updated"}${!unscored && delta !== null ? ` (${delta >= 0 ? "+" : ""}${delta.toFixed(1)})` : ""}`,
    sub: evt.reasoning?.[0] ?? evt.entity_id,
    badge: { label: (evt.data_status ?? "score").toUpperCase(), cls: STATUS_CLS[evt.data_status] ?? "bg-violet-500/15 text-violet-300 border-violet-500/30" },
    score: evt.score,
    scoreLabel: unscored ? "Unscored" : `${Math.round(evt.score as number)}`,
  };
}

export function LiveIntelligenceFeed({ compact = false, limit }: { compact?: boolean; limit?: number }) {
  const { intelligenceEvents, scoreUpdates } = useAlerts();

  const entries = useMemo(() => {
    const merged: FeedEntry[] = [
      ...intelligenceEvents.map(triagedToEntry),
      ...scoreUpdates.map(scoreUpdateToEntry),
    ];
    merged.sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());
    return limit ? merged.slice(0, limit) : merged.slice(0, 40);
  }, [intelligenceEvents, scoreUpdates, limit]);

  return (
    <div className={`rounded-2xl border border-white/[0.07] bg-[#080c14] ${compact ? "p-4" : "p-5"}`}>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-violet-400" />
          <h3 className="text-[12px] font-black uppercase tracking-[0.1em] text-white">Live Intelligence Feed</h3>
        </div>
        <span className="flex items-center gap-1.5 text-[10px] font-semibold text-slate-500">
          <Radio className="h-3 w-3 text-emerald-400" />
          Live
        </span>
      </div>

      {entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <p className="text-[12px] text-slate-500">Watching for the next real-time signal…</p>
          <p className="mt-1 text-[10px] text-slate-600">Every new event, score change, and alert appears here as it happens — nothing simulated.</p>
        </div>
      ) : (
        <div className={`space-y-2 ${compact ? "" : "max-h-[520px] overflow-y-auto pr-1"}`}>
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
