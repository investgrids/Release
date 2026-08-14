"use client";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// apps/web/app/events/[id]/EventSidebarCharts.tsx for the full rationale.
import { AreaChart, Area, ResponsiveContainer } from "recharts";

interface ChartPoint { label: string; value: number }

const COLORS: Record<string, string> = {
  gold: "#fbbf24", silver: "#94a3b8", copper: "#f97316", platinum: "#38bdf8",
  brent: "#60a5fa", wti: "#93c5fd", natgas: "#818cf8", petrol: "#34d399",
};

export function SparkLine({ data, id }: { data: ChartPoint[]; id: string }) {
  const color = COLORS[id] ?? "#818cf8";
  if (!data.length) return <div className="mt-3 min-h-[48px] flex-1 rounded-lg bg-text-primary/[0.02]" />;
  return (
    <div className="mt-3 min-h-[48px] flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`g-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0}   />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5}
            fill={`url(#g-${id})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
