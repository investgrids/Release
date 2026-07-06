"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Zap } from "lucide-react";
import type { ReactNode } from "react";

interface TopMoverItem {
  company: string;
  ticker: string;
  value: string;
  subtitle: string;
  positive?: boolean;
  isVolume?: boolean;
}

interface TopMoverCardProps {
  title: string;
  items: TopMoverItem[];
  icon?: ReactNode;
}

function TickerAvatar({ ticker }: { ticker: string }) {
  const short = ticker.slice(0, 4);
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-slate-900 text-[10px] font-bold text-slate-300">
      {short}
    </div>
  );
}

export function TopMoverCard({ title, items, icon }: TopMoverCardProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 shadow-glow h-full"
    >
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon && <span className="text-slate-400">{icon}</span>}
          <h3 className="text-sm font-semibold text-white">{title}</h3>
        </div>
        <button className="text-xs text-slate-500 transition hover:text-white">View All</button>
      </div>
      <div className="space-y-2.5">
        {items.map((item) => (
          <Link
            key={item.ticker}
            href={`/companies/${item.ticker}`}
            className="flex items-center justify-between gap-3 rounded-[16px] border border-white/5 bg-slate-950/60 px-3 py-2.5 transition hover:bg-slate-900/60 hover:border-white/10"
          >
            <div className="flex items-center gap-3 min-w-0">
              <TickerAvatar ticker={item.ticker} />
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{item.ticker}</p>
                <p className="text-[11px] text-slate-500 truncate">{item.company}</p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <p className={`text-sm font-semibold ${
                item.isVolume ? "text-slate-300" : item.positive === false ? "text-rose-400" : "text-emerald-400"
              }`}>
                {item.value}
              </p>
              <p className="text-[11px] text-slate-500">{item.subtitle}</p>
            </div>
          </Link>
        ))}
      </div>
    </motion.section>
  );
}

interface TopMoversGridProps {
  gainers: TopMoverItem[];
  losers: TopMoverItem[];
  active: TopMoverItem[];
}

export function TopMoversGrid({ gainers, losers, active }: TopMoversGridProps) {
  return (
    <div className="grid gap-6 xl:grid-cols-3 items-stretch">
      <TopMoverCard title="Top Gainers" icon={<TrendingUp className="h-4 w-4 text-emerald-400" />} items={gainers} />
      <TopMoverCard title="Top Losers"  icon={<TrendingDown className="h-4 w-4 text-rose-400" />} items={losers} />
      <TopMoverCard title="Most Active" icon={<Zap className="h-4 w-4 text-amber-400" />} items={active} />
    </div>
  );
}
