"use client";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// apps/web/app/events/[id]/EventSidebarCharts.tsx for the full rationale.
import { AreaChart, Area, ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";

interface GmpPoint { label: string; value: number }

export function GmpChart({ data }: { data: GmpPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gmp-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#34d399" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#34d399" stopOpacity={0}   />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="value" stroke="#34d399" strokeWidth={1.5}
          fill="url(#gmp-grad)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function SectorTrendsDonut({ sectorTrends }: { sectorTrends: { name: string; count: number; color: string }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={sectorTrends} dataKey="count" cx="50%" cy="50%"
          innerRadius={40} outerRadius={65} paddingAngle={2}>
          {sectorTrends.map((s, i) => <Cell key={i} fill={s.color} />)}
        </Pie>
        <Tooltip
          contentStyle={{ background: "#020617", border: "1px solid rgb(var(--text-primary) / 0.1)", borderRadius: 8 }}
          formatter={(v: number, n: string) => [`${v} IPOs`, n]}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
