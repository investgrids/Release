"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Check } from "lucide-react";
import type { StageEvent } from "@/lib/hooks/useAISearchStream";

/**
 * Replaces the old fake-cycling-phrase loading state for AI Search V3 (see
 * useAISearchStream). Every stage shown here already happened — it's a
 * completed real backend checkpoint (see pipeline.py's STAGE_LABELS), and
 * every elapsed-time figure is a real Date.now() delta measured the instant
 * that stage's SSE event arrived. Nothing here is a fabricated estimate:
 * the current stage still in progress has no elapsed time next to it until
 * it actually completes.
 */
export function SearchProgressStages({
  query,
  stageHistory,
  elapsedMs,
  loading,
}: {
  query: string;
  stageHistory: StageEvent[];
  elapsedMs: number;
  loading: boolean;
}) {
  const fmtSec = (ms: number) => `${(ms / 1000).toFixed(1)}s`;

  // Each "stage" SSE event means "the PREVIOUS stage just finished, this one
  // is starting now" (see pipeline.py's _run_v3_steps — it yields a stage
  // label before doing that stage's work, not after). So the last entry in
  // stageHistory is always the one currently in progress, not a completed
  // one — rendering it with a checkmark+timestamp would be a fabricated
  // "done" claim about work that hasn't finished. Split accordingly.
  const completed = loading ? stageHistory.slice(0, -1) : stageHistory;
  const inProgress = loading ? stageHistory[stageHistory.length - 1] : null;

  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-6">
      <div className="flex items-start gap-4 mb-6">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-500/20 text-violet-400">
          <Sparkles className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <p className="text-[11px] uppercase tracking-widest text-violet-400 mb-1">AI Answer</p>
          <p className="text-sm text-text-secondary">
            Researching: <span className="text-text-primary font-medium">{query}</span>
          </p>
        </div>
        <span className="text-[10px] text-text-muted tabular-nums shrink-0 mt-1">{fmtSec(elapsedMs)} elapsed</span>
      </div>

      <ol className="space-y-2.5">
        <AnimatePresence initial={false}>
          {completed.map((s, i) => (
            <motion.li
              key={`${s.stage}-${i}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="flex items-center gap-2.5 text-[13px]"
            >
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
                <Check className="h-2.5 w-2.5" strokeWidth={3} />
              </span>
              <span className="text-text-secondary">{s.label}</span>
              <span className="ml-auto shrink-0 text-[11px] tabular-nums text-text-muted">{fmtSec(s.elapsedMs)}</span>
            </motion.li>
          ))}
        </AnimatePresence>

        {inProgress && (
          <motion.li
            key={`${inProgress.stage}-current`}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex items-center gap-2.5 text-[13px]"
          >
            <span className="h-1.5 w-1.5 shrink-0 ml-1 rounded-full bg-violet-400 animate-pulse" />
            <span className="text-text-primary font-medium">{inProgress.label}</span>
          </motion.li>
        )}
      </ol>
    </div>
  );
}
