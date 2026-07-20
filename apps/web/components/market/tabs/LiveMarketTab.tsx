"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { LiveIntelligenceFeed } from "@/components/market/LiveIntelligenceFeed";
import { useMarketIntelligence } from "@/hooks/useMarketIntelligence";
import { mieClient } from "@/services/intelligence/mie-client";
import { compareScoresDesc, impactToStyle } from "@/lib/scoring";
import { API_BASE_URL as API } from "@/lib/api";
import {
  TrendingUp, TrendingDown, Minus, ChevronRight,
  CalendarClock, CheckCircle2, XCircle,
} from "lucide-react";


// ── Types ──────────────────────────────────────────────────────────────────────
type MarketStory = {
  text: string; mood: string; pulse: string; direction: string;
  opportunity: string; risk: string; trader_watch: string;
  investor_watch: string; sector_rotation: string;
  confidence: number | null; generated_at: string;
};
type ThemeData = {
  theme: string; score: number | null; momentum: string;
  top_stocks: string[]; news_count_24h: number; updated_at: string;
};
type FeedItem = {
  id: string; headline: string; urgency: number;
  sentiment: string; direction: string; one_liner: string;
  themes: string[]; sectors: string[]; tickers: string[];
  source: string; triaged_at: string;
};
type ReplayEntry = {
  generated_at: string; mood: string; pulse: string;
  direction: string; story: string; nifty_at: number; vix_at: number; confidence: number;
};
type IndexItem = { name: string; value: string; change: string; positive: boolean; chart?: { value: number }[] };

// ── Helpers ────────────────────────────────────────────────────────────────────
function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

