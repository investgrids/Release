"use client";

import { useState, useEffect, useCallback } from "react";
import { ChevronDown, ChevronRight, Zap, RefreshCw } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type OutlookLevel = 0 | 1 | 2 | 3 | 4 | 5;

export interface HorizonData {
  id:            "immediate" | "short_term" | "medium_term" | "long_term" | "structural";
  label:         string;
  range:         string;
  icon:          string;
  outlook:       string;
  outlook_level: OutlookLevel;
  confidence:    number;
  reason:        string;
  catalysts:     string[];
  risks:         string[];
}

export interface HorizonFetchContext {
  type:       "stock" | "event" | "opportunity" | "story" | "ripple" | "query";
  title:      string;
  symbol?:    string;
  context?:   string;
  sectors?:   string[];
  context_id?: string;
}

export interface MultiHorizonOutlookCardProps {
  /** Pre-loaded horizons — skip internal fetch */
  horizons?:     HorizonData[];
  /** Provide these to lazy-fetch on mount */
  fetchContext?: HorizonFetchContext;
  /** Narrow card title */
  title?:        string;
  /** Show only a subset of horizon ids */
  filter?:       Array<HorizonData["id"]>;
  /** Compact single-column layout without expand */
  compact?:      boolean;
}

// ── Visual config ─────────────────────────────────────────────────────────────

const LEVEL_CONFIG: Record<OutlookLevel, {
  dot: string; badge: string; label: string; indicator: string;
}> = {
  5: { dot: "bg-emerald-400", badge: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10", label: "text-emerald-400", indicator: "🟢" },
  4: { dot: "bg-emerald-400", badge: "text-emerald-300 border-emerald-500/25 bg-emerald-500/8",  label: "text-emerald-300", indicator: "🟢" },
  3: { dot: "bg-sky-400",     badge: "text-sky-400 border-sky-500/30 bg-sky-500/10",             label: "text-sky-400",     indicator: "🟢" },
  2: { dot: "bg-amber-400",   badge: "text-amber-400 border-amber-500/30 bg-amber-500/10",       label: "text-amber-400",   indicator: "🟡" },
  1: { dot: "bg-orange-400",  badge: "text-orange-400 border-orange-500/30 bg-orange-500/10",    label: "text-orange-400",  indicator: "🟠" },
  0: { dot: "bg-rose-400",    badge: "text-rose-400 border-rose-500/30 bg-rose-500/10",          label: "text-rose-400",    indicator: "🔴" },
};

function outlookLevel(level: number): OutlookLevel {
  const clamped = Math.max(0, Math.min(5, Math.round(level)));
  return clamped as OutlookLevel;
}

// ── Confidence bar ────────────────────────────────────────────────────────────

function ConfidenceBar({ value, level }: { value: number; level: OutlookLevel }) {
  const cfg = LEVEL_CONFIG[level];
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="h-1 flex-1 rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${cfg.dot}`}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className={`text-[10px] font-bold tabular-nums ${cfg.label}`}>{value}%</span>
    </div>
  );
}

// ── Single horizon row ────────────────────────────────────────────────────────

