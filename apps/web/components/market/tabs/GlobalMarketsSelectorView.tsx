"use client";

import { useEffect, useMemo, useState } from "react";
import { Globe, ArrowUpRight, Lock } from "lucide-react";
import Link from "next/link";
import { API_BASE_URL as API } from "@/lib/api";
import { MarketSelector } from "@/components/market/MarketSelector";
import {
  getMarket,
  DEFAULT_MARKET_ID,
  type MarketId,
  type SectionAvailability,
} from "@/lib/marketRegistry";

// Global Markets selector experience (Phase C — 2026-10-25). Gated behind
// NEXT_PUBLIC_GLOBAL_MARKET_SELECTOR_ENABLED; when the flag is off, MarketClient
// renders the original GlobalMarketsTab instead, so existing behavior/tests are
// untouched. The selected market (from the typed registry) drives BOTH the data
// shown (index strip filtered from the existing /api/market/global response) and
// every section's availability. Unsupported sections state the limitation
// honestly — an index-only market never masquerades as a full stock dashboard.

const FRESHNESS_META: Record<string, { label: string; cls: string }> = {
  live: { label: "Live", cls: "text-emerald-400 bg-emerald-500/10" },
  delayed: { label: "Delayed", cls: "text-amber-400 bg-amber-500/10" },
  closed: { label: "Closed", cls: "text-slate-400 bg-slate-500/10" },
  unknown: { label: "Unknown", cls: "text-slate-400 bg-slate-500/10" },
  unavailable: { label: "Unavailable", cls: "text-rose-400 bg-rose-500/10" },
};

function fmtAsOf(iso?: string | null, tz?: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", timeZone: tz || undefined, timeZoneName: "short" });
  } catch {
    return null;
  }
}

interface IndexRow {
  name: string; flag?: string; value: string; pct: string; change?: string;
  positive: boolean; source?: string; source_timestamp?: string | null;
  session?: string | null; timezone?: string | null; freshness?: string;
}
interface FutureRow extends IndexRow { ticker: string; instrument: string; }

