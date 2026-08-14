"use client";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// EventSidebarCharts.tsx (apps/web/app/events/[id]/) for the same pattern
// and its full rationale.
import {
  Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
  PieChart, Pie, Cell,
} from "recharts";

export function ScoreHistoryChart({ historySliced }: { historySliced: any[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={historySliced} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="#22c55e" stopOpacity={0.35}/>
            <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02}/>
          </linearGradient>
        </defs>
        <XAxis dataKey="month" tick={{ fill: "rgb(var(--text-muted))", fontSize: 10 }} axisLine={false} tickLine={false}/>
        <YAxis domain={[0, 100]} tick={{ fill: "rgb(var(--text-muted))", fontSize: 10 }} axisLine={false} tickLine={false}/>
        <Tooltip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.08)", borderRadius: 10, fontSize: 11 }} itemStyle={{ color: "#22c55e" }} labelStyle={{ color: "#94a3b8" }}/>
        <Area type="monotone" dataKey="value" stroke="#22c55e" fill="url(#scoreGrad)" strokeWidth={2} dot={{ fill: "#22c55e", r: 3 }}/>
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function SectorDistributionDonut({ sectorDistribution }: { sectorDistribution: { sector: string; percentage: number; color: string }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={sectorDistribution.map(s => ({ name: s.sector, value: s.percentage, color: s.color }))}
          cx="50%" cy="50%" innerRadius={45} outerRadius={70} dataKey="value" paddingAngle={2}>
          {sectorDistribution.map((s, i) => (
            <Cell key={i} fill={s.color}/>
          ))}
        </Pie>
        <Tooltip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.08)", borderRadius: 10, fontSize: 11 }} formatter={(v: any) => [`${v}%`]}/>
      </PieChart>
    </ResponsiveContainer>
  );
}
