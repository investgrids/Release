"use client";

import { useEffect, useState } from "react";
import { Droplets } from "lucide-react";
import { getBrentObservation, type BrentObservation } from "@/lib/brent";

// EIA Brent macro-context card for Global Markets. Renders ONLY the real, dated
// EIA observation with explicit source + observation date + freshness — never a
// live tick, never a fabricated value. Reused by both Global Markets tab variants.

function fmtAsOf(iso: string | null): string | null {
  if (!iso) return null;
  try {
    // Date-only observation ("2026-10-27") — anchor to UTC so the displayed day
    // never shifts by the viewer's timezone.
    const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T00:00:00Z` : iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });
  } catch {
    return null;
  }
}

export function BrentMacroCard() {
  const [obs, setObs] = useState<BrentObservation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getBrentObservation().then((o) => {
      if (!active) return;
      setObs(o);
      setLoading(false);
    });
    return () => { active = false; };
  }, []);

  if (loading) {
    return <div className="h-24 animate-pulse rounded-2xl border border-surface-border/5 bg-text-primary/[0.02]" />;
  }

  if (!obs) {
    return (
      <div className="rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] px-5 py-4 text-[12px] text-text-muted">
        Brent crude (EIA) is unavailable right now — nothing is shown rather than a stale value.
      </div>
    );
  }

  const asOf = fmtAsOf(obs.asOf);
  const freshness = obs.stale
    ? { label: "Stale", cls: "text-rose-400 bg-rose-500/10" }
    : { label: "Delayed", cls: "text-amber-400 bg-amber-500/10" };

  return (
    <div className="rounded-2xl border border-surface-border/7 bg-surface-card px-5 py-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-text-primary/[0.06]">
            <Droplets className="h-5 w-5 text-blue-400" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-[13px] font-bold text-text-primary">Brent Crude</p>
            <p className="mt-0.5 text-[11px] text-text-muted">{obs.unit}</p>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[18px] font-black tabular-nums text-text-primary">${obs.price}</p>
          {obs.change !== "" && (
            <p className={`text-[12px] font-bold tabular-nums ${obs.positive ? "text-emerald-400" : "text-rose-400"}`}>
              {obs.change} ({obs.pct > 0 ? "+" : ""}{obs.pct.toFixed(2)}%)
            </p>
          )}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-surface-border/5 pt-3 text-[10px] text-text-muted">
        <span>Source: {obs.source} (EIA)</span>
        <span>· Series RBRTE</span>
        {asOf && <span>· As of {asOf}</span>}
        <span className={`rounded px-1.5 py-0.5 font-bold uppercase tracking-wide ${freshness.cls}`}>{freshness.label}</span>
      </div>
      <p className="mt-1.5 text-[10px] leading-relaxed text-text-muted">
        EIA daily spot observation (public domain), lagged several business days — a dated value, not a real-time tick.
      </p>
    </div>
  );
}
