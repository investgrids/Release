"use client";

import { useEffect, useState } from "react";
import { History, Trash2 } from "lucide-react";

export const AI_SEARCH_HISTORY_KEY = "recent_ai_searches";
export const AI_SEARCH_HISTORY_EVENT = "ai-search-history-updated";

interface HistoryEntry {
  id: string;
  title: string;
  href: string;
  timestamp: number;
}

function readHistory(): HistoryEntry[] {
  try {
    const raw = JSON.parse(localStorage.getItem(AI_SEARCH_HISTORY_KEY) ?? "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function groupLabel(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const startOfDay = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOfDay(now) - startOfDay(d)) / 86_400_000);
  if (diffDays === 0) return "Today's Research";
  if (diffDays === 1) return "Yesterday";
  if (diffDays <= 7) return "This Week";
  return "Earlier";
}

/**
 * Real history — every entry here is a search the user actually ran (written
 * by page.tsx's runSearch right after a real request), never a suggested or
 * synthetic example. Reopening replays the same query text through the
 * normal search flow, which naturally resolves from the backend's own
 * cache (30-min TTL, both V2 and V3) when the entry is recent enough — no
 * separate client-side cache to keep in sync.
 */
export function AISearchHistory({ onReopen, activeQuery }: { onReopen: (query: string) => void; activeQuery?: string }) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    setEntries(readHistory());
    const refresh = () => setEntries(readHistory());
    window.addEventListener(AI_SEARCH_HISTORY_EVENT, refresh);
    window.addEventListener("storage", refresh); // syncs across tabs too
    return () => {
      window.removeEventListener(AI_SEARCH_HISTORY_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  function clearAll() {
    localStorage.setItem(AI_SEARCH_HISTORY_KEY, "[]");
    setEntries([]);
  }

  if (entries.length === 0) return null;

  const groups = new Map<string, HistoryEntry[]>();
  for (const e of entries) {
    const key = groupLabel(e.timestamp);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(e);
  }

  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <History size={14} strokeWidth={1.8} className="text-violet-400" />
          <p className="text-[12px] font-semibold text-slate-300">Research History</p>
        </div>
        <button onClick={clearAll} title="Clear history"
          className="text-slate-600 hover:text-rose-400 transition">
          <Trash2 size={13} strokeWidth={1.8} />
        </button>
      </div>

      <div className="space-y-3 max-h-[280px] overflow-y-auto" style={{ scrollbarWidth: "none" }}>
        {[...groups.entries()].map(([label, items]) => (
          <div key={label}>
            <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1.5">{label}</p>
            <div className="space-y-0.5">
              {items.map(e => {
                const isActive = activeQuery && e.title === activeQuery;
                return (
                  <button
                    key={e.id}
                    onClick={() => onReopen(e.title)}
                    className={`flex w-full items-start gap-2 rounded-[10px] px-2 py-1.5 text-left transition hover:bg-white/[0.05] ${isActive ? "bg-violet-500/10" : ""}`}
                  >
                    <span className={`mt-[3px] h-1.5 w-1.5 shrink-0 rounded-full ${isActive ? "bg-violet-400" : "bg-emerald-500/70"}`} />
                    <span className={`text-[11px] leading-4 line-clamp-2 ${isActive ? "text-violet-300 font-medium" : "text-slate-400"}`}>
                      {e.title}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
