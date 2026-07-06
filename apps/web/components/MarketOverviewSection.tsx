"use client";

import { useEffect, useState, useCallback } from "react";
import { AreaChart, Area, ResponsiveContainer, Tooltip } from "recharts";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const PERIODS = ["1D", "1W", "1M", "3M", "1Y"] as const;
type Period = typeof PERIODS[number];

const PERIOD_API: Record<Period, string> = {
  "1D": "1D", "1W": "1W", "1M": "1M", "3M": "6M", "1Y": "1Y",
};

const INDEX_SYMBOL: Record<string, string> = {
  "NIFTY 50":   "NIFTY",
  "SENSEX":     "SENSEX",
  "NIFTY BANK": "BANKNIFTY",
  "NIFTY IT":   "NIFTYIT",
};

interface IndexCard {
  title: string;
  value: string;
  change: string;
  positive: boolean;
  high?: string;
  low?: string;
}

function MiniChart({ data, positive, id }: { data: any[]; positive: boolean; id: string }) {
  const color = positive ? "#22c55e" : "#f43f5e";
  return (
    <div className="h-14 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`mg-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.25}/>
              <stop offset="100%" stopColor={color} stopOpacity={0}/>
            </linearGradient>
          </defs>
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 10 }}
            formatter={(v: number) => [v.toLocaleString("en-IN"), ""]}
            labelFormatter={() => ""}
          />
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5}
            fill={`url(#mg-${id})`} dot={false}/>
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function IndexCardItem({ card, period, idx }: { card: IndexCard; period: Period; idx: number }) {
  const [chartData, setChartData] = useState<any[]>([]);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    if (!card.title) { setLoading(false); return; }
    const sym = INDEX_SYMBOL[card.title] ?? card.title.replace(/\s/g, "");
    setLoading(true);
    fetch(`${API}/api/indices/chart/${sym}?period=${PERIOD_API[period]}`)
      .then(r => r.ok ? r.json() : [])
      .then(d => setChartData(Array.isArray(d) ? d : []))
      .catch(() => setChartData([]))
      .finally(() => setLoading(false));
  }, [card.title, period]);

  return (
    <div className="flex flex-col gap-1 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4 hover:border-sky-500/20 hover:bg-white/[0.05] transition">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{card.title}</p>
      <p className="text-[20px] font-black text-white leading-none mt-0.5">{card.value}</p>
      <p className={`text-[11px] font-semibold ${card.positive ? "text-emerald-400" : "text-rose-400"}`}>
        {card.change}
      </p>
      <div className="mt-1">
        {loading ? (
          <div className="flex h-14 items-center justify-center">
            <div className="h-3 w-3 animate-spin rounded-full border-2 border-white/10 border-t-slate-400"/>
          </div>
        ) : (
          <MiniChart data={chartData} positive={card.positive} id={`${card.title}-${idx}`}/>
        )}
      </div>
    </div>
  );
}

export function MarketOverviewSection({ indices }: { indices: IndexCard[] }) {
  const [period, setPeriod] = useState<Period>("1D");

  return (
    <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[14px] font-bold text-white">Market Overview</h2>
        <div className="flex gap-0.5 rounded-xl bg-white/[0.04] p-0.5">
          {PERIODS.map(p => (
            <button key={p} onClick={() => setPeriod(p)}
              className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                p === period ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}>
              {p}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {indices.slice(0, 4).map((c, i) => (
          <IndexCardItem key={`${c.title ?? ""}-${i}`} card={c} period={period} idx={i}/>
        ))}
      </div>
    </div>
  );
}
