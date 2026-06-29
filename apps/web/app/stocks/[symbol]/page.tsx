"use client";

import { use, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { StockDetailChart } from "@/components/StockDetailChart";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const TABS    = ["Overview", "Financials", "Events", "News", "Government Exposure", "Stock DNA", "Peers", "Charts", "Historical", "AI Analysis"];
const PERIODS = ["1D", "1W", "1M", "6M", "1Y", "3Y", "5Y", "Max"];

// ── Types ────────────────────────────────────────────────────────────────────

interface StockEvent { title: string; date: string; }
interface DnaScore  { [key: string]: number; }
interface GovBreak  { label: string; pct: number; color: string; }

interface StockDetail {
  symbol: string; name: string; price: string; prev_close: string;
  open: string; day_high: string; day_low: string; change: string;
  change_abs: string; pct_change: number; week52_high: string; week52_low: string;
  volume: string; avg_volume: string; market_cap: string; industry: string;
  sector: string; description: string; pe: string; forward_pe: string;
  pb: string; eps: string; roe: string; roa: string; beta: string;
  dividend_yield: string; dividend_rate: string; gross_margins: string;
  operating_margins: string; net_margins: string; debt_to_equity: string;
  current_ratio: string; free_cashflow: string; recommendation: string;
  target_mean: string; target_high: string; target_low: string;
  analyst_count: number; held_institutions: string; held_insiders: string;
  quarterly_revenue: { label: string; value: number }[];
  quarterly_net_income: { label: string; value: number }[];
  enterprise_value: string; roce: string;
  annual_financials: { year: string; revenue: number; net_income: number }[];
  dna_scores: DnaScore; gov_score: number; gov_level: string;
  gov_breakdown: GovBreak[]; gov_support_areas: string[];
  buy_count: number; hold_count: number; sell_count: number;
  events: StockEvent[]; news: any[]; peers: string[]; chart_data: any[];
}

interface PageProps { params: Promise<{ symbol: string }>; }

// ── Recommendation styling ───────────────────────────────────────────────────

const REC: Record<string, { label: string; cls: string; bg: string }> = {
  "strong buy":   { label: "Strong Buy",   cls: "text-emerald-300 border-emerald-500/40", bg: "bg-emerald-500/15" },
  "buy":          { label: "Buy",          cls: "text-emerald-300 border-emerald-500/30", bg: "bg-emerald-500/10" },
  "hold":         { label: "Hold",         cls: "text-amber-300  border-amber-500/30",    bg: "bg-amber-500/10"  },
  "underperform": { label: "Underperform", cls: "text-rose-300   border-rose-500/30",     bg: "bg-rose-500/10"   },
  "sell":         { label: "Sell",         cls: "text-rose-300   border-rose-500/30",     bg: "bg-rose-500/10"   },
  "strong sell":  { label: "Strong Sell",  cls: "text-rose-400   border-rose-500/40",     bg: "bg-rose-500/15"   },
};

// ── Small helpers ────────────────────────────────────────────────────────────

function Tag({ children, color = "slate" }: { children: React.ReactNode; color?: string }) {
  const cls: Record<string, string> = {
    slate:   "border-white/10  bg-white/[0.05]  text-slate-300",
    green:   "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    sky:     "border-sky-500/30     bg-sky-500/10     text-sky-300",
    violet:  "border-violet-500/30  bg-violet-500/10  text-violet-300",
    amber:   "border-amber-500/30   bg-amber-500/10   text-amber-300",
    rose:    "border-rose-500/30    bg-rose-500/10    text-rose-300",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${cls[color] ?? cls.slate}`}>
      {children}
    </span>
  );
}

function metricColor(label: string, value: string): string {
  const n = parseFloat((value || "").replace(/[₹,% ₹]/g, ""));
  if (!value || value === "—" || isNaN(n)) return "text-white";
  switch (label) {
    case "PE Ratio (TTM)":
    case "PE Ratio":
    case "Forward PE":
      if (n <= 0)  return "text-slate-500";
      if (n < 15)  return "text-emerald-400";
      if (n < 25)  return "text-white";
      if (n < 40)  return "text-amber-400";
      return "text-rose-400";
    case "PB Ratio":
      if (n < 1)   return "text-emerald-400";
      if (n < 3)   return "text-white";
      if (n < 5)   return "text-amber-400";
      return "text-rose-400";
    case "ROE":
    case "Return on Equity":
      if (n > 20)  return "text-emerald-400";
      if (n > 12)  return "text-white";
      if (n > 5)   return "text-amber-400";
      return "text-rose-400";
    case "ROCE":
      if (n > 20)  return "text-emerald-400";
      if (n > 12)  return "text-white";
      if (n > 5)   return "text-amber-400";
      return "text-rose-400";
    case "Return on Assets":
      if (n > 10)  return "text-emerald-400";
      if (n > 5)   return "text-white";
      if (n > 2)   return "text-amber-400";
      return "text-rose-400";
    case "Dividend Yield":
      if (n > 3)   return "text-emerald-400";
      if (n > 1)   return "text-sky-300";
      return "text-white";
    case "EPS (TTM)":
      if (n > 0)   return "text-emerald-400";
      return "text-rose-400";
    case "Beta":
      if (n < 0.8) return "text-emerald-400";
      if (n < 1.2) return "text-white";
      if (n < 1.8) return "text-amber-400";
      return "text-rose-400";
    case "Debt / Equity":
      if (n < 0.3) return "text-emerald-400";
      if (n < 0.8) return "text-white";
      if (n < 1.5) return "text-amber-400";
      return "text-rose-400";
    case "Current Ratio":
      if (n > 2)   return "text-emerald-400";
      if (n > 1.5) return "text-white";
      if (n > 1)   return "text-amber-400";
      return "text-rose-400";
    case "Free Cash Flow":
      if (n > 0)   return "text-emerald-400";
      return "text-rose-400";
    default:
      return "text-white";
  }
}

function KvRow({ label, value, colored = false }: { label: string; value: string; colored?: boolean }) {
  const valueClass = colored ? metricColor(label, value) : "text-white";
  return (
    <div className="flex items-center justify-between gap-2 py-1.5 border-b border-white/[0.04] last:border-0">
      <span className="text-[12px] text-slate-500 shrink-0">{label}</span>
      <span className={`text-[12px] font-semibold text-right truncate ${valueClass}`}>{value || "—"}</span>
    </div>
  );
}

function SectionCard({ title, action, children }: { title?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4 backdrop-blur-sm">
      {title && (
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[13px] font-semibold text-white">{title}</span>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

function ActionLink({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button onClick={onClick} className="text-[11px] text-sky-400 hover:text-sky-300 cursor-pointer transition">
      {children}
    </button>
  );
}

// ── Radar chart for Stock DNA ─────────────────────────────────────────────────

function RadarChart({ scores }: { scores: DnaScore }) {
  const keys = Object.keys(scores);
  const n = keys.length;
  if (n === 0) return <div className="h-52 flex items-center justify-center text-slate-500 text-sm">No data</div>;
  const cx = 130, cy = 130, r = 85;

  const angleOf = (i: number) => (i * 2 * Math.PI / n) - Math.PI / 2;
  const pt = (i: number, scale: number) => ({
    x: cx + r * scale * Math.cos(angleOf(i)),
    y: cy + r * scale * Math.sin(angleOf(i)),
  });

  const rings = [0.25, 0.5, 0.75, 1.0];
  const gridPoly = (s: number) => keys.map((_, i) => `${pt(i, s).x},${pt(i, s).y}`).join(" ");
  const dataPoly = keys.map((k, i) => `${pt(i, (scores[k] ?? 0) / 100).x},${pt(i, (scores[k] ?? 0) / 100).y}`).join(" ");

  return (
    <svg viewBox="0 0 260 260" className="w-full max-w-[220px] mx-auto">
      {rings.map(s => (
        <polygon key={s} points={gridPoly(s)} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="1" />
      ))}
      {keys.map((_, i) => {
        const end = pt(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={end.x} y2={end.y} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />;
      })}
      <polygon points={dataPoly} fill="rgba(139,92,246,0.18)" stroke="#8b5cf6" strokeWidth="1.5" />
      {keys.map((k, i) => {
        const dp = pt(i, (scores[k] ?? 0) / 100);
        const lp = pt(i, 1.28);
        return (
          <g key={k}>
            <circle cx={dp.x} cy={dp.y} r="3.5" fill="#8b5cf6" />
            <text x={lp.x} y={lp.y} textAnchor="middle" dominantBaseline="middle" fill="rgba(148,163,184,0.85)" fontSize="8.5" fontFamily="sans-serif">
              {k}
            </text>
            <text x={lp.x} y={lp.y + 10} textAnchor="middle" dominantBaseline="middle" fill="rgba(255,255,255,0.6)" fontSize="8" fontFamily="sans-serif">
              {scores[k]}/100
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Donut chart for Government Exposure ──────────────────────────────────────

function DonutChart({ breakdown }: { breakdown: GovBreak[] }) {
  if (!breakdown.length) return null;
  const cx = 70, cy = 70, r = 52, ir = 30;
  const total = breakdown.reduce((s, b) => s + b.pct, 0) || 100;
  let angle = -Math.PI / 2;
  const segs = breakdown.map(b => {
    const sweep = (b.pct / total) * 2 * Math.PI;
    const sa = angle, ea = angle + sweep;
    angle = ea;
    return { ...b, sa, ea };
  });
  const arcPath = (sa: number, ea: number, or_: number, ir_: number) => {
    const x1 = cx + or_ * Math.cos(sa), y1 = cy + or_ * Math.sin(sa);
    const x2 = cx + or_ * Math.cos(ea), y2 = cy + or_ * Math.sin(ea);
    const xi1 = cx + ir_ * Math.cos(ea), yi1 = cy + ir_ * Math.sin(ea);
    const xi2 = cx + ir_ * Math.cos(sa), yi2 = cy + ir_ * Math.sin(sa);
    const lg = ea - sa > Math.PI ? 1 : 0;
    return `M${x1},${y1} A${or_},${or_} 0 ${lg} 1 ${x2},${y2} L${xi1},${yi1} A${ir_},${ir_} 0 ${lg} 0 ${xi2},${yi2} Z`;
  };
  return (
    <svg viewBox="0 0 140 140" className="w-36 h-36 shrink-0">
      {segs.map((s, i) => (
        <path key={i} d={arcPath(s.sa, s.ea, r, ir)} fill={s.color} opacity={0.85 - i * 0.08} />
      ))}
    </svg>
  );
}

// ── Bar chart (financials) ───────────────────────────────────────────────────

function BarChart({ data, color, label }: { data: {label:string; value:number}[]; color: string; label: string }) {
  const maxAbs = Math.max(...data.map(d => Math.abs(d.value)), 1);
  return (
    <div>
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{label}</p>
      <div className="flex h-32 items-end gap-2">
        {data.map((d, i) => {
          const pct = Math.round((Math.abs(d.value) / maxAbs) * 100);
          const neg = d.value < 0;
          const val = d.value === 0 ? "—" : `${neg ? "−" : ""}₹${Math.abs(d.value).toLocaleString()}Cr`;
          return (
            <div key={i} className="group flex flex-1 flex-col items-center gap-1">
              <span className="text-[8px] text-slate-500 group-hover:text-slate-300 transition leading-tight text-center">{val}</span>
              <div className="flex w-full flex-1 items-end">
                <div style={{ height: `${Math.max(pct, 3)}%` }}
                  className={`w-full rounded-t-md transition-all duration-500 ${neg ? "bg-rose-500/50" : color}`} />
              </div>
              <span className="text-[9px] text-slate-600">{d.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MarginBar({ label, value, color }: { label: string; value: string; color: string }) {
  const pct = parseFloat((value || "0").replace("%", "")) || 0;
  return (
    <div>
      <div className="mb-1 flex justify-between">
        <span className="text-[12px] text-slate-400">{label}</span>
        <span className="text-[12px] font-bold text-white">{value || "—"}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }} />
      </div>
    </div>
  );
}

function TargetBand({ current, low, mean, high }: { current: string; low: string; mean: string; high: string }) {
  const parse = (s: string) => parseFloat((s || "").replace(/[₹,\s]/g, "")) || 0;
  const c = parse(current), l = parse(low), m = parse(mean), h = parse(high);
  if (!l || !h || l >= h) return null;
  const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - l) / (h - l)) * 100)).toFixed(1)}%`;
  return (
    <div className="mt-4">
      <div className="relative mx-2 h-2 rounded-full bg-white/[0.06]">
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-amber-500/20 via-sky-500/20 to-emerald-500/20" />
        <div className="absolute top-1/2 h-3.5 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-sky-400" style={{ left: pos(m) }} />
        <div className="absolute top-1/2 h-5 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white" style={{ left: pos(c) }} />
      </div>
      <div className="mt-3 flex justify-between text-[10px]">
        <div className="text-center"><span className="block text-slate-500">Low</span><span className="font-semibold text-amber-300">{low}</span></div>
        <div className="text-center"><span className="block text-slate-500">Mean</span><span className="font-semibold text-sky-300">{mean}</span></div>
        <div className="text-center"><span className="block text-slate-500">High</span><span className="font-semibold text-emerald-300">{high}</span></div>
      </div>
    </div>
  );
}

// ── Overview tab (3-column) ───────────────────────────────────────────────────

function OverviewTab({ stock, chartData, loadingChart, period, setPeriod, symbol, relatedNews, setActiveTab }: {
  stock: StockDetail; chartData: any[]; loadingChart: boolean; period: string;
  setPeriod: (p: string) => void; symbol: string; relatedNews: any[];
  setActiveTab: (t: string) => void;
}) {
  const govLevelColor = stock.gov_level === "High" ? "text-emerald-300" : stock.gov_level === "Medium" ? "text-amber-300" : "text-slate-300";

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_300px_260px] gap-4 items-start">

      {/* ── LEFT COLUMN ─────────────────────────────────────────────── */}
      <div className="space-y-4">

        {/* Price Chart */}
        <SectionCard title="Price Chart" action={
          <div className="flex gap-0.5">
            {PERIODS.map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`rounded-md px-2 py-0.5 text-[10px] font-medium transition ${
                  period === p ? "bg-sky-500/20 text-sky-300" : "text-slate-500 hover:text-slate-300"}`}>
                {p}
              </button>
            ))}
          </div>
        }>
          {loadingChart
            ? <div className="flex h-44 items-center justify-center rounded-xl bg-white/[0.02]">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-sky-400" />
              </div>
            : chartData.length > 0
              ? <StockDetailChart data={chartData} />
              : <div className="flex h-44 items-center justify-center rounded-xl border border-white/5 bg-white/[0.02]">
                  <p className="text-sm text-slate-500">No chart data — check backend</p>
                </div>
          }
          <div className="mt-3 grid grid-cols-3 gap-x-4 gap-y-1.5 border-t border-white/5 pt-3">
            {[
              ["Open",       `₹${stock.open}`],
              ["High",       `₹${stock.day_high}`],
              ["Low",        `₹${stock.day_low}`],
              ["Prev. Close",`₹${stock.prev_close}`],
              ["52W High",   `₹${stock.week52_high}`],
              ["52W Low",    `₹${stock.week52_low}`],
            ].map(([l, v]) => (
              <div key={l}>
                <p className="text-[10px] text-slate-500">{l}</p>
                <p className="text-[12px] font-bold text-white">{v}</p>
              </div>
            ))}
          </div>
        </SectionCard>

        {/* Recent Events */}
        <SectionCard title="Recent Events Impacting This Company"
          action={<ActionLink onClick={() => setActiveTab("Events")}>View All Events →</ActionLink>}>
          {stock.events.length > 0
            ? <div className="space-y-2">
                {stock.events.map((e, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3">
                    <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-500/15">
                      <svg className="h-3.5 w-3.5 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                      </svg>
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] font-medium text-white line-clamp-2 leading-snug">{e.title}</p>
                      <p className="mt-0.5 text-[10px] text-slate-500">{e.date}</p>
                    </div>
                  </div>
                ))}
              </div>
            : <p className="py-6 text-center text-sm text-slate-500">No events linked to {symbol.toUpperCase()} yet.</p>
          }
        </SectionCard>

        {/* Financial Highlights */}
        <SectionCard title="Financial Highlights (Consolidated)"
          action={<ActionLink onClick={() => setActiveTab("Financials")}>View Financials →</ActionLink>}>
          {stock.annual_financials.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="pb-2 text-left text-[10px] text-slate-500 font-medium">₹ in Crore</th>
                    {stock.annual_financials.map(f => (
                      <th key={f.year} className="pb-2 text-right text-[10px] text-slate-500 font-medium">{f.year}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.03]">
                  <tr>
                    <td className="py-2 text-slate-400">Revenue</td>
                    {stock.annual_financials.map(f => (
                      <td key={f.year} className="py-2 text-right text-white font-medium">{f.revenue.toLocaleString()}</td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2 text-slate-400">Net Profit</td>
                    {stock.annual_financials.map(f => (
                      <td key={f.year} className={`py-2 text-right font-medium ${f.net_income >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                        {f.net_income.toLocaleString()}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2 text-slate-400">ROE (%)</td>
                    {stock.annual_financials.map((f, i) => (
                      <td key={f.year} className="py-2 text-right text-white font-medium">
                        {i === stock.annual_financials.length - 1 ? (stock.roe || "—") : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2 text-slate-400">Debt to Equity</td>
                    {stock.annual_financials.map((f, i) => (
                      <td key={f.year} className="py-2 text-right text-white font-medium">
                        {i === stock.annual_financials.length - 1 ? (stock.debt_to_equity || "—") : "—"}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500">Annual data not available for {symbol.toUpperCase()}</p>
          )}
        </SectionCard>
      </div>

      {/* ── MIDDLE COLUMN ───────────────────────────────────────────── */}
      <div className="space-y-4">

        {/* Stock DNA */}
        <SectionCard title="Stock DNA">
          <p className="mb-3 text-[11px] text-slate-500">What makes this company move?</p>
          {Object.keys(stock.dna_scores).length > 0
            ? <RadarChart scores={stock.dna_scores} />
            : <p className="py-8 text-center text-sm text-slate-500">Financial data unavailable</p>
          }
          <button onClick={() => setActiveTab("Stock DNA")}
            className="mt-3 w-full rounded-xl border border-white/8 bg-white/[0.03] py-2 text-[11px] font-medium text-sky-400 hover:bg-white/[0.06] transition">
            View Full DNA →
          </button>
        </SectionCard>

        {/* Government Exposure */}
        <SectionCard title="Government Exposure"
          action={<ActionLink onClick={() => setActiveTab("Government Exposure")}>View Details →</ActionLink>}>
          <div className="mb-3 flex items-center gap-3">
            <span className="text-[13px] text-slate-400">Overall Exposure</span>
            <span className={`text-[15px] font-bold ${govLevelColor}`}>{stock.gov_level || "—"}</span>
          </div>
          <div className="mb-1 flex items-center gap-1">
            <span className="text-[26px] font-black text-white">{stock.gov_score}</span>
            <span className="text-[13px] text-slate-500">/100</span>
          </div>

          <div className="mt-3 flex gap-4">
            <DonutChart breakdown={stock.gov_breakdown} />
            <div className="flex-1 space-y-1.5">
              {stock.gov_breakdown.map(b => (
                <div key={b.label} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full shrink-0" style={{ background: b.color }} />
                    <span className="text-[10px] text-slate-400 leading-tight">{b.label}</span>
                  </div>
                  <span className="text-[10px] font-semibold text-white">{b.pct}%</span>
                </div>
              ))}
            </div>
          </div>

          {stock.gov_support_areas.length > 0 && (
            <div className="mt-3 border-t border-white/5 pt-3">
              <p className="mb-2 text-[10px] text-slate-500">Key Support Areas</p>
              <div className="flex flex-wrap gap-1.5">
                {stock.gov_support_areas.map(a => (
                  <span key={a} className="rounded-full border border-sky-500/20 bg-sky-500/8 px-2 py-0.5 text-[10px] text-sky-300">{a}</span>
                ))}
              </div>
            </div>
          )}
        </SectionCard>

        {/* Peers Comparison */}
        <SectionCard title="Peers Comparison"
          action={<ActionLink onClick={() => setActiveTab("Peers")}>View All Peers →</ActionLink>}>
          {stock.peers.length > 0
            ? <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="pb-2 text-left text-[10px] text-slate-500 font-medium">Company</th>
                    <th className="pb-2 text-right text-[10px] text-slate-500 font-medium">Sector</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.03]">
                  {stock.peers.map(p => (
                    <tr key={p}>
                      <td className="py-2">
                        <Link href={`/stocks/${p}`} className="flex items-center gap-2 hover:text-sky-300 transition">
                          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-white/[0.06] text-[9px] font-bold text-slate-300">
                            {p.slice(0, 2)}
                          </div>
                          <span className="text-white font-medium">{p}</span>
                        </Link>
                      </td>
                      <td className="py-2 text-right text-slate-500">View →</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            : <p className="py-4 text-center text-sm text-slate-500">No peer data</p>
          }
        </SectionCard>
      </div>

      {/* ── RIGHT COLUMN ────────────────────────────────────────────── */}
      <div className="space-y-4 xl:sticky xl:top-[84px]">

        {/* AI Summary */}
        <SectionCard>
          <div className="mb-2 flex items-center gap-2">
            <span className="text-[12px] text-violet-400">✦</span>
            <span className="text-[13px] font-semibold text-white">AI Summary</span>
          </div>
          {stock.description
            ? <>
                <p className="text-[12px] leading-5 text-slate-300 line-clamp-5">{stock.description}</p>
                {stock.dna_scores && (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <div>
                      <p className="mb-1.5 text-[10px] font-semibold text-emerald-400">Bullish Factors</p>
                      <ul className="space-y-1">
                        {[
                          stock.gov_score >= 75 && "Government support",
                          stock.dna_scores["Growth"] >= 60 && "Strong growth metrics",
                          stock.dna_scores["Execution Quality"] >= 60 && "Good execution",
                          stock.dividend_yield && stock.dividend_yield !== "—" && `Dividend yield ${stock.dividend_yield}`,
                        ].filter(Boolean).slice(0, 3).map((f, i) => (
                          <li key={i} className="flex items-start gap-1 text-[10px] text-slate-300">
                            <span className="mt-0.5 text-emerald-400">•</span>{f}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="mb-1.5 text-[10px] font-semibold text-rose-400">Risks</p>
                      <ul className="space-y-1">
                        {[
                          stock.dna_scores["Debt Strength"] < 40 && "High leverage",
                          parseFloat(stock.pe || "0") > 40 && "High valuation",
                          stock.dna_scores["News Sensitivity"] > 70 && "High volatility",
                          stock.gov_score >= 75 && "Regulatory risks",
                        ].filter(Boolean).slice(0, 3).map((r, i) => (
                          <li key={i} className="flex items-start gap-1 text-[10px] text-slate-300">
                            <span className="mt-0.5 text-rose-400">•</span>{r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
                <button className="mt-3 w-full rounded-xl bg-violet-500/10 border border-violet-500/20 py-2 text-[11px] font-medium text-violet-300 hover:bg-violet-500/15 transition">
                  Ask AI about {stock.name.split(" ")[0]} →
                </button>
              </>
            : <p className="py-4 text-center text-sm text-slate-500">Description unavailable</p>
          }
        </SectionCard>

        {/* Key Statistics */}
        <SectionCard title="Key Statistics">
          <div className="space-y-0">
            <KvRow label="Market Cap"       value={stock.market_cap} />
            <KvRow label="Enterprise Value" value={stock.enterprise_value} />
            <KvRow label="PE Ratio (TTM)"   value={stock.pe}                              colored />
            <KvRow label="PB Ratio"         value={stock.pb}                              colored />
            <KvRow label="ROE"              value={stock.roe}                             colored />
            <KvRow label="ROCE"             value={stock.roce}                            colored />
            <KvRow label="Dividend Yield"   value={stock.dividend_yield}                  colored />
            <KvRow label="EPS (TTM)"        value={stock.eps ? `₹${stock.eps}` : "—"}    colored />
            <KvRow label="Beta"             value={stock.beta}                            colored />
          </div>
        </SectionCard>

        {/* Quick Actions */}
        <SectionCard title="Quick Actions">
          <div className="space-y-1.5">
            {[
              { icon: "☆", label: "Add to Watchlist" },
              { icon: "🔔", label: "Set Price Alert" },
              { icon: "↔", label: "Compare with Peers", action: () => {} },
              { icon: "↓", label: "Download Report" },
            ].map(item => (
              <button key={item.label}
                className="w-full flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2.5 hover:border-white/10 hover:bg-white/[0.04] transition">
                <div className="flex items-center gap-2.5">
                  <span className="text-[14px]">{item.icon}</span>
                  <span className="text-[12px] text-slate-300">{item.label}</span>
                </div>
                <svg className="h-3.5 w-3.5 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
                </svg>
              </button>
            ))}
          </div>
        </SectionCard>

        {/* Latest News */}
        {relatedNews.length > 0 && (
          <SectionCard title="Latest News"
            action={<ActionLink onClick={() => {}}>View All News →</ActionLink>}>
            <div className="space-y-3">
              {relatedNews.slice(0, 3).map((n: any, i: number) => (
                <div key={i} className="flex gap-2">
                  <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/8 bg-white/[0.04] text-[10px] font-bold text-slate-400">
                    {(n.source || "N").slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium text-white line-clamp-2 leading-snug">{n.headline}</p>
                    <p className="mt-0.5 text-[10px] text-slate-500">{n.source} · {n.published_at}</p>
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function StockPage({ params }: PageProps) {
  const { symbol } = use(params);
  const [stock,        setStock]        = useState<StockDetail | null>(null);
  const [chartData,    setChartData]    = useState<any[]>([]);
  const [loadingInfo,  setLoadingInfo]  = useState(true);
  const [loadingChart, setLoadingChart] = useState(true);
  const [activeTab,    setActiveTab]    = useState("Overview");
  const [period,       setPeriod]       = useState("1Y");
  const [watchlisted,  setWatchlisted]  = useState(false);
  const [relatedNews,  setRelatedNews]  = useState<any[]>([]);

  useEffect(() => {
    setLoadingInfo(true);
    fetch(`${API}/api/stocks/${symbol}`)
      .then(r => r.ok ? r.json() : null)
      .then(setStock)
      .catch(() => {})
      .finally(() => setLoadingInfo(false));
  }, [symbol]);

  const fetchChart = useCallback((p: string) => {
    setLoadingChart(true);
    fetch(`${API}/api/stocks/${symbol}/chart?period=${p}`)
      .then(r => r.ok ? r.json() : [])
      .then(d => setChartData(Array.isArray(d) ? d : []))
      .catch(() => setChartData([]))
      .finally(() => setLoadingChart(false));
  }, [symbol]);

  useEffect(() => { fetchChart(period); }, [symbol, period, fetchChart]);

  useEffect(() => {
    fetch(`${API}/api/stocks/${symbol}/news`)
      .then(r => r.ok ? r.json() : [])
      .then(d => setRelatedNews(Array.isArray(d) ? d : []))
      .catch(() => {});
  }, [symbol]);

  if (loadingInfo) {
    return (
      <main className="min-w-0 space-y-4 pb-10">
        <div className="h-6 w-48 animate-pulse rounded-lg bg-white/[0.04]" />
        <div className="h-44 animate-pulse rounded-2xl border border-white/8 bg-white/[0.02]" />
        <div className="h-80 animate-pulse rounded-2xl border border-white/8 bg-white/[0.02]" />
      </main>
    );
  }

  if (!stock) {
    return (
      <main className="min-w-0 flex flex-col items-center justify-center gap-4 py-24 text-center">
        <span className="text-5xl">📉</span>
        <h1 className="text-2xl font-semibold text-white">{symbol.toUpperCase()} not found</h1>
        <p className="text-slate-400">Not listed on NSE or backend offline.</p>
        <Link href="/stocks" className="mt-2 rounded-full bg-sky-500/15 px-5 py-2 text-sm text-sky-300 hover:bg-sky-500/25 transition">
          ← Back to Companies
        </Link>
      </main>
    );
  }

  const isPos = stock.pct_change >= 0;
  const rec   = REC[stock.recommendation] ?? REC["hold"];
  const changeSign = isPos ? "+" : "";

  return (
    <main className="min-w-0 space-y-5 pb-10">

      {/* ── Breadcrumb ────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 text-[12px] text-slate-500">
        <Link href="/stocks" className="hover:text-slate-300 transition">Companies</Link>
        <span>›</span>
        <span className="text-slate-300">{stock.name}</span>
      </div>

      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-5 backdrop-blur-sm">

        {/* Top row: name + actions */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black text-white tracking-tight">{stock.name}</h1>
              <button className="text-slate-500 hover:text-amber-400 transition text-lg">☆</button>
            </div>

            {/* Tag pills */}
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Tag>{symbol.toUpperCase()}</Tag>
              <Tag color="green">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                NSE
              </Tag>
              {stock.sector && stock.sector !== "N/A" && <Tag>{stock.sector}</Tag>}
              {stock.industry && stock.industry !== "N/A" && stock.industry !== stock.sector && (
                <Tag>{stock.industry}</Tag>
              )}
            </div>

            {/* Price */}
            <div className="mt-3 flex flex-wrap items-baseline gap-3">
              <span className="text-4xl font-black text-white">₹{stock.price}</span>
              <span className={`text-base font-semibold ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
                {changeSign}{stock.change_abs} ({changeSign}{stock.pct_change.toFixed(2)}%) {isPos ? "▲" : "▼"}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-slate-500">
              {new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" })} ·{" "}
              <span className="text-slate-400">NSE</span>
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setWatchlisted(w => !w)}
              className={`flex items-center gap-1.5 rounded-xl border px-4 py-2 text-[12px] font-medium transition ${
                watchlisted
                  ? "border-sky-500/40 bg-sky-500/15 text-sky-300"
                  : "border-white/10 bg-white/[0.03] text-slate-300 hover:border-white/20 hover:text-white"
              }`}>
              + {watchlisted ? "Watchlisted ✓" : "Add to Watchlist"}
            </button>
            <button className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-[12px] font-medium text-slate-300 hover:border-white/20 hover:text-white transition">
              ↔ Compare
            </button>
            <button className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-slate-400 hover:text-white transition">
              ⋯
            </button>
          </div>
        </div>

        {/* Stats bar */}
        <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-0 border-t border-white/5 pt-4 sm:grid-cols-4">
          {[
            ["Market Cap",    stock.market_cap],
            ["PE Ratio",      stock.pe],
            ["Dividend Yield",stock.dividend_yield],
            ["52W High",      `₹${stock.week52_high}`],
          ].map(([l, v]) => (
            <div key={l} className="py-1">
              <p className="text-[10px] text-slate-500">{l}</p>
              <p className="text-[13px] font-bold text-white">{v || "—"}</p>
            </div>
          ))}
        </div>

        {/* Tab bar */}
        <div className="mt-4 flex gap-0.5 overflow-x-auto border-t border-white/5 pt-4 scrollbar-hide">
          {TABS.map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`shrink-0 rounded-lg px-3 py-1.5 text-[12px] font-medium transition whitespace-nowrap ${
                activeTab === t ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]"
              }`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab content ───────────────────────────────────────────────── */}

      {activeTab === "Overview" && (
        <OverviewTab
          stock={stock} chartData={chartData} loadingChart={loadingChart}
          period={period} setPeriod={setPeriod} symbol={symbol}
          relatedNews={relatedNews} setActiveTab={setActiveTab}
        />
      )}

      {activeTab === "Financials" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 items-start">
          <div className="space-y-4">
            <SectionCard>
              {stock.quarterly_revenue.length > 0
                ? <BarChart data={stock.quarterly_revenue} color="bg-gradient-to-t from-sky-500/60 to-sky-400/30" label="Quarterly Revenue (₹Cr)" />
                : <p className="py-10 text-center text-sm text-slate-500">Revenue data unavailable</p>
              }
            </SectionCard>
            <SectionCard>
              {stock.quarterly_net_income.length > 0
                ? <BarChart data={stock.quarterly_net_income} color="bg-gradient-to-t from-emerald-500/60 to-emerald-400/30" label="Quarterly Net Income (₹Cr)" />
                : <p className="py-10 text-center text-sm text-slate-500">Net income data unavailable</p>
              }
            </SectionCard>
          </div>
          <div className="space-y-4">
            <SectionCard title="Profit Margins">
              <div className="space-y-3.5">
                <MarginBar label="Gross Margin"     value={stock.gross_margins}     color="bg-sky-500" />
                <MarginBar label="Operating Margin" value={stock.operating_margins} color="bg-violet-500" />
                <MarginBar label="Net Margin"       value={stock.net_margins}       color="bg-emerald-500" />
              </div>
            </SectionCard>
            <SectionCard title="Key Ratios">
              <div className="space-y-0">
                <KvRow label="Return on Equity"   value={stock.roe}              colored />
                <KvRow label="Return on Assets"   value={stock.roa}              colored />
                <KvRow label="ROCE"               value={stock.roce}             colored />
                <KvRow label="Debt / Equity"      value={stock.debt_to_equity}   colored />
                <KvRow label="Current Ratio"      value={stock.current_ratio}    colored />
                <KvRow label="Free Cash Flow"     value={stock.free_cashflow}    colored />
                <KvRow label="Enterprise Value"   value={stock.enterprise_value} />
              </div>
            </SectionCard>
          </div>
        </div>
      )}

      {activeTab === "Events" && (
        <SectionCard title="Related Events">
          {stock.events.length > 0
            ? <div className="space-y-3">
                {stock.events.map((e, i) => (
                  <div key={i} className="rounded-xl border border-white/5 bg-white/[0.02] p-3.5">
                    <p className="text-[13px] font-medium text-white leading-snug">{e.title}</p>
                    <p className="mt-1 text-[11px] text-slate-500">{e.date}</p>
                  </div>
                ))}
              </div>
            : <div className="flex flex-col items-center gap-3 py-16 text-center">
                <span className="text-4xl">📋</span>
                <p className="text-sm text-slate-400">No events linked to {symbol.toUpperCase()} yet.</p>
                <Link href="/events" className="text-sm text-sky-400 hover:text-sky-300 transition">Browse all events →</Link>
              </div>
          }
        </SectionCard>
      )}

      {activeTab === "News" && (
        <SectionCard title="Latest News">
          {relatedNews.length > 0
            ? <div className="space-y-3">
                {relatedNews.map((a: any, i: number) => (
                  <div key={i} className="flex gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3 hover:border-white/10 transition">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[11px] font-bold text-slate-400">
                      {(a.source || "N").slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-white line-clamp-2 leading-snug">{a.headline}</p>
                      <div className="mt-1.5 flex items-center gap-2">
                        <span className="text-[10px] text-slate-500">{a.source}</span>
                        <span className="text-[10px] text-slate-600">{a.published_at}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            : <div className="flex flex-col items-center gap-3 py-16 text-center">
                <span className="text-4xl">📰</span>
                <p className="text-sm text-slate-400">No recent news for {symbol.toUpperCase()}.</p>
              </div>
          }
        </SectionCard>
      )}

      {activeTab === "Government Exposure" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 items-start">
          <SectionCard title="Government Exposure Overview">
            <div className="mb-5 flex items-center gap-4">
              <div>
                <p className="text-[12px] text-slate-500">Overall Exposure Level</p>
                <p className={`text-2xl font-black mt-1 ${
                  stock.gov_level === "High" ? "text-emerald-300" : stock.gov_level === "Medium" ? "text-amber-300" : "text-slate-300"
                }`}>{stock.gov_level || "—"}</p>
              </div>
              <div className="ml-auto text-right">
                <p className="text-[40px] font-black text-white leading-none">{stock.gov_score}</p>
                <p className="text-[12px] text-slate-500">out of 100</p>
              </div>
            </div>

            <DonutChart breakdown={stock.gov_breakdown} />

            <div className="mt-4 space-y-2">
              {stock.gov_breakdown.map(b => (
                <div key={b.label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-2.5 w-2.5 rounded-full" style={{ background: b.color }} />
                    <span className="text-[12px] text-slate-300">{b.label}</span>
                  </div>
                  <span className="text-[12px] font-semibold text-white">{b.pct}%</span>
                </div>
              ))}
            </div>

            {stock.gov_support_areas.length > 0 && (
              <div className="mt-4 border-t border-white/5 pt-4">
                <p className="mb-2 text-[11px] text-slate-500">Key Support Areas</p>
                <div className="flex flex-wrap gap-2">
                  {stock.gov_support_areas.map(a => (
                    <span key={a} className="rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-[11px] text-sky-300">{a}</span>
                  ))}
                </div>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Policy Impact Metrics">
            <div className="space-y-0">
              <KvRow label="Government Score"   value={`${stock.gov_score}/100`} />
              <KvRow label="Exposure Level"     value={stock.gov_level} />
              <KvRow label="Policy Dependence"  value={`${stock.dna_scores["Policy Dependence"] ?? "—"}/100`} />
              <KvRow label="Sector"             value={stock.sector} />
              <KvRow label="Industry"           value={stock.industry} />
            </div>
            <p className="mt-4 text-[10px] text-slate-600">
              Scores derived from sector classification and financial profile. Higher values indicate stronger government linkage.
            </p>
          </SectionCard>
        </div>
      )}

      {activeTab === "Stock DNA" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 items-start">
          <SectionCard title="Stock DNA — What Makes This Company Move?">
            {Object.keys(stock.dna_scores).length > 0 ? (
              <>
                <RadarChart scores={stock.dna_scores} />
                <div className="mt-4 grid grid-cols-2 gap-2">
                  {Object.entries(stock.dna_scores).map(([k, v]) => (
                    <div key={k} className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                      <p className="text-[10px] text-slate-500">{k}</p>
                      <div className="mt-1.5 flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                          <div className="h-full bg-violet-500 rounded-full" style={{ width: `${v}%` }} />
                        </div>
                        <span className="text-[12px] font-bold text-white">{v}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="mt-4 text-[10px] text-slate-600">
                  DNA scores are derived from real financial metrics (ROE, D/E, beta, margins, sector). Not manually assigned.
                </p>
              </>
            ) : (
              <p className="py-8 text-center text-sm text-slate-500">DNA data unavailable — check backend</p>
            )}
          </SectionCard>

          <div className="space-y-4">
            <SectionCard title="Score Breakdown">
              <div className="space-y-3">
                {Object.entries(stock.dna_scores).map(([k, v]) => (
                  <div key={k}>
                    <div className="mb-1 flex justify-between text-[12px]">
                      <span className="text-slate-400">{k}</span>
                      <span className="font-bold text-white">{v}/100</span>
                    </div>
                    <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden">
                      <div className={`h-full rounded-full transition-all duration-700 ${
                        v >= 75 ? "bg-emerald-500" : v >= 50 ? "bg-sky-500" : v >= 30 ? "bg-amber-500" : "bg-rose-500"
                      }`} style={{ width: `${v}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
        </div>
      )}

      {activeTab === "Peers" && (
        <SectionCard title={`Peer Companies — ${stock.industry}`}>
          {stock.peers.length > 0
            ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {stock.peers.map(p => (
                  <Link key={p} href={`/stocks/${p}`}
                    className="group flex items-center gap-3 rounded-2xl border border-white/8 bg-white/[0.025] p-4 hover:border-sky-500/30 hover:bg-sky-500/[0.04] transition">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-xs font-bold text-slate-300">
                      {p.slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white group-hover:text-sky-300 transition truncate">{p}</p>
                      <p className="text-[11px] text-slate-500">View →</p>
                    </div>
                  </Link>
                ))}
              </div>
            : <p className="py-8 text-center text-sm text-slate-500">No peer data available.</p>
          }
        </SectionCard>
      )}

      {activeTab === "Charts" && (
        <SectionCard title="Price Chart">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {PERIODS.map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`rounded-lg px-3 py-1.5 text-[12px] font-medium transition ${
                  period === p ? "bg-sky-500/20 text-sky-300" : "text-slate-500 hover:text-slate-300"
                }`}>
                {p}
              </button>
            ))}
          </div>
          {loadingChart
            ? <div className="flex h-72 items-center justify-center"><div className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-sky-400" /></div>
            : chartData.length > 0
              ? <StockDetailChart data={chartData} />
              : <div className="flex h-72 items-center justify-center text-sm text-slate-500">No chart data available</div>
          }
        </SectionCard>
      )}

      {activeTab === "Historical" && (
        <SectionCard title="Historical Financial Data">
          {stock.annual_financials.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-white/8">
                    <th className="pb-3 text-left text-[11px] text-slate-500 font-medium">₹ in Crore</th>
                    {stock.annual_financials.map(f => (
                      <th key={f.year} className="pb-3 text-right text-[11px] text-slate-500 font-medium">{f.year}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.03]">
                  <tr>
                    <td className="py-3 text-slate-400">Revenue</td>
                    {stock.annual_financials.map(f => (
                      <td key={f.year} className="py-3 text-right font-semibold text-white">{f.revenue.toLocaleString()}</td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-3 text-slate-400">Net Profit</td>
                    {stock.annual_financials.map(f => (
                      <td key={f.year} className={`py-3 text-right font-semibold ${f.net_income >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                        {f.net_income.toLocaleString()}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-3 text-slate-400">ROE (%)</td>
                    {stock.annual_financials.map((f, i) => (
                      <td key={f.year} className="py-3 text-right text-white font-medium">
                        {i === stock.annual_financials.length - 1 ? stock.roe : "—"}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-3 text-slate-400">Debt to Equity</td>
                    {stock.annual_financials.map((f, i) => (
                      <td key={f.year} className="py-3 text-right text-white font-medium">
                        {i === stock.annual_financials.length - 1 ? stock.debt_to_equity : "—"}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-10 text-center text-sm text-slate-500">No historical data available for {symbol.toUpperCase()}</p>
          )}
        </SectionCard>
      )}

      {activeTab === "AI Analysis" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 items-start">
          <SectionCard title="✦ AI Summary">
            {stock.description
              ? <>
                  <p className="text-[13px] leading-6 text-slate-300">{stock.description}</p>
                  <div className="mt-5 grid grid-cols-2 gap-4">
                    <div>
                      <p className="mb-2 text-[11px] font-semibold text-emerald-400">Bullish Factors</p>
                      <ul className="space-y-1.5">
                        {[
                          stock.gov_score >= 75 && "Strong government support",
                          stock.dna_scores["Growth"] >= 60 && "Strong revenue growth trend",
                          stock.dna_scores["Execution Quality"] >= 60 && "High execution quality",
                          stock.dividend_yield && stock.dividend_yield !== "—" && `Dividend yield of ${stock.dividend_yield}`,
                          stock.roe && stock.roe !== "—" && `ROE of ${stock.roe}`,
                        ].filter(Boolean).slice(0, 4).map((f, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-[12px] text-slate-300">
                            <span className="mt-0.5 text-emerald-400">•</span>{f}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="mb-2 text-[11px] font-semibold text-rose-400">Key Risks</p>
                      <ul className="space-y-1.5">
                        {[
                          stock.dna_scores["Debt Strength"] < 40 && "High leverage risk",
                          parseFloat(stock.pe || "0") > 40 && "Premium valuation",
                          stock.dna_scores["News Sensitivity"] > 70 && "High market volatility",
                          stock.gov_score >= 75 && "Regulatory exposure",
                        ].filter(Boolean).slice(0, 4).map((r, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-[12px] text-slate-300">
                            <span className="mt-0.5 text-rose-400">•</span>{r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  <button className="mt-5 w-full rounded-xl bg-violet-500/10 border border-violet-500/20 py-2.5 text-[12px] font-medium text-violet-300 hover:bg-violet-500/15 transition">
                    Ask AI about {stock.name} →
                  </button>
                </>
              : <p className="py-8 text-center text-sm text-slate-500">Description unavailable</p>
            }
          </SectionCard>

          <SectionCard title="Analyst Consensus">
            {stock.analyst_count > 0 ? (
              <>
                <div className="mb-4 flex items-center gap-4">
                  <span className={`rounded-full border px-4 py-1.5 text-[14px] font-bold ${rec.cls} ${rec.bg}`}>
                    {rec.label}
                  </span>
                  <span className="text-[12px] text-slate-500">{stock.analyst_count} analysts</span>
                </div>
                {(stock.buy_count > 0 || stock.hold_count > 0 || stock.sell_count > 0) && (() => {
                  const total = stock.buy_count + stock.hold_count + stock.sell_count || 1;
                  return (
                    <div className="space-y-2 mb-5">
                      {[
                        { label: "Buy",  count: stock.buy_count,  color: "bg-emerald-500" },
                        { label: "Hold", count: stock.hold_count, color: "bg-amber-500" },
                        { label: "Sell", count: stock.sell_count, color: "bg-rose-500" },
                      ].map(r => (
                        <div key={r.label}>
                          <div className="mb-1 flex justify-between text-[11px]">
                            <span className="text-slate-400">{r.label}</span>
                            <span className="font-semibold text-white">{r.count}</span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                            <div className={`h-full rounded-full ${r.color}`} style={{ width: `${Math.round((r.count / total) * 100)}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })()}
                {stock.target_mean && stock.target_mean !== "—" && (
                  <>
                    <p className="mb-1 text-[11px] text-slate-500">12-month price target range</p>
                    <TargetBand current={stock.price} low={stock.target_low} mean={stock.target_mean} high={stock.target_high} />
                  </>
                )}
              </>
            ) : (
              <p className="py-8 text-center text-sm text-slate-500">Analyst data not available for {symbol.toUpperCase()}</p>
            )}
          </SectionCard>
        </div>
      )}
    </main>
  );
}
