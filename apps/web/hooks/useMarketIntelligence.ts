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
import { API_BASE_URL as API } from "@/lib/api";
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

// Shared badge colors for EventTriage's priority_tier (Critical/High/Medium/Low
// — see _compute_priority() in engine.py) so every consumer (homepage,
// Live Market) renders the same tier the same way.
export const PRIORITY_TIER_CLS: Record<string, string> = {
  Critical: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  High:     "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Medium:   "bg-sky-500/15 text-sky-300 border-sky-500/30",
  Low:      "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

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
  // Richer fields carried through for consumers that want more than the
  // compact homepage card (e.g. the Live Market tab's own card design) —
  // all sourced from EventTriage, nothing synthesized.
  headlineRaw?: string;
  oneLiner?: string;
  confidence?: number | null;
  marketImpact?: string | null;
  priorityTier?: string;
  sectors?: string[];
  tickers?: string[];
}

function triagedToEntry(evt: IntelligenceEvent): FeedEntry {
  const isAlert = evt.urgency >= 7;
  return {
    key: `triaged-${evt.id}-${evt.ts}`,
    kind: isAlert ? "alert" : "update",
    ts: evt.ts,
    headline: evt.one_liner || evt.headline,
    sub: [...(evt.sectors ?? []), ...(evt.tickers ?? [])].slice(0, 3).join(" · ") || evt.source,
    // Not every triaged event has a row in the events table: NSE/BSE items
    // (id prefix "nse-"/"bse-") and all policy items do — see
    // ingest_tasks.py's _create_events — but RSS items ("RSS items do NOT
    // become Events (too generic)", same file) and synthetic price-move /
    // story-update ids (uuid4 / "story-update") don't, and would 404 at
    // /events/{id}. "rss-" is the one prefix confirmed non-event-backed;
    // everything else that isn't real is caught by the id format below.
    href: (evt.id && !evt.id.startsWith("rss-") && (evt.source === "news" || evt.source === "policy"))
      ? `/events/${evt.id}`
      : evt.tickers?.[0] ? `/companies/${evt.tickers[0]}` : undefined,
    // priority_tier (Critical/High/Medium/Low) is the more meaningful signal
    // — it's what homepage filters on — so prefer it for the badge; fall
    // back to the urgency-based ALERT/UPDATE split only if a tier is
    // somehow missing (e.g. an older cached SSE payload).
    badge: evt.priority_tier
      ? { label: evt.priority_tier, cls: PRIORITY_TIER_CLS[evt.priority_tier] ?? PRIORITY_TIER_CLS.Low }
      : isAlert
        ? { label: "ALERT", cls: "bg-rose-500/15 text-rose-300 border-rose-500/30" }
        : { label: "UPDATE", cls: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
    headlineRaw: evt.headline,
    oneLiner: evt.one_liner,
    confidence: evt.confidence,
    marketImpact: evt.market_impact,
    priorityTier: evt.priority_tier,
    sectors: evt.sectors ?? [],
    tickers: evt.tickers ?? [],
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

export function useLiveFeed(limit?: number, opts?: { criticalHighOnly?: boolean }): FeedEntry[] {
  const { intelligenceEvents, scoreUpdates } = useAlerts();
  const criticalHighOnly = opts?.criticalHighOnly ?? false;

  // The SSE stream (AlertProvider) only pushes events that happen *after*
  // the connection opens — a quiet news cycle can leave it empty for a long
  // time even though the backend already has plenty of real recent triaged
  // events. Seed once from the same real feed (/api/mie/feed, the endpoint
  // this widget was built for — see mie.py's docstring) so the feed shows
  // real history immediately; live SSE items merge on top as they arrive.
  // When filtering to Critical/High only, fetch a wider raw window since
  // most triaged events land in Medium/Low and would otherwise get filtered
  // down to near-nothing.
  const fetchLimit = criticalHighOnly ? Math.max(50, (limit ?? 10) * 6) : (limit ?? 40);
  const [seed, setSeed] = useState<IntelligenceEvent[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/mie/feed?limit=${fetchLimit}&min_urgency=4&hours=24`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (cancelled || !Array.isArray(d?.feed)) return;
        setSeed(d.feed.map((f: any): IntelligenceEvent => ({
          id: f.id, headline: f.headline, urgency: f.urgency,
          importance: f.importance, confidence: f.confidence,
          sentiment: f.sentiment, horizon: f.horizon, market_impact: f.market_impact,
          is_structural: f.is_structural, direction: f.direction, one_liner: f.one_liner,
          themes: f.themes ?? [], sectors: f.sectors ?? [], tickers: f.tickers ?? [],
          refresh_homepage: false, source: f.source, ts: f.triaged_at,
          priority_score: f.priority_score, priority_tier: f.priority_tier,
        })));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [fetchLimit]);

  return useMemo(() => {
    const liveIds = new Set(intelligenceEvents.map(e => e.id));
    let merged: FeedEntry[] = [
      ...intelligenceEvents.map(triagedToEntry),
      ...seed.filter(e => !liveIds.has(e.id)).map(triagedToEntry),
      ...scoreUpdates.map(scoreUpdateToEntry),
    ];
    if (criticalHighOnly) {
      // score_update entries carry no priority_tier — they're a different
      // signal type (score changes, not triaged news) and are excluded from
      // the "high impact only" view rather than guessed into a tier.
      merged = merged.filter(e => e.priorityTier === "Critical" || e.priorityTier === "High");
    }
    merged.sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());
    return limit ? merged.slice(0, limit) : merged.slice(0, 40);
  }, [intelligenceEvents, scoreUpdates, seed, limit, criticalHighOnly]);
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
