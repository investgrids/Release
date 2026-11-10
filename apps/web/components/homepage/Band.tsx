/**
 * Band — a homepage section (7-band redesign, 2026-11-01).
 *
 * Each band carries its own accent via the `--band-tint` CSS variable (an
 * "R G B" triple). Cards and tinted panels inside the band pick it up through
 * the `.mr-card` / `.band-tint-*` utilities in globals.css, so colour comes
 * from section composition rather than gradients, and the same classes work
 * unchanged in light and dark themes.
 *
 * Header typography deliberately matches the rest of the site (2026-11-10,
 * owner feedback: the oversized display headings made the homepage look
 * unlike the header, footer and inner pages): 11px muted eyebrow, 19px bold
 * Geist title, plain "View all" style link — the same scale /events and
 * /newsroom use for their section headings.
 */
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

// 600-level shades: readable as text on white, legible on the dark surface,
// and strong enough as bar/badge fills behind white text.
export const BAND = {
  sky: "2 132 199",
  amber: "217 119 6",
  violet: "99 102 241",
  emerald: "5 150 105",
  cyan: "8 145 178",
  rose: "225 29 72",
} as const;

export function Band({
  id,
  eyebrow,
  title,
  subtitle,
  href,
  hrefLabel,
  tint,
  panel = false,
  headingLevel = "h2",
  children,
}: {
  id: string;
  /** Kept for call-site compatibility; section numbers are no longer shown. */
  index?: string;
  eyebrow: string;
  title: string;
  subtitle?: string;
  href?: string;
  hrefLabel?: string;
  tint: string;
  panel?: boolean;
  /** Exactly one band per page should pass "h1". */
  headingLevel?: "h1" | "h2";
  children: ReactNode;
}) {
  const Heading = headingLevel;
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      style={{ "--band-tint": tint } as CSSProperties}
      className={panel ? "rounded-2xl border band-tint-border band-tint-bg p-4 md:p-5" : undefined}
    >
      <header className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: "rgb(var(--band-tint))" }} aria-hidden="true" />
            {eyebrow}
          </p>
          <Heading
            id={`${id}-title`}
            className={`mt-1 font-bold tracking-tight text-text-primary ${headingLevel === "h1" ? "text-[20px] md:text-[22px]" : "text-[17px] md:text-[19px]"}`}
          >
            {title}
          </Heading>
          {subtitle && <p className="mt-0.5 max-w-2xl text-[13px] leading-relaxed text-text-muted">{subtitle}</p>}
        </div>
        {href && hrefLabel && (
          <Link
            href={href as any}
            className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-accent-violet transition hover:underline"
          >
            {hrefLabel} <span aria-hidden="true">→</span>
          </Link>
        )}
      </header>
      {children}
    </section>
  );
}
