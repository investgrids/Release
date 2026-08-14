"use client";

// Recharts (+ its d3 dependencies) split into its own chunk, only fetched
// when this file is actually dynamically imported (2026-08 performance
// audit — recharts was previously a static top-level import in
// EventPageClient.tsx, pulling ~50-90kB into the initial JS for every
// event page even though both charts here are secondary sidebar widgets,
// not Layer 1 content). Client-only (no SSR value for a chart that needs
// a mounted container to size itself).
import {
  AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";

interface SectorSlice { name: string; value: number; color: string }
interface ChartPoint { label: string; value: number }

export function SectorDonut({ sectorData }: { sectorData: SectorSlice[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={sectorData} cx="50%" cy="50%" innerRadius={28} outerRadius={44} paddingAngle={2} dataKey="value" strokeWidth={0}>
          {sectorData.map((e, i) => <Cell key={i} fill={e.color}/>)}
        </Pie>
        <RechartsTip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.08)", borderRadius: 8, fontSize: 10 }}/>
      </PieChart>
    </ResponsiveContainer>
  );
}

export function MarketReactionChart({ chartData }: { chartData: ChartPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <defs>
          <linearGradient id="aGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3}/>
            <stop offset="100%" stopColor="#6366f1" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <XAxis dataKey="label" hide/>
        <YAxis domain={["auto","auto"]} hide/>
        <RechartsTip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.08)", borderRadius: 6, fontSize: 10, padding: "4px 8px" }} formatter={(v: number) => [v.toLocaleString("en-IN"), ""]}/>
        <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={1.5} fill="url(#aGrad)"/>
      </AreaChart>
    </ResponsiveContainer>
  );
}
