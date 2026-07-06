"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Sun, Moon } from "lucide-react";

interface HeroStats {
  sentimentScore: number;
  sentimentLabel: string;
  sentimentChange: string;
  eventsToday: number;
  eventsTodayVs: string;
  highImpactEvents: number;
  highImpactVs: string;
  opportunityScore: number;
  opportunityVs: string;
  aiConfidence: number;
  aiConfidenceLabel: string;
  aiConfidenceVs: string;
}

interface DashboardHeroProps {
  date: string;
  status: "Market Open" | "Market Closed";
  greeting: string;
  timeIST: string;
  stats: HeroStats;
}

function AnimCounter({ to, duration = 1.2 }: { to: number; duration?: number }) {
  return <span>{to}</span>;
}

export function DashboardHero({ date, status, greeting, timeIST, stats }: DashboardHeroProps) {
  const open = status === "Market Open";

  const kpis = [
    {
      id: "sentiment",
      label: "Market Sentiment",
      value: stats.sentimentLabel,
      sub: `${stats.sentimentScore} / 100`,
      vs: `↑ ${stats.sentimentChange} vs yesterday`,
      color: "text-emerald-400",
      border: "border-emerald-500/20",
      glow: "from-emerald-500/10 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-emerald-400">
          <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>
          <polyline points="16 7 22 7 22 13"/>
        </svg>
      ),
      sparkline: [68, 70, 69, 72, 71, 74, stats.sentimentScore],
      sparkColor: "#22c55e",
    },
    {
      id: "events",
      label: "Events Today",
      value: String(stats.eventsToday),
      sub: "",
      vs: `↑ ${stats.eventsTodayVs} vs yesterday`,
      color: "text-sky-400",
      border: "border-sky-500/20",
      glow: "from-sky-500/10 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-sky-400">
          <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
        </svg>
      ),
      sparkline: null,
      sparkColor: "#38bdf8",
    },
    {
      id: "highimpact",
      label: "High Impact Events",
      value: String(stats.highImpactEvents),
      sub: "",
      vs: `↑ ${stats.highImpactVs} vs yesterday`,
      color: "text-orange-400",
      border: "border-orange-500/25",
      glow: "from-orange-500/12 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-orange-400">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
        </svg>
      ),
      sparkline: null,
      sparkColor: "#f97316",
    },
    {
      id: "opportunity",
      label: "Opportunity Score",
      value: String(stats.opportunityScore),
      sub: "",
      vs: `↑ ${stats.opportunityVs} pts vs yesterday`,
      color: "text-violet-400",
      border: "border-violet-500/20",
      glow: "from-violet-500/10 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-violet-400">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
        </svg>
      ),
      sparkline: null,
      sparkColor: "#a78bfa",
    },
    {
      id: "confidence",
      label: "AI Confidence",
      value: `${stats.aiConfidence}%`,
      sub: stats.aiConfidenceLabel,
      vs: `↑ ${stats.aiConfidenceVs} vs yesterday`,
      color: "text-teal-400",
      border: "border-teal-500/20",
      glow: "from-teal-500/10 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-teal-400">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
      ),
      sparkline: null,
      sparkColor: "#2dd4bf",
    },
  ];

  return (
    <div className="relative overflow-hidden rounded-[28px] border border-white/10 bg-[#030812] shadow-[0_20px_60px_rgba(0,0,0,0.5)]">
      {/* Animated gradient background */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-20 left-[10%] h-64 w-64 rounded-full bg-sky-600/8 blur-3xl"/>
        <div className="absolute -bottom-10 left-[40%] h-48 w-48 rounded-full bg-violet-600/8 blur-3xl"/>
        <div className="absolute -right-10 top-0 h-56 w-56 rounded-full bg-emerald-600/6 blur-3xl"/>
      </div>

      <div className="relative p-6 pb-5">
        {/* Top row */}
        <div className="mb-5 flex items-start justify-between">
          <div>
            <motion.h1
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="flex items-center gap-2 text-[26px] font-black text-white tracking-tight">
              {greeting}, Investor
              <span className="text-slate-400">{open ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</span>
            </motion.h1>
            <p className="mt-1 text-[13px] text-slate-400">Stay ahead with AI-powered market intelligence</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[11px] text-slate-400">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3 w-3">
                <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
              </svg>
              Updated: {date} {timeIST} IST
              <button className="ml-1 text-slate-600 hover:text-white transition">↻</button>
            </div>
            <button className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/[0.08] transition">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3 w-3">
                <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
              </svg>
              Customize
            </button>
          </div>
        </div>

        {/* 5 KPI cards */}
        <div className="grid grid-cols-5 gap-3">
          {kpis.map((kpi, i) => (
            <motion.div
              key={kpi.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: i * 0.06 }}
              className={`relative overflow-hidden rounded-2xl border ${kpi.border} bg-gradient-to-br ${kpi.glow} p-4`}>
              <div className="flex items-center justify-between mb-2">
                <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{kpi.label}</p>
                <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-white/[0.05]">
                  {kpi.icon}
                </div>
              </div>
              <div className="flex items-end justify-between">
                <div>
                  <p className={`text-[26px] font-black leading-none ${kpi.color}`}>{kpi.value}</p>
                  {kpi.sub && <p className="mt-0.5 text-[11px] text-slate-400">{kpi.sub}</p>}
                </div>
                {kpi.sparkline && (
                  <svg viewBox="0 0 60 28" className="h-7 w-14 shrink-0" fill="none">
                    <polyline
                      points={kpi.sparkline.map((v, j) => `${j * 10},${28 - ((v - 60) / 20) * 28}`).join(" ")}
                      stroke={kpi.sparkColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"
                    />
                  </svg>
                )}
              </div>
              <p className="mt-2 text-[10px] text-slate-500">{kpi.vs}</p>
            </motion.div>
          ))}
        </div>

        {/* Quick action buttons */}
        <div className="mt-4 flex gap-2">
          <Link href="/events"
            className="flex items-center gap-2 rounded-xl border border-sky-500/25 bg-sky-500/10 px-4 py-2 text-[12px] font-medium text-sky-300 hover:bg-sky-500/18 transition">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            AI Market Wrap
          </Link>
          <Link href="/events"
            className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-[12px] font-medium text-slate-300 hover:bg-white/[0.08] transition">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
            Explore Events
          </Link>
          <Link href="/opportunity-radar"
            className="flex items-center gap-2 rounded-xl border border-violet-500/25 bg-violet-500/10 px-4 py-2 text-[12px] font-medium text-violet-300 hover:bg-violet-500/18 transition">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
            Opportunity Radar
          </Link>
          <div className="ml-auto flex items-center gap-1.5 text-[11px]">
            <span className={`h-2 w-2 rounded-full ${open ? "bg-emerald-400 animate-pulse" : "bg-rose-400"}`}/>
            <span className={open ? "text-emerald-400" : "text-rose-400"}>{status}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
