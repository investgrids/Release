"use client";

/**
 * Shared score-rendering components — the ONLY place a score/confidence
 * number should be turned into UI anywhere in the app. Every score field
 * from the backend (impact_score, confidence, company_score,
 * opportunity_score, risk_score, ripple_score, sector_strength,
 * theme_strength, ai_confidence, ...) is `number | null`; null means the
 * Scoring Engine had insufficient real evidence. These components render
 * that state honestly — "Unscored" / "Collecting Evidence", never "0",
 * never "Low", never a fabricated percentage.
 */

import {
  isUnscored, impactToStyle, dataStatusStyle,
  type DataStatus, type ScoreStatus,
} from "@/lib/scoring";

const CIRCLE_SIZE: Record<"sm" | "md" | "lg", string> = {
  sm: "h-10 w-10 text-[13px]",
  md: "h-14 w-14 text-[18px]",
  lg: "h-20 w-20 text-[26px]",
};

export interface ScoreDisplayProps {
  score: number | null | undefined;
  confidence?: number | null;
  status?: ScoreStatus;
  dataStatus?: DataStatus | null;
  /** e.g. "Impact", "Opportunity", "Risk" — shown above a circle, omitted for pill/inline */
  label?: string;
  variant?: "circle" | "pill" | "inline";
  size?: "sm" | "md" | "lg";
  showConfidence?: boolean;
  /** Shown when the score is unscored. Default reflects data_status when available. */
  unscoredMessage?: string;
  className?: string;
}

function defaultUnscoredMessage(dataStatus?: DataStatus | null): string {
  if (dataStatus === "preliminary") return "Collecting Evidence";
  return "Insufficient verified data";
}

export function ScoreDisplay({
  score, confidence, status, dataStatus, label,
  variant = "circle", size = "md", showConfidence = true,
  unscoredMessage, className = "",
}: ScoreDisplayProps) {
  const unscored = isUnscored(score, status);
  const style = impactToStyle(score);
  const dsStyle = dataStatus ? dataStatusStyle(dataStatus) : null;
  const message = unscoredMessage ?? defaultUnscoredMessage(dataStatus);

  if (variant === "pill") {
    return (
      <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${style.pill} ${className}`}>
        {unscored ? message : `${Math.round(score as number)} · ${style.label}`}
      </span>
    );
  }

  if (variant === "inline") {
    return (
      <span className={`inline-flex items-center gap-1.5 text-[12px] ${className}`}>
        {unscored ? (
          <span className="text-slate-500">{message}</span>
        ) : (
          <>
            <span className={`font-bold ${style.text}`}>{Math.round(score as number)}</span>
            {showConfidence && confidence != null && (
              <span className="text-slate-500">({Math.round(confidence)}% confidence)</span>
            )}
            {dsStyle?.label && (
              <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${dsStyle.text} ${dsStyle.bg}`}>{dsStyle.label}</span>
            )}
          </>
        )}
      </span>
    );
  }

  // circle (default)
  return (
    <div className={`flex flex-col items-center gap-1 ${className}`}>
      {label && <p className="text-[9px] uppercase tracking-wider text-slate-600">{label}</p>}
      <div className={`flex flex-col items-center justify-center rounded-full border-2 ${style.circle} ${CIRCLE_SIZE[size]}`}>
        {unscored ? (
          <span className="px-1 text-center text-[9px] font-medium leading-tight">N/A</span>
        ) : (
          <span className="font-black leading-none">{Math.round(score as number)}</span>
        )}
        <span className="text-[8px] font-medium">{style.label}</span>
      </div>
      {unscored ? (
        <p className="max-w-[84px] text-center text-[9px] leading-tight text-slate-500">{message}</p>
      ) : (
        showConfidence && confidence != null && (
          <p className="text-[9px] text-slate-500">{Math.round(confidence)}% confidence</p>
        )
      )}
      {!unscored && dsStyle?.label && (
        <span className={`rounded-full px-1.5 py-0.5 text-[8px] font-medium ${dsStyle.text} ${dsStyle.bg}`}>{dsStyle.label}</span>
      )}
    </div>
  );
}

/**
 * Compact standalone status badge — for places that want to show
 * "Preliminary / Verified / Live" or "Insufficient verified data"
 * without the full score circle (e.g. a table cell, a list row).
 */
export function IntelligenceStatus({
  dataStatus, status, className = "",
}: { dataStatus?: DataStatus | null; status?: ScoreStatus; className?: string }) {
  if (status === "insufficient_data" || !dataStatus) {
    return (
      <span className={`inline-flex items-center gap-1 rounded-full border border-slate-700/50 bg-slate-800/30 px-2 py-0.5 text-[10px] font-medium text-slate-500 ${className}`}>
        Insufficient verified data
      </span>
    );
  }
  const s = dataStatusStyle(dataStatus);
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${s.text} ${s.bg} ${className}`}>
      {s.label}
    </span>
  );
}