function HorizonRow({
  horizon,
  isLast,
  compact,
}: {
  horizon: HorizonData;
  isLast:  boolean;
  compact: boolean;
}) {
  const [open, setOpen] = useState(false);
  const level = outlookLevel(horizon.outlook_level);
  const cfg   = LEVEL_CONFIG[level];
  const hasDetails = horizon.catalysts.length > 0 || horizon.risks.length > 0;

  return (
    <div className="relative flex gap-3.5">
      {/* ── Timeline spine ─────────────────────────────────────────────────── */}
      <div className="flex flex-col items-center">
        <div className={`mt-0.5 h-5 w-5 shrink-0 rounded-full border-2 border-slate-900 flex items-center justify-center shadow-sm ${cfg.dot}`}>
          <span className="text-[8px] font-black text-slate-900">{cfg.indicator === "🟢" ? "↑" : cfg.indicator === "🟡" ? "—" : cfg.indicator === "🟠" ? "!" : "↓"}</span>
        </div>
        {!isLast && (
          <div className="mt-1 w-px flex-1 min-h-[28px] bg-white/[0.07]" />
        )}
      </div>

      {/* ── Content ────────────────────────────────────────────────────────── */}
      <div className={`pb-4 min-w-0 flex-1 ${isLast ? "pb-0" : ""}`}>
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-base leading-none">{horizon.icon}</span>
            <div>
              <span className="text-[12px] font-bold text-white">{horizon.label}</span>
              <span className="ml-1.5 text-[10px] text-slate-500">{horizon.range}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${cfg.badge}`}>
              {cfg.indicator} {horizon.outlook}
            </span>
            {!compact && hasDetails && (
              <button
                onClick={() => setOpen(v => !v)}
                className="rounded-lg border border-white/[0.07] bg-white/[0.03] p-0.5 text-slate-500 hover:text-slate-300 transition"
                aria-label={open ? "Collapse" : "Expand"}
              >
                {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              </button>
            )}
          </div>
        </div>

        {/* Confidence */}
        <ConfidenceBar value={horizon.confidence} level={level} />

        {/* Reason */}
        <p className="mt-2 text-[12px] leading-[1.55] text-slate-300">{horizon.reason}</p>

        {/* Expanded details */}
        {!compact && open && hasDetails && (
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {horizon.catalysts.length > 0 && (
              <div className="rounded-[12px] border border-emerald-500/15 bg-emerald-500/[0.04] p-2.5">
                <p className="mb-1.5 text-[9px] font-bold uppercase tracking-[0.12em] text-emerald-400">
                  Catalysts
                </p>
                <ul className="space-y-1">
                  {horizon.catalysts.map((c, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-300 leading-[1.4]">
                      <ChevronRight className="mt-0.5 h-2.5 w-2.5 shrink-0 text-emerald-400" />
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {horizon.risks.length > 0 && (
              <div className="rounded-[12px] border border-rose-500/15 bg-rose-500/[0.04] p-2.5">
                <p className="mb-1.5 text-[9px] font-bold uppercase tracking-[0.12em] text-rose-400">
                  Risks
                </p>
                <ul className="space-y-1">
                  {horizon.risks.map((r, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-300 leading-[1.4]">
                      <ChevronRight className="mt-0.5 h-2.5 w-2.5 shrink-0 text-rose-400" />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function HorizonSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} className="flex gap-3.5">
          <div className="h-5 w-5 shrink-0 rounded-full bg-white/[0.06]" />
          <div className="flex-1 space-y-2 pt-0.5">
            <div className="flex items-center gap-2">
              <div className="h-3 w-20 rounded bg-white/[0.06]" />
              <div className="h-4 w-24 rounded-full bg-white/[0.06]" />
            </div>
            <div className="h-1.5 w-full rounded-full bg-white/[0.04]" />
            <div className="h-3 w-full rounded bg-white/[0.04]" />
            <div className="h-3 w-4/5 rounded bg-white/[0.04]" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── API call ──────────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function fetchHorizons(ctx: HorizonFetchContext): Promise<HorizonData[]> {
  const res = await fetch(`${API_BASE}/api/intelligence/horizon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      type:       ctx.type,
      title:      ctx.title,
      symbol:     ctx.symbol ?? null,
      context:    ctx.context ?? "",
      sectors:    ctx.sectors ?? [],
      context_id: ctx.context_id ?? null,
    }),
  });
  if (!res.ok) throw new Error(`horizon fetch failed: ${res.status}`);
  const data = await res.json();
  return data.horizons as HorizonData[];
}

// ── Main component ────────────────────────────────────────────────────────────

export function MultiHorizonOutlookCard({
  horizons:     preloaded,
  fetchContext,
  title = "Expected Horizons",
  filter,
  compact = false,
}: MultiHorizonOutlookCardProps) {
  const [horizons, setHorizons] = useState<HorizonData[] | null>(preloaded ?? null);
  const [loading,  setLoading]  = useState(!preloaded && !!fetchContext);
  const [error,    setError]    = useState(false);

  const load = useCallback(async () => {
    if (!fetchContext) return;
    setLoading(true);
    setError(false);
    try {
      const data = await fetchHorizons(fetchContext);
      setHorizons(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [fetchContext]);

  useEffect(() => {
    if (!preloaded && fetchContext) {
      load();
    }
  }, [preloaded, fetchContext, load]);

  // Update if pre-loaded horizons prop changes (parent re-fetched)
  useEffect(() => {
    if (preloaded) setHorizons(preloaded);
  }, [preloaded]);

  const visible = filter
    ? (horizons ?? []).filter(h => filter.includes(h.id))
    : (horizons ?? []);

  return (
    <div className="rounded-[20px] border border-violet-500/20 bg-violet-500/[0.03] p-5">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/[0.08] border border-violet-500/20">
            <Zap className="h-3.5 w-3.5 text-violet-400" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
            {title}
          </span>
        </div>
        {error && !loading && (
          <button
            onClick={load}
            className="flex items-center gap-1 rounded-lg border border-white/[0.07] bg-white/[0.03] px-2 py-1 text-[10px] text-slate-500 hover:text-slate-300 transition"
          >
            <RefreshCw className="h-3 w-3" /> Retry
          </button>
        )}
      </div>

      {/* ── Body ───────────────────────────────────────────────────────────── */}
      {loading && <HorizonSkeleton />}

      {!loading && error && (
        <p className="text-[12px] text-slate-500">
          Could not load horizon analysis. <button onClick={load} className="underline hover:text-slate-300 transition">Try again</button>
        </p>
      )}

      {!loading && !error && visible.length === 0 && (
        <p className="text-[12px] text-slate-500">No horizon data available.</p>
      )}

      {!loading && !error && visible.length > 0 && (
        <div className="space-y-0">
          {visible.map((h, i) => (
            <HorizonRow
              key={h.id}
              horizon={h}
              isLast={i === visible.length - 1}
              compact={compact}
            />
          ))}
        </div>
      )}

      {/* ── Legend ─────────────────────────────────────────────────────────── */}
      {!loading && !error && visible.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 border-t border-white/[0.04] pt-3">
          {(["🟢 Positive", "🟡 Neutral", "🟠 Cautious", "🔴 Negative"] as const).map(l => (
            <span key={l} className="text-[10px] text-slate-600">{l}</span>
          ))}
          {!compact && (
            <span className="ml-auto text-[10px] text-slate-700">Click any row to expand catalysts &amp; risks</span>
          )}
        </div>
      )}
    </div>
  );
}

export default MultiHorizonOutlookCard;
