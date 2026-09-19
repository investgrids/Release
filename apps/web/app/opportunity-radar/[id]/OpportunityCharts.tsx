"use client";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// EventSidebarCharts.tsx (apps/web/app/events/[id]/) for the same pattern
// and its full rationale.
import {
  ResponsiveContainer, Tooltip,
  PieChart, Pie, Cell,
} from "recharts";

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
