"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";

interface FloatingAISearchProps {
  className?: string;
}

export function FloatingAISearch({ className = "" }: FloatingAISearchProps) {
  const [query, setQuery] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    router.push(`/ai-search?q=${encodeURIComponent(q)}`);
    setQuery("");
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={`fixed left-1/2 z-50 w-[min(92vw,680px)] -translate-x-1/2 ${className}`}
    >
      <form onSubmit={handleSubmit}>
        <div className="flex items-center gap-3 rounded-full border border-white/10 bg-slate-950/95 px-2 py-2 shadow-[0_8px_60px_rgba(56,189,248,0.2)] backdrop-blur-xl">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-sky-400 text-white shadow-lg">
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
              <path d="M12 2L13.8 8.2H20L14.9 12L16.7 18.2L12 15L7.3 18.2L9.1 12L4 8.2H10.2Z"/>
            </svg>
          </div>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Ask MarketRipple AI — RBI rate impact, sector outlook…"
            className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
          />
          <button
            type="submit"
            disabled={!query.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 to-violet-500 text-white shadow-lg transition hover:opacity-90 disabled:opacity-40"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
              <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>
      </form>
    </motion.div>
  );
}
