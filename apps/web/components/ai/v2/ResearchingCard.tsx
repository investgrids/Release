"use client";

// The card shown while a question is being answered. Everything on it is true: the question, a real elapsed timer, and (only when the stream supplies them) the real stages. There is no percentage and no
// invented step list, so a transport without stage events shows just the question and the timer. Motion is a small ring and a pulsing dot, both off for reduced-motion users.
import { useEffect, useState } from "react";
import { Check } from "lucide-react";

export interface ResearchStage { stage: string; label: string; elapsedMs: number }

const fmt = (ms: number) => `${(ms / 1000).toFixed(1)}s`;
/** Past this the card says so plainly; the request itself stops at its own deadline (about 24 s). */
const SLOW_AFTER_MS = 15000;

export function ResearchingCard({ query, stages = [] }: { query: string; stages?: ResearchStage[] }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t0 = Date.now();
    const id = setInterval(() => setElapsed(Date.now() - t0), 200);
    return () => clearInterval(id);
  }, []);

  // Each stage event means "the previous stage just finished and this one has started", so the last entry is in progress and only the earlier ones are done.
  const done = stages.slice(0, -1);
  const current = stages.length ? stages[stages.length - 1] : null;

  return (
    <div className="rounded-2xl border border-surface-border/10 bg-surface-card p-5 sm:p-6" role="status" aria-live="polite" data-testid="ai-search-working">
      <div className="flex items-center gap-3">
        <span aria-hidden className="h-4 w-4 shrink-0 rounded-full border-2 border-violet-500/25 border-t-violet-600 motion-safe:animate-spin" />
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-muted">Researching</p>
        <span className="ml-auto text-[12px] tabular-nums text-text-muted" data-testid="working-elapsed">{fmt(elapsed)}</span>
      </div>
      <p className="mt-3 break-words text-[17px] font-semibold leading-snug text-text-primary sm:text-[19px]" data-testid="working-query">{query}</p>

      {stages.length > 0 ? (
        <ol className="mt-5 space-y-2.5 border-t border-surface-border/10 pt-4" data-testid="working-stages">
          {done.map((s, i) => (
            <li key={`${s.stage}-${i}`} className="flex items-center gap-2.5 text-[13px]">
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600"><Check className="h-2.5 w-2.5" strokeWidth={3} /></span>
              <span className="text-text-secondary">{s.label}</span>
              <span className="ml-auto shrink-0 text-[11px] tabular-nums text-text-muted">{fmt(s.elapsedMs)}</span>
            </li>
          ))}
          {current && (
            <li className="flex items-center gap-2.5 text-[13px]" aria-current="step">
              <span aria-hidden className="ml-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-600 motion-safe:animate-pulse" />
              <span className="font-medium text-text-primary">{current.label}</span>
            </li>
          )}
        </ol>
      ) : (
        <p className="mt-4 text-[13px] leading-5 text-text-muted">Gathering evidence from live news, filings and market data, then checking it before answering.</p>
      )}

      {elapsed >= SLOW_AFTER_MS && (
        <p className="mt-4 text-[12.5px] leading-5 text-text-muted" data-testid="working-slow">This is taking longer than usual. If it can&apos;t finish in time, you&apos;ll get a clear message and can try again.</p>
      )}
    </div>
  );
}
