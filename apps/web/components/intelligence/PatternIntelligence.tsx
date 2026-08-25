"use client";

import { useEffect, useState } from "react";
import { History, Loader2, ChevronRight, TrendingUp, TrendingDown } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface HistoricalPattern {
  historical_match:   string;
  similarity_score:   number | null;
  historical_outcome: string;
  average_duration?:  string;
  success_rate?:      number | null;
  key_differences?:   string;
  lessons_learned?:   string;
  confidence?:        number | null;
}

export type PatternEntityType =
  | "event" | "company" | "story" | "opportunity" | "ripple" | "search";

export interface PatternIntelligenceProps {
  patterns?:          HistoricalPattern[];
  typicalWinners?:    string[];
  typicalLosers?:     string[];
  averageTimeline?:   string;
  overallConfidence?: number;
  entityType?:        PatternEntityType;
  entityId?:          string;
  entityTitle?:       string;
  entityDescription?: string;
  entitySector?:      string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return "text-text-muted";
  if (score >= 75) return "text-emerald-400";
  if (score >= 55) return "text-amber-400";
  return "text-text-muted";
}

function scoreBarColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return "bg-text-primary/[0.07]";
  if (score >= 75) return "bg-emerald-500";
  if (score >= 55) return "bg-amber-500";
  return "bg-slate-600";
}

