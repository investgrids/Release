"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const data = [
  { time: "Jun 23", value: 2800 },
  { time: "Jul 23", value: 3100 },
  { time: "Aug 23", value: 2950 },
  { time: "Sep 23", value: 3250 },
  { time: "Oct 23", value: 3400 },
  { time: "Nov 23", value: 3600 },
  { time: "Dec 23", value: 3850 },
  { time: "Jan 24", value: 3950 },
  { time: "Feb 24", value: 4200 },
  { time: "Mar 24", value: 4480 },
  { time: "Apr 24", value: 4620 }
];

export function StockChart() {
  return (
    <div className="h-72 rounded-3xl border border-white/10 bg-slate-950/80 p-4">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} width={36} />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(148,163,184,0.2)", color: "#fff" }} cursor={{ stroke: "rgba(56,189,248,0.25)", strokeWidth: 2 }} />
          <Area type="monotone" dataKey="value" stroke="#38bdf8" strokeWidth={3} fillOpacity={1} fill="url(#colorValue)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
