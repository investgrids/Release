"use client";

import { MARKETS, type MarketId } from "@/lib/marketRegistry";

// Segmented market selector (Global Markets Phase C — 2026-10-25). Presentational
// only: it renders the markets from the registry and reports the selected id. It
// holds NO market-specific data logic — the registry decides what each market is.

export function MarketSelector({
  selected,
  onSelect,
}: {
  selected: MarketId;
  onSelect: (id: MarketId) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Select market"
      className="flex flex-wrap gap-2 rounded-2xl border border-surface-border/7 bg-surface-card p-1.5"
    >
      {MARKETS.map((m) => {
        const active = m.id === selected;
        return (
          <button
            key={m.id}
            role="tab"
            aria-selected={active}
            onClick={() => onSelect(m.id)}
            className={[
              "flex items-center gap-2 rounded-xl px-3.5 py-2 text-[13px] font-semibold transition",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-500/50",
              active
                ? "bg-text-primary/[0.06] text-text-primary"
                : "text-text-muted hover:text-text-secondary",
            ].join(" ")}
          >
            <span className="text-[16px] leading-none">{m.flag}</span>
            <span>{m.label}</span>
          </button>
        );
      })}
    </div>
  );
}
