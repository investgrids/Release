"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

interface StockDetailChartProps {
  data: Array<{ month: string; value: number }>;
}

export function StockDetailChart({ data }: StockDetailChartProps) {
  return (
    <div className="mt-6 h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="month" stroke="#94a3b8" axisLine={false} tickLine={false} />
          <YAxis stroke="#94a3b8" axisLine={false} tickLine={false} width={40} />
          <Tooltip contentStyle={{ backgroundColor: "#020617", border: "1px solid rgba(255,255,255,0.08)", color: "#fff" }} />
          <Line type="monotone" dataKey="value" stroke="#38bdf8" strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
