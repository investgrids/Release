"use client";

// Small visual building blocks for the answer page. Plain SVG and Tailwind, no library, no animation beyond CSS transitions. Every one of them draws a number the answer already carries: nothing is decoration pretending to be data.
import { useId } from "react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

type Icon = React.ComponentType<{ className?: string }>;

/** The last few daily closes as a line with a soft fill. Colour follows the direction of the series; with fewer than two closes it draws nothing. */
export function Sparkline({ data, w = 96, h = 32 }: { data?: number[] | null; w?: number; h?: number }) {
  const id = useId();
  const pts = (data ?? []).filter((n) => typeof n === "number" && Number.isFinite(n));
  if (pts.length < 2) return null;
  const min = Math.min(...pts), max = Math.max(...pts), span = max - min || 1;
  const x = (i: number) => (i / (pts.length - 1)) * (w - 4) + 2;
  const y = (v: number) => h - 3 - ((v - min) / span) * (h - 6);
  const line = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const up = pts[pts.length - 1] >= pts[0];
  const stroke = up ? "#059669" : "#e11d48";
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`Last ${pts.length} closes, ${up ? "up" : "down"}`} className="shrink-0" data-testid="sparkline">
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={stroke} stopOpacity="0.22" /><stop offset="100%" stopColor={stroke} stopOpacity="0" /></linearGradient>
      </defs>
      <path d={`${line} L${x(pts.length - 1).toFixed(1)},${h} L${x(0).toFixed(1)},${h} Z`} fill={`url(#${id})`} />
      <path d={line} fill="none" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={x(pts.length - 1)} cy={y(pts[pts.length - 1])} r="2.4" fill={stroke} />
    </svg>
  );
}

/** A signed percentage as a tinted pill with an arrow. */
export function ChangePill({ text, up }: { text: string; up: boolean }) {
  const Arrow = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[12px] font-semibold tabular-nums ${up ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-rose-500/10 text-rose-700 dark:text-rose-300"}`}>
      <Arrow className="h-3 w-3" aria-hidden />{text}
    </span>
  );
}

/** Where the current price sits between the 52-week low and high. The marker is the price itself, not a score. */
export function RangeBar({ low, high, price, fmt }: { low: number; high: number; price?: number | null; fmt: (n: number) => string }) {
  const span = high - low;
  if (!(span > 0)) return null;
  const pos = price != null && Number.isFinite(price) ? Math.max(0, Math.min(100, ((price - low) / span) * 100)) : null;
  return (
    <div className="space-y-1" data-testid="range-bar">
      <div className="relative h-1.5 rounded-full bg-gradient-to-r from-rose-300/70 via-amber-200/70 to-emerald-300/70">
        {pos != null && <span className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-violet-600 shadow" style={{ left: `${pos}%` }} title="Current price" aria-label={`Current price is ${Math.round(pos)}% of the way from the 52-week low to the high`} />}
      </div>
      <div className="flex justify-between text-[11px] tabular-nums text-text-muted"><span>{fmt(low)}</span><span>{fmt(high)}</span></div>
    </div>
  );
}

/** Rounded icon tile used beside headings. */
export function IconTile({ icon: I, tone = "violet" }: { icon: Icon; tone?: "violet" | "emerald" | "amber" | "sky" }) {
  const t = { violet: "bg-violet-500/10 text-violet-600", emerald: "bg-emerald-500/10 text-emerald-600", amber: "bg-amber-500/10 text-amber-600", sky: "bg-sky-500/10 text-sky-600" }[tone];
  return <span aria-hidden className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${t}`}><I className="h-4 w-4" /></span>;
}

/** Colour for a kind of evidence, so a news item, an event and an exchange filing are told apart at a glance. */
export const KIND_BADGE: Record<string, string> = {
  news: "bg-sky-500/10 text-sky-700 dark:text-sky-300",
  event: "bg-violet-500/10 text-violet-700 dark:text-violet-300",
  announcement: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  policy: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  context: "bg-slate-500/10 text-slate-600 dark:text-slate-300",
};
export const KIND_DOT: Record<string, string> = { news: "bg-sky-500", event: "bg-violet-500", announcement: "bg-emerald-500", policy: "bg-amber-500", context: "bg-slate-400" };

/** Gradient tile that stands in for a logo: initials on a soft tint (the logos themselves are not available). */
export function Avatar({ name, size = "h-9 w-9" }: { name: string; size?: string }) {
  const ini = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return <span aria-hidden className={`flex ${size} shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/15 to-sky-500/15 text-[12px] font-semibold text-violet-700 dark:text-violet-300`}>{ini}</span>;
}
