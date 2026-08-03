"use client";

// Shared hero for hub pages — title, one-line pitch, a row of real (caller-
// supplied, never fabricated) live stats, an optional hub-scoped search
// box, and optional quick-action links. Each hub page fetches its own real
// numbers and passes them in as `stats`; this component never invents data.

import Link from "next/link";
import { Search } from "lucide-react";
import { useState } from "react";
import { trackHubSearch } from "@/lib/navAnalytics";

export interface HubStat {
  label: string;
  value: string;
}

export interface HubQuickAction {
  label: string;
  href: string;
}

export function HubHero({
  hub, eyebrow, title, pitch, stats, searchPlaceholder, onSearch, quickActions,
}: {
  hub: string;
  eyebrow: string;
  title: string;
  pitch: string;
  stats?: HubStat[];
  searchPlaceholder?: string;
  onSearch?: (query: string) => void;
  quickActions?: HubQuickAction[];
}) {
  const [query, setQuery] = useState("");

  return (
    <div className="mb-6 rounded-2xl border border-surface-border/8 bg-gradient-to-br from-violet-500/[0.06] to-surface-card p-6 md:p-8">
      <p className="mb-2 text-[10.5px] font-black uppercase tracking-[0.18em] text-accent-violet">{eyebrow}</p>
      <h1 className="text-[26px] md:text-[30px] font-black leading-tight text-text-primary">{title}</h1>
      <p className="mt-1.5 max-w-2xl text-[14px] text-text-secondary">{pitch}</p>

      {stats && stats.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
          {stats.map(s => (
            <div key={s.label}>
              <p className="text-[20px] font-black text-text-primary tabular-nums">{s.value}</p>
              <p className="text-[10.5px] uppercase tracking-wide text-text-muted">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {onSearch && (
        <form
          className="relative mt-5 max-w-md"
          onSubmit={e => { e.preventDefault(); trackHubSearch(hub, query); onSearch(query); }}
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
          <input
            value={query}
            onChange={e => { setQuery(e.target.value); onSearch(e.target.value); }}
            placeholder={searchPlaceholder ?? "Search…"}
            className="w-full rounded-xl border border-surface-border/10 bg-surface-card py-2 pl-9 pr-3 text-[13px] text-text-primary outline-none transition placeholder:text-text-muted focus:border-violet-500/40"
          />
        </form>
      )}

      {quickActions && quickActions.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {quickActions.map(a => (
            <Link
              key={a.href}
              href={a.href as any}
              className="rounded-full border border-surface-border/10 bg-surface-card px-3.5 py-1.5 text-[12px] font-semibold text-text-secondary transition hover:border-violet-500/30 hover:text-text-primary"
            >
              {a.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
