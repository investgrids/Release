"use client";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// apps/web/app/events/[id]/EventSidebarCharts.tsx for the full rationale.
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export function ImpactTrendChart({ trendData }: { trendData: any[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={trendData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="day" tick={{ fill: "rgb(var(--text-muted))", fontSize: 9 }} axisLine={false} tickLine={false}/>
        <YAxis tick={{ fill: "rgb(var(--text-muted))", fontSize: 9 }} axisLine={false} tickLine={false}/>
        <Tooltip contentStyle={{ background: "rgb(var(--surface-card))", border: "1px solid rgb(var(--text-primary) / 0.08)", borderRadius: 8, fontSize: 10 }} labelStyle={{ color: "#94a3b8" }}/>
        <Line type="monotone" dataKey="veryHigh" stroke="#f43f5e" strokeWidth={1.5} dot={{ fill: "#f43f5e", r: 2 }} name="Very High"/>
        <Line type="monotone" dataKey="high"     stroke="#f59e0b" strokeWidth={1.5} dot={{ fill: "#f59e0b", r: 2 }} name="High"/>
        <Line type="monotone" dataKey="medium"   stroke="#6366f1" strokeWidth={1.5} dot={{ fill: "#6366f1", r: 2 }} name="Medium"/>
        <Line type="monotone" dataKey="low"      stroke="#22c55e" strokeWidth={1.5} dot={{ fill: "#22c55e", r: 2 }} name="Low"/>
      </LineChart>
    </ResponsiveContainer>
  );
}
