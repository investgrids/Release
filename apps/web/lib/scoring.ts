/**
 * Shared score → color/label presentation helpers.
 *
 * These are purely presentational (given a score the backend already
 * computed, map it to a color/label) — they do not calculate or fabricate
 * any score themselves. Score *calculation* belongs entirely on the
 * backend; this file exists so the same score doesn't render five
 * different colors depending on which page you're looking at it from.
 */

/** General 0-100 score → color. Used for confidence/quality-style scores. */
export function scoreToColor(score: number): string {
  if (score >= 75) return "#22c55e";
  if (score >= 50) return "#38bdf8";
  if (score >= 30) return "#f59e0b";
  return "#f43f5e";
}

export function scoreToLabel(score: number): string {
  if (score >= 75) return "High";
  if (score >= 50) return "Medium";
  if (score >= 30) return "Low";
  return "Very Low";
}

export interface ImpactStyle {
  text: string;
  bg: string;
  ring: string;
  label: string;
}

/** 0-100 impact score → { text, bg, ring, label }. Used for event/news impact badges. */
export function impactToStyle(score: number): ImpactStyle {
  if (score >= 75) return { text: "text-rose-400",  bg: "bg-rose-500/15",  ring: "#f43f5e", label: "Very High" };
  if (score >= 55) return { text: "text-amber-400", bg: "bg-amber-500/15", ring: "#f59e0b", label: "High" };
  if (score >= 35) return { text: "text-sky-400",   bg: "bg-sky-500/15",   ring: "#38bdf8", label: "Medium" };
  return              { text: "text-slate-400", bg: "bg-slate-700/20", ring: "#64748b", label: "Low" };
}
