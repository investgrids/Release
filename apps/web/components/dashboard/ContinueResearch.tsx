"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { CalendarDays, Building2, Newspaper, BookOpen, Sparkles } from "lucide-react";
import type { RecentItem } from "@/types/history";

interface ContinueResearchProps {
  items: RecentItem[];
  searches: RecentItem[];
}

const TYPE_META: Record<string, { icon: ReactNode; label: string; color: string }> = {
  event:   { icon: <CalendarDays className="h-3 w-3" />, label: "Event",   color: "border-sky-500/25 bg-sky-500/8 text-sky-400"     },
  company: { icon: <Building2 className="h-3 w-3" />,    label: "Stock",   color: "border-emerald-500/25 bg-emerald-500/8 text-emerald-400" },
  news:    { icon: <Newspaper className="h-3 w-3" />,    label: "News",    color: "border-amber-500/25 bg-amber-500/8 text-amber-400" },
  story:   { icon: <BookOpen className="h-3 w-3" />,     label: "Story",   color: "border-violet-500/25 bg-violet-500/8 text-violet-400" },
  search:  { icon: <Sparkles className="h-3 w-3" />,     label: "Search",  color: "border-rose-500/25 bg-rose-500/8 text-rose-400"   },
};

function timeAgo(ts: number): string {
  const mins = Math.floor((Date.now() - ts) / 60_000);
  if (mins < 1)  return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function RecentCard({ item, index }: { item: RecentItem; index: number }) {
  const meta = TYPE_META[item.type] ?? TYPE_META.event;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
    >
      <Link
        href={item.href}
        className="group flex h-full flex-col justify-between rounded-2xl border border-white/8 bg-white/[0.025] p-3.5 transition hover:border-white/15 hover:bg-white/[0.04] hover:-translate-y-0.5"
      >
        <div className="flex items-start justify-between gap-2 mb-2">
          <span className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${meta.color}`}>
            {meta.icon}
            {meta.label}
          </span>
          <span className="text-[10px] text-slate-600 shrink-0">{timeAgo(item.timestamp)}</span>
        </div>
        <p className="text-[12px] font-medium leading-snug text-white line-clamp-2 group-hover:text-sky-200 transition mb-2">
          {item.title}
        </p>
        {item.subtitle && (
          <p className="text-[10px] text-slate-500 truncate">{item.subtitle}</p>
        )}
        <div className="mt-2 flex items-center gap-1 text-[11px] text-slate-500 group-hover:text-sky-400 transition">
          <span>Continue</span>
          <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M2 6h8M7 3l3 3-3 3" />
          </svg>
        </div>
      </Link>
    </motion.div>
  );
}

export function ContinueResearch({ items, searches }: ContinueResearchProps) {
  if (items.length === 0 && searches.length === 0) return null;

  const displayItems = items.slice(0, 4);
  // Deduplicate by id to handle stale localStorage entries with colliding keys
  const seenIds = new Set<string>();
  const displaySearches = searches.filter(s => {
    if (seenIds.has(s.id)) return false;
    seenIds.add(s.id);
    return true;
  }).slice(0, 4);

  return (
    <div className="rounded-[20px] border border-white/8 bg-white/[0.02] p-4">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-white/[0.06]">
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="8" cy="8" r="6.5" />
              <path d="M8 4.5V8l2.5 2" strokeLinecap="round" />
            </svg>
          </div>
          <span className="text-[12px] font-semibold text-white">Continue where you left off</span>
        </div>
      </div>

      {/* Recent items grid */}
      {displayItems.length > 0 && (
        <div className={`grid gap-2 mb-3 ${
          displayItems.length === 1 ? "grid-cols-1" :
          displayItems.length === 2 ? "grid-cols-2" :
          displayItems.length === 3 ? "grid-cols-3" :
          "grid-cols-4"
        }`}>
          {displayItems.map((item, i) => (
            <RecentCard key={item.id} item={item} index={i} />
          ))}
        </div>
      )}

      {/* Recent searches */}
      {displaySearches.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">Recent AI Searches</p>
          <div className="flex flex-wrap gap-1.5">
            {displaySearches.map(s => (
              <Link
                key={s.id}
                href={s.href}
                className="flex items-center gap-1.5 rounded-full border border-white/8 bg-white/[0.02] px-2.5 py-1 text-[11px] text-slate-400 transition hover:border-sky-500/30 hover:bg-sky-500/8 hover:text-sky-300"
              >
                <svg viewBox="0 0 12 12" className="h-3 w-3 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M10.5 10.5 7.5 7.5m0 0A4 4 0 1 0 3.5 3.5a4 4 0 0 0 4 4Z" strokeLinecap="round" />
                </svg>
                <span className="max-w-[160px] truncate">{s.title}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
