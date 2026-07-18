import type { ReactNode } from "react";

export type ConfidenceLevel = "very-high" | "high" | "medium" | "low" | "unscored";

/** null/undefined means the backend had insufficient evidence to compute a confidence score — never coerce that into "low". */
export function getConfidenceLevel(score: number | null | undefined): ConfidenceLevel {
  if (score === null || score === undefined) return "unscored";
  if (score >= 90) return "very-high";
  if (score >= 75) return "high";
  if (score >= 50) return "medium";
  return "low";
}

const LEVEL_CONFIG: Record<ConfidenceLevel, { label: string; cls: string; bar: string }> = {
  "very-high": {
    label: "Very High",
    cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
    bar: "bg-emerald-400",
  },
  high: {
    label: "High",
    cls: "border-sky-500/30 bg-sky-500/10 text-sky-400",
    bar: "bg-sky-400",
  },
  medium: {
    label: "Medium",
    cls: "border-amber-500/30 bg-amber-500/10 text-amber-400",
    bar: "bg-amber-400",
  },
  low: {
    label: "Low",
    cls: "border-rose-500/30 bg-rose-500/10 text-rose-400",
    bar: "bg-rose-400",
  },
  unscored: {
    label: "Unscored",
    cls: "border-slate-700/50 bg-slate-800/30 text-slate-500",
    bar: "bg-slate-600",
  },
};

export interface ConfidenceBadgeProps {
  score: number | null | undefined;
  showBar?: boolean;
  showLabel?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function ConfidenceBadge({
  score,
  showBar = false,
  showLabel = true,
  size = "sm",
  className = "",
}: ConfidenceBadgeProps) {
  const level = getConfidenceLevel(score);
  const config = LEVEL_CONFIG[level];
  const unscored = level === "unscored";
  const textSize = size === "sm" ? "text-xs" : size === "md" ? "text-sm" : "text-base";
  const padding = size === "sm" ? "px-2 py-0.5" : size === "md" ? "px-2.5 py-1" : "px-3 py-1.5";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${padding} font-semibold ${textSize} ${config.cls} ${className}`}
      aria-label={unscored ? "AI confidence: insufficient verified data" : `AI confidence: ${config.label} (${score}%)`}
    >
      {showBar && (
        <span className="flex h-1.5 w-12 overflow-hidden rounded-full bg-white/10">
          <span
            className={`h-full rounded-full transition-all ${config.bar}`}
            style={{ width: unscored ? "0%" : `${score}%` }}
          />
        </span>
      )}
      {showLabel && config.label}
      {!unscored && <span className="opacity-70">{score}%</span>}
    </span>
  );
}

export function ConfidenceMeter({ score }: { score: number | null | undefined }) {
  const level = getConfidenceLevel(score);
  const config = LEVEL_CONFIG[level];
  const unscored = level === "unscored";

  return (
    <div className="space-y-1.5" aria-label={unscored ? "Confidence meter: insufficient verified data" : `Confidence meter: ${score}%`}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-slate-500">AI Confidence</span>
        <span className={`text-[11px] font-bold ${config.cls.split(" ").find(c => c.startsWith("text-"))}`}>
          {unscored ? "Insufficient verified data" : `${config.label} · ${score}%`}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={`h-full rounded-full transition-all duration-500 ${config.bar}`}
          style={{ width: unscored ? "0%" : `${score}%` }}
        />
      </div>
    </div>
  );
}
