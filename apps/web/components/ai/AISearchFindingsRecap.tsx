"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { ConfidenceBadge } from "./ConfidenceBadge";

interface RecapCompany { symbol: string; name: string; impact_type: string; confidence: number | null; }
interface RecapSector { name: string; positive: boolean; }
interface RecapHistoricalMatch { event_title: string; similarity: number; }

interface Props {
  sourcesCount: number;
  companies: RecapCompany[];
  sectors: RecapSector[];
  topHistoricalMatch: RecapHistoricalMatch | null;
  className?: string;
}

/**
 * A short, animated recap built strictly from fields already on the AI
 * search result — nothing fetched separately, nothing invented. Plays
 * alongside AISearchGraphReveal the instant a real response arrives.
 */
export function AISearchFindingsRecap({ sourcesCount, companies, sectors, topHistoricalMatch, className = "" }: Props) {
  const rows: { key: string; node: ReactNode }[] = [];

  if (sourcesCount > 0) {
    rows.push({
      key: "sources",
      node: <p className="text-[12.5px] text-text-secondary">✓ {sourcesCount} source{sourcesCount === 1 ? "" : "s"} reviewed</p>,
    });
  }

  if (companies.length > 0) {
    rows.push({
      key: "companies",
      node: (
        <div>
          <p className="text-[12.5px] text-text-secondary">✓ {companies.length} compan{companies.length === 1 ? "y" : "ies"} identified</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {companies.slice(0, 3).map(c => (
              <span key={c.symbol}
                className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                  c.impact_type === "beneficiary" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
                  : c.impact_type === "at_risk"    ? "border-rose-500/25 bg-rose-500/10 text-rose-600 dark:text-rose-300"
                  : "border-surface-border/10 bg-text-primary/5 text-text-secondary"
                }`}>
                {c.symbol}
              </span>
            ))}
          </div>
        </div>
      ),
    });
  }

  if (sectors.length > 0) {
    rows.push({
      key: "sectors",
      node: (
        <div>
          <p className="text-[12.5px] text-text-secondary">✓ {sectors.length} sector{sectors.length === 1 ? "" : "s"} affected</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {sectors.slice(0, 5).map(s => (
              <span key={s.name}
                className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                  s.positive ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300" : "border-rose-500/25 bg-rose-500/10 text-rose-600 dark:text-rose-300"
                }`}>
                {s.name}
              </span>
            ))}
          </div>
        </div>
      ),
    });
  }

  if (topHistoricalMatch) {
    rows.push({
      key: "historical",
      node: (
        <div className="flex items-center gap-2">
          <p className="text-[12.5px] text-text-secondary">✓ Historical match: {topHistoricalMatch.event_title}</p>
          <ConfidenceBadge score={Math.round(topHistoricalMatch.similarity)} showLabel={false} size="sm" />
        </div>
      ),
    });
  }

  if (rows.length === 0) return null;

  return (
    <div className={`rounded-xl border border-[#1e293b] bg-surface-card p-4 ${className}`}>
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-muted">What we found</p>
      <div className="space-y-2.5">
        {rows.map((row, i) => (
          <motion.div key={row.key}
            initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.12 }}>
            {row.node}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
