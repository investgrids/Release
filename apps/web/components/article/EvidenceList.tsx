import { Shield, ChevronRight, FileCheck, Brain } from "lucide-react";

// Article-level Evidence — built entirely from the article's OWN existing
// real fields (never a new engine, never a Fact Registry extension per the
// AI Newsroom redesign's Decision 3, 2026-08-10). Splits into two honest
// groups rather than one undifferentiated list: FACT (things that happened
// — sources, historical outcomes, the raw what_happened account) vs AI
// INTERPRETATION (the model's own read of why a company/sector is
// affected, what it means, what to watch) — so a reader can tell which is
// which at a glance instead of treating every line with equal certainty.
// Replaces the old 4-counter-only "Evidence Panel" (kept those counters
// here too — nothing removed, just no longer the whole story).

export interface EvidenceFact {
  label: string;
  detail?: string | null;
}

export interface EvidenceListProps {
  sources: string[];
  facts: EvidenceFact[];
  interpretations: EvidenceFact[];
  confidenceScore?: number | null;
  historicalCount: number;
  storyVersion?: number | null;
}

export function EvidenceList({ sources, facts, interpretations, confidenceScore, historicalCount, storyVersion }: EvidenceListProps) {
  return (
    <details className="group rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] p-5 open:bg-text-primary/[0.03]">
      <summary className="flex cursor-pointer list-none items-center justify-between marker:content-none">
        <span className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-text-muted">
          <Shield className="h-3.5 w-3.5" /> Evidence
        </span>
        <ChevronRight className="h-4 w-4 text-text-muted transition group-open:rotate-90" />
      </summary>

      <div className="mt-4 grid grid-cols-2 gap-4 border-b border-surface-border/6 pb-4 sm:grid-cols-4">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider text-text-muted">AI Confidence</p>
          <p className="mt-1 text-[16px] font-bold tabular-nums text-text-primary">{confidenceScore != null ? `${Math.round(confidenceScore * 100)}%` : "—"}</p>
        </div>
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider text-text-muted">Sources</p>
          <p className="mt-1 text-[16px] font-bold tabular-nums text-text-primary">{sources.length || "—"}</p>
        </div>
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider text-text-muted">Historical Data</p>
          <p className="mt-1 text-[16px] font-bold tabular-nums text-text-primary">{historicalCount} events</p>
        </div>
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider text-text-muted">Story Version</p>
          <p className="mt-1 text-[16px] font-bold tabular-nums text-text-primary">v{storyVersion ?? 1}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {facts.length > 0 && (
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-emerald-600 dark:text-emerald-300">
              <FileCheck className="h-3 w-3" /> Fact
            </p>
            <ul className="space-y-1.5">
              {facts.slice(0, 8).map((f, i) => (
                <li key={i} className="text-[12px] leading-5 text-text-secondary">
                  <span className="font-medium text-text-primary">{f.label}</span>{f.detail ? ` — ${f.detail}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
        {interpretations.length > 0 && (
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-violet-600 dark:text-violet-300">
              <Brain className="h-3 w-3" /> AI Interpretation
            </p>
            <ul className="space-y-1.5">
              {interpretations.slice(0, 8).map((f, i) => (
                <li key={i} className="text-[12px] leading-5 text-text-secondary">
                  <span className="font-medium text-text-primary">{f.label}</span>{f.detail ? ` — ${f.detail}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  );
}
