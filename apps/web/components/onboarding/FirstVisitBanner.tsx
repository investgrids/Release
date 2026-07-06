"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { CalendarDays, Building2, BookOpen, Sparkles } from "lucide-react";

interface FirstVisitBannerProps {
  onDismiss: () => void;
}

const FEATURES: { icon: ReactNode; label: string; color: string }[] = [
  { icon: <CalendarDays className="h-3.5 w-3.5" />, label: "Live Events",    color: "sky"    },
  { icon: <Building2 className="h-3.5 w-3.5" />,    label: "Company Impact", color: "emerald" },
  { icon: <BookOpen className="h-3.5 w-3.5" />,     label: "Market Stories", color: "violet" },
  { icon: <Sparkles className="h-3.5 w-3.5" />,     label: "AI Search",      color: "amber"  },
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
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0  }}
      exit={{   opacity: 0, y: -12, transition: { duration: 0.2 } }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="relative overflow-hidden rounded-[24px] border border-sky-500/15 bg-gradient-to-br from-sky-500/[0.07] via-transparent to-violet-500/[0.05] p-5"
    >
      {/* Ambient glows */}
      <div className="pointer-events-none absolute -top-8 left-16 h-32 w-32 rounded-full bg-sky-600/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-4 right-16 h-24 w-24 rounded-full bg-violet-600/8 blur-2xl" />

      {/* Dismiss */}
      <button
        onClick={onDismiss}
        aria-label="Dismiss welcome banner"
        className="absolute right-4 top-4 flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-500 transition hover:bg-white/10 hover:text-white"
      >
        <svg viewBox="0 0 14 14" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M2 2l10 10M12 2L2 12" />
        </svg>
      </button>

      <div className="relative flex flex-col gap-4 md:flex-row md:items-center md:gap-6">
        {/* Logo + headline */}
        <div className="flex items-start gap-4 flex-1 min-w-0">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-sky-400/20 bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-sky-400">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-[16px] font-bold text-white">Welcome to MarketRipple</h2>
              <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-sky-400">New</span>
            </div>
            <p className="text-[13px] leading-relaxed text-slate-400">
              Understand why markets move using AI-powered event intelligence. Track events, discover company impact, and uncover investment stories.
            </p>

            {/* Feature chips */}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {FEATURES.map(f => (
                <span key={f.label} className={`flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium ${COLOR_MAP[f.color]}`}>
                  {f.icon}
                  {f.label}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="flex shrink-0 items-center gap-2 md:flex-col md:items-end">
          <button
            onClick={onDismiss}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-blue-500 px-4 py-2 text-[12px] font-bold text-white shadow-md shadow-sky-500/20 hover:opacity-90 transition"
          >
            Explore Dashboard →
          </button>
          <button
            onClick={onDismiss}
            className="text-[12px] text-slate-500 hover:text-slate-300 transition"
          >
            Skip
          </button>
        </div>
      </div>
    </motion.div>
  );
}
