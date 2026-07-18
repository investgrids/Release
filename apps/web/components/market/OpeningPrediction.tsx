"use client";

import React, { useEffect, useState } from "react";
import { API_BASE_URL as API } from "@/lib/api";


interface PredictionData {
  direction:           string;
  confidence:          number | null;
  range_low:           number;
  range_high:          number;
  primary_drivers:     string[];
  risks:               string[];
  conflicting_signals: string[];
  reasoning:           string;
  historical_note:     string | null;
  uncertainty_note:    string | null;
  ai_generated:        boolean;
}

interface SignalData {
  gift_nifty?:      { value: string; change: string; positive: boolean; premium_pct?: number; opening_range?: { low: number; high: number } };
  india_vix?:       { value: string; float: number; level: string };
  fii?:             { net: number | null; buying: boolean | null; available: boolean };
  brent_crude?:     { value: string; change: string; direction: string };
  us_futures?:      { name: string; value: string; pct: string; positive: boolean }[];
  asian_markets?:   { name: string; value: string; pct: string; positive: boolean }[];
  global_sentiment?: { label: string; pct_positive: number; positive_count: number; total: number };
}

interface EventData {
  today:       { title: string; category: string }[];
  tomorrow:    { title: string; category: string }[];
  mie_signals: { title: string; urgency: number }[];
}

interface HistoricalData {
  avg_nifty_1d:             number | null;
  bullish_sessions:         number;
  total_sessions:           number;
  historical_accuracy_hint: string | null;
  similar_events:           { event_title: string; nifty_1d: number | null }[];
}

interface OpeningPredictionResponse {
  prediction:   PredictionData;
  signals:      SignalData;
  events:       EventData;
  historical:   HistoricalData;
  generated_at: string;
}

