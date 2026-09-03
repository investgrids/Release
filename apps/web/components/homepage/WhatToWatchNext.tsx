import type { WatchItem } from "@/lib/whatToWatchNext";

// Homepage Hero — "What To Watch Next" (2026-09-03). Pure presentational
// component: all derivation happens in lib/whatToWatchNext.ts before this
// renders, so this file has no fetch/logic of its own to keep it trivially
// testable and to keep provenance decisions in one place.
//
// Deliberately no directional color (emerald/rose) on these items — the
// monitoring condition itself is neutral by design (see the task's own
// "MONITOR" being visually neutral, not a Buy/Sell-style signal). Same
// visual language as the sibling "Since Previous Session" / Opportunity-
// Risk strip cards directly above this in the hero's left column: same
// border/radius/background tokens, same type scale, no new gradients.
export function WhatToWatchNext({ items }: { items: WatchItem[] }) {
  if (items.length === 0) return null;

  return (
    <div className="rounded-[16px] border border-surface-border/6 bg-text-primary/[0.02] p-4">
      <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">What To Watch Next</p>
      <div className="divide-y divide-surface-border/6">
        {items.map((item, i) => (
          <div key={`${item.kind}-${item.entity}-${i}`} className="py-2 first:pt-0 last:pb-0">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[12px] font-bold text-text-primary">{item.entity}</span>
              {item.kind === "trigger" ? (
                <span className="text-[10px] font-semibold text-text-muted">{item.detail}</span>
              ) : (
                <span className="text-[9px] font-bold uppercase tracking-wide text-text-muted">Monitor</span>
              )}
            </div>
            {item.kind === "condition" ? (
              <p className="mt-0.5 text-[10.5px] leading-4 text-text-secondary">{item.detail}</p>
            ) : item.meta ? (
              <p className="mt-0.5 text-[10.5px] leading-4 text-text-secondary">{item.meta}</p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
