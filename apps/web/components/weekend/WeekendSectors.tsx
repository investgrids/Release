"use client";

import { useState } from "react";
import { Building2 } from "lucide-react";
import type { WeekendSectorRef } from "@/types/weekendIntelligence";
import { sectorDirectionStyle } from "./weekendLabels";

const VISIBLE_LIMIT = 5;

/**
 * "Sectors to Watch" — brief §13. The backend already returns a capped,
 * ranked primary set (5 today) — used as-is, no client-side reranking.
 * "View All" only renders when there's real bounded content beyond the
 * first 5 (defensive: today's backend cap already matches 5, so this is
 * future-proofing against that cap changing, not a control that's dead
 * today). The "why" is honestly just the evidence count: the API's
 * top_sectors entries carry no free-text reason field (SectorSignal.
 * key_reasons exists backend-side but isn't serialized into
 * top_sector_refs — see final report), so a richer explanation is not
 * fabricated here.
 */
export function WeekendSectors({ sectors }: { sectors: WeekendSectorRef[] }) {
  const [expanded, setExpanded] = useState(false);
  if (sectors.length === 0) return null;

  const visible = expanded ? sectors : sectors.slice(0, VISIBLE_LIMIT);
  const hasMore = sectors.length > VISIBLE_LIMIT;

  return (
    <section className="flex min-h-[360px] max-h-[400px] flex-col overflow-hidden rounded-2xl border border-surface-border/7 bg-surface-card p-5 shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-[13px] font-black text-text-primary">Sectors to Watch</h2>
        {hasMore && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="rounded text-[11px] font-semibold text-violet-500 transition duration-200 hover:text-violet-400 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
          >
            {expanded ? "Show fewer" : "View All →"}
          </button>
        )}
      </div>
      <ul className="flex-1 divide-y divide-surface-border/10 overflow-y-auto">
        {visible.map((s) => {
          const style = sectorDirectionStyle(s.direction);
          return (
            <li key={s.sector} className="flex min-h-[58px] items-center gap-3 py-2.5 first:pt-0 last:pb-0">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-border/10 text-text-muted">
                <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-bold text-text-primary">{s.sector}</p>
                <p className="mt-0.5 text-[10px] text-text-muted">
                  {s.evidence_count} development{s.evidence_count === 1 ? "" : "s"}
                </p>
              </div>
              <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-black ${style.chipClass}`}>
                <span aria-hidden="true">{style.symbol} </span>{style.label}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
