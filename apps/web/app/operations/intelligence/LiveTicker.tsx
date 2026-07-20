"use client";

import { useEffect, useState } from "react";
import { Radio } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

interface FeedItem {
  id: string;
  headline: string;
  priority_tier: string;
  direction: string;
  triaged_at: string;
}

const TIER_COLOR: Record<string, string> = {
  Critical: "text-rose-400",
  High:     "text-amber-400",
  Medium:   "text-sky-400",
  Low:      "text-slate-400",
};

function timeAgo(iso: string): string {
  const diffMin = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  return `${Math.floor(diffMin / 60)}h ago`;
}

export function LiveTicker({ initial }: { initial: FeedItem[] }) {
  const [items, setItems] = useState<FeedItem[]>(initial);

  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/intelligence/market/feed?limit=10`);
        if (r.ok) {
          const d = await r.json();
          if (Array.isArray(d.feed) && d.feed.length) setItems(d.feed);
        }
      } catch {}
    }, 45_000);
    return () => clearInterval(id);
  }, []);

  if (items.length === 0) return null;

  // Duplicate the list so the CSS marquee can loop seamlessly.
  const loop = [...items, ...items];

  return (
    <div className="relative border-y border-white/[0.06] bg-white/[0.02] py-3 overflow-hidden">
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-[#040711] to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-[#040711] to-transparent" />
      <div className="flex items-center gap-2 px-6 mb-2.5">
        <span className="flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-rose-400">
          <Radio className="h-3 w-3 animate-pulse" /> Live
        </span>
        <span className="text-[11px] text-slate-500">Market Intelligence Feed</span>
      </div>
      <div className="flex w-max animate-[marquee_50s_linear_infinite] gap-8 px-6 hover:[animation-play-state:paused]">
        {loop.map((item, i) => (
          <div key={`${item.id}-${i}`} className="flex shrink-0 items-center gap-2.5 whitespace-nowrap text-[13px]">
            <span className={`font-bold uppercase text-[10px] tracking-wide ${TIER_COLOR[item.priority_tier] ?? "text-slate-400"}`}>
              {item.priority_tier}
            </span>
            <span className="text-slate-300">{item.headline}</span>
            <span className="text-slate-600 text-[11px]">{timeAgo(item.triaged_at)}</span>
            <span className="text-slate-700">•</span>
          </div>
        ))}
      </div>
      <style>{`
        @keyframes marquee {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        @media (prefers-reduced-motion: reduce) {
          .animate-\\[marquee_50s_linear_infinite\\] { animation: none; }
        }
      `}</style>
    </div>
  );
}
