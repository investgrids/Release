"use client";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// apps/web/app/events/[id]/EventSidebarCharts.tsx for the full rationale.
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export function MiniArea({ data, positive }: { data: { label: string; value: number }[]; positive: boolean }) {
  if (!data.length) return <div className="mt-3 h-12 rounded-lg bg-text-primary/[0.02]" />;
  const color = positive ? "#10b981" : "#f43f5e";
  return (
    <div className="mt-3 h-12">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`g-${positive}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0}   />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5}
            fill={`url(#g-${positive})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function HeroAreaChart({ chart }: { chart: { label: string; value: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={chart}>
        <defs>
          <linearGradient id="hero-g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#38bdf8" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#38bdf8" stopOpacity={0}   />
          </linearGradient>
        </defs>
        <XAxis dataKey="label" hide />
        <YAxis domain={["auto", "auto"]} hide />
        <Tooltip contentStyle={{ background: "#020617", border: "1px solid rgb(var(--text-primary) / 0.08)", color: "#fff", borderRadius: 12 }} />
        <Area type="monotone" dataKey="value" stroke="#38bdf8" strokeWidth={2} fill="url(#hero-g)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
