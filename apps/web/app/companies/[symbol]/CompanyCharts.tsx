"use client";

// Recharts (+ its d3 dependencies) split into its own chunk, only fetched
// when one of these is dynamically imported (2026-08 performance audit —
// this page statically imported recharts at the top of a 1600+ line file
// for 7 separate chart widgets scattered through the page, pulling
// ~50-90kB into the initial JS even for the parts of the page a visitor
// never scrolls to). Client-only — these all need a mounted container to
// size themselves, no SSR value.
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis,
} from "recharts";

// ── Price Chart (Section 2) ──────────────────────────────────────────────────
export function PriceAreaChart({ chartData, chartColor }: { chartData: any[]; chartColor: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={chartColor} stopOpacity={0.25}/>
            <stop offset="100%" stopColor={chartColor} stopOpacity={0}/>
          </linearGradient>
        </defs>
        <XAxis dataKey="label" tick={{ fill: "rgb(var(--text-muted))", fontSize: 10 }} tickLine={false} axisLine={false}/>
        <YAxis domain={["auto","auto"]} tick={{ fill: "rgb(var(--text-muted))", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `₹${v}`} width={60}/>
        <RTooltip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.12)", borderRadius: 10, fontSize: 11 }}
          formatter={(v: number) => [`₹${v.toLocaleString("en-IN")}`, "Price"]}/>
        <Area type="monotone" dataKey="value" stroke={chartColor} strokeWidth={2} fill="url(#cg)" dot={false}/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Stock DNA radar (Section 4) ──────────────────────────────────────────────
export function DnaRadarChart({ entries }: { entries: [string, number][] }) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <RadarChart data={entries.map(([k, v]) => ({ subject: k.split(" ")[0], value: v }))}>
        <PolarGrid stroke="rgb(var(--text-primary) / 0.08)"/>
        <PolarAngleAxis dataKey="subject" tick={{ fill: "rgb(var(--text-muted))", fontSize: 9 }}/>
        <Radar dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2}/>
      </RadarChart>
    </ResponsiveContainer>
  );
}

// ── Financial Highlights sparkline (Section 5) ───────────────────────────────
export function Sparkline({ data, stroke }: { data: any[]; stroke: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <Line type="monotone" dataKey="value" stroke={stroke} strokeWidth={1.5} dot={false}/>
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Government Exposure donut (Section 8) ────────────────────────────────────
// pieData / govBreakdown deliberately separate props, matching the original
// inline JSX exactly: the Pie's own `data` uses a 2-slice synthetic
// fallback when there's no real breakdown, but Cell colors are only ever
// generated from the real `govBreakdown` array (empty when synthetic) — a
// pure lift-and-shift, not a behavior change.
export function GovBreakdownDonut({ pieData, govBreakdown, colors }: {
  pieData: { label: string; pct: number; color?: string }[];
  govBreakdown: { label: string; pct: number; color?: string }[];
  colors: string[];
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={pieData} cx="50%" cy="50%" innerRadius={38} outerRadius={58} paddingAngle={2} dataKey="pct" strokeWidth={0}>
          {govBreakdown.map((b, i) => <Cell key={i} fill={b.color || colors[i % colors.length]}/>)}
        </Pie>
        <RTooltip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.12)", borderRadius: 8, fontSize: 10 }} formatter={(v: number, n: any, p: any) => [p.payload.label, `${v}%`]}/>
      </PieChart>
    </ResponsiveContainer>
  );
}

// ── AI Sentiment weekly trend (Section 11) ───────────────────────────────────
export function SentimentTrendChart({ trend }: { trend: { w: string; v: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={trend}>
        <defs>
          <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3}/>
            <stop offset="100%" stopColor="#22c55e" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <XAxis dataKey="w" tick={{ fill: "rgb(var(--text-muted))", fontSize: 9 }} tickLine={false} axisLine={false}/>
        <YAxis domain={[0, 100]} hide/>
        <RTooltip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.12)", borderRadius: 8, fontSize: 10 }} formatter={(v: number) => [`${v}%`, "Bullish"]}/>
        <Area type="monotone" dataKey="v" stroke="#22c55e" strokeWidth={1.5} fill="url(#sg)"/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Shareholding donut (Section 16) ──────────────────────────────────────────
export function ShareholdingDonut({ data }: { data: { name: string; value: number; color: string }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={data} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={2} dataKey="value" strokeWidth={0}>
          {data.map((d, i) => <Cell key={i} fill={d.color}/>)}
        </Pie>
        <RTooltip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.12)", borderRadius: 8, fontSize: 10 }}/>
      </PieChart>
    </ResponsiveContainer>
  );
}

// ── Historical Performance bar chart (Section 18) ────────────────────────────
export function HistoricalPerformanceBarChart({ data, activeMetric }: { data: any[]; activeMetric: "revenue" | "profit" }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
        <XAxis dataKey="year" tick={{ fill: "rgb(var(--text-muted))", fontSize: 10 }} tickLine={false} axisLine={false}/>
        <YAxis tick={{ fill: "rgb(var(--text-muted))", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${(v/1000).toFixed(0)}K`} width={40}/>
        <RTooltip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.12)", borderRadius: 10, fontSize: 11 }} formatter={(v: number) => [`₹${v.toLocaleString()} Cr`, activeMetric === "revenue" ? "Revenue" : "Net Profit"]}/>
        <Bar dataKey={activeMetric === "revenue" ? "revenue" : "net_income"} radius={[6, 6, 0, 0]}
          fill={activeMetric === "revenue" ? "#38bdf8" : "#22c55e"} fillOpacity={0.8}/>
      </BarChart>
    </ResponsiveContainer>
  );
}
