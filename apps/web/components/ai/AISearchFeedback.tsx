"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Check } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

const REASONS: { key: string; label: string }[] = [
  { key: "wrong_company", label: "Wrong company detected" },
  { key: "too_generic", label: "Too generic" },
  { key: "too_slow", label: "Too slow" },
  { key: "missing_news", label: "Missing latest news" },
  { key: "incorrect_conclusion", label: "Incorrect conclusion" },
  { key: "didnt_answer", label: "Didn't answer my question" },
  { key: "hallucination", label: "Hallucination" },
  { key: "other", label: "Other" },
];

export interface AISearchFeedbackMeta {
  responseId: string | null;
  query: string;
  specialist?: string | null;
  schemaVersion?: string | null;
  cached: boolean;
  latencyMs: number | null;
  provider: string | null;
}

/**
 * 👍/👎 on the current AI Search V3 answer. Feeds AISearchFeedback on the
 * backend — the raw dataset behind the continuous-improvement loop (see
 * that model's docstring). Renders nothing when there's no response_id to
 * attach feedback to (V2 responses, or before a V3 result has arrived).
 */
export function AISearchFeedback({ meta }: { meta: AISearchFeedbackMeta }) {
  const [status, setStatus] = useState<"idle" | "picking_reason" | "submitting" | "done" | "error">("idle");
  const [selectedReason, setSelectedReason] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [submittedRating, setSubmittedRating] = useState<"helpful" | "not_helpful" | null>(null);

  if (!meta.responseId) return null;

  async function submit(rating: "helpful" | "not_helpful", reason: string | null) {
    setStatus("submitting");
    try {
      const res = await fetch(`${API}/api/ai/search/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          response_id: meta.responseId,
          query: meta.query,
          rating,
          reason,
          reason_text: text.trim() || null,
          specialist: meta.specialist ?? null,
          provider: meta.provider,
          cache_hit: meta.cached,
          latency_ms: meta.latencyMs,
          schema_version: meta.schemaVersion ?? null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSubmittedRating(rating);
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }

  if (status === "done") {
    return (
      <div className="flex items-center gap-2 rounded-[14px] border border-white/[0.06] bg-white/[0.02] px-4 py-3 text-[12px] text-slate-400">
        <Check className="h-3.5 w-3.5 text-emerald-400" />
        Thanks for the feedback{submittedRating === "not_helpful" ? " — we'll use this to improve." : "."}
      </div>
    );
  }

  return (
    <div className="rounded-[14px] border border-white/[0.06] bg-white/[0.02] px-4 py-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-[12px] text-slate-400">Was this answer helpful?</p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => submit("helpful", null)}
            disabled={status === "submitting"}
            className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[12px] text-slate-300 transition hover:border-emerald-500/30 hover:bg-emerald-500/10 hover:text-emerald-300 disabled:opacity-50"
          >
            <ThumbsUp className="h-3.5 w-3.5" /> Helpful
          </button>
          <button
            onClick={() => setStatus("picking_reason")}
            disabled={status === "submitting"}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] transition disabled:opacity-50 ${
              status === "picking_reason"
                ? "border-rose-500/30 bg-rose-500/10 text-rose-300"
                : "border-white/10 bg-white/[0.03] text-slate-300 hover:border-rose-500/30 hover:bg-rose-500/10 hover:text-rose-300"
            }`}
          >
            <ThumbsDown className="h-3.5 w-3.5" /> Not Helpful
          </button>
        </div>
      </div>

      {status === "picking_reason" && (
        <div className="mt-3 border-t border-white/[0.06] pt-3">
          <p className="mb-2 text-[11px] text-slate-500">What went wrong?</p>
          <div className="mb-2 flex flex-wrap gap-1.5">
            {REASONS.map(r => (
              <button
                key={r.key}
                onClick={() => setSelectedReason(r.key)}
                className={`rounded-full border px-2.5 py-1 text-[11px] transition ${
                  selectedReason === r.key
                    ? "border-rose-500/40 bg-rose-500/15 text-rose-300"
                    : "border-white/10 bg-white/[0.02] text-slate-400 hover:bg-white/[0.05]"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
          {selectedReason === "other" && (
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              maxLength={500}
              placeholder="Tell us more (optional)"
              rows={2}
              className="mb-2 w-full resize-none rounded-[10px] border border-white/10 bg-white/[0.02] px-3 py-2 text-[12px] text-slate-300 placeholder:text-slate-600 focus:border-violet-500/40 focus:outline-none"
            />
          )}
          <button
            onClick={() => selectedReason && submit("not_helpful", selectedReason)}
            disabled={!selectedReason}
            className="rounded-[10px] border border-rose-500/30 bg-rose-500/20 px-3 py-1.5 text-[11.5px] font-medium text-rose-300 transition hover:bg-rose-500/30 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Submit
          </button>
        </div>
      )}

      {status === "error" && (
        <p className="mt-2 text-[11px] text-rose-400">Couldn&apos;t submit feedback — please try again.</p>
      )}
    </div>
  );
}