function QuoteCard({ row }: { row: IndexRow | FutureRow }) {
  const meta = FRESHNESS_META[row.freshness ?? "unknown"] ?? FRESHNESS_META.unknown;
  const asOf = fmtAsOf(row.source_timestamp, row.timezone);
  const hasData = row.value !== "—";
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-surface-border/7 bg-surface-card px-5 py-4 hover:border-sky-500/15 transition">
      <div className="flex min-w-0 items-center gap-3">
        {row.flag ? <span className="shrink-0 text-[22px]">{row.flag}</span> : null}
        <div className="min-w-0">
          <p className="truncate text-[13px] font-bold text-text-primary">{row.name}</p>
          <p className="mt-0.5 text-[11px] text-text-muted">{hasData ? `Last: ${row.value}` : "No data"}</p>
        </div>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-[16px] font-black text-text-primary tabular-nums">{row.value}</p>
        <p className={`text-[12px] font-bold tabular-nums ${row.positive ? "text-emerald-400" : "text-rose-400"}`}>
          {row.change && row.change !== "—" ? <span className="mr-1 text-text-muted font-normal">{row.change}</span> : null}
          {row.pct}
        </p>
        {row.freshness ? (
          <div className="mt-1 flex items-center justify-end gap-1.5">
            <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${meta.cls}`}>{meta.label}</span>
            {asOf ? <span className="text-[9px] text-text-muted">as of {asOf}</span> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function SectionShell({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3" aria-label={title}>
      <div>
        <h3 className="text-[13px] font-bold text-text-primary">{title}</h3>
        {sub ? <p className="mt-0.5 text-[11px] text-text-muted">{sub}</p> : null}
      </div>
      {children}
    </section>
  );
}

function LimitationCard({ availability }: { availability: SectionAvailability }) {
  if (availability.status === "external") {
    return (
      <Link
        href={availability.href}
        className="flex items-center justify-between gap-3 rounded-2xl border border-sky-500/15 bg-sky-500/[0.04] px-5 py-4 text-left transition hover:border-sky-500/30"
      >
        <span className="text-[12px] text-text-secondary">{availability.label}</span>
        <ArrowUpRight className="h-4 w-4 shrink-0 text-sky-400" />
      </Link>
    );
  }
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] px-5 py-4">
      <Lock className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
      {availability.status === "unavailable" ? (
        <div>
          <p className="text-[12px] font-semibold text-text-secondary">{availability.title}</p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-text-muted">{availability.detail}</p>
        </div>
      ) : null}
    </div>
  );
}

export function GlobalMarketsSelectorView() {
  const [selected, setSelected] = useState<MarketId>(DEFAULT_MARKET_ID);
  const [allIndices, setAllIndices] = useState<IndexRow[] | null>(null);
  const [futures, setFutures] = useState<{ enabled: boolean; rows: FutureRow[] }>({ enabled: false, rows: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/market/global`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setAllIndices(Array.isArray(d?.indices) ? d.indices : []))
      .catch(() => setAllIndices([]))
      .finally(() => setLoading(false));
    fetch(`${API}/api/market/futures`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setFutures({ enabled: !!d?.enabled, rows: Array.isArray(d?.futures) ? d.futures : [] }))
      .catch(() => setFutures({ enabled: false, rows: [] }));
  }, []);

  const market = getMarket(selected)!;

  // Index strip for the selected market — filtered from the single shared dataset,
  // so switching markets can never leave another market's rows behind.
  const strip = useMemo(() => {
    const byName = new Map((allIndices ?? []).map((r) => [r.name, r]));
    return market.indexNames.map((n) => byName.get(n)).filter((r): r is IndexRow => !!r);
  }, [allIndices, market]);

  return (
    <div className="space-y-6">
      <MarketSelector selected={selected} onSelect={setSelected} />

      {/* role=tabpanel keyed to the market so assistive tech announces the switch */}
      <div role="tabpanel" aria-label={`${market.label} market`} key={market.id} className="space-y-6">
        {/* ── Index strip (cash) ───────────────────────────────────────────── */}
        {market.sections.indexStrip.status === "available" ? (
          <SectionShell title="Index strip" sub="Cash indices — last official value; a closed market shows its last close, not a live tick.">
            {loading ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {[1, 2, 3].map((i) => <div key={i} className="h-20 animate-pulse rounded-2xl border border-surface-border/5 bg-text-primary/[0.02]" />)}
              </div>
            ) : strip.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-surface-border/7 bg-surface-card py-12 text-center">
                <Globe className="mb-3 h-7 w-7 text-text-muted" />
                <p className="text-[13px] font-semibold text-text-secondary">Index data is unavailable right now.</p>
                <p className="mt-1 text-[11px] text-text-muted">Nothing is shown rather than a stale estimate.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {strip.map((row) => <QuoteCard key={row.name} row={row} />)}
              </div>
            )}
          </SectionShell>
        ) : (
          // India: route out to existing rich surfaces instead of a native strip.
          <SectionShell title={`${market.label} market data`} sub="India is covered by this hub's existing tabs — opened rather than duplicated here.">
            <LimitationCard availability={market.sections.indexStrip} />
          </SectionShell>
        )}

        {/* ── Futures (separate from cash) ─────────────────────────────────── */}
        <SectionShell title="Index futures" sub="Shown separately from cash — a prior cash close is never presented as a live futures quote.">
          {market.sections.futures.status === "available" ? (
            !futures.enabled ? (
              <div className="rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] px-5 py-4 text-[12px] text-text-muted">
                Futures feed is disabled in this environment.
              </div>
            ) : futures.rows.length === 0 ? (
              <div className="rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] px-5 py-4 text-[12px] text-text-muted">
                Futures data is unavailable right now — nothing is shown rather than a stale value.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {futures.rows.map((row) => <QuoteCard key={row.ticker} row={row} />)}
              </div>
            )
          ) : (
            <LimitationCard availability={market.sections.futures} />
          )}
        </SectionShell>

        {/* ── Data-blocked / routed sections — honest, never fabricated ─────── */}
        <SectionShell title="Top gainers & losers">
          <LimitationCard availability={market.sections.movers} />
        </SectionShell>
        <SectionShell title="Sector heatmap">
          <LimitationCard availability={market.sections.sectorHeatmap} />
        </SectionShell>
        <SectionShell title="Market news">
          <LimitationCard availability={market.sections.news} />
        </SectionShell>
      </div>

      <p className="border-t border-surface-border/7 pt-3 text-[10px] text-text-muted">
        Index and futures quotes as reported by the data source (Yahoo Finance); values may be delayed. Market-specific stock movers, sector data and news are available only where a supported data source exists — otherwise the limitation is shown, never fabricated.
      </p>
    </div>
  );
}
