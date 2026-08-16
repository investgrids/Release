import Link from "next/link";
import type { WeekendCompanyRef } from "@/types/weekendIntelligence";
import { companyStateStyle } from "./weekendLabels";

/**
 * "Companies to Watch" — brief §14. The backend already guarantees
 * every symbol here is a real, tradable, canonical company (Phase 1B's
 * _is_real_symbol filter) — used as-is, no client-side reranking, no
 * BUY/SELL/ACCUMULATE language (backend semantics don't provide that).
 * Every real item the backend returned (already ranked, up to its own
 * cap of 12) is rendered — beyond the first ~5 the list scrolls
 * internally within the card's fixed height (owner correction,
 * 2026-08-15) rather than an expand/collapse toggle.
 *
 * Single column, not a 2-up sub-grid: this card sits in the narrow
 * (0.9fr of a 3-column) main-grid slot, where a 2-column split left too
 * little room for the avatar + a real symbol like "BAJFINANCE" + the
 * state chip, truncating the symbol to a single letter — a real bug
 * found during redesign verification. One column per row gives every
 * element room regardless of viewport width, since this card's actual
 * width is set by the outer grid ratio, not the viewport breakpoint a
 * `sm:` class would key off.
 */
export function WeekendCompanies({ companies }: { companies: WeekendCompanyRef[] }) {
  if (companies.length === 0) return null;

  return (
    <section className="flex min-h-[360px] max-h-[400px] flex-col overflow-hidden rounded-2xl border border-surface-border/7 bg-surface-card p-5 shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]">
      <h2 className="mb-3 text-[13px] font-black text-text-primary">Companies to Watch</h2>
      <ul className="flex-1 grid grid-cols-1 gap-2 overflow-y-auto">
        {companies.map((c) => {
          const style = companyStateStyle(c.state);
          return (
            <li key={c.symbol} className="min-h-[58px]">
              <Link
                href={`/companies/${c.symbol}` as any}
                className="group flex h-full items-center gap-2.5 rounded-xl border border-surface-border/10 px-3 py-2 transition duration-200 hover:border-violet-400/30 hover:bg-violet-500/[0.03] active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
              >
                {/* Same TickerAvatar convention as TopMoversSection.tsx —
                    initials, not a fetched external logo (brief §11: use
                    existing initials/avatar treatment). */}
                <div className="flex h-9 w-9 shrink-0 items-center justify-center whitespace-nowrap rounded-full border border-surface-border/10 bg-surface-bg text-[9px] font-bold text-text-secondary">
                  {c.symbol.slice(0, 4)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12px] font-black text-text-primary group-hover:text-violet-300">{c.symbol}</p>
                  <p className="truncate text-[10px] text-text-muted">
                    {c.evidence_count} development{c.evidence_count === 1 ? "" : "s"}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-black ${style.chipClass}`}>
                  <span aria-hidden="true">{style.symbol} </span>{style.label}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
