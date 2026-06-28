"use client";

import { motion } from "framer-motion";

interface FloatingAISearchProps {
  className?: string;
}

export function FloatingAISearch({ className = "" }: FloatingAISearchProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={`fixed left-1/2 z-50 w-[min(92vw,680px)] -translate-x-1/2 ${className}`}
    >
      <div className="flex items-center gap-3 rounded-full border border-white/10 bg-slate-950/95 px-2 py-2 shadow-[0_8px_60px_rgba(56,189,248,0.2)] backdrop-blur-xl">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-sky-400 text-white text-base shadow-lg">
          ✦
        </div>
        <input
          type="text"
          placeholder="Ask EventIQ AI..."
          className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
        />
        <button className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 to-violet-500 text-white shadow-lg transition hover:opacity-90">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z" />
          </svg>
        </button>
      </div>
    </motion.div>
  );
}
