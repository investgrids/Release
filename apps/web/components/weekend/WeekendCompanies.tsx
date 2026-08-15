"use client";

import { useState } from "react";
import Link from "next/link";
import type { WeekendCompanyRef } from "@/types/weekendIntelligence";
import { companyStateStyle } from "./weekendLabels";

const INITIAL_VISIBLE = 6;

/**
 * "Companies to Watch" — brief §14. The backend already guarantees
 * every symbol here is a real, tradable, canonical company (Phase 1B's
 * _is_real_symbol filter) — used as-is, no client-side reranking, no
 * BUY/SELL/ACCUMULATE language (backend semantics don't provide that).
 * "Show all" only ever reveals more of the SAME backend-capped list
 * (max 12) — never fetches or fabricates additional entries.
 */
export function WeekendCompanies({ companies }: { companies: WeekendCompanyRef[] }) {
  const [expanded, setExpanded] = useState(false);
  if (companies.length === 0) return null;

  const visible = expanded ? companies : companies.slice(0, INITIAL_VISIBLE);
  const hasMore = companies.length > INITIAL_VISIBLE;

  return (
    <section className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <h2 className="mb-3 text-[13px] font-black text-text-primary">Companies to Watch</h2>
      <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        {visible.map((c) => {
          const style = companyStateStyle(c.state);
          return (
            <li key={c.symbol}>
              <Link
                href={`/companies/${c.symbol}` as any}
                className="group flex items-center justify-between gap-2 rounded-xl border border-surface-border/10 px-3 py-2.5 transition hover:border-violet-400/30"
              >
                <div className="min-w-0">
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
      {hasMore && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-3 text-[11px] font-semibold text-violet-400 transition hover:text-violet-300"
        >
          {expanded ? "Show fewer" : `Show all ${companies.length}`}
        </button>
      )}
    </section>
  );
}
