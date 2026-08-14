"use client";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// EventSidebarCharts.tsx (apps/web/app/events/[id]/) for the same pattern
// and its full rationale.
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine,
} from "recharts";

function PerfTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-surface-border/10 bg-surface-card px-3 py-2 text-[11px] shadow-xl">
      <p className="mb-1 text-text-secondary">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <div className="h-1.5 w-3 rounded-full" style={{ background: p.color }} />
          <span className="text-text-secondary">{p.dataKey}</span>
          <span className="font-semibold text-text-primary">{p.value > 0 ? "+" : ""}{p.value?.toFixed(2)}%</span>
        </div>
      ))}
    </div>
  );
}

export function CompareLineChart({ mergedChart, selected, color }: {
  mergedChart: any[]; selected: string[]; color: (i: number) => string;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={mergedChart}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--text-primary) / 0.03)" vertical={false} />
        <XAxis dataKey="label" stroke="#475569" axisLine={false} tickLine={false}
          tick={{ fontSize: 9, fill: "rgb(var(--text-muted))" }} interval="preserveStartEnd" />
        <YAxis stroke="#475569" axisLine={false} tickLine={false} width={50}
          tick={{ fontSize: 9, fill: "rgb(var(--text-muted))" }}
          tickFormatter={v => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`} />
        <ReferenceLine y={0} stroke="rgb(var(--text-primary) / 0.08)" />
        <Tooltip content={<PerfTooltip />} />
        {selected.map((sym, i) => (
          <Line key={sym} type="monotone" dataKey={sym} stroke={color(i)}
            strokeWidth={2} dot={false} connectNulls name={sym} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
