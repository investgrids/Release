"use client";

import { useEffect, useState } from "react";
import { Eye, TrendingUp, TrendingDown, Minus, ArrowRight, CalendarClock } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { confidenceWord, plainDate } from "@/lib/intelligenceView";

export interface WatchSubject {
  subject_key: string;
  subject_type: "company" | "sector";
  subject_label: string;
  company_name?: string | null;
}

interface WatchTrigger {
  label: string;
  status: string;
  detail: string;
  why?: string;                       // one plain sentence on why this indicator matters for the subject
  scope?: "company" | "sector" | "market";
}

export interface WatchResponse {
  available: boolean;
  subject_label?: string;
  current_verdict?: { verdict_scale: string | null; confidence: number; as_of: string; age_days?: number | null };
  last_change?: { from: string; to: string; from_date: string; to_date: string; why: string | null } | null;
  watching?: WatchTrigger[];
  next_trigger?: { label: string; category: string; date: string; days_until: number; description: string; scope?: "company" | "market" } | null;
}

const VERDICT_TONE: Record<string, string> = {
  "Strong Positive": "text-emerald-400",
  "Positive": "text-emerald-400",
  "Neutral": "text-amber-400",
  "Cautious": "text-orange-400",
  "Negative": "text-rose-400",
  "Strong Negative": "text-rose-400",
};

// Direction only: whether an indicator rising is good or bad depends on the company, so the arrow is neutral and the "why" line carries the meaning.
const STATUS_ARROW: Record<string, string> = { rising: "▲", falling: "▼", flat: "▬", selling: "▼", buying: "▲" };
const SCOPE_TAG: Record<string, string> = { company: "This company", sector: "Sector", market: "Market-wide" };
const STALE_AFTER_DAYS = 14;

function verdictDelta(from: string, to: string) {
  const order = ["Strong Negative", "Negative", "Cautious", "Neutral", "Positive", "Strong Positive"];
  const fi = order.indexOf(from), ti = order.indexOf(to);
  if (fi === -1 || ti === -1) return null;
  return ti > fi ? "up" : ti < fi ? "down" : "flat";
}

/**
 * Investment Watch (Phase 2B) — the merged "Monitoring Dashboard +
 * Verdict Change Explainer" panel. Fetches by response["watch_subject"]
 * (the exact key pipeline.py resolved and wrote a snapshot under — see
 * that field's docstring), so this never re-derives which company/sector
 * a query was "about". Renders nothing for multi-subject queries
 * (comparisons etc.) or before any verdict history exists for a subject —
 * same "don't guess, don't show a hollow panel" stance as the rest of
 * this session's features.
 */
