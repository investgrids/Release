"use client";

import { HelpCircle } from "lucide-react";

/**
 * Shown instead of a normal result when the backend returns
 * needs_clarification (see session_context.check_ambiguous_group) — a
 * bare conglomerate name ("Tata", "Adani", ...) that genuinely maps to
 * several real companies. Never guesses; asks.
 */
export function ClarificationPicker({
  ambiguousTerm,
  candidates,
  onPick,
}: {
  ambiguousTerm: string;
  candidates: { symbol: string; name: string }[];
  onPick: (symbol: string, name: string) => void;
}) {
  return (
    <div className="rounded-[20px] border border-amber-500/25 bg-amber-500/[0.05] p-6">
      <div className="mb-4 flex items-center gap-2">
        <HelpCircle className="h-4 w-4 text-amber-400" />
        <p className="text-[14px] font-semibold text-white">Which {ambiguousTerm} company did you mean?</p>
      </div>
      <p className="mb-4 text-[12px] text-slate-400">
        &quot;{ambiguousTerm}&quot; matches several listed companies — pick one to continue.
      </p>
      <div className="flex flex-wrap gap-2">
        {candidates.map(c => (
          <button
            key={c.symbol}
            onClick={() => onPick(c.symbol, c.name)}
            className="rounded-[12px] border border-white/10 bg-white/[0.03] px-4 py-2.5 text-left transition hover:border-violet-500/40 hover:bg-violet-500/10"
          >
            <p className="text-[12.5px] font-medium text-white">{c.name}</p>
            <p className="text-[10.5px] text-slate-500">{c.symbol}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
