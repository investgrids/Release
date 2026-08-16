import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import type { WeekendIntelligenceSnapshotDTO } from "@/types/weekendIntelligence";
import { summaryTemplate } from "./weekendLabels";

/**
 * "Weekend Intelligence Summary" — brief §15. summaryTemplate builds this
 * from real structured fields only (overall_bias, top two sectors by
 * evidence, production_confidence, baseline_available/status) — no LLM
 * call, no free-text backend field is read (there isn't one). "How We
 * Generate This" links to the real, existing /how-marketripple-thinks
 * methodology page (confirmed present in the app) rather than a dead
 * control — the brief's own instruction was to omit ONLY if no real
 * destination exists.
 */
export function WeekendSummary({ snapshot }: { snapshot: WeekendIntelligenceSnapshotDTO }) {
  const text = summaryTemplate(snapshot);
  if (!text) return null;

  return (
    <section className="flex min-h-[230px] max-h-[250px] flex-col overflow-hidden rounded-2xl border border-surface-border/7 bg-surface-card p-5 shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]">
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-violet-500" aria-hidden="true" />
        <h2 className="text-[13px] font-black text-text-primary">Weekend Intelligence Summary</h2>
      </div>
      <p className="flex-1 text-[12px] leading-relaxed text-text-secondary">{text}</p>
      <Link
        href="/how-marketripple-thinks"
        className="group/link mt-3 flex w-fit items-center gap-1 self-end rounded text-[11px] font-semibold text-violet-500 transition duration-200 hover:text-violet-400 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
      >
        How We Generate This
        <ArrowRight className="h-3 w-3 transition-transform duration-200 group-hover/link:translate-x-0.5" aria-hidden="true" />
      </Link>
    </section>
  );
}
