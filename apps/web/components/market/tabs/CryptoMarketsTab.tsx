"use client";

import { useEffect, useState } from "react";
import { Bitcoin } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

// Crypto Markets (enhancement 2026-10-20). Separate tab, gated server-side by
// settings.crypto_markets_enabled (defaults OFF) and client-side by the tab's
// own visibility flag. Data via the existing Yahoo integration — verified
// coverage for BTC/ETH/SOL/XRP/BNB. Never fabricates a price, timestamp, or
// volume: a failed fetch renders an explicit "Unavailable" state.

const FRESHNESS_META: Record<string, { label: string; cls: string }> = {
  live:        { label: "Live",        cls: "text-emerald-400 bg-emerald-500/10" },
  delayed:     { label: "Delayed",     cls: "text-amber-400 bg-amber-500/10"     },
  unknown:     { label: "Unknown",     cls: "text-slate-400 bg-slate-500/10"     },
  unavailable: { label: "Unavailable", cls: "text-rose-400 bg-rose-500/10"       },
};

function fmtAsOf(iso?: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", timeZoneName: "short" });
  } catch { return null; }
}

function fmtVolume(v: unknown): string | null {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n) || n <= 0) return null;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
}

export function CryptoMarketsTab() {
  const [assets, setAssets] = useState<any[] | null>(null);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/market/crypto`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { setEnabled(d?.enabled ?? false); setAssets(Array.isArray(d?.assets) ? d.assets : []); })
      .catch(() => { setEnabled(false); setAssets([]); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="space-y-5">
      {[1, 2, 3].map(i => <div key={i} className="h-24 animate-pulse rounded-2xl border border-surface-border/5 bg-text-primary/[0.02]" />)}
    </div>
  );

  if (enabled === false || (assets ?? []).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-surface-border/7 bg-surface-card py-16 text-center">
        <Bitcoin className="mb-3 h-8 w-8 text-text-muted" />
        <p className="text-[14px] font-semibold text-text-secondary">Crypto market data is unavailable right now.</p>
        <p className="mt-1 text-[12px] text-text-muted">Nothing is shown rather than a stale or estimated value.</p>
      </div>
    );
  }

  const rows = assets ?? [];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {rows.map((a) => {
          const meta = FRESHNESS_META[a.freshness] ?? FRESHNESS_META.unknown;
          const asOf = fmtAsOf(a.source_timestamp);
          const vol = fmtVolume(a.volume_24h);
          return (
            <div key={a.symbol}
              className="flex items-center justify-between gap-3 rounded-2xl border border-surface-border/7 bg-surface-card px-5 py-4 hover:border-amber-500/15 transition">
              <div className="flex min-w-0 items-center gap-3">
                <span className="shrink-0 text-[22px]">{a.glyph}</span>
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-bold text-text-primary">{a.name}</p>
                  <p className="mt-0.5 text-[11px] text-text-muted">{a.pair}{vol ? ` · 24h vol ${vol}` : ""}</p>
                </div>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-[16px] font-black text-text-primary">{a.value !== "—" ? `${a.value}` : "No data"}</p>
                <p className={`text-[12px] font-bold ${a.positive ? "text-emerald-400" : "text-rose-400"}`}>
                  {a.pct}{a.pct !== "—" ? <span className="ml-1 text-[9px] font-normal text-text-muted">24h</span> : null}
                </p>
                <div className="mt-1 flex items-center justify-end gap-1.5">
                  <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${meta.cls}`}>{meta.label}</span>
                  {asOf && <span className="text-[9px] text-text-muted">as of {asOf}</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-text-muted">
        Crypto trades 24/7; prices in USD via Yahoo Finance and may be delayed. 24h change is measured against the prior UTC-day close. A delayed or unavailable feed is shown as such — never substituted with a stale value.
      </p>
    </div>
  );
}
