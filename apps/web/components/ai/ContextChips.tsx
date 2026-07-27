"use client";

import { X } from "lucide-react";
import type { SessionEntity } from "@/lib/hooks/useResearchSession";

/**
 * "Current Context" strip above the search bar — every chip is something
 * the session actually accumulated from real answers (or a preference the
 * user explicitly set), and every chip is removable. Renders nothing when
 * the session is empty, rather than an empty placeholder bar.
 */
export function ContextChips({
  companies, sectors, timeHorizon, riskTolerance,
  onRemoveCompany, onRemoveSector, onClearHorizon, onClearRisk,
}: {
  companies: SessionEntity[];
  sectors: string[];
  timeHorizon: string | null;
  riskTolerance: string | null;
  onRemoveCompany: (symbol: string) => void;
  onRemoveSector: (sector: string) => void;
  onClearHorizon: () => void;
  onClearRisk: () => void;
}) {
  const hasAny = companies.length > 0 || sectors.length > 0 || timeHorizon || riskTolerance;
  if (!hasAny) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wide text-slate-600 mr-0.5">Current Context</span>
      {companies.map(c => (
        <span key={c.symbol} className="flex items-center gap-1 rounded-full border border-violet-500/25 bg-violet-500/10 px-2 py-1 text-[11px] font-medium text-violet-300">
          {c.symbol}
          <button onClick={() => onRemoveCompany(c.symbol)} className="text-violet-400/60 hover:text-violet-200 transition" aria-label={`Remove ${c.symbol} from context`}>
            <X className="h-2.5 w-2.5" />
          </button>
        </span>
      ))}
      {sectors.map(s => (
        <span key={s} className="flex items-center gap-1 rounded-full border border-sky-500/25 bg-sky-500/10 px-2 py-1 text-[11px] font-medium text-sky-300">
          {s}
          <button onClick={() => onRemoveSector(s)} className="text-sky-400/60 hover:text-sky-200 transition" aria-label={`Remove ${s} from context`}>
            <X className="h-2.5 w-2.5" />
          </button>
        </span>
      ))}
      {timeHorizon && (
        <span className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] font-medium text-slate-300">
          {timeHorizon}
          <button onClick={onClearHorizon} className="text-slate-500 hover:text-slate-200 transition" aria-label="Clear time horizon"><X className="h-2.5 w-2.5" /></button>
        </span>
      )}
      {riskTolerance && (
        <span className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] font-medium text-slate-300">
          {riskTolerance} Risk
          <button onClick={onClearRisk} className="text-slate-500 hover:text-slate-200 transition" aria-label="Clear risk tolerance"><X className="h-2.5 w-2.5" /></button>
        </span>
      )}
    </div>
  );
}
