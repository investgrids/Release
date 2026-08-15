import type { WeekendSectorRef } from "@/types/weekendIntelligence";
import { sectorDirectionStyle } from "./weekendLabels";

/**
 * "Sectors to Watch" — brief §13. The backend already returns a capped,
 * ranked primary set (5) — used as-is, no client-side reranking. The
 * "why" is honestly just the evidence count: the API's top_sectors
 * entries carry no free-text reason field (SectorSignal.key_reasons
 * exists backend-side but isn't serialized into top_sector_refs — see
 * final report), so a richer explanation is not fabricated here.
 */
export function WeekendSectors({ sectors }: { sectors: WeekendSectorRef[] }) {
  if (sectors.length === 0) return null;

  return (
    <section className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <h2 className="mb-3 text-[13px] font-black text-text-primary">Sectors to Watch</h2>
      <ul className="divide-y divide-surface-border/10">
        {sectors.map((s) => {
          const style = sectorDirectionStyle(s.direction);
          return (
            <li key={s.sector} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
              <div className="min-w-0">
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
