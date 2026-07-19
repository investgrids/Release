"use client";

/**
 * The ONLY way pages should read intelligence data. Every hook here reads
 * from MarketIntelligenceProvider (one shared cache, one 60s refresh timer,
 * one SSE-driven live-update path) or from the app's single shared SSE
 * connection (AlertProvider) — never a page-local fetch to /api/intelligence/*,
 * /api/story/*, /api/theme/*, or similar.
 */

import { useEffect, useMemo, useState } from "react";
import { useMarketIntelligenceContext } from "@/components/MarketIntelligenceProvider";
import { useAlerts, type IntelligenceEvent, type ScoreUpdateEvent } from "@/components/AlertProvider";
import { mieClient } from "@/services/intelligence/mie-client";
import type { SymbolIntelligenceContext, MIEStatus } from "@/types/intelligence";

// ── useMarketIntelligence ───────────────────────────────────────────────────────
// The primary hook. Story, themes, signals, biggest_opportunity, biggest_risk,
// companies_to_watch, market_drivers, tomorrow_watch, market_health — all of it.

export function useMarketIntelligence() {
  return useMarketIntelligenceContext();
}

// ── useLiveFeed ──────────────────────────────────────────────────────────────
// Real-time feed of triaged events + score updates, sourced from the app's
// single shared SSE connection. Consolidates the merge/format logic that
// previously lived inline in components/market/LiveIntelligenceFeed.tsx so
// every consumer (Live Market tab, any future homepage live feed widget)
// gets identical entries instead of each reimplementing the merge.

type FeedKind = "alert" | "update" | "score_update";

export interface FeedEntry {
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
  verified:    "bg-sky-500/15 text-sky-300 border-sky-500/30",
  live:        "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
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

export function useLiveFeed(limit?: number): FeedEntry[] {
  const { intelligenceEvents, scoreUpdates } = useAlerts();
  return useMemo(() => {
    const merged: FeedEntry[] = [
      ...intelligenceEvents.map(triagedToEntry),
      ...scoreUpdates.map(scoreUpdateToEntry),
    ];
    merged.sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());
    return limit ? merged.slice(0, limit) : merged.slice(0, 40);
  }, [intelligenceEvents, scoreUpdates, limit]);
}

// ── useCompanyIntelligence ──────────────────────────────────────────────────────
// Per-symbol context, 30s-cached via mieClient (client owns the cache, this
// hook is just a thin React binding over it).

export function useCompanyIntelligence(symbol: string | null | undefined) {
  const [data, setData] = useState<SymbolIntelligenceContext | null>(null);
  const [loading, setLoading] = useState(!!symbol);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) { setData(null); setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    mieClient.getCompanyContext(symbol)
      .then(d => { if (!cancelled) { setData(d); setError(null); } })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load company intelligence"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [symbol]);

  return { data, loading, error };
}

// ── useMarketStatus ──────────────────────────────────────────────────────────
// Engine health — 10s-cached via mieClient.

export function useMarketStatus(): MIEStatus | null {
  const [status, setStatus] = useState<MIEStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => mieClient.getStatus().then(d => { if (!cancelled) setStatus(d); }).catch(() => {});
    load();
    const id = setInterval(load, 10_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return status;
}
