"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Clock, TrendingUp, TrendingDown, BookOpen, Zap, ChevronRight } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────────

interface HistoricalWinner {
  symbol:     string;
  name:       string;
  return_1w?: number;
  return_1m?: number;
  return_1d?: number;
  reason:     string;
}

interface HistoricalEvent {
  id:                string;
  event_title:       string;
  event_date:        string;
  category:          string;
  sentiment:         string | null;
  sectors:           string[];
  market_regime:     string | null;
  what_happened:     string | null;
  key_lesson:        string | null;
  nifty_1d:          number | null;
  nifty_3d:          number | null;
  nifty_1w:          number | null;
  nifty_1m:          number | null;
  sector_reactions:  Record<string, number>;
  historical_winners: HistoricalWinner[];
  historical_losers:  HistoricalWinner[];
  opportunity_score: number | null;
  risk_score:        number | null;
  confidence:        number | null;
  similarity:        number;
  interest_rate_level: number | null;
  vix_level:         number | null;
}

interface HistoricalMemoryProps {
  category?:            string;
  sectors?:             string[];
  sentiment?:           string;
  market_regime?:       string;
  interest_rate_trend?: string;
  crude_trend?:         string;
  limit?:               number;
  className?:           string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function pct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`;
}

function pctCls(v: number | null | undefined): string {
  if (v == null) return "text-slate-500";
  return v >= 0 ? "text-emerald-400" : "text-rose-400";
}

function sentimentBadge(s: string | null): { label: string; cls: string } {
  if (!s) return { label: "Neutral", cls: "bg-slate-700/60 text-slate-400" };
  if (s === "bullish")  return { label: "Bullish",  cls: "bg-emerald-500/15 text-emerald-400" };
  if (s === "bearish")  return { label: "Bearish",  cls: "bg-rose-500/15 text-rose-400" };
  if (s === "mixed")    return { label: "Mixed",    cls: "bg-amber-500/15 text-amber-400" };
  return { label: s, cls: "bg-slate-700/60 text-slate-400" };
}

function similarityColor(sim: number): string {
  if (sim >= 75) return "#22c55e";
  if (sim >= 50) return "#f59e0b";
  return "#64748b";
}

function bestReturn(w: HistoricalWinner): number {
  return w.return_1w ?? w.return_1m ?? w.return_1d ?? 0;
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function SimilarityRing({ pct: sim }: { pct: number }) {
  const color  = similarityColor(sim);
  const radius = 16;
  const circ   = 2 * Math.PI * radius;
  const stroke = circ * (sim / 100);

  return (
    <div className="relative flex items-center justify-center" style={{ width: 44, height: 44 }}>
      <svg width="44" height="44" className="-rotate-90">
        <circle cx="22" cy="22" r={radius} fill="none" stroke="#1e293b" strokeWidth="3" />
        <circle cx="22" cy="22" r={radius} fill="none" stroke={color}
          strokeWidth="3" strokeDasharray={`${stroke} ${circ}`} strokeLinecap="round" />
      </svg>
      <span className="absolute text-[10px] font-black" style={{ color }}>
        {Math.round(sim)}%
      </span>
    </div>
  );
}

function NiftyBadge({ label, value }: { label: string; value: number | null }) {
  if (value == null) return null;
  const pos = value >= 0;
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-[8px] font-semibold uppercase tracking-wider text-slate-600">{label}</span>
      <span className={`text-[12px] font-black ${pos ? "text-emerald-400" : "text-rose-400"}`}>
        {pct(value)}
      </span>
    </div>
  );
}

function EventCard({ ev, index }: { ev: HistoricalEvent; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const sb = sentimentBadge(ev.sentiment);
  const topWinners = ev.historical_winners.slice(0, 3);
  const topLosers  = ev.historical_losers.slice(0, 3);

  return (
    <div className="overflow-hidden rounded-[16px] border border-white/[0.06] bg-[#0a1628]/80">
      {/* Header row */}
      <button
        className="flex w-full items-start gap-3 px-4 py-3.5 text-left transition hover:bg-white/[0.02]"
        onClick={() => setExpanded(e => !e)}
      >
        {/* Rank */}
        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-800 text-[9px] font-black text-slate-400">
          {index + 1}
        </span>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-[13px] font-semibold text-white leading-snug">{ev.event_title}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] text-slate-500 flex items-center gap-1">
              <Clock className="h-2.5 w-2.5" /> {ev.event_date}
            </span>
            <span className={`rounded-full border px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wider ${sb.cls}`}
              style={{ borderColor: "transparent" }}>
              {sb.label}
            </span>
            <span className="rounded-full bg-slate-800 px-1.5 py-0.5 text-[8px] text-slate-400">
              {ev.category}
            </span>
          </div>
        </div>

        {/* Similarity ring */}
        <SimilarityRing pct={ev.similarity} />
      </button>

      {/* Nifty reaction strip */}
      <div className="flex items-center gap-4 border-t border-white/[0.05] bg-[#060d1b] px-4 py-2.5">
        <span className="text-[9px] font-black uppercase tracking-widest text-slate-600">Nifty Reaction</span>
        <div className="flex items-center gap-4 ml-auto">
          <NiftyBadge label="1 Day"  value={ev.nifty_1d} />
          <NiftyBadge label="3 Day"  value={ev.nifty_3d} />
          <NiftyBadge label="1 Week" value={ev.nifty_1w} />
          <NiftyBadge label="1 Month" value={ev.nifty_1m} />
        </div>
      </div>

      {/* Winners + Losers (always visible) */}
      <div className="grid grid-cols-2 gap-px border-t border-white/[0.05]">
        {/* Winners */}
        <div className="bg-[#060d1b] px-3 py-2.5">
          <p className="mb-1.5 flex items-center gap-1 text-[8px] font-black uppercase tracking-widest text-emerald-600">
            <TrendingUp className="h-2.5 w-2.5" /> Historical Winners
          </p>
          {topWinners.length > 0 ? (
            <div className="space-y-1">
              {topWinners.map((w, i) => (
                <div key={i} className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold text-slate-300 truncate">{w.name || w.symbol}</span>
                  <span className="shrink-0 text-[11px] font-black text-emerald-400">
                    {pct(bestReturn(w))}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-slate-600">No clear sector winners</p>
          )}
        </div>

        {/* Losers */}
        <div className="border-l border-white/[0.05] bg-[#060d1b] px-3 py-2.5">
          <p className="mb-1.5 flex items-center gap-1 text-[8px] font-black uppercase tracking-widest text-rose-700">
            <TrendingDown className="h-2.5 w-2.5" /> Historical Losers
          </p>
          {topLosers.length > 0 ? (
            <div className="space-y-1">
              {topLosers.map((l, i) => (
                <div key={i} className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold text-slate-300 truncate">{l.name || l.symbol}</span>
                  <span className="shrink-0 text-[11px] font-black text-rose-400">
                    {pct(bestReturn(l))}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-slate-600">No significant losers</p>
          )}
        </div>
      </div>

      {/* Expandable detail */}
      {expanded && (
        <div className="border-t border-white/[0.05] bg-[#060d1b] px-4 py-3 space-y-3">
          {ev.what_happened && (
            <div>
              <p className="mb-1 text-[8px] font-black uppercase tracking-widest text-slate-600">What Happened</p>
              <p className="text-[12px] leading-[1.6] text-slate-400">{ev.what_happened}</p>
            </div>
          )}
          {ev.key_lesson && (
            <div className="rounded-xl border border-amber-500/[0.15] bg-amber-500/[0.05] px-3 py-2.5">
              <p className="mb-1 text-[8px] font-black uppercase tracking-widest text-amber-500/70">Key Lesson</p>
              <p className="text-[12px] leading-[1.6] text-amber-200/80">{ev.key_lesson}</p>
            </div>
          )}
          {/* Sector reactions */}
          {Object.keys(ev.sector_reactions).length > 0 && (
            <div>
              <p className="mb-1.5 text-[8px] font-black uppercase tracking-widest text-slate-600">Sector Reactions</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(ev.sector_reactions).map(([sec, chg]) => (
                  <span key={sec}
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${chg >= 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
                    {sec} {pct(chg)}
                  </span>
                ))}
              </div>
            </div>
          )}
          {/* Meta */}
          <div className="flex flex-wrap gap-3 pt-0.5">
            {ev.confidence && (
              <span className="text-[10px] text-slate-600">
                Data confidence: <span className="text-slate-400">{ev.confidence}%</span>
              </span>
            )}
            {ev.interest_rate_level && (
              <span className="text-[10px] text-slate-600">
                Repo rate then: <span className="text-slate-400">{ev.interest_rate_level}%</span>
              </span>
            )}
            {ev.vix_level && (
              <span className="text-[10px] text-slate-600">
                VIX then: <span className="text-slate-400">{ev.vix_level.toFixed(1)}</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="flex w-full items-center justify-center gap-1 border-t border-white/[0.04] py-1.5 text-[9px] font-semibold uppercase tracking-wider text-slate-600 transition hover:text-slate-400"
      >
        {expanded ? "Less detail" : "Key lesson + sectors"}
        <ChevronRight className={`h-2.5 w-2.5 transition-transform ${expanded ? "rotate-90" : ""}`} />
      </button>
    </div>
  );
}

// ── Aggregate insights bar ─────────────────────────────────────────────────────

function InsightBar({ events }: { events: HistoricalEvent[] }) {
  if (events.length < 2) return null;

  const withReaction = events.filter(e => e.nifty_1w != null);
  const avgNifty1w   = withReaction.length
    ? withReaction.reduce((s, e) => s + (e.nifty_1w ?? 0), 0) / withReaction.length
    : null;
  const bullish   = events.filter(e => (e.nifty_1w ?? 0) > 1).length;
  const recovered = events.filter(e => (e.nifty_1w ?? 0) > 0).length;

  // Most common winner sector
  const sectorFreq: Record<string, number> = {};
  for (const ev of events) {
    for (const w of ev.historical_winners) {
      // derive sector from name (rough)
      const key = w.name || w.symbol;
      sectorFreq[key] = (sectorFreq[key] || 0) + 1;
    }
  }
  const topStock = Object.entries(sectorFreq).sort((a, b) => b[1] - a[1])[0];

  return (
    <div className="mb-3 rounded-[14px] border border-sky-500/[0.12] bg-sky-500/[0.04] px-4 py-3">
      <p className="mb-2 text-[8px] font-black uppercase tracking-widest text-sky-600">Pattern Across {events.length} Similar Events</p>
      <div className="flex flex-wrap gap-x-6 gap-y-1.5">
        {avgNifty1w != null && (
          <span className="text-[12px] text-slate-400">
            Avg Nifty 1W: <span className={`font-black ${avgNifty1w >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{pct(avgNifty1w)}</span>
          </span>
        )}
        <span className="text-[12px] text-slate-400">
          Recovered in 1W: <span className="font-black text-white">{recovered}/{withReaction.length}</span>
        </span>
        {topStock && (
          <span className="text-[12px] text-slate-400">
            Most consistent winner: <span className="font-black text-emerald-300">{topStock[0]}</span>
            <span className="text-slate-600"> ({topStock[1]}× in similar events)</span>
          </span>
        )}
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export function HistoricalMemory({
  category,
  sectors,
  sentiment,
  market_regime,
  interest_rate_trend,
  crude_trend,
  limit = 5,
  className = "",
}: HistoricalMemoryProps) {
  const [events,  setEvents]  = useState<HistoricalEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams();
    if (category)            params.set("category", category);
    if (sectors?.length)     params.set("sectors",  sectors.join(","));
    if (sentiment)           params.set("sentiment", sentiment);
    if (market_regime)       params.set("market_regime", market_regime);
    if (interest_rate_trend) params.set("interest_rate_trend", interest_rate_trend);
    if (crude_trend)         params.set("crude_trend", crude_trend);
    params.set("limit", String(limit));
    params.set("min_similarity", "20");

    fetch(`${API}/api/historical/similar?${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.events) setEvents(d.events); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [category, sectors?.join(","), sentiment, market_regime, interest_rate_trend, crude_trend, limit]);

  if (loading) {
    return (
      <div className={`space-y-2 ${className}`}>
        {[1, 2, 3].map(i => (
          <div key={i} className="h-24 animate-pulse rounded-[16px] bg-white/[0.03]" />
        ))}
      </div>
    );
  }

  if (!events.length) return null;

  return (
    <div className={className}>
      {/* Section header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="h-3.5 w-3.5 text-slate-500" />
          <h3 className="text-[11px] font-black uppercase tracking-[0.12em] text-slate-400">
            Historical Precedents
          </h3>
          <span className="rounded-full bg-slate-800 px-1.5 py-0.5 text-[9px] font-semibold text-slate-500">
            {events.length} similar events
          </span>
        </div>
        <div className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5">
          <Zap className="h-2.5 w-2.5 text-amber-400" />
          <span className="text-[8px] font-black uppercase tracking-wider text-amber-400/80">Verified Data</span>
        </div>
      </div>

      {/* Aggregate insight bar */}
      <InsightBar events={events} />

      {/* Event cards */}
      <div className="space-y-2">
        {events.map((ev, i) => (
          <EventCard key={ev.id} ev={ev} index={i} />
        ))}
      </div>

      <p className="mt-3 text-[10px] text-slate-700 text-center">
        Reactions are real historical data points, not AI estimates. Similarity scored on category · sector · sentiment · market regime.
      </p>
    </div>
  );
}