function scoreLabel(score: number | null | undefined): string {
  if (score === null || score === undefined) return "Unscored";
  if (score >= 80) return "Very Similar";
  if (score >= 65) return "Similar";
  if (score >= 50) return "Moderate";
  return "Weak Match";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PatternCard({ pattern, index }: { pattern: HistoricalPattern; index: number }) {
  const [open, setOpen] = useState(false);
  const hasDetail = !!(pattern.key_differences || pattern.lessons_learned);

  return (
    <div className="rounded-[16px] border border-surface-border/7 bg-text-primary/[0.02] p-4 space-y-3">
      {/* Match title + similarity */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2 min-w-0">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-lg bg-violet-500/10 border border-violet-500/20 text-[9px] font-black text-violet-400">
            {index + 1}
          </span>
          <span className="text-[13px] font-semibold text-text-primary leading-snug">
            {pattern.historical_match}
          </span>
        </div>
        <div className="shrink-0 text-right">
          <span className={`text-[11px] font-black ${scoreColor(pattern.similarity_score)}`}>
            {pattern.similarity_score === null || pattern.similarity_score === undefined ? "Unscored" : `${pattern.similarity_score}%`}
          </span>
          <p className="text-[9px] text-text-muted">{scoreLabel(pattern.similarity_score)}</p>
        </div>
      </div>

      {/* Similarity bar */}
      <div className="h-1 overflow-hidden rounded-full bg-text-primary/[0.06]">
        {pattern.similarity_score !== null && pattern.similarity_score !== undefined && (
          <div
            className={`h-full rounded-full transition-all duration-700 ${scoreBarColor(pattern.similarity_score)}`}
            style={{ width: `${pattern.similarity_score}%` }}
          />
        )}
      </div>

      {/* Historical outcome */}
      <p className="text-[12px] text-text-secondary leading-[1.55]">{pattern.historical_outcome}</p>

      {/* Metrics row */}
      <div className="flex flex-wrap gap-3">
        {pattern.average_duration && (
          <div>
            <p className="text-[9px] text-text-muted uppercase tracking-widest">Duration</p>
            <p className="text-[11px] text-text-secondary">{pattern.average_duration}</p>
          </div>
        )}
        {pattern.success_rate != null && (
          <div>
            <p className="text-[9px] text-text-muted uppercase tracking-widest">Success Rate</p>
            <p className={`text-[11px] font-semibold ${scoreColor(pattern.success_rate)}`}>
              {pattern.success_rate}%
            </p>
          </div>
        )}
        {pattern.confidence != null && (
          <div>
            <p className="text-[9px] text-text-muted uppercase tracking-widest">Confidence</p>
            <p className="text-[11px] text-text-secondary">{pattern.confidence}%</p>
          </div>
        )}
      </div>

      {/* Expand */}
      {hasDetail && (
        <button
          onClick={() => setOpen(o => !o)}
          className="flex items-center gap-1 text-[10px] font-medium text-violet-400 opacity-70 hover:opacity-100 transition-opacity"
        >
          <ChevronRight className={`h-3 w-3 transition-transform duration-200 ${open ? "rotate-90" : ""}`} />
          {open ? "Less" : "Key differences & lessons"}
        </button>
      )}

      {open && hasDetail && (
        <div className="space-y-2 border-t border-surface-border/5 pt-3">
          {pattern.key_differences && (
            <div>
              <p className="text-[9px] font-bold uppercase tracking-widest text-text-muted mb-1">Key Differences</p>
              <p className="text-[11px] text-text-secondary leading-[1.55]">{pattern.key_differences}</p>
            </div>
          )}
          {pattern.lessons_learned && (
            <div>
              <p className="text-[9px] font-bold uppercase tracking-widest text-text-muted mb-1">Lessons Learned</p>
              <p className="text-[11px] text-amber-600/70 dark:text-amber-300/70 leading-[1.55]">{pattern.lessons_learned}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function PatternIntelligenceCard({
  patterns:          staticPatterns,
  typicalWinners:    staticWinners,
  typicalLosers:     staticLosers,
  averageTimeline:   staticTimeline,
  overallConfidence: staticConfidence,
  entityType,
  entityId,
  entityTitle,
  entityDescription,
  entitySector,
}: PatternIntelligenceProps) {
  const [fetched, setFetched] = useState<{
    patterns?: HistoricalPattern[];
    typical_winners?: string[];
    typical_losers?: string[];
    average_timeline?: string;
    overall_confidence?: number;
    degraded?: boolean;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!entityType || !entityId) return;
    setLoading(true);
    const params = new URLSearchParams();
    if (entityTitle)       params.set("title",       entityTitle.slice(0, 200));
    if (entityDescription) params.set("description", entityDescription.slice(0, 800));
    if (entitySector)      params.set("sector",      entitySector.slice(0, 100));

    fetch(`${API}/api/pattern/${entityType}/${encodeURIComponent(entityId)}?${params}`)
      .then(r => r.ok ? r.json() : null)
      // Company redesign final-re-audit fix — the backend's own `degraded`
      // flag means "generic template, not real analysis" (see
      // ai_service.py's own comment on this exact field: "caller must not
      // present this as personalized"). This component was never reading
      // it, so a failed real pattern-match silently rendered a fabricated-
      // looking historical analog (a real live-observed case: "68%
      // similarity", "75% success rate") with zero disclosure. Degraded
      // responses are now treated the same as "no real analysis" — never
      // stored into `fetched`, so the existing honest empty state renders
      // instead of fabricated content.
      .then(d => { if (d?.patterns && !d?.degraded) setFetched(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [entityType, entityId, entityTitle, entityDescription, entitySector]);

  const patterns   = staticPatterns   ?? fetched?.patterns   ?? [];
  const winners    = staticWinners    ?? fetched?.typical_winners   ?? [];
  const losers     = staticLosers     ?? fetched?.typical_losers    ?? [];
  const timeline   = staticTimeline   ?? fetched?.average_timeline;
  const confidence = staticConfidence ?? fetched?.overall_confidence;

  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.025] p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/[0.08] border border-violet-500/20">
            <History className="h-3.5 w-3.5 text-violet-400" />
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted">
              Pattern Intelligence
            </span>
            <p className="text-[9px] text-text-muted">Historical similarity matching</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {loading && <Loader2 className="h-3 w-3 text-text-muted animate-spin" />}
          {confidence != null && (
            <span className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2 py-0.5 text-[9px] font-bold text-violet-400">
              {confidence}% confidence
            </span>
          )}
        </div>
      </div>

      {/* Loading skeleton */}
      {loading && !patterns.length && (
        <div className="space-y-3">
          {[0, 1].map(i => (
            <div key={i} className="rounded-[16px] border border-surface-border/7 bg-text-primary/[0.02] p-4 space-y-3">
              <div className="flex justify-between">
                <div className="h-4 w-40 rounded bg-text-primary/[0.06] animate-pulse" />
                <div className="h-4 w-12 rounded bg-text-primary/[0.06] animate-pulse" />
              </div>
              <div className="h-1 rounded-full bg-text-primary/[0.06] animate-pulse" />
              <div className="space-y-1.5">
                <div className="h-2.5 w-full rounded bg-text-primary/[0.05] animate-pulse" />
                <div className="h-2.5 w-3/4 rounded bg-text-primary/[0.05] animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && !patterns.length && (
        <p className="text-[12px] text-text-secondary leading-5">No historical patterns identified</p>
      )}

      {/* Pattern cards */}
      {patterns.length > 0 && (
        <div className="space-y-3">
          {patterns.map((p, i) => (
            <PatternCard key={i} pattern={p} index={i} />
          ))}
        </div>
      )}

      {/* Winners / Losers */}
      {(winners.length > 0 || losers.length > 0) && (
        <div className="mt-4 grid grid-cols-2 gap-3">
          {winners.length > 0 && (
            <div className="rounded-[14px] border border-emerald-500/15 bg-emerald-500/[0.04] p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <TrendingUp className="h-3 w-3 text-emerald-400" aria-hidden />
                <p className="text-[9px] font-bold uppercase tracking-widest text-emerald-500">Typical Winners</p>
              </div>
              <ul className="space-y-0.5">
                {winners.map((w, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[11px] text-text-secondary">
                    <span className="mt-[5px] h-1 w-1 shrink-0 rounded-full bg-emerald-500" />
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {losers.length > 0 && (
            <div className="rounded-[14px] border border-rose-500/15 bg-rose-500/[0.04] p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <TrendingDown className="h-3 w-3 text-rose-400" aria-hidden />
                <p className="text-[9px] font-bold uppercase tracking-widest text-rose-500">Typical Losers</p>
              </div>
              <ul className="space-y-0.5">
                {losers.map((l, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[11px] text-text-secondary">
                    <span className="mt-[5px] h-1 w-1 shrink-0 rounded-full bg-rose-500" />
                    {l}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Timeline */}
      {timeline && (
        <div className="mt-3 flex items-center justify-between rounded-[12px] border border-surface-border/5 bg-text-primary/[0.02] px-3 py-2">
          <span className="text-[10px] text-text-muted uppercase tracking-widest">Avg. Timeline</span>
          <span className="text-[12px] font-semibold text-text-secondary">{timeline}</span>
        </div>
      )}

      <p className="mt-3 text-[9px] text-text-muted text-right">
        AI-generated historical comparison · Not financial advice
      </p>
    </div>
  );
}

export { PatternIntelligenceCard as PatternIntelligence };
