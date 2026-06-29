"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const PERIODS = ["1D", "1W", "1M", "6M", "1Y", "3Y"] as const;
type Period = typeof PERIODS[number];

const PERIOD_API: Record<Period, string> = {
  "1D": "1D", "1W": "1W", "1M": "1M", "6M": "6M", "1Y": "1Y", "3Y": "3Y",
};

// How to abbreviate date labels depending on period
function formatLabel(raw: string, period: Period): string {
  if (!raw) return "";
  // For intraday (1D / 1W) the label is "YYYY-MM-DD HH:MM"
  if (period === "1D" || period === "1W") {
    const parts = raw.split(" ");
    return parts[1]?.slice(0, 5) ?? parts[0]; // "HH:MM"
  }
  // For monthly+ just show "DD MMM" or "MMM 'YY"
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  if (period === "6M" || period === "1M") {
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  }
  return d.toLocaleDateString("en-IN", { month: "short", year: "2-digit" });
}

interface IndexData {
  title: string;
  value: string;
  change: string;
  positive: boolean;
  high: string;
  low: string;
}

interface Point { label: string; value: number }

// Symbol key to pass to the API
const INDEX_KEY: Record<string, string> = {
  "NIFTY 50":  "NIFTY",
  "SENSEX":    "SENSEX",
  "BANKNIFTY": "BANKNIFTY",
};

export function MarketIndexCard({ indices }: { indices: IndexData[] }) {
  const [activeIdx, setActiveIdx]   = useState(0);
  const [period, setPeriod]         = useState<Period>("1M");
  const [chartData, setChartData]   = useState<Point[]>([]);
  const [loading, setLoading]       = useState(false);

  const card = indices[activeIdx] ?? indices[0];

  const fetchChart = useCallback(async (indexTitle: string, p: Period) => {
    const sym = INDEX_KEY[indexTitle] ?? indexTitle.replace(/\s/g, "");
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/indices/chart/${sym}?period=${PERIOD_API[p]}`);
      const data: Point[] = await res.json();
      setChartData(data);
    } catch {
      setChartData([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (card?.title) fetchChart(card.title, period);
  }, [card?.title, period, fetchChart]);

  if (!card) return null;

  const color    = card.positive ? "#22c55e" : "#f43f5e";
  const gradId   = `grad-idx-${activeIdx}`;
  const tickCount = chartData.length;
  // Show ~5 evenly spaced ticks
  const tickInterval = Math.max(1, Math.floor(tickCount / 5));

  return (
    <div className="rounded-[24px] border border-white/10 bg-slate-950/80 p-5 shadow-glow backdrop-blur-xl h-full flex flex-col">

      {/* Index selector */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex gap-1">
          {indices.map((idx, i) => (
            <button
              key={idx.title}
              onClick={() => setActiveIdx(i)}
              className={`px-3 py-1 rounded-full text-[11px] font-semibold tracking-wide transition-colors ${
                i === activeIdx
                  ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {idx.title}
            </button>
          ))}
        </div>

        {/* Period selector */}
        <div className="flex gap-0.5">
          {PERIODS.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                p === period
                  ? "bg-white/10 text-white"
                  : "text-slate-500 hover:text-slate-400"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Value row */}
      <div className="flex items-end justify-between mb-3">
        <div>
          <p className="text-3xl font-bold text-white tracking-tight">{card.value}</p>
          <p className={`mt-0.5 text-sm font-medium ${card.positive ? "text-emerald-400" : "text-rose-400"}`}>
            {card.change}
          </p>
        </div>
        <div className="text-right text-[11px] text-slate-500">
          <div>H <span className="text-slate-300 font-medium">{card.high}</span></div>
          <div>L <span className="text-slate-300 font-medium">{card.low}</span></div>
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 min-h-[110px] relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-4 w-4 rounded-full border-2 border-sky-500/40 border-t-sky-400 animate-spin" />
          </div>
        )}
        {!loading && chartData.length > 0 && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor={color} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="label"
                interval={tickInterval}
                tickFormatter={raw => formatLabel(raw, period)}
                tick={{ fill: "#64748b", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fill: "#64748b", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                width={55}
                tickFormatter={v => v.toLocaleString("en-IN")}
              />
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 10,
                  fontSize: 11,
                }}
                labelStyle={{ color: "#94a3b8" }}
                itemStyle={{ color }}
                formatter={(v: number) => [v.toLocaleString("en-IN"), card.title]}
                labelFormatter={raw => formatLabel(String(raw), period)}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                fill={`url(#${gradId})`}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: color }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
        {!loading && chartData.length === 0 && (
          <div className="flex h-full items-center justify-center text-[11px] text-slate-600">
            No data
          </div>
        )}
      </div>
    </div>
  );
}

// Legacy export — kept so other imports don't break
export function MarketOverviewCard({ card }: { card: IndexData & { chartData?: Point[] } }) {
  return <MarketIndexCard indices={[card]} />;
}