function directionColor(dir: string) {
  if (dir === "Positive") return { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", dot: "bg-emerald-400" };
  if (dir === "Negative") return { text: "text-rose-400", bg: "bg-rose-500/10", border: "border-rose-500/20", dot: "bg-rose-400" };
  return { text: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", dot: "bg-amber-400" };
}

function dirLabel(dir: string) {
  if (dir === "Positive") return "Likely Positive Opening";
  if (dir === "Negative") return "Likely Negative Opening";
  return "Flat / Neutral Opening";
}

function SignalChip({ label, value, positive }: { label: string; value: string; positive?: boolean | null }) {
  const col = positive === true
    ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/8"
    : positive === false
    ? "text-rose-400 border-rose-500/20 bg-rose-500/8"
    : "text-slate-400 border-white/10 bg-white/4";
  return (
    <div className={`flex items-center gap-1 rounded-lg border px-2 py-1 ${col}`} style={{ background: "rgba(255,255,255,0.03)" }}>
      <span className="text-[9px] font-bold uppercase tracking-[0.12em] text-slate-500">{label}</span>
      <span className="text-[11px] font-bold">{value}</span>
      {positive !== null && positive !== undefined && (
        <svg viewBox="0 0 8 8" className={`h-2 w-2 shrink-0 ${positive ? "text-emerald-400" : "text-rose-400"}`} fill="currentColor">
          <path d={positive ? "M4 1 L7 6 L1 6 Z" : "M4 7 L7 2 L1 2 Z"} />
        </svg>
      )}
    </div>
  );
}

function EventPill({ title, category }: { title: string; category: string }) {
  const catMap: Record<string, string> = {
    Results: "bg-violet-500/15 text-violet-300 border-violet-500/20",
    RBI:     "bg-blue-500/15 text-blue-300 border-blue-500/20",
    Macro:   "bg-indigo-500/15 text-indigo-300 border-indigo-500/20",
    Global:  "bg-orange-500/15 text-orange-300 border-orange-500/20",
    Government: "bg-teal-500/15 text-teal-300 border-teal-500/20",
  };
  const cls = catMap[category] ?? "bg-slate-500/15 text-slate-300 border-slate-500/20";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${cls}`}>
      {title}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number | null | undefined }) {
  const unscored = value === null || value === undefined;
  const color = unscored ? "#64748b" : value >= 70 ? "#22c55e" : value >= 55 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 flex-1 rounded-full bg-white/6 overflow-hidden">
        {!unscored && (
          <div className="absolute inset-y-0 left-0 rounded-full transition-all duration-700"
            style={{ width: `${value}%`, background: color }} />
        )}
      </div>
      <span className="text-[11px] font-black" style={{ color }}>{unscored ? "Unscored" : `${value}%`}</span>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      <div className="h-5 w-2/5 rounded-md bg-white/6" />
      <div className="h-10 w-3/4 rounded-lg bg-white/4" />
      <div className="flex gap-2">
        {[...Array(5)].map((_, i) => <div key={i} className="h-7 w-24 rounded-lg bg-white/5" />)}
      </div>
      <div className="h-16 w-full rounded-lg bg-white/4" />
    </div>
  );
}

export default function OpeningPrediction() {
  const [data, setData] = useState<OpeningPredictionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetch_() {
      try {
        const r = await fetch(`${API}/api/market/opening-prediction`, { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        setData(json);
      } catch (e: any) {
        setError(e.message ?? "Failed to load");
      } finally {
        setLoading(false);
      }
    }
    fetch_();
  }, []);

  const pred      = data?.prediction;
  const signals   = data?.signals    ?? {};
  const events    = data?.events     ?? { today: [], tomorrow: [], mie_signals: [] };
  const hist      = data?.historical ?? { avg_nifty_1d: null, bullish_sessions: 0, total_sessions: 0, historical_accuracy_hint: null, similar_events: [] };
  const dc        = pred ? directionColor(pred.direction) : directionColor("Neutral");
  const generated = data?.generated_at ? new Date(data.generated_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : null;

  return (
    <div className="rounded-xl border border-white/8 bg-[#070b14] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/6 px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/15">
            <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5 text-indigo-400" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div>
            <h3 className="text-[13px] font-bold text-white leading-none">Tomorrow&apos;s Opening Prediction</h3>
            <p className="text-[10px] text-slate-500 mt-0.5">5-layer AI · Signal + Event + Historical + Reasoning</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {generated && <span className="text-[9px] text-slate-600">{generated}</span>}
          <span className="flex items-center gap-1 rounded-full border border-indigo-500/25 bg-indigo-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-indigo-400">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
            Live AI
          </span>
        </div>
      </div>

      <div className="p-5 space-y-5">
        {loading && <LoadingSkeleton />}

        {error && !data && (
          <div className="flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/8 px-4 py-3">
            <span className="text-[11px] text-rose-400">Prediction unavailable · {error}</span>
          </div>
        )}

        {pred && (
          <>
            {/* ── Verdict row ─────────────────────────────────────────────── */}
            <div className={`flex items-center justify-between rounded-xl border px-4 py-3 ${dc.bg} ${dc.border}`}>
              <div className="flex items-center gap-3">
                <div className={`h-2.5 w-2.5 rounded-full shrink-0 ${dc.dot}`} />
                <div>
                  <p className={`text-[18px] font-black leading-none ${dc.text}`}>{dirLabel(pred.direction)}</p>
                  {pred.range_low !== undefined && (
                    <p className="mt-1 text-[11px] text-slate-400">
                      Expected range:&nbsp;
                      <span className="font-bold text-white">
                        {pred.range_low >= 0 ? "+" : ""}{pred.range_low} to {pred.range_high >= 0 ? "+" : ""}{pred.range_high} pts
                      </span>
                      &nbsp;from prev. close
                    </p>
                  )}
                </div>
              </div>
              <div className="shrink-0 text-right min-w-[80px]">
                <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500 mb-1">Confidence</p>
                <ConfidenceBar value={pred.confidence} />
                {pred.ai_generated === false && (
                  <p className="mt-0.5 text-[8px] text-slate-600">formula estimate</p>
                )}
              </div>
            </div>

            {/* ── Signal Layer ────────────────────────────────────────────── */}
            {(signals.gift_nifty || signals.india_vix || signals.fii || signals.brent_crude) && (
              <div>
                <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600">
                  Signal Layer
                </p>
                <div className="flex flex-wrap gap-2">
                  {signals.gift_nifty && (
                    <SignalChip label="Gift Nifty" value={`${signals.gift_nifty.value} (${signals.gift_nifty.change})`} positive={signals.gift_nifty.positive} />
                  )}
                  {signals.india_vix && (
                    <SignalChip label={`VIX · ${signals.india_vix.level}`} value={signals.india_vix.value} positive={null} />
                  )}
                  {signals.fii?.available && signals.fii.net !== null && (
                    <SignalChip
                      label="FII"
                      value={`${signals.fii.net >= 0 ? "+" : ""}₹${Math.abs(signals.fii.net).toLocaleString("en-IN", { maximumFractionDigits: 0 })}Cr`}
                      positive={signals.fii.buying}
                    />
                  )}
                  {signals.brent_crude && (
                    <SignalChip label="Brent" value={`${signals.brent_crude.value} ${signals.brent_crude.change}`} positive={signals.brent_crude.direction === "falling" ? true : signals.brent_crude.direction === "rising" ? false : null} />
                  )}
                  {(signals.us_futures ?? []).slice(0, 2).map((f) => (
                    <SignalChip key={f.name} label={f.name.replace(" Futures", "").replace(" Fut.", "")} value={f.pct} positive={f.positive} />
                  ))}
                  {signals.global_sentiment && (
                    <SignalChip
                      label="Global"
                      value={`${signals.global_sentiment.positive_count}/${signals.global_sentiment.total} ↑ · ${signals.global_sentiment.label}`}
                      positive={signals.global_sentiment.pct_positive >= 55 ? true : signals.global_sentiment.pct_positive < 40 ? false : null}
                    />
                  )}
                </div>
              </div>
            )}

            {/* ── Event Layer ─────────────────────────────────────────────── */}
            {(events.today.length > 0 || events.tomorrow.length > 0 || events.mie_signals.length > 0) && (
              <div>
                <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600">
                  Event Layer
                </p>
                <div className="space-y-2">
                  {events.today.length > 0 && (
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
                      <span className="text-[9px] font-bold uppercase tracking-wide text-slate-600 shrink-0">Today</span>
                      {events.today.map((e) => <EventPill key={e.title} title={e.title} category={e.category} />)}
                    </div>
                  )}
                  {events.tomorrow.length > 0 && (
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
                      <span className="text-[9px] font-bold uppercase tracking-wide text-slate-600 shrink-0">Tomorrow</span>
                      {events.tomorrow.map((e) => <EventPill key={e.title} title={e.title} category={e.category} />)}
                    </div>
                  )}
                  {events.mie_signals.length > 0 && (
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
                      <span className="text-[9px] font-bold uppercase tracking-wide text-amber-600/80 shrink-0">Breaking</span>
                      {events.mie_signals.map((e) => (
                        <span key={e.title} className="inline-flex items-center gap-1 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-amber-300">
                          {e.title}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Drivers + Risks ─────────────────────────────────────────── */}
            {(pred.primary_drivers?.length > 0 || pred.risks?.length > 0) && (
              <div className="grid grid-cols-2 gap-4">
                {pred.primary_drivers?.length > 0 && (
                  <div>
                    <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600">
                      Primary Drivers
                    </p>
                    <ul className="space-y-1.5">
                      {pred.primary_drivers.map((d, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <div className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />
                          <span className="text-[11px] text-slate-300 leading-snug">{d}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {pred.risks?.length > 0 && (
                  <div>
                    <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600">
                      Risks
                    </p>
                    <ul className="space-y-1.5">
                      {pred.risks.map((r, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <div className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-rose-400" />
                          <span className="text-[11px] text-slate-300 leading-snug">{r}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* ── Conflicting Signals ─────────────────────────────────────── */}
            {pred.conflicting_signals?.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 rounded-lg border border-amber-500/15 bg-amber-500/6 px-3 py-2">
                <span className="text-[9px] font-bold uppercase tracking-wide text-amber-500/80 shrink-0">Conflicting</span>
                {pred.conflicting_signals.map((s, i) => (
                  <span key={i} className="text-[10px] text-amber-300/80">{s}{i < pred.conflicting_signals.length - 1 ? " ·" : ""}</span>
                ))}
              </div>
            )}

            {/* ── AI Reasoning ────────────────────────────────────────────── */}
            {pred.reasoning && (
              <div className="rounded-xl border border-indigo-500/12 bg-indigo-500/5 px-4 py-3.5">
                <p className="mb-1.5 text-[9px] font-bold uppercase tracking-[0.16em] text-indigo-500/70">
                  AI Reasoning
                </p>
                <p className="text-[12px] leading-relaxed text-slate-300">{pred.reasoning}</p>
                {pred.uncertainty_note && (
                  <p className="mt-2 text-[10px] italic text-slate-500">{pred.uncertainty_note}</p>
                )}
              </div>
            )}

            {/* ── Historical Layer ────────────────────────────────────────── */}
            {(hist.total_sessions > 0 || hist.historical_accuracy_hint) && (
              <div className="flex items-start gap-3 rounded-lg border border-white/6 bg-white/2 px-4 py-3">
                <svg viewBox="0 0 24 24" fill="none" className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                <div>
                  <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600 mb-1">Historical Similarity</p>
                  {hist.historical_accuracy_hint && (
                    <p className="text-[11px] text-slate-400">{hist.historical_accuracy_hint}</p>
                  )}
                  {hist.avg_nifty_1d !== null && (
                    <p className="mt-0.5 text-[11px] text-slate-400">
                      Avg next-day move:&nbsp;
                      <span className={`font-bold ${hist.avg_nifty_1d >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {hist.avg_nifty_1d >= 0 ? "+" : ""}{hist.avg_nifty_1d}%
                      </span>
                    </p>
                  )}
                  {pred.historical_note && (
                    <p className="mt-0.5 text-[11px] text-slate-400 italic">{pred.historical_note}</p>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
