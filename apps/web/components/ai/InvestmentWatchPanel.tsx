"use client";

import { useEffect, useState } from "react";
import { Eye, TrendingUp, TrendingDown, Minus, ArrowRight, CalendarClock } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

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
}

interface WatchResponse {
  available: boolean;
  subject_label?: string;
  current_verdict?: { verdict_scale: string | null; confidence: number; as_of: string };
  last_change?: { from: string; to: string; from_date: string; to_date: string; why: string | null } | null;
  watching?: WatchTrigger[];
  next_trigger?: { label: string; category: string; date: string; days_until: number; description: string } | null;
}

const VERDICT_TONE: Record<string, string> = {
  "Strong Positive": "text-emerald-400",
  "Positive": "text-emerald-400",
  "Neutral": "text-amber-400",
  "Cautious": "text-orange-400",
  "Negative": "text-rose-400",
  "Strong Negative": "text-rose-400",
};

const STATUS_TONE: Record<string, string> = {
  rising: "text-rose-400", easing: "text-emerald-400",
  selling: "text-rose-400", buying: "text-emerald-400",
};

function statusTone(status: string): string {
  if (STATUS_TONE[status]) return STATUS_TONE[status];
  return "text-sky-400"; // "in Nd" / "today" calendar statuses
}

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
export function InvestmentWatchPanel({ subject }: { subject: WatchSubject | null | undefined }) {
  const [data, setData] = useState<WatchResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!subject) { setData(null); return; }
    let cancelled = false;
    setLoading(true);
    fetch(`${API}/api/ai/search/investment-watch?key=${encodeURIComponent(subject.subject_key)}`)
      .then(r => r.json())
      .then(d => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [subject?.subject_key]);

  if (!subject || loading) return null;
  if (!data?.available || !data.current_verdict) return null;

  const { current_verdict, last_change, watching, next_trigger } = data;
  const delta = last_change ? verdictDelta(last_change.from, last_change.to) : null;
  const label = subject.subject_type === "company" ? subject.subject_label : `${subject.subject_label} sector`;

  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
      <div className="mb-4 flex items-center gap-2">
        <Eye size={14} strokeWidth={1.8} className="text-violet-400" />
        <p className="text-[13px] font-semibold text-white">Investment Watch</p>
        <span className="ml-auto truncate text-[10px] text-slate-500">{label}</span>
      </div>

      {/* Current verdict */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Current Verdict</p>
          <p className={`text-[15px] font-bold ${VERDICT_TONE[current_verdict.verdict_scale || ""] ?? "text-slate-300"}`}>
            {current_verdict.verdict_scale || "—"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Confidence</p>
          <p className="text-[15px] font-bold text-white">{current_verdict.confidence}%</p>
        </div>
      </div>

      {/* Last change */}
      {last_change && (
        <div className="mb-4 rounded-[12px] border border-white/[0.06] bg-white/[0.02] p-3">
          <p className="mb-1.5 flex items-center gap-1.5 text-[9px] uppercase tracking-wider text-slate-500">
            {delta === "up" ? <TrendingUp className="h-3 w-3 text-emerald-400" />
              : delta === "down" ? <TrendingDown className="h-3 w-3 text-rose-400" />
              : <Minus className="h-3 w-3 text-slate-500" />}
            Last Change · {last_change.from_date} → {last_change.to_date}
          </p>
          <p className="flex items-center gap-1.5 text-[12px] font-medium text-slate-200">
            <span className={VERDICT_TONE[last_change.from] ?? "text-slate-400"}>{last_change.from}</span>
            <ArrowRight className="h-3 w-3 text-slate-600" />
            <span className={VERDICT_TONE[last_change.to] ?? "text-slate-400"}>{last_change.to}</span>
          </p>
          {last_change.why && <p className="mt-1.5 text-[11px] leading-snug text-slate-400">{last_change.why}</p>}
        </div>
      )}

      {/* Watching */}
      {watching && watching.length > 0 && (
        <div className="mb-4">
          <p className="mb-1.5 text-[9px] uppercase tracking-wider text-slate-500">Watching</p>
          <div className="space-y-1.5">
            {watching.map((w, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px]">
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${statusTone(w.status).replace("text-", "bg-")}`} />
                <span className="text-slate-300 shrink-0">{w.label}</span>
                <span className="ml-auto truncate text-slate-500">{w.detail}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Next possible trigger */}
      {next_trigger && (
        <div className="rounded-[12px] border border-violet-500/15 bg-violet-500/[0.05] p-3">
          <p className="mb-1 flex items-center gap-1.5 text-[9px] uppercase tracking-wider text-violet-300">
            <CalendarClock className="h-3 w-3" /> Next Possible Trigger
          </p>
          <p className="text-[12px] font-medium text-slate-200">{next_trigger.label}</p>
          <p className="mt-0.5 text-[10px] text-slate-500">
            {next_trigger.date} · in {next_trigger.days_until}d
          </p>
        </div>
      )}
    </div>
  );
}
