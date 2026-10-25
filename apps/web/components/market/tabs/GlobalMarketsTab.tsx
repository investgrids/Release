"use client";

import { useEffect, useState } from "react";
import { Globe } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

// Single source of truth for the frontend's regional grouping — must cover all
// ten configured indices exactly once (mirrors the backend _BRIEF_REGIONS).
// Shanghai Composite was previously missing from Asia-Pacific here (a pre-existing
// drift bug); a regression test asserts full, non-overlapping coverage.
export const REGION_GROUPS: { region: string; indices: string[]; cls: string }[] = [
  { region: "Americas",     indices: ["Dow Jones", "S&P 500", "Nasdaq"],                          cls: "border-sky-500/10 bg-sky-500/[0.04]" },
  { region: "Europe",       indices: ["FTSE 100", "DAX", "CAC 40"],                               cls: "border-violet-500/10 bg-violet-500/[0.04]" },
  { region: "Asia-Pacific", indices: ["Nikkei 225", "Hang Seng", "Shanghai Composite", "KOSPI"], cls: "border-emerald-500/10 bg-emerald-500/[0.04]" },
];

export function GlobalMarketsTab() {
  const [indices, setIndices] = useState<any[] | null>(null);
  const [brief, setBrief] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/market/global`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setIndices(Array.isArray(d?.indices) ? d.indices : []))
      .catch(() => setIndices([]))
      .finally(() => setLoading(false));
    // Deterministic Intelligence Brief — separate, non-blocking. When the server
    // flag is off it returns {enabled:false} and no Brief renders (graceful).
    fetch(`${API}/api/market/global-brief`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setBrief(d?.enabled ? d : null))
      .catch(() => setBrief(null));
  }, []);

  if (loading) return (
    <div className="space-y-5">
      {[1, 2, 3].map(i => <div key={i} className="h-32 animate-pulse rounded-2xl border border-surface-border/5 bg-text-primary/[0.02]" />)}
    </div>
  );

  const rows = indices ?? [];

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-surface-border/7 bg-surface-card py-16 text-center">
        <Globe className="mb-3 h-8 w-8 text-text-muted" />
        <p className="text-[14px] font-semibold text-text-secondary">Global market data is unavailable right now.</p>
        <p className="mt-1 text-[12px] text-text-muted">Try again shortly — nothing is shown rather than a stale estimate.</p>
      </div>
    );
  }

  const positiveCount = rows.filter(r => r.positive).length;
  const globalSentiment = positiveCount >= rows.length * 0.7 ? "Bullish" : positiveCount >= rows.length * 0.4 ? "Mixed" : "Bearish";
  const sentColor = globalSentiment === "Bullish" ? "text-emerald-400" : globalSentiment === "Mixed" ? "text-amber-400" : "text-rose-400";

  // Freshness (enhancement 2026-10-20) — rendered ONLY when the backend sends
  // these fields (gated by the server freshness flag). Absent ⇒ UI unchanged.
  const FRESHNESS_META: Record<string, { label: string; cls: string }> = {
    live:        { label: "Live",        cls: "text-emerald-400 bg-emerald-500/10" },
    delayed:     { label: "Delayed",     cls: "text-amber-400 bg-amber-500/10"     },
    closed:      { label: "Closed",      cls: "text-slate-400 bg-slate-500/10"     },
    unknown:     { label: "Unknown",     cls: "text-slate-400 bg-slate-500/10"     },
    unavailable: { label: "Unavailable", cls: "text-rose-400 bg-rose-500/10"       },
  };
  const fmtAsOf = (iso?: string | null, tz?: string | null): string | null => {
    if (!iso) return null;
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return null;
      return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", timeZone: tz || undefined, timeZoneName: "short" });
    } catch { return null; }
  };
  const anyFreshness = rows.some(r => r.freshness);

  const MOOD_COLOR: Record<string, string> = {
    Positive: "text-emerald-400", Negative: "text-rose-400", Mixed: "text-amber-400", Uncertain: "text-slate-400",
  };
  // Count-led headline (breadth, not a definitive market-wide judgment). The
  // deterministic "Negative/Positive/Mixed" label is shown as a supporting chip.
  const moodHeadline = (m: any): string => {
    if (!m) return "Global market breadth unavailable";
    if (m.label === "Uncertain") return `Only ${m.observed} of ${m.total} tracked indices have a usable quote`;
    if (m.label === "Positive") return `${m.positive} of ${m.observed} tracked indices are advancing`;
    if (m.label === "Negative") return `${m.negative} of ${m.observed} tracked indices are declining`;
    return `${m.positive} advancing, ${m.negative} declining of ${m.observed} tracked indices`;
  };
  // Session context from the coverage breakdown — "closed" means last official
  // close, not a live tick; the ten indices are NOT one synchronized snapshot.
  const sessionContext = (m: any): string | null => {
    const cov = m?.coverage_by_freshness; if (!cov) return null;
    const parts: string[] = [];
    if (cov.live) parts.push(`${cov.live} live`);
    if (cov.delayed) parts.push(`${cov.delayed} delayed`);
    if (cov.closed) parts.push(`${cov.closed} showing last official close`);
    if (!parts.length) return null;
    return `${parts.join(" · ")} — these are not a single synchronized real-time snapshot.`;
  };

  return (
    <div className="space-y-5">
      {/* Global Markets Intelligence Brief (deterministic) — glass-panel, AI-Search tokens.
          Renders only when the server flag is on; explains the grid below, never duplicates it. */}
      {brief && (
        <div className="glass-panel rounded-2xl border border-surface-border/7 p-6 space-y-4">
          <div>
            <p className="mb-1 text-[11px] uppercase tracking-wider text-text-muted">Global Market Brief</p>
            <h2 className="text-[20px] font-black leading-snug text-text-primary tabular-nums">
              {moodHeadline(brief.mood)}
            </h2>
            {brief.mood?.label && (
              <span className={`mt-1 inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-text-primary/[0.05] ${MOOD_COLOR[brief.mood.label] ?? "text-text-muted"}`}>
                Breadth: {brief.mood.label}
              </span>
            )}
            <p className="mt-1.5 text-[13px] text-text-secondary">{brief.mood?.reason}</p>
            {sessionContext(brief.mood) && (
              <p className="mt-1 text-[10px] text-text-muted tabular-nums">{sessionContext(brief.mood)}</p>
            )}
          </div>

          {/* Regional leaders / laggards */}
          {Array.isArray(brief.regions) && brief.regions.length > 0 && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {brief.regions.map((r: any) => (
                <div key={r.region} className="glass-pill rounded-xl border border-surface-border/7 p-3">
                  <p className="mb-1.5 text-[11px] font-bold text-text-secondary">{r.region}</p>
                  {r.observed === 0 ? (
                    <p className="text-[11px] text-text-muted">{r.note ?? "No eligible observations."}</p>
                  ) : (
                    <div className="space-y-1 text-[11px]">
                      <div className="flex justify-between gap-2">
                        <span className="text-text-muted">Leader</span>
                        <span className="truncate text-text-primary">{r.leader?.name} <span className="tabular-nums text-emerald-400">{r.leader?.pct}</span></span>
                      </div>
                      <div className="flex justify-between gap-2">
                        <span className="text-text-muted">Laggard</span>
                        <span className="truncate text-text-primary">{r.laggard?.name} <span className="tabular-nums text-rose-400">{r.laggard?.pct}</span></span>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* India context — labeled hypotheses only; empty by design in Phase 1 */}
          <div>
            <p className="mb-1 text-[11px] uppercase tracking-wider text-text-muted">India context</p>
            {Array.isArray(brief.india_implications) && brief.india_implications.length > 0 ? (
              <ul className="space-y-1.5">
                {brief.india_implications.map((h: any, i: number) => (
                  <li key={i} className="flex gap-2 text-[12px] text-text-secondary">
                    <span className="mt-0.5 shrink-0 rounded bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-amber-400">Hypothesis</span>
                    <span>
                      {h.hypothesis}{h.basis ? <span className="text-text-muted"> — {h.basis}</span> : null}
                      {h.limitation ? <span className="mt-0.5 block text-[10px] italic text-text-muted">{h.limitation}</span> : null}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[12px] text-text-muted">{brief.india_implications_note ?? "No supported transmission path from current data."}</p>
            )}
          </div>

          {/* What to watch */}
          <div>
            <p className="mb-1 text-[11px] uppercase tracking-wider text-text-muted">What to watch</p>
            {Array.isArray(brief.what_to_watch) && brief.what_to_watch.length > 0 ? (
              <ul className="space-y-1 text-[12px] text-text-secondary">
                {brief.what_to_watch.map((w: any, i: number) => (
                  <li key={i} className="flex gap-2"><span className="text-accent-violet">→</span>
                    <span><span className="font-semibold text-text-primary">{w.title}</span>{w.date ? <span className="text-text-muted"> · {w.date}</span> : null}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[12px] text-text-muted">{brief.what_to_watch_note ?? "No verified events available."}</p>
            )}
          </div>

          <p className="border-t border-surface-border/7 pt-3 text-[10px] text-text-muted">{brief.cannot_conclude}</p>
        </div>
      )}

      {/* Global sentiment header */}
      <div className="flex flex-col gap-4 rounded-2xl border border-surface-border/7 bg-surface-card px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wider text-text-muted">Global Sentiment</p>
          <p className={`text-[24px] font-black ${sentColor}`}>{globalSentiment}</p>
        </div>
        <div className="flex gap-6">
          {[
            { label: "Advancing", val: positiveCount,                color: "text-emerald-400" },
            { label: "Declining", val: rows.length - positiveCount,  color: "text-rose-400"    },
            { label: "Total",     val: rows.length,                  color: "text-text-secondary"   },
          ].map(s => (
            <div key={s.label} className="text-center">
              <p className={`text-[22px] font-black ${s.color}`}>{s.val}</p>
              <p className="text-[10px] text-text-muted">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Index grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {rows.map((idx) => (
          <div key={idx.name}
            className="flex items-center justify-between gap-3 rounded-2xl border border-surface-border/7 bg-surface-card px-5 py-4 hover:border-sky-500/15 transition">
            <div className="flex min-w-0 items-center gap-3">
              <span className="shrink-0 text-[24px]">{idx.flag}</span>
              <div className="min-w-0">
                <p className="truncate text-[13px] font-bold text-text-primary">{idx.name}</p>
                <p className="mt-0.5 text-[11px] text-text-muted">{idx.value !== "—" ? `Last: ${idx.value}` : "No data"}</p>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-[16px] font-black text-text-primary">{idx.value}</p>
              <p className={`text-[12px] font-bold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.pct}</p>
              {idx.freshness && (
                <div className="mt-1 flex items-center justify-end gap-1.5">
                  <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${(FRESHNESS_META[idx.freshness] ?? FRESHNESS_META.unknown).cls}`}>
                    {(FRESHNESS_META[idx.freshness] ?? FRESHNESS_META.unknown).label}
                  </span>
                  {fmtAsOf(idx.source_timestamp, idx.timezone) && (
                    <span className="text-[9px] text-text-muted">as of {fmtAsOf(idx.source_timestamp, idx.timezone)}</span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      {anyFreshness && (
        <p className="text-[10px] text-text-muted">
          Quote times and session states shown as reported by the data source (Yahoo Finance); values may be delayed. A closed market shows its last official close, not a live tick.
        </p>
      )}

      {/* Regional summary */}
      <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
        <h3 className="mb-4 text-[13px] font-bold text-text-primary">Regional Summary</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {REGION_GROUPS.map(({ region, indices: names, cls }) => {
            const regionRows = rows.filter(r => names.includes(r.name));
            if (regionRows.length === 0) return null;
            const regPos = regionRows.filter(r => r.positive).length;
            const regSent = regPos === regionRows.length ? "All Up" : regPos === 0 ? "All Down" : "Mixed";
            const regColor = regPos === regionRows.length ? "text-emerald-400" : regPos === 0 ? "text-rose-400" : "text-amber-400";
            return (
              <div key={region} className={`rounded-2xl border p-4 ${cls}`}>
                <p className="mb-2 text-[11px] font-bold text-text-secondary">{region}</p>
                <p className={`mb-3 text-[18px] font-black ${regColor}`}>{regSent}</p>
                <div className="space-y-1">
                  {regionRows.map(r => (
                    <div key={r.name} className="flex justify-between text-[10px]">
                      <span className="text-text-muted">{r.name}</span>
                      <span className={r.positive ? "text-emerald-400" : "text-rose-400"}>{r.pct}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
