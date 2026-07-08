"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { CalendarDays, Building2, BookOpen, Sparkles } from "lucide-react";

interface FirstVisitBannerProps {
  onDismiss: () => void;
}

const FEATURES: { icon: ReactNode; label: string; color: string }[] = [
  { icon: <CalendarDays className="h-3 w-3" />, label: "Live Events",    color: "sky"     },
  { icon: <Building2 className="h-3 w-3" />,   label: "Company Impact", color: "emerald" },
  { icon: <BookOpen className="h-3 w-3" />,     label: "Market Stories", color: "violet"  },
  { icon: <Sparkles className="h-3 w-3" />,     label: "AI Search",      color: "amber"   },
];

const COLOR_MAP: Record<string, string> = {
  sky:    "border-sky-500/25 bg-sky-500/10 text-sky-300",
  emerald:"border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  violet: "border-violet-500/25 bg-violet-500/10 text-violet-300",
  amber:  "border-amber-500/25 bg-amber-500/10 text-amber-300",
};

export function FirstVisitBanner({ onDismiss }: FirstVisitBannerProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 32, y: -8 }}
      animate={{ opacity: 1, x: 0,  y: 0  }}
      exit={{   opacity: 0, x: 32,  transition: { duration: 0.18 } }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="fixed top-20 right-4 z-50 w-[320px] overflow-hidden rounded-2xl border border-sky-500/20 bg-slate-900/95 shadow-2xl shadow-black/50 backdrop-blur-md"
    >
      {/* Ambient glow */}
      <div className="pointer-events-none absolute -top-6 -right-6 h-24 w-24 rounded-full bg-sky-600/15 blur-2xl" />

      {/* Dismiss */}
      <button
        onClick={onDismiss}
        aria-label="Dismiss welcome banner"
        className="absolute right-3 top-3 flex h-6 w-6 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] text-slate-500 transition hover:bg-white/10 hover:text-white"
      >
        <svg viewBox="0 0 14 14" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M2 2l10 10M12 2L2 12" />
        </svg>
      </button>

      <div className="relative p-4">
        {/* Logo + headline */}
        <div className="mb-3 flex items-center gap-3 pr-6">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-sky-400/20 bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-sky-400">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5">
              <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="text-[14px] font-bold text-white">Welcome to MarketRipple</h2>
              <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-1.5 py-px text-[9px] font-bold uppercase tracking-wider text-sky-400">New</span>
            </div>
            <p className="mt-0.5 text-[11px] leading-4 text-slate-400">
              AI-powered market intelligence for India
            </p>
          </div>
        </div>

        {/* Feature chips */}
        <div className="mb-4 flex flex-wrap gap-1.5">
          {FEATURES.map(f => (
            <span key={f.label} className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${COLOR_MAP[f.color]}`}>
              {f.icon}
              {f.label}
            </span>
          ))}
        </div>

        {/* CTAs */}
        <div className="flex items-center gap-2">
          <button
            onClick={onDismiss}
            className="flex-1 rounded-lg bg-gradient-to-r from-sky-500 to-blue-500 py-2 text-[12px] font-bold text-white shadow-md shadow-sky-500/20 transition hover:opacity-90"
          >
            Explore Dashboard →
          </button>
          <button
            onClick={onDismiss}
            className="text-[11px] text-slate-500 transition hover:text-slate-300"
          >
            Skip
          </button>
        </div>
      </div>
    </motion.div>
  );
}
