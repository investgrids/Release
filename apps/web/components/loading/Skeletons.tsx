/**
 * Shared, presentation-only loading-skeleton primitives for `loading.tsx`
 * files (2026-08 site-wide loading-state pass — see
 * apps/web/app/loadingSafety.test.ts for the safety rule these are only
 * ever placed under).
 *
 * Deliberately dumb: no data fetching, no client state, no animation
 * beyond the existing `animate-pulse` utility already used for every other
 * skeleton in this app (globals.css) — reused here rather than inventing a
 * second shimmer/pulse language. Every block below is sized to roughly the
 * real content it stands in for, so mounting/unmounting causes minimal
 * layout shift once real content replaces it.
 */

function Block({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-text-primary/[0.05] ${className}`} />;
}

/** A single card in a headline/summary card list — newsroom sub-pages, search, market-signals. */
export function SkelCard() {
  return (
    <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-4">
      <Block className="h-3 w-20 rounded-full" />
      <Block className="mt-3 h-4 w-[85%]" />
      <Block className="mt-2 h-4 w-[60%]" />
      <Block className="mt-3 h-3 w-full" />
      <Block className="mt-1.5 h-3 w-[70%]" />
    </div>
  );
}

/** A page built around a repeated card list — the most common shape on this site. */
export function CardListSkeleton({ cards = 6, columns = 2 }: { cards?: number; columns?: 1 | 2 | 3 }) {
  const colClass = columns === 3 ? "sm:grid-cols-2 lg:grid-cols-3" : columns === 2 ? "sm:grid-cols-2" : "";
  return (
    <div className="py-6">
      <Block className="h-3 w-32 rounded-full" />
      <Block className="mt-3 h-7 w-72" />
      <Block className="mt-2 h-4 w-96 max-w-full" />
      <div className={`mt-6 grid grid-cols-1 gap-4 ${colClass}`}>
        {Array.from({ length: cards }, (_, i) => <SkelCard key={i} />)}
      </div>
    </div>
  );
}

/** A long-form prose/section page — the Knowledge pages. */
export function ProseSkeleton() {
  return (
    <div className="mx-auto max-w-3xl py-8">
      <Block className="h-3 w-24 rounded-full" />
      <Block className="mt-3 h-9 w-[80%]" />
      <Block className="mt-2 h-9 w-[55%]" />
      <Block className="mt-4 h-4 w-full" />
      <Block className="mt-1.5 h-4 w-[92%]" />
      <Block className="mt-1.5 h-4 w-[75%]" />
      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="rounded-2xl border border-surface-border/7 p-4">
            <Block className="h-8 w-8 rounded-full" />
            <Block className="mt-3 h-4 w-[70%]" />
            <Block className="mt-1.5 h-3 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** A hero + form page — Tools / Portfolio Confidence. */
export function ToolFormSkeleton() {
  return (
    <div className="mx-auto max-w-3xl py-8">
      <Block className="h-3 w-28 rounded-full" />
      <Block className="mt-3 h-8 w-[70%]" />
      <Block className="mt-2 h-4 w-[90%]" />
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => <Block key={i} className="h-20" />)}
      </div>
      <Block className="mt-8 h-40 w-full rounded-2xl" />
    </div>
  );
}

/** A single, large full-bleed visualization area — the Graph page. */
export function CanvasSkeleton() {
  return (
    <div className="flex h-[70vh] min-h-[420px] items-center justify-center">
      <Block className="h-full w-full rounded-2xl" />
    </div>
  );
}
