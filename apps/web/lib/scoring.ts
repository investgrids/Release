/**
 * Shared score presentation helpers + null-safe types for the Scoring
 * Engine's output contract.
 *
 * Every intelligence field (impact_score, confidence, company_score,
 * opportunity_score, risk_score, ripple_score, sector_strength,
 * theme_strength, ai_confidence, ...) is `number | null` on the wire —
 * null means the Scoring Engine had insufficient real evidence to
 * compute a number, not "zero" and not "low". These helpers are the
 * ONLY place score -> color/label/status mapping should happen; they do
 * not calculate or fabricate a score themselves, and every one of them
 * treats null explicitly instead of letting it fall through arithmetic
 * (`null || 0`, `null <= x`, `null * y`) and silently become a fake 0.
 */

export type ScoreStatus = "ok" | "insufficient_data";
export type DataStatus = "preliminary" | "verified" | "live";

export interface ScoreLike {
  score: number | null | undefined;
  confidence?: number | null;
  status?: ScoreStatus;
  data_status?: DataStatus | null;
}

/** The one correct way to check "is this score actually missing". */
export function isUnscored(score: number | null | undefined, status?: ScoreStatus | null): boolean {
  return score === null || score === undefined || status === "insufficient_data";
}

/** General 0-100 score -> color. Neutral slate for a missing score — never "red" (bad) or "green" (good) for unknown. */
export function scoreToColor(score: number | null | undefined): string {
  if (isUnscored(score)) return "#64748b";
  const s = score as number;
  if (s >= 75) return "#22c55e";
  if (s >= 50) return "#38bdf8";
  if (s >= 30) return "#f59e0b";
  return "#f43f5e";
}

export function scoreToLabel(score: number | null | undefined): string {
  if (isUnscored(score)) return "Unscored";
  const s = score as number;
  if (s >= 75) return "High";
  if (s >= 50) return "Medium";
  if (s >= 30) return "Low";
  return "Very Low";
}

export interface ImpactStyle {
  text: string;
  bg: string;
  ring: string;    // hex, for SVG/canvas/inline-style borders (avoids dynamic Tailwind class strings)
  circle: string;  // full Tailwind class string for a bordered circle badge
  pill: string;    // full Tailwind class string for a pill badge
  label: string;
}

/** 0-100 impact score -> full style object. Used for event/news/company impact badges. */
export function impactToStyle(score: number | null | undefined): ImpactStyle {
  if (isUnscored(score)) {
    return {
      text: "text-slate-500", bg: "bg-slate-800/25", ring: "#475569",
      circle: "border-slate-700 bg-slate-800/30 text-slate-500",
      pill: "bg-slate-800/30 text-slate-500 border-slate-700/40",
      label: "Unscored",
    };
  }
  const s = score as number;
  if (s >= 75) return {
    text: "text-rose-400", bg: "bg-rose-500/15", ring: "#f43f5e",
    circle: "border-rose-500 bg-rose-500/20 text-rose-400",
    pill: "bg-rose-500/15 text-rose-300 border-rose-500/30",
    label: "Very High",
  };
  if (s >= 55) return {
    text: "text-amber-400", bg: "bg-amber-500/15", ring: "#f59e0b",
    circle: "border-amber-400 bg-amber-500/20 text-amber-400",
    pill: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    label: "High",
  };
  if (s >= 35) return {
    text: "text-sky-400", bg: "bg-sky-500/15", ring: "#38bdf8",
    circle: "border-sky-400 bg-sky-500/20 text-sky-400",
    pill: "bg-sky-500/15 text-sky-300 border-sky-500/30",
    label: "Medium",
  };
  return {
    text: "text-slate-400", bg: "bg-slate-700/20", ring: "#64748b",
    circle: "border-slate-500 bg-slate-700/30 text-slate-400",
    pill: "bg-slate-700/30 text-slate-400 border-slate-500/30",
    label: "Low",
  };
}

/** data_status -> short badge label + classes, for "Preliminary / Verified / Live" tags. */
export function dataStatusStyle(dataStatus: DataStatus | null | undefined): { label: string; text: string; bg: string } {
  switch (dataStatus) {
    case "live":       return { label: "Live",        text: "text-emerald-400", bg: "bg-emerald-500/10" };
    case "verified":   return { label: "Verified",    text: "text-sky-400",     bg: "bg-sky-500/10" };
    case "preliminary":return { label: "Preliminary", text: "text-amber-400",   bg: "bg-amber-500/10" };
    default:           return { label: "", text: "", bg: "" };
  }
}

/**
 * Null-safe descending-score comparator. Unscored entities always sort
 * to the end — never mixed in as if they scored 0, which would rank a
 * "we don't know" entity below every real low score instead of simply
 * outside the ranking entirely.
 */
export function compareScoresDesc(a: number | null | undefined, b: number | null | undefined): number {
  const aU = isUnscored(a);
  const bU = isUnscored(b);
  if (aU && bU) return 0;
  if (aU) return 1;
  if (bU) return -1;
  return (b as number) - (a as number);
}

/**
 * Null-safe average — ignores unscored entries instead of treating a
 * missing score as 0, which would silently drag down the average for
 * every entity that genuinely has no score yet. Returns null (not 0)
 * when nothing in the list has a real score.
 */
export function averageScores(scores: Array<number | null | undefined>): number | null {
  const real = scores.filter((s): s is number => s !== null && s !== undefined);
  if (real.length === 0) return null;
  return real.reduce((sum, s) => sum + s, 0) / real.length;
}

/** Null-safe count of entities crossing a threshold — never counts an unscored entity toward any bucket. */
export function countAtOrAbove(scores: Array<number | null | undefined>, threshold: number): number {
  return scores.filter((s): s is number => s !== null && s !== undefined && s >= threshold).length;
}
