/**
 * Band — a numbered homepage section (7-band redesign, 2026-11-01).
 *
 * Each band carries its own accent via the `--band-tint` CSS variable (an
 * "R G B" triple). Cards and tinted panels inside the band pick it up through
 * the `.mr-card` / `.band-tint-*` utilities in globals.css, so colour comes
 * from section composition rather than gradients, and the same classes work
 * unchanged in light and dark themes.
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
  index,
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
  index: string;
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
      className={panel ? "rounded-[28px] border band-tint-border band-tint-bg p-4 md:p-7" : undefined}
    >
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-[12px] font-extrabold uppercase tracking-[0.16em]" style={{ color: "rgb(var(--band-tint))" }}>
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: "rgb(var(--band-tint))" }} aria-hidden="true" />
            {eyebrow}
          </p>
          <Heading id={`${id}-title`} className="font-display mt-2 text-[24px] font-extrabold tracking-tight text-text-primary md:text-[30px]">
            {title}
          </Heading>
          {subtitle && <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-text-secondary md:text-[15px]">{subtitle}</p>}
        </div>
        {href && hrefLabel && (
          <Link
            href={href as any}
            className="mr-glass inline-flex items-center gap-1.5 rounded-full border band-tint-border px-4 py-2 text-[13px] font-bold transition hover:-translate-y-0.5"
            style={{ color: "rgb(var(--band-tint))" }}
          >
            {hrefLabel} <span aria-hidden="true">→</span>
          </Link>
        )}
      </header>
      {children}
    </section>
  );
}