function moodMeta(mood: string): { cls: string; bg: string; border: string } {
  const m = (mood ?? "").toLowerCase();
  if (m.includes("bull") || m.includes("optimis") || m.includes("positive") || m.includes("strong"))
    return { cls: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/25" };
  if (m.includes("bear") || m.includes("pessim") || m.includes("negative") || m.includes("weak"))
    return { cls: "text-rose-400",    bg: "bg-rose-500/10",    border: "border-rose-500/25" };
  if (m.includes("cautious") || m.includes("mixed") || m.includes("uncertain"))
    return { cls: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/25" };
  return   { cls: "text-slate-400",   bg: "bg-slate-500/10",   border: "border-slate-500/20" };
}

function signalColor(text: string) {
  const t = (text ?? "").toLowerCase();
  if (/\b(up|rise|gain|lead|strong|bull|recover|advance|buy)\b/.test(t)) return "text-emerald-400";
  if (/\b(down|fall|drop|lose|weak|bear|declin|sell|pressure)\b/.test(t)) return "text-rose-400";
  return "text-amber-400";
}

function computeHealthScore(data: any, story: MarketStory | null): number {
  let s = 50;
  const niftyChg = parseFloat(data?.indices?.[0]?.change?.replace(/[^0-9.-]/g, "") ?? "0");
  const positive  = data?.indices?.[0]?.positive !== false;
  s += Math.min(Math.max((positive ? niftyChg : -niftyChg) * 4, -18), 18);

  const b = data?.breadth;
  if (b?.advances && b?.declines) {
    const ratio = b.advances / (b.advances + b.declines + 1);
    s += (ratio - 0.5) * 28;
  }

  if (story) {
    const { cls } = moodMeta(story.mood);
    if (cls === "text-emerald-400") s += 7;
    if (cls === "text-rose-400")    s -= 7;
    s += ((story.confidence ?? 50) - 50) * 0.08;
  }

  return Math.round(Math.min(Math.max(s, 0), 100));
}

function MiniSparkline({ data, positive, w = 56, h = 24 }: { data: number[]; positive: boolean; w?: number; h?: number }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;
  const pts = data.map((v, i) =>
    `${pad + (i / (data.length - 1)) * (w - pad * 2)},${pad + (h - pad * 2) - ((v - min) / range) * (h - pad * 2)}`
  ).join(" ");
  const color = positive ? "#22c55e" : "#f43f5e";
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <polyline points={pts} stroke={color} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function CardHeader({ title, sub, href, linkLabel = "View All" }: { title: string; sub?: string; href?: string; linkLabel?: string }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <div>
        <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">{title}</h3>
        {sub && <p className="mt-0.5 text-[9px] text-slate-600">{sub}</p>}
      </div>
      {href && (
        <Link href={href as any} className="shrink-0 flex items-center gap-0.5 text-[10px] font-semibold text-violet-400 hover:text-violet-300 transition">
          {linkLabel} <ChevronRight className="h-3 w-3" />
        </Link>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Top ticker strip + Market Replay trigger
// ─────────────────────────────────────────────────────────────────────────────
function TopTickerRow({ indices, onReplayClick, replayOpen }: { indices: IndexItem[]; onReplayClick: () => void; replayOpen: boolean }) {
  const WANT = ["NIFTY 50", "SENSEX", "BANK NIFTY", "INDIA VIX"];
  const cells = WANT.map(name => indices.find(i => (i.name ?? "").toUpperCase() === name)).filter(Boolean) as IndexItem[];

  return (
    <div className="flex items-stretch gap-3 overflow-x-auto scrollbar-hide">
      <div className="flex flex-1 items-stretch divide-x divide-white/[0.06] rounded-2xl border border-white/[0.07] bg-[#080c14]">
        {cells.map(c => {
          const chart = (c.chart ?? []).map(p => p.value).filter(v => typeof v === "number");
          return (
            <div key={c.name} className="flex min-w-[150px] flex-1 items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">{c.name}</p>
                <p className="text-[14px] font-black tabular-nums text-white leading-tight">{c.value}</p>
                <p className={`text-[10px] font-bold tabular-nums ${c.positive ? "text-emerald-400" : "text-rose-400"}`}>{c.change}</p>
              </div>
              {chart.length >= 2 && <MiniSparkline data={chart} positive={c.positive !== false} />}
            </div>
          );
        })}
      </div>
      <button onClick={onReplayClick}
        className={`shrink-0 flex items-center gap-2 rounded-2xl border px-4 text-[12px] font-bold transition ${
          replayOpen ? "border-violet-500/30 bg-violet-500/10 text-violet-300" : "border-white/[0.08] bg-[#080c14] text-slate-300 hover:border-violet-500/25 hover:text-violet-300"
        }`}>
        <ChevronRight className={`h-3.5 w-3.5 transition-transform ${replayOpen ? "rotate-90" : ""}`} />
        Market Replay
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Market Brief (+ Key Drivers pills) — paired with Market Health gauge
// ─────────────────────────────────────────────────────────────────────────────
function pulseDisplay(p: string): { label: string; cls: string } {
  if (p === "+") return { label: "Bullish", cls: "text-emerald-400" };
  if (p === "-") return { label: "Bearish", cls: "text-rose-400"   };
  return              { label: "Neutral", cls: "text-amber-400"  };
}

function AIMarketBriefAndHealth({ story, storyLoading, themes, health, data, calendar }: {
  story: MarketStory | null; storyLoading: boolean; themes: ThemeData[]; health: number; data: any; calendar: any[];
}) {
  const pulse = story ? pulseDisplay(story.pulse) : null;
  const meta  = moodMeta(story?.mood ?? "");

  // Key Drivers — top 4 real themes by score, momentum-derived status word (never fabricated)
  const drivers = [...themes]
    .filter(t => t.score !== null && t.score !== undefined)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 4)
    .map(t => ({
      label: t.theme,
      status: /rising|up|strong|gaining/i.test(t.momentum ?? "") ? "Positive" : /falling|down|weak|losing/i.test(t.momentum ?? "") ? "Weakening" : "Steady",
      up: /rising|up|strong|gaining/i.test(t.momentum ?? ""),
    }));

  const nextWatch = calendar.slice(0, 3).map((e: any) => e.title).filter(Boolean);

  const scoreColor = health >= 70 ? "#34d399" : health >= 50 ? "#fbbf24" : "#f43f5e";
  const label      = health >= 70 ? "Healthy" : health >= 50 ? "Mixed" : health >= 30 ? "Weak" : "Stressed";
  const r = 54, cx = 74, cy = 68;
  const angle = (health / 100) * 180;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const ex = cx + r * Math.cos(toRad(180 + angle));
  const ey = cy + r * Math.sin(toRad(180 + angle));
  const large = angle > 180 ? 1 : 0;
  const niftyChg = parseFloat(data?.indices?.[0]?.change?.replace(/[^0-9.-]/g, "") ?? "0");
  const niftyPos = data?.indices?.[0]?.positive !== false;
  const b = data?.breadth;

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-white/[0.07] bg-[#080c14] lg:flex-row">
      {/* Brief */}
      <div className="min-w-0 flex-1 p-5">
        <div className="mb-2 flex items-center gap-2">
          <span className="flex h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse" />
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-violet-400">AI Market Brief</span>
        </div>
        {storyLoading ? (
          <div className="space-y-2">{[1, 0.8].map((w, i) => <div key={i} className="h-4 animate-pulse rounded bg-white/[0.04]" style={{ width: `${w * 100}%` }} />)}</div>
        ) : story ? (
          <>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`text-[22px] font-black ${meta.cls}`}>{pulse?.label ?? story.mood}</span>
              <span className="rounded-full border border-white/[0.1] bg-white/[0.04] px-2 py-0.5 text-[10px] font-bold text-slate-300">
                {story.confidence !== null && story.confidence !== undefined ? `${story.confidence}% Confidence` : "Confidence unscored"}
              </span>
            </div>
            <p className="mb-4 text-[12px] leading-[1.7] text-slate-300 line-clamp-3">{story.text}</p>
          </>
        ) : (
          <p className="mb-4 text-[12px] italic text-slate-500">Market narrative will appear here during trading hours.</p>
        )}

        {drivers.length > 0 && (
          <>
            <p className="mb-2 text-[9px] font-bold uppercase tracking-wider text-slate-600">Key Drivers</p>
            <div className="mb-4 grid grid-cols-2 gap-2">
              {drivers.map(d => (
                <div key={d.label} className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-2.5 py-2">
                  <p className="line-clamp-2 text-[10px] font-bold leading-tight text-white">{d.label}</p>
                  <p className={`mt-1 text-[9px] font-semibold ${d.up ? "text-emerald-400" : "text-amber-400"}`}>{d.status}</p>
                </div>
              ))}
            </div>
          </>
        )}

        {nextWatch.length > 0 && (
          <p className="line-clamp-2 border-t border-white/[0.06] pt-3 text-[10px] leading-relaxed text-slate-500">
            <span className="font-bold text-slate-400">Next Watch: </span>{nextWatch.join(" · ")}
          </p>
        )}
      </div>

      {/* Health gauge */}
      <div className="shrink-0 border-t border-white/[0.06] p-5 lg:w-[195px] lg:border-l lg:border-t-0">
        <p className="mb-1 text-[9px] font-bold uppercase tracking-[0.15em] text-slate-500">Market Health</p>
        <div className="flex justify-center">
          <svg width="148" height="80" viewBox="0 0 148 80">
            <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="9" strokeLinecap="round" />
            {health > 0 && <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`} fill="none" stroke={scoreColor} strokeWidth="9" strokeLinecap="round" />}
            <text x={cx} y={cy + 2} textAnchor="middle" fill="white" fontSize="22" fontWeight="900">{health}</text>
            <text x={cx} y={cy + 17} textAnchor="middle" fill="#475569" fontSize="9">{label}</text>
          </svg>
        </div>
        <div className="mt-1 space-y-1.5">
          <div className="flex items-center justify-between rounded-lg border border-white/[0.04] bg-white/[0.02] px-2.5 py-1.5">
            <span className="text-[10px] text-slate-500">Trend (Today)</span>
            <span className={`text-[11px] font-bold ${niftyPos ? "text-emerald-400" : "text-rose-400"}`}>{niftyPos ? "+" : ""}{niftyChg.toFixed(2)}%</span>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-white/[0.04] bg-white/[0.02] px-2.5 py-1.5">
            <span className="text-[10px] text-slate-500">Market Breadth</span>
            <span className="text-[11px] font-bold text-slate-300">{b ? `${b.advances}↑ ${b.unchanged ?? 0}→ ${b.declines}↓` : "—"}</span>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-white/[0.04] bg-white/[0.02] px-2.5 py-1.5">
            <span className="text-[10px] text-slate-500">Market Mood</span>
            <span className={`text-[11px] font-bold ${meta.cls}`}>{story?.mood ?? "—"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Today's Top Market Drivers — real scored events, /10 scale
// ─────────────────────────────────────────────────────────────────────────────
function TodaysTopMarketDrivers({ events, loading }: { events: any[]; loading: boolean }) {
  const sorted = [...events].sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score)).slice(0, 5);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <CardHeader title="Today's Top Market Drivers" sub="Who is moving the market" href="/events" />
      {loading ? (
        <div className="flex-1 space-y-2.5">{[1, 2, 3].map(i => <div key={i} className="h-10 animate-pulse rounded-xl bg-white/[0.03]" />)}</div>
      ) : sorted.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No scored events yet today.</p>
      ) : (
        <div className="flex-1 space-y-2">
          {sorted.map((e, i) => {
            const style = impactToStyle(e.impact_score);
            const score10 = e.impact_score != null ? (e.impact_score / 10).toFixed(1) : null;
            return (
              <Link key={e.id} href={`/events/${e.id}` as any} className="group flex items-center gap-2.5 rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2 hover:border-violet-500/15 transition">
                <span className="w-4 shrink-0 text-[10px] font-black tabular-nums text-slate-600">#{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-[11px] font-bold leading-snug text-white group-hover:text-violet-200 transition">{e.title}</p>
                  <p className="line-clamp-1 mt-0.5 text-[9px] text-slate-500">Driving: {(e.sectors ?? []).slice(0, 3).join(", ") || "—"}</p>
                </div>
                <span className={`shrink-0 self-start text-[12px] font-black tabular-nums ${style.text}`}>{score10 ?? "—"}<span className="text-[9px] text-slate-600">/10</span></span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Opportunities + Risks (combined card)
// ─────────────────────────────────────────────────────────────────────────────
function OpportunitiesRisksCard({ story, opps, feed }: { story: MarketStory | null; opps: any[]; feed: FeedItem[] }) {
  const risks = feed.filter(f => f.urgency >= 7 && f.direction === "down").slice(0, 3);
  const hasOpps  = !!story?.opportunity || opps.length > 0;
  const hasRisks = !!story?.risk || risks.length > 0;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <div className="flex-1 space-y-4">
        <div>
          <div className="mb-2 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            <h3 className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Opportunities</h3>
          </div>
          {!hasOpps ? (
            <p className="text-[10px] text-slate-600">Scanning for opportunities…</p>
          ) : (
            <div className="space-y-1.5">
              {story?.opportunity && (
                <p className="line-clamp-2 text-[10px] leading-4 text-slate-400">{story.opportunity}</p>
              )}
              {opps.slice(0, 2).map((o) => (
                <div key={o.id} className="rounded-lg border border-emerald-500/10 bg-emerald-500/[0.03] p-2">
                  <p className="line-clamp-1 text-[10px] font-bold text-white">{o.theme || o.title || "Opportunity"}</p>
                  <p className="line-clamp-1 text-[9px] text-slate-500">{o.reason || o.summary || ""}</p>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="border-t border-white/[0.06] pt-3">
          <div className="mb-2 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rose-400" />
            <h3 className="text-[10px] font-bold uppercase tracking-wider text-rose-400">Risks</h3>
          </div>
          {!hasRisks ? (
            <p className="text-[10px] text-slate-600">No elevated risk signals.</p>
          ) : (
            <div className="space-y-1.5">
              {story?.risk && (
                <p className="line-clamp-2 text-[10px] leading-4 text-slate-400">{story.risk}</p>
              )}
              {risks.map((r) => (
                <div key={r.id} className="rounded-lg border border-rose-500/10 bg-rose-500/[0.03] p-2">
                  <p className="line-clamp-1 text-[10px] font-bold text-white">{r.headline}</p>
                  <p className="line-clamp-1 text-[9px] text-slate-500">{r.one_liner}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <Link href="/opportunity-radar"
        className="mt-4 flex items-center justify-center gap-1 rounded-xl border border-white/[0.07] bg-white/[0.02] py-2 text-[10px] font-semibold text-slate-400 hover:text-white transition">
        View Detailed Opportunity Radar <ChevronRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sector Rotation
// ─────────────────────────────────────────────────────────────────────────────
type SectorStatus = { label: string; cls: string; bg: string; border: string };
function getSectorStatus(val: number): SectorStatus {
  if (val >= 2.0)  return { label: "Leading",    cls: "text-emerald-300", bg: "bg-emerald-500/12", border: "border-emerald-500/25" };
  if (val >= 0.8)  return { label: "Strong",     cls: "text-emerald-400", bg: "bg-emerald-500/8",  border: "border-emerald-500/18" };
  if (val >= 0.1)  return { label: "Gaining",    cls: "text-sky-400",     bg: "bg-sky-500/8",      border: "border-sky-500/18" };
  if (val >= -0.1) return { label: "Neutral",    cls: "text-slate-400",   bg: "bg-white/[0.03]",   border: "border-white/[0.06]" };
  if (val >= -0.8) return { label: "Weakening",  cls: "text-amber-400",   bg: "bg-amber-500/8",    border: "border-amber-500/18" };
  if (val >= -2.0) return { label: "Losing",     cls: "text-rose-400",    bg: "bg-rose-500/8",     border: "border-rose-500/18" };
  return              { label: "Declining",  cls: "text-rose-300",    bg: "bg-rose-500/12",    border: "border-rose-500/25" };
}

function SectorRotationCard({ sectors }: { sectors: any[] }) {
  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <CardHeader title="Sector Rotation" sub="Live sector performance" />
      {sectors.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">Sector data unavailable.</p>
      ) : (
        <div className="flex-1 space-y-1.5">
          {sectors.slice(0, 8).map((s) => {
            const raw = parseFloat(s.value?.replace(/[^0-9.-]/g, "") ?? "0");
            const val = s.positive === false ? -raw : raw;
            const st  = getSectorStatus(val);
            return (
              <div key={s.name} className="flex items-center justify-between rounded-lg border border-white/[0.04] bg-white/[0.02] px-2.5 py-1.5">
                <span className="text-[11px] font-semibold text-white">{s.name}</span>
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-1.5 py-0.5 text-[8px] font-bold ${st.bg} ${st.cls}`}>{st.label}</span>
                  <span className={`w-12 text-right text-[11px] font-black tabular-nums ${st.cls}`}>{val >= 0 ? "+" : ""}{val.toFixed(2)}%</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
      <Link href="/themes" className="mt-3 flex items-center justify-center gap-1 rounded-xl border border-white/[0.07] bg-white/[0.02] py-1.5 text-[10px] font-semibold text-slate-400 hover:text-white transition">
        Sector Heatmap
      </Link>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Companies That Matter Today — real event-linked companies, /10 scale
// ─────────────────────────────────────────────────────────────────────────────
function CompaniesThatMatterCard({ events, loading }: { events: any[]; loading: boolean }) {
  const sorted = [...events].sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score));
  const seen = new Set<string>();
  const rows: { ticker: string; name: string; reason: string; score: number | null }[] = [];
  outer:
  for (const e of sorted) {
    for (const c of (e.companies ?? [])) {
      if (!c.symbol || seen.has(c.symbol)) continue;
      seen.add(c.symbol);
      rows.push({ ticker: c.symbol, name: c.name ?? c.symbol, reason: e.title, score: e.impact_score ?? null });
      if (rows.length >= 5) break outer;
    }
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <CardHeader title="Companies That Matter Today" sub="Most relevant companies" href="/companies" />
      {loading ? (
        <div className="flex-1 space-y-2.5">{[1, 2, 3].map(i => <div key={i} className="h-11 animate-pulse rounded-xl bg-white/[0.03]" />)}</div>
      ) : rows.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">Company data is loading.</p>
      ) : (
        <div className="flex-1 space-y-2">
          {rows.map((r, i) => {
            const style = impactToStyle(r.score);
            return (
              <Link key={r.ticker} href={`/companies/${r.ticker}` as any} className="group flex items-center gap-2.5 rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2 hover:border-violet-500/15 transition">
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[9px] font-black ${style.circle}`}>
                  {r.ticker.slice(0, 3)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[11px] font-bold text-white group-hover:text-violet-200 transition">{r.name} <span className="text-slate-600">({r.ticker})</span></p>
                  <p className="line-clamp-2 text-[9px] leading-snug text-slate-500">{r.reason}</p>
                </div>
                <span className={`shrink-0 self-start text-[13px] font-black tabular-nums ${style.text}`}>{r.score != null ? (r.score / 10).toFixed(1) : "—"}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Market Timeline — real chronological feed of today's triaged events
// ─────────────────────────────────────────────────────────────────────────────
function MarketTimelineCard({ feed, loading }: { feed: FeedItem[]; loading: boolean }) {
  const today = [...feed]
    .filter(f => {
      try { return new Date(f.triaged_at).toDateString() === new Date().toDateString(); } catch { return false; }
    })
    .sort((a, b) => new Date(a.triaged_at).getTime() - new Date(b.triaged_at).getTime())
    .slice(0, 6);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <CardHeader title="Market Timeline" sub="How today unfolded" href="/events" linkLabel="Full Timeline" />
      {loading ? (
        <div className="flex-1 space-y-3">{[1, 2, 3].map(i => <div key={i} className="h-8 animate-pulse rounded-lg bg-white/[0.03]" />)}</div>
      ) : today.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No timestamped events yet today.</p>
      ) : (
        <div className="relative flex-1">
          <div className="absolute left-[13px] top-1 bottom-1 w-px bg-white/[0.06]" />
          <div className="space-y-3.5">
            {today.map(f => {
              const t = new Date(f.triaged_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
              const up = f.direction === "up";
              const down = f.direction === "down";
              return (
                <div key={f.id} className="flex items-start gap-3">
                  <span className={`z-10 flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full border ${up ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-400" : down ? "border-rose-500/30 bg-rose-500/15 text-rose-400" : "border-slate-600/30 bg-slate-700/20 text-slate-400"}`}>
                    {up ? <TrendingUp className="h-3 w-3" /> : down ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                  </span>
                  <div className="min-w-0 flex-1 pt-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-black tabular-nums text-white">{t}</span>
                    </div>
                    <p className="line-clamp-2 text-[11px] font-semibold leading-snug text-slate-300">{f.one_liner || f.headline}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Ripple Effects — AI Ripple Map for today's top event (honest about template fallback)
// ─────────────────────────────────────────────────────────────────────────────
function RippleEffectsCard({ ripple, loading, eventId }: { ripple: any; loading: boolean; eventId: string | null }) {
  const nodes: any[] = ripple?.graph_data?.nodes ?? [];
  const source = nodes.find(n => n.type === "event") ?? nodes[0];
  const sectorNodes = nodes.filter(n => n.type === "sector").slice(0, 3);
  const isTemplate = ripple?.source === "fallback_template";

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <CardHeader title="Ripple Effects" sub="AI Ripple Map" href={eventId ? `/ripple/${eventId}` as any : undefined} linkLabel="Full Map" />
      {loading ? (
        <div className="flex-1 space-y-2">{[1, 2, 3].map(i => <div key={i} className="h-9 animate-pulse rounded-lg bg-white/[0.03]" />)}</div>
      ) : !source ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No ripple analysis available today.</p>
      ) : (
        <div className="flex-1 space-y-2">
          {isTemplate && (
            <span className="inline-block rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-0.5 text-[8px] font-bold uppercase tracking-wider text-amber-400">
              Illustrative Template
            </span>
          )}
          <div className="rounded-xl border border-violet-500/20 bg-violet-500/[0.06] px-3 py-2 text-center">
            <p className="line-clamp-2 text-[11px] font-bold leading-snug text-white">{source.label}</p>
            {source.subtitle && <p className="text-[9px] text-violet-300">{source.subtitle}</p>}
          </div>
          {sectorNodes.length > 0 && (
            <div className="grid grid-cols-3 gap-1.5">
              {sectorNodes.map(n => (
                <div key={n.id} className={`rounded-lg border px-1.5 py-2 text-center ${n.impact === "positive" ? "border-emerald-500/20 bg-emerald-500/[0.06]" : n.impact === "negative" ? "border-rose-500/20 bg-rose-500/[0.06]" : "border-white/[0.06] bg-white/[0.02]"}`}>
                  <p className="truncate text-[9px] font-bold text-white">{n.label}</p>
                  <p className={`text-[9px] ${n.impact === "positive" ? "text-emerald-400" : n.impact === "negative" ? "text-rose-400" : "text-slate-500"}`}>{n.subtitle ?? n.impact}</p>
                </div>
              ))}
            </div>
          )}
          {ripple?.insights && (
            <div className="grid grid-cols-2 gap-1.5">
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2 py-1.5 text-center">
                <p className="text-[8px] uppercase tracking-wider text-slate-600">Inflation Risk</p>
                <p className="text-[10px] font-bold text-slate-300">{ripple.insights.inflation_risk ?? "—"}</p>
              </div>
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2 py-1.5 text-center">
                <p className="text-[8px] uppercase tracking-wider text-slate-600">Volatility</p>
                <p className="text-[10px] font-bold text-slate-300">{ripple.insights.market_volatility ?? "—"}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Tomorrow Outlook — real 5-layer prediction service
// ─────────────────────────────────────────────────────────────────────────────
function TomorrowOutlookCard({ pred, loading }: { pred: any; loading: boolean }) {
  const p = pred?.prediction;
  const dirUp = p?.direction === "Positive";
  const dirDown = p?.direction === "Negative";
  const label = dirUp ? "Bullish" : dirDown ? "Bearish" : "Neutral";
  const cls   = dirUp ? "text-emerald-400" : dirDown ? "text-rose-400" : "text-amber-400";

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <CardHeader title="Tomorrow Outlook" sub="Tomorrow's probability" />
      {loading ? (
        <div className="flex-1 space-y-2">{[1, 2].map(i => <div key={i} className="h-6 animate-pulse rounded bg-white/[0.03]" />)}</div>
      ) : !p ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">Outlook unavailable.</p>
      ) : (
        <div className="flex-1">
          <p className={`text-[30px] font-black leading-none ${cls}`}>{p.confidence}%</p>
          <p className={`mt-1 text-[13px] font-bold ${cls}`}>{label}</p>
          {p.ai_generated === false && <p className="mt-0.5 text-[9px] text-slate-600">Signal-based estimate</p>}

          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <p className="mb-1.5 text-[9px] font-bold uppercase tracking-wider text-slate-600">Main Drivers</p>
              <div className="space-y-1">
                {(p.primary_drivers ?? []).slice(0, 3).map((d: string, i: number) => (
                  <div key={i} className="flex items-start gap-1">
                    <CheckCircle2 className="mt-0.5 h-2.5 w-2.5 shrink-0 text-emerald-400" />
                    <span className="text-[9px] leading-tight text-slate-400">{d}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-1.5 text-[9px] font-bold uppercase tracking-wider text-slate-600">Key Risks</p>
              <div className="space-y-1">
                {(p.risks ?? []).slice(0, 3).map((d: string, i: number) => (
                  <div key={i} className="flex items-start gap-1">
                    <XCircle className="mt-0.5 h-2.5 w-2.5 shrink-0 text-rose-400" />
                    <span className="text-[9px] leading-tight text-slate-400">{d}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
      <Link href="/market-intelligence" className="mt-4 flex items-center justify-center gap-1 rounded-xl border border-white/[0.07] bg-white/[0.02] py-1.5 text-[10px] font-semibold text-slate-400 hover:text-white transition">
        Full Market Outlook <ChevronRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Market Breadth (compact, with Breadth Health gauge)
// ─────────────────────────────────────────────────────────────────────────────
function MarketBreadthCard({ breadth }: { breadth: any }) {
  if (!breadth) return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <CardHeader title="Market Breadth" />
      <p className="flex-1 py-6 text-center text-[12px] text-slate-600">Breadth data unavailable.</p>
    </div>
  );

  const total = (breadth.advances || 0) + (breadth.declines || 0) + (breadth.unchanged || 0) || 1;
  const advPct = breadth.advances / total;
  const narrative = advPct > 0.65 ? "The rally is broad-based" : advPct > 0.5 ? "Advancing with moderate participation" : advPct > 0.4 ? "Mixed — roughly balanced" : "Broad-based selling pressure";
  const healthLabel = advPct > 0.6 ? "Healthy" : advPct > 0.45 ? "Mixed" : "Weak";
  const healthColor = advPct > 0.6 ? "#34d399" : advPct > 0.45 ? "#fbbf24" : "#f43f5e";

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <CardHeader title="Market Breadth" sub={narrative} />
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-white/[0.05]">
        <div className="h-full bg-emerald-500" style={{ width: `${(advPct * 100).toFixed(1)}%` }} />
        <div className="h-full bg-amber-500" style={{ width: `${((breadth.unchanged / total) * 100).toFixed(1)}%` }} />
        <div className="h-full bg-rose-500" style={{ width: `${((breadth.declines / total) * 100).toFixed(1)}%` }} />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div><p className="text-[18px] font-black tabular-nums text-emerald-400">{breadth.advances}</p><p className="text-[8px] uppercase tracking-wider text-slate-600">Advancing</p></div>
        <div><p className="text-[18px] font-black tabular-nums text-amber-400">{breadth.unchanged ?? 0}</p><p className="text-[8px] uppercase tracking-wider text-slate-600">Unchanged</p></div>
        <div><p className="text-[18px] font-black tabular-nums text-rose-400">{breadth.declines}</p><p className="text-[8px] uppercase tracking-wider text-slate-600">Declining</p></div>
      </div>
      <div className="mt-3 flex flex-1 items-end justify-between gap-3">
        <div className="space-y-1.5">
          {breadth.high52w != null && (
            <div><p className="text-[8px] uppercase tracking-wider text-slate-600">52W High</p><p className="text-[13px] font-black text-emerald-400">{breadth.high52w}</p></div>
          )}
          {breadth.low52w != null && (
            <div><p className="text-[8px] uppercase tracking-wider text-slate-600">52W Low</p><p className="text-[13px] font-black text-rose-400">{breadth.low52w}</p></div>
          )}
        </div>
        <div className="text-center">
          <svg width="72" height="40" viewBox="0 0 72 40">
            <path d="M 4 36 A 32 32 0 0 1 68 36" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" strokeLinecap="round" />
            <path d="M 4 36 A 32 32 0 0 1 68 36" fill="none" stroke={healthColor} strokeWidth="6" strokeLinecap="round"
              strokeDasharray={`${advPct * 100.5} 200`} />
          </svg>
          <p className="text-[9px] text-slate-600">Breadth Health</p>
          <p className="text-[11px] font-bold" style={{ color: healthColor }}>{healthLabel}</p>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Market Sentiment — real breadth-derived sentiment_score (not the fabricated /insights endpoint)
// ─────────────────────────────────────────────────────────────────────────────
function MarketSentimentCard({ value }: { value: number | null }) {
  const v = value ?? 50;
  const label = v >= 75 ? "Extreme Greed" : v >= 60 ? "Greed" : v >= 40 ? "Neutral" : v >= 25 ? "Fear" : "Extreme Fear";
  const color = v >= 75 ? "#22c55e" : v >= 60 ? "#84cc16" : v >= 40 ? "#f59e0b" : v >= 25 ? "#f97316" : "#f43f5e";
  const R = 44, CX = 52, CY = 52;
  const valueDeg = 180 - (v / 100) * 180;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const nx = CX + R * Math.cos(toRad(valueDeg));
  const ny = CY - R * Math.sin(toRad(valueDeg));

  return (
    <div className="flex h-full flex-col items-center rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <p className="mb-1 self-start text-[11px] font-bold uppercase tracking-wider text-slate-400">Market Sentiment</p>
      <p className="mb-2 self-start text-[9px] text-slate-600">Breadth-derived index</p>
      <svg width="104" height="58" viewBox="0 0 104 58">
        <path d="M 8 52 A 44 44 0 0 1 96 52" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="7" strokeLinecap="round" />
        <path d="M 8 52 A 44 44 0 0 1 96 52" fill="none" stroke={color} strokeWidth="7" strokeLinecap="round" strokeDasharray={`${(v / 100) * 138} 200`} />
        <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="white" strokeWidth="2" strokeLinecap="round" />
        <circle cx={CX} cy={CY} r="3" fill="white" />
      </svg>
      <p className="text-[22px] font-black leading-none text-white">{v}</p>
      <p className="mt-0.5 text-[11px] font-semibold" style={{ color }}>{label}</p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Confidence Meter — real story confidence + real prediction-accuracy tracker
// ─────────────────────────────────────────────────────────────────────────────
function AIConfidenceMeterCard({ confidence, accuracy, tracked, updatedAt }: {
  confidence: number | null; accuracy: number | null; tracked: number | null; updatedAt: string | null;
}) {
  const unscored = confidence === null || confidence === undefined;
  const label = unscored ? "Unscored" : confidence >= 85 ? "Very High" : confidence >= 70 ? "High" : confidence >= 55 ? "Medium" : "Low";
  const R = 32, CX = 38, CY = 38;
  const circ = 2 * Math.PI * R;
  const offset = unscored ? circ : circ - (confidence / 100) * circ;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">AI Confidence Meter</p>
      <p className="mb-3 text-[9px] text-slate-600">Overall market confidence</p>
      <div className="flex items-center gap-4">
        <div className="relative shrink-0">
          <svg width="76" height="76" viewBox="0 0 76 76">
            <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="7"/>
            {!unscored && <circle cx={CX} cy={CY} r={R} fill="none" stroke="#a855f7" strokeWidth="7" strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" transform="rotate(-90,38,38)"/>}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <p className="text-[14px] font-black text-white leading-none">{unscored ? "—" : `${confidence}%`}</p>
            <p className="text-[7px] text-violet-400 font-semibold">{label}</p>
          </div>
        </div>
        <div className="space-y-1">
          <div className="flex justify-between gap-3 text-[10px]">
            <span className="text-slate-500">Accuracy</span>
            <span className="font-semibold text-slate-300">{accuracy != null ? `${accuracy.toFixed(0)}%` : "—"}</span>
          </div>
          <div className="flex justify-between gap-3 text-[10px]">
            <span className="text-slate-500">Predictions Tracked</span>
            <span className="font-semibold text-slate-300">{tracked != null ? tracked.toLocaleString() : "—"}</span>
          </div>
          <div className="flex justify-between gap-3 text-[10px]">
            <span className="text-slate-500">Updated</span>
            <span className="font-semibold text-slate-300">{updatedAt ? timeAgo(updatedAt) : "—"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Upcoming Today — real calendar
// ─────────────────────────────────────────────────────────────────────────────
function UpcomingTodayCard({ events, loading }: { events: any[]; loading: boolean }) {
  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <CardHeader title="Upcoming Today" sub="Key events & earnings" href="/calendar" linkLabel="View Calendar" />
      {loading ? (
        <div className="flex-1 space-y-2">{[1, 2, 3].map(i => <div key={i} className="h-8 animate-pulse rounded-lg bg-white/[0.03]" />)}</div>
      ) : events.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No upcoming events.</p>
      ) : (
        <div className="flex-1 space-y-2.5">
          {events.slice(0, 5).map((e, i) => {
            const colors = ["bg-sky-500/10 text-sky-400", "bg-violet-500/10 text-violet-400", "bg-amber-500/10 text-amber-400", "bg-emerald-500/10 text-emerald-400", "bg-rose-500/10 text-rose-400"];
            return (
              <div key={e.id ?? i} className="flex items-start gap-2.5">
                <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${colors[i % colors.length]}`}>
                  <CalendarClock className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-[10px] font-semibold leading-snug text-white">{e.title}</p>
                  <p className="text-[9px] text-slate-600">{e.category ?? "Event"}</p>
                </div>
                <span className="shrink-0 self-start text-[9px] font-semibold text-slate-500">{e.date}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Market Replay (expandable timeline, triggered by top button)
// ─────────────────────────────────────────────────────────────────────────────
function MarketReplayPanel({ open }: { open: boolean }) {
  const [entries, setEntries] = useState<ReplayEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    if (!open || loaded.current) return;
    loaded.current = true;
    setLoading(true);
    fetch(`${API}/api/intelligence/market/replay`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.entries) setEntries(d.entries); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  return (
    <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <h3 className="mb-4 text-[12px] font-bold text-white">Market Replay — how today evolved from open to now</h3>
      <div className="relative">
        <div className="absolute left-[18px] top-0 bottom-0 w-px bg-white/[0.06]" />
        {loading ? (
          <div className="space-y-4 pl-12">{[1, 2, 3].map(i => <div key={i} className="h-16 animate-pulse rounded-xl bg-white/[0.02]" />)}</div>
        ) : entries.length ? (
          <div className="space-y-4">
            {entries.map((e, i) => {
              const d = new Date(e.generated_at);
              const t = d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" });
              const { cls: mCls, bg: mBg, border: mBdr } = moodMeta(e.mood);
              const arrow = e.pulse === "+" ? <TrendingUp size={11} strokeWidth={2}/> : e.pulse === "-" ? <TrendingDown size={11} strokeWidth={2}/> : <Minus size={11} strokeWidth={2}/>;
              return (
                <div key={i} className="flex items-start gap-4">
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border ${mBdr} ${mBg} z-10 ${mCls}`}>{arrow}</div>
                  <div className="flex-1 min-w-0 rounded-xl border border-white/[0.04] bg-white/[0.02] p-3">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <span className="text-[12px] font-black tabular-nums text-white">{t}</span>
                      <span className={`rounded-full border ${mBdr} ${mBg} px-1.5 py-0.5 text-[8px] font-bold ${mCls}`}>{e.mood}</span>
                      {e.nifty_at ? <span className="ml-auto text-[10px] tabular-nums text-slate-600">Nifty {e.nifty_at.toFixed(0)}</span> : null}
                      {e.vix_at ? <span className="text-[10px] tabular-nums text-slate-600">VIX {e.vix_at.toFixed(1)}</span> : null}
                    </div>
                    <p className="line-clamp-3 text-[11px] leading-5 text-slate-400">{e.story}</p>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="py-8 pl-12 text-center">
            <p className="text-[13px] text-slate-500">No replay data yet.</p>
            <p className="mt-1 text-[11px] text-slate-700">The AI snapshots the market every 5 minutes during trading hours.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────
export function LiveMarketTab({ initialData }: { initialData?: any }) {
  // Story, themes, and market health come from the shared MarketIntelligenceProvider
  // (one 60s-refreshed fetch + SSE-driven live updates, reused across every page)
  // instead of this component polling its own /api/intelligence/market/* endpoints.
  const { state: mie, loading: storyLoading } = useMarketIntelligence();
  const story  = (mie?.story ?? null) as MarketStory | null;
  const themes = (mie?.themes ?? []) as unknown as ThemeData[];

  const [data,         setData]         = useState<any>(initialData ?? null);
  const [feed,         setFeed]         = useState<FeedItem[]>([]);
  const [opps,         setOpps]         = useState<any[]>([]);
  const [events,       setEvents]       = useState<any[]>([]);
  const [calendar,     setCalendar]     = useState<any[]>([]);
  const [indices,      setIndices]      = useState<IndexItem[]>([]);
  const [predStats,    setPredStats]    = useState<{ overall_accuracy: number | null; total_predictions: number | null }>({ overall_accuracy: null, total_predictions: null });
  const [openingPred,  setOpeningPred]  = useState<any>(null);
  const [predLoading,  setPredLoading]  = useState(true);
  const [ripple,       setRipple]       = useState<any>(null);
  const [rippleLoading,setRippleLoading]= useState(true);
  const [replayOpen,   setReplayOpen]   = useState(false);
  const [dataLoading,  setDataLoading]  = useState(!initialData);

  const safe = <T,>(p: Promise<T>) => p.catch(() => null);

  // Main fast fetches — story/themes come from useMarketIntelligence() above,
  // not fetched here. Live feed goes through the shared mieClient (same
  // cache/dedup the rest of the app uses) instead of a page-local fetch.
  useEffect(() => {
    const base: Promise<any>[] = [
      safe(mieClient.getLiveFeed({ limit: 30 })),
      safe(fetch(`${API}/api/market/opportunities?limit=4`).then(r => r.ok ? r.json() : null)),
      safe(fetch(`${API}/api/events/?sort_by=impact_score&page_size=10`).then(r => r.ok ? r.json() : null)),
      safe(fetch(`${API}/api/calendar/`).then(r => r.ok ? r.json() : null)),
      safe(fetch(`${API}/api/indices/`).then(r => r.ok ? r.json() : null)),
      safe(fetch(`${API}/api/predictions/stats`).then(r => r.ok ? r.json() : null)),
    ];
    if (!initialData) base.push(safe(fetch(`${API}/api/market/live`).then(r => r.ok ? r.json() : null)));

    Promise.all(base).then(([feedRes, oppsRes, eventsRes, calRes, idxRes, predStatsRes, liveRes]) => {
      if ((feedRes as any)?.feed) {
        // The backend feed can contain the same triaged event twice (e.g. an
        // RSS item re-triaged within the window) — dedupe by id so React keys
        // stay unique across every card that renders this list.
        const seenIds = new Set<string>();
        const deduped = ((feedRes as any).feed as FeedItem[]).filter(f => {
          if (seenIds.has(f.id)) return false;
          seenIds.add(f.id);
          return true;
        });
        setFeed(deduped);
      }
      if (oppsRes?.opportunities) setOpps(oppsRes.opportunities);
      const evs = (eventsRes as any)?.results ?? eventsRes ?? [];
      if (Array.isArray(evs)) setEvents(evs);
      if (Array.isArray(calRes)) setCalendar(calRes);
      if (Array.isArray(idxRes)) setIndices(idxRes);
      if (predStatsRes) setPredStats({ overall_accuracy: predStatsRes.overall_accuracy ?? null, total_predictions: predStatsRes.total_predictions ?? null });
      if (liveRes) setData(liveRes);
    }).finally(() => { setDataLoading(false); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Tomorrow Outlook — slow, cached server-side for 30 min, fetched independently
  useEffect(() => {
    setPredLoading(true);
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), 90_000);
    fetch(`${API}/api/market/opening-prediction`, { signal: ac.signal })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setOpeningPred(d); })
      .catch(() => {})
      .finally(() => { clearTimeout(t); setPredLoading(false); });
    return () => { clearTimeout(t); ac.abort(); };
  }, []);

  // Ripple Effects — fetched once we know today's top event id
  const topEventId = events.length
    ? [...events].sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score))[0]?.id
    : null;

  useEffect(() => {
    if (!topEventId) return;
    setRippleLoading(true);
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), 60_000);
    fetch(`${API}/api/ripple/event/${topEventId}`, { signal: ac.signal })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setRipple(d); })
      .catch(() => {})
      .finally(() => { clearTimeout(t); setRippleLoading(false); });
    return () => { clearTimeout(t); ac.abort(); };
  }, [topEventId]);

  const sectors = data?.sectors ?? [];
  const breadth = data?.breadth ?? null;
  // Prefer the canonical backend-computed market_health from the MIE state —
  // computeHealthScore() is now only a fallback for the brief window before
  // the Provider's first fetch resolves.
  const health  = mie?.market_health?.score ?? computeHealthScore(data, story);
  // Same real formula the backend uses for /api/market/overview's sentiment_score,
  // computed here from the indices we already have — /api/market/live has no such field.
  const sentimentScore = indices.length
    ? Math.min(90, Math.max(20, Math.round(50 + (indices.filter(i => i.positive).length / indices.length - 0.5) * 80)))
    : null;

  if (dataLoading && !initialData) {
    return (
      <div className="space-y-5">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-36 animate-pulse rounded-2xl border border-white/[0.05] bg-white/[0.02]" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Top ticker strip + Market Replay trigger */}
      {indices.length > 0 && (
        <TopTickerRow indices={indices} onReplayClick={() => setReplayOpen(o => !o)} replayOpen={replayOpen} />
      )}
      <MarketReplayPanel open={replayOpen} />

      {/* Row 1 — AI Market Brief+Health · Today's Top Market Drivers · Opportunities+Risks · Live Feed */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.9fr_1fr_1.2fr_1fr]">
        <AIMarketBriefAndHealth story={story} storyLoading={storyLoading} themes={themes} health={health} data={data} calendar={calendar} />
        <TodaysTopMarketDrivers events={events} loading={dataLoading} />
        <OpportunitiesRisksCard story={story} opps={opps} feed={feed} />
        <LiveIntelligenceFeed limit={8} />
      </div>

      {/* Row 2 — Sector Rotation · Companies That Matter · Market Timeline · Ripple Effects */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <SectorRotationCard sectors={sectors} />
        <CompaniesThatMatterCard events={events} loading={dataLoading} />
        <MarketTimelineCard feed={feed} loading={dataLoading} />
        <RippleEffectsCard ripple={ripple} loading={rippleLoading} eventId={topEventId} />
      </div>

      {/* Row 3 — Tomorrow Outlook · Market Breadth · Market Sentiment · AI Confidence · Upcoming Today */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-[1.3fr_1.3fr_0.9fr_1fr_1.3fr]">
        <TomorrowOutlookCard pred={openingPred} loading={predLoading} />
        <MarketBreadthCard breadth={breadth} />
        <MarketSentimentCard value={sentimentScore} />
        <AIConfidenceMeterCard
          confidence={story?.confidence ?? null}
          accuracy={predStats.overall_accuracy}
          tracked={predStats.total_predictions}
          updatedAt={story?.generated_at ?? null}
        />
        <UpcomingTodayCard events={calendar} loading={dataLoading} />
      </div>
    </div>
  );
}
