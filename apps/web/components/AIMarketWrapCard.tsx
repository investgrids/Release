"use client";

import { motion } from "framer-motion";

interface AIMarketWrapCardProps {
  title: string;
  description: string;
}

export function AIMarketWrapCard({ title, description }: AIMarketWrapCardProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.05 }}
      className="relative overflow-hidden rounded-[28px] border border-white/10 bg-[#070d1a] p-5 shadow-glow min-h-[220px] h-full"
    >
      {/* Background radial glow */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-10 top-0 h-56 w-56 rounded-full bg-sky-600/10 blur-3xl" />
        <div className="absolute -bottom-10 left-1/3 h-40 w-40 rounded-full bg-violet-600/10 blur-3xl" />
      </div>

      <div className="relative flex h-full gap-4">
        {/* Left content */}
        <div className="flex flex-col gap-4 flex-1 min-w-0">
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1.5 text-xs font-medium text-sky-300">
            <span>✨</span> AI Market Wrap
          </div>
          <div className="space-y-3 flex-1">
            <h2 className="text-xl font-semibold leading-snug text-white line-clamp-3">{title}</h2>
            <p className="text-sm leading-6 text-slate-400 line-clamp-3">{description}</p>
          </div>
          <button className="inline-flex w-fit items-center gap-2 rounded-[16px] border border-white/10 bg-white/5 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-white/10">
            Read Full Wrap <span>→</span>
          </button>
        </div>

        {/* Globe — only at 2xl (1536px+) where there is enough room */}
        <div className="hidden 2xl:flex items-center justify-center shrink-0">
          <div className="relative h-[120px] w-[120px]">
            {/* Atmospheric halo */}
            <div className="absolute inset-[-8px] rounded-full"
              style={{ background: "radial-gradient(circle, transparent 60%, rgba(56,189,248,0.12) 100%)" }} />
            {/* Globe sphere */}
            <div className="relative h-full w-full rounded-full overflow-hidden"
              style={{
                background: "radial-gradient(circle at 38% 36%, #1a4a8a 0%, #0d2147 55%, #060e20 100%)",
                boxShadow: "0 0 50px rgba(56,189,248,0.18), inset -24px -20px 50px rgba(0,0,30,0.7)"
              }}>
              {/* Continent masses */}
              <div className="absolute rounded-full"
                style={{ top: "18%", left: "8%", width: "55%", height: "40%",
                  background: "radial-gradient(ellipse, rgba(34,120,70,0.45) 0%, transparent 70%)",
                  transform: "rotate(-15deg)" }} />
              <div className="absolute rounded-full"
                style={{ top: "52%", left: "42%", width: "38%", height: "26%",
                  background: "radial-gradient(ellipse, rgba(34,100,60,0.35) 0%, transparent 70%)" }} />
              <div className="absolute rounded-full"
                style={{ top: "30%", left: "62%", width: "28%", height: "32%",
                  background: "radial-gradient(ellipse, rgba(28,90,55,0.30) 0%, transparent 70%)",
                  transform: "rotate(10deg)" }} />
              {/* Cloud wisps */}
              <div className="absolute rounded-full"
                style={{ top: "12%", left: "30%", width: "45%", height: "16%",
                  background: "radial-gradient(ellipse, rgba(200,220,255,0.12) 0%, transparent 70%)" }} />
              {/* Limb glow */}
              <div className="absolute inset-0 rounded-full"
                style={{ background: "radial-gradient(circle at 72% 68%, transparent 48%, rgba(56,189,248,0.18) 100%)" }} />
            </div>
            {/* Soft ring */}
            <div className="absolute inset-[-2px] rounded-full ring-1 ring-sky-400/15" />
          </div>
        </div>
      </div>
    </motion.section>
  );
}