export function InvestmentWatchPanel({ subject, initialData }: { subject: WatchSubject | null | undefined; initialData?: WatchResponse | null }) {
  // initialData: the caller already has this payload (the company intelligence response carries it), so no second request is made.
  const [data, setData] = useState<WatchResponse | null>(initialData ? { ...initialData, available: initialData.available ?? true } : null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialData !== undefined) { setData(initialData ? { ...initialData, available: initialData.available ?? true } : null); return; }
    if (!subject) { setData(null); return; }
    let cancelled = false;
    setLoading(true);
    fetch(`${API}/api/ai/search/investment-watch?key=${encodeURIComponent(subject.subject_key)}`)
      .then(r => r.json())
      .then(d => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [subject?.subject_key, initialData]);

  if (!subject || loading) return null;
  if (!data?.available || !data.current_verdict) return null;

  const { current_verdict, last_change, watching, next_trigger } = data;
  const delta = last_change ? verdictDelta(last_change.from, last_change.to) : null;
  const label = subject.subject_type === "company" ? subject.subject_label : `${subject.subject_label} sector`;

  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
      <div className="mb-4 flex items-center gap-2">
        <Eye size={14} strokeWidth={1.8} className="text-violet-400" />
        <p className="text-[13px] font-semibold text-text-primary">Investment Watch</p>
        <span className="ml-auto truncate text-[10px] text-text-muted">{label}</span>
      </div>

      {/* Current verdict */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-[9px] uppercase tracking-wider text-text-muted mb-1">Current verdict{current_verdict.as_of ? ` · as of ${plainDate(current_verdict.as_of)}` : ""}</p>
          <p className={`text-[15px] font-bold ${VERDICT_TONE[current_verdict.verdict_scale || ""] ?? "text-text-secondary"}`}>
            {current_verdict.verdict_scale || "—"}
          </p>
        </div>
        {/* CD3-C: verdict_scale is decision_engine_v2's vocabulary --
            confidence here is very likely the same confidence_breakdown.
            final_confidence HYBRID_RUBRIC composite used by
            InvestmentVerdictHero/AISearchClient (not independently
            re-traced through this panel's own watch endpoint), disclosed
            via tooltip rather than asserted without confirming. */}
        <div className="text-right" title="An evidence-based composite with a minor self-assessed component -- not a fully computed score">
          <p className="text-[9px] uppercase tracking-wider text-text-muted mb-1">Confidence in this view</p>
          <p className="text-[15px] font-bold text-text-primary">{confidenceWord(current_verdict.confidence)} <span className="text-[12px] font-medium text-text-muted">({current_verdict.confidence}%)</span></p>
        </div>
      </div>

      {typeof current_verdict.age_days === "number" && current_verdict.age_days > STALE_AFTER_DAYS && (
        <p className="mb-4 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2 text-[11px] leading-snug text-amber-800 dark:text-amber-300">
          This verdict is {current_verdict.age_days} days old and may be out of date. It refreshes when a new AI analysis of {label} is run.
        </p>
      )}

      {/* Last change */}
      {last_change && (
        <div className="mb-4 rounded-[12px] border border-surface-border/6 bg-text-primary/[0.02] p-3">
          <p className="mb-1.5 flex items-center gap-1.5 text-[9px] uppercase tracking-wider text-text-muted">
            {delta === "up" ? <TrendingUp className="h-3 w-3 text-emerald-400" />
              : delta === "down" ? <TrendingDown className="h-3 w-3 text-rose-400" />
              : <Minus className="h-3 w-3 text-text-muted" />}
            Last change · {plainDate(last_change.from_date)} → {plainDate(last_change.to_date)}
          </p>
          <p className="flex items-center gap-1.5 text-[12px] font-medium text-text-primary">
            <span className={VERDICT_TONE[last_change.from] ?? "text-text-secondary"}>{last_change.from}</span>
            <ArrowRight className="h-3 w-3 text-text-muted" />
            <span className={VERDICT_TONE[last_change.to] ?? "text-text-secondary"}>{last_change.to}</span>
          </p>
          {last_change.why && <p className="mt-1.5 text-[11px] leading-snug text-text-secondary">{last_change.why}</p>}
        </div>
      )}

      {/* Watching */}
      {watching && watching.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-[9px] uppercase tracking-wider text-text-muted">What we are watching</p>
          <ul className="space-y-2.5">
            {watching.map((w, i) => (
              <li key={i} className="text-[12px]">
                <div className="flex items-center gap-2">
                  <span className="w-3 shrink-0 text-center text-[9px] text-sky-500" aria-hidden>{STATUS_ARROW[w.status] ?? "●"}</span>
                  <span className="font-medium text-text-primary">{w.label}</span>
                  {w.scope && <span className="rounded bg-text-primary/[0.06] px-1.5 py-px text-[9px] font-medium text-text-muted">{SCOPE_TAG[w.scope]}</span>}
                  <span className="ml-auto text-right tabular-nums text-text-secondary">{w.detail}</span>
                </div>
                {w.why && <p className="mt-0.5 pl-5 text-[11px] leading-snug text-text-muted">{w.why}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Next possible trigger */}
      {next_trigger && (
        <div className="rounded-[12px] border border-violet-500/15 bg-violet-500/[0.05] p-3">
          <p className="mb-1 flex items-center gap-1.5 text-[9px] uppercase tracking-wider text-violet-600 dark:text-violet-300">
            <CalendarClock className="h-3 w-3" /> {next_trigger.scope === "market" ? "Next market-wide event" : "Next event for " + label}
          </p>
          <p className="text-[12px] font-medium text-text-primary">{next_trigger.label}</p>
          <p className="mt-0.5 text-[10px] text-text-muted">
            {plainDate(next_trigger.date)} · in {next_trigger.days_until} day{next_trigger.days_until === 1 ? "" : "s"}
          </p>
        </div>
      )}
    </div>
  );
}
