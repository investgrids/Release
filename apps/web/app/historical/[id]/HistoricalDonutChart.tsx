"use client";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// apps/web/app/events/[id]/EventSidebarCharts.tsx for the full rationale.
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

const DONUT_COLORS = ["#10b981", "#f43f5e", "#f59e0b", "#0ea5e9", "#8b5cf6"];

export function HistoricalDonutChart({ filtered }: { filtered: { name: string; value: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={filtered} dataKey="value" nameKey="name" innerRadius={40} outerRadius={62} paddingAngle={2} strokeWidth={0}>
          {filtered.map((_, i) => <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} />)}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
}
