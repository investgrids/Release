import type { ReactNode } from "react";

/**
 * Shared primary-metric card — Overall Outlook / Confidence / Since Close
 * / Evidence Quality all use this same shell (redesign brief §6: same
 * card style, header row + big value + supporting copy). Purely
 * presentational — every value/caption is passed in by the caller, never
 * computed here, so this component has no opinion about what's real.
 */
export function WeekendMetricCard({
  icon,
  label,
  value,
  valueClassName = "text-text-primary",
  caption,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  valueClassName?: string;
  caption?: ReactNode;
}) {
  return (
    // Shadow is tinted to the page's own text-primary token at low
    // opacity (not a generic flat black) so it reads correctly in both
    // themes — a considered lift instead of pure border-only flatness.
    <div className="flex h-full min-h-[225px] flex-col overflow-hidden rounded-2xl border border-surface-border/7 bg-surface-card p-5 shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]">
      <div className="flex items-center gap-2.5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-surface-border/8 text-text-muted">
          {icon}
        </div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-text-muted">{label}</p>
      </div>
      <p className={`mt-3.5 text-[38px] font-black leading-none tabular-nums [text-wrap:balance] ${valueClassName}`}>{value}</p>
      {caption && <div className="mt-2.5 text-[13px] leading-relaxed text-text-secondary">{caption}</div>}
    </div>
  );
}
