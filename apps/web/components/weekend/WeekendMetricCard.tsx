import type { ReactNode } from "react";

/**
 * Shared primary-metric card — Overall Outlook / Confidence / Since Close
 * / Evidence Quality all use this same shell (redesign brief §6: same
 * card style, header row + big value + supporting copy). Purely
 * presentational — every value/caption is passed in by the caller, never
 * computed here, so this component has no opinion about what's real.
 */
const ACCENT_VAR: Record<"violet" | "emerald" | "rose", string> = {
  violet: "rgb(var(--accent-violet))",
  emerald: "rgb(var(--accent-emerald))",
  rose: "rgb(var(--accent-rose))",
};

export function WeekendMetricCard({
  icon,
  iconClassName = "bg-surface-border/8 text-text-muted",
  accent = "violet",
  label,
  value,
  valueClassName = "text-text-primary",
  valueTextSize = "text-[38px]",
  caption,
}: {
  icon: ReactNode;
  /** bg + text color classes for the icon's circle — defaults to the
   * original neutral treatment; callers pass a tinted pair (e.g.
   * "bg-emerald-500/10 text-emerald-500") to match a card's real
   * direction/severity, same tone convention as valueClassName below. */
  iconClassName?: string;
  /** Instrument-panel top accent (globals.css .weekend-card-accent, same
   * recipe as the existing .card-data treatment elsewhere in the app) —
   * matches each card's own real direction, never a uniform color. */
  accent?: "violet" | "emerald" | "rose";
  label: string;
  value: ReactNode;
  valueClassName?: string;
  /** Smaller sizes let a real (possibly long) opportunity/risk headline
   * wrap to 2-3 lines without overwhelming the fixed-width card — the
   * three numeric cards keep the original large size. */
  valueTextSize?: string;
  caption?: ReactNode;
}) {
  return (
    // Shadow is tinted to the page's own text-primary token at low
    // opacity (not a generic flat black) so it reads correctly in both
    // themes — a considered lift instead of pure border-only flatness.
    // h-full + the grid's items-stretch (WeekendPrimaryMetrics) is what
    // keeps every card in the row — and the hero panel beside them — at
    // the same height regardless of how much real content each one has;
    // this shell must never gain a max-height/overflow cap or that
    // equalization breaks.
    <div
      className="weekend-card-accent flex h-full min-h-[225px] flex-col overflow-hidden rounded-2xl border border-surface-border/7 bg-surface-card p-5 shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]"
      style={{
        // @ts-expect-error -- CSS custom property
        "--card-accent": ACCENT_VAR[accent],
      }}
    >
      <div className="flex items-center gap-2.5">
        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${iconClassName}`}>
          {icon}
        </div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-text-muted">{label}</p>
      </div>
      <p className={`mt-3.5 ${valueTextSize} font-black leading-tight tabular-nums [text-wrap:balance] ${valueClassName}`}>{value}</p>
      {caption && <div className="mt-2.5 flex-1 text-[13px] leading-relaxed text-text-secondary">{caption}</div>}
    </div>
  );
}
