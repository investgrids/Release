"use client";

import { motion } from "framer-motion";
import { Area, AreaChart, ResponsiveContainer } from "recharts";

interface MarketOverviewCard {
  title: string;
  value: string;
  change: string;
  chartData: Array<{ label: string; value: number }>;
  positive: boolean;
  high: string;
  low: string;
}

export function MarketOverviewCard({ card }: { card: MarketOverviewCard }) {
  const gradId = `grad-${card.title.replace(/\s/g, "")}`;

  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-[24px] border border-white/10 bg-slate-950/80 p-5 shadow-glow backdrop-blur-xl transition duration-300 hover:-translate-y-0.5 h-full flex flex-col justify-between"
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-500">{card.title}</p>
      <p className="mt-2 text-2xl font-bold text-white">{card.value}</p>
      <p className={`mt-1 text-xs font-medium ${card.positive ? "text-emerald-400" : "text-rose-400"}`}>
        {card.change}
      </p>
      <div className="mt-3 h-14">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={card.chartData}>
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={card.positive ? "#22c55e" : "#f43f5e"} stopOpacity={0.4} />
                <stop offset="100%" stopColor={card.positive ? "#22c55e" : "#f43f5e"} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="value"
              stroke={card.positive ? "#22c55e" : "#f43f5e"}
              fill={`url(#${gradId})`}
              strokeWidth={1.5}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 space-y-0.5 text-[10px] text-slate-500">
        <div className="flex justify-between"><span>High</span><span className="text-slate-400">{card.high}</span></div>
        <div className="flex justify-between"><span>Low</span><span className="text-slate-400">{card.low}</span></div>
      </div>
    </motion.article>
  );
}
