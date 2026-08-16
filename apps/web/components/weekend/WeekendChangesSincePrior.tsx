"use client";

import { useState } from "react";
import type { WeekendChangeSincePrior } from "@/types/weekendIntelligence";
import { sectorDirectionStyle } from "./weekendLabels";

const VISIBLE_LIMIT = 3;

const TYPE_VERB: Record<string, string> = {
  strengthened: "strengthened",
  weakened: "weakened",
  state_changed: "moved",
  new: "newly appeared",
};

/**
 * Short compact copy for the strip row, built from STRUCTURED fields
 * only — the backend's free-text `reason` field is deliberately never
 * read here. It is NOT safe to show verbatim for "strengthened"/
 * "weakened": the backend's own template (changes.py) embeds the raw
 * internal per-sector confidence float transition, e.g. "(0.80 -> 0.65)"
 * — a 0-1 internal score with no explained meaning to a user, confirmed
 * as a real leak by real local-data verification. Every change type here
 * is built from structured fields (type/entity_id/direction/strength) —
 * reason is not read at all — so a future backend wording change can
 * never reintroduce a raw-number leak here without a corresponding
 * frontend review.
 */
function shortCopyFor(c: WeekendChangeSincePrior): string {
  if (c.type === "new" && c.direction) {
    const style = sectorDirectionStyle(c.direction);
    return `turned ${style.label.toLowerCase()}`;
  }
  const verb = TYPE_VERB[c.type] ?? c.type;
  return verb;
}

/**
 * "Since Our Last Update" — a distinct, secondary concept from
 * WeekendChanges: version-to-version drift within the SAME weekend
 * (Saturday v1 -> v2, etc.), not "what's new since Friday". Only
 * rendered when there is a REAL prior version to have changed from
 * (version > 1) — on v1, changes_since_prior is trivially "every top
 * entity is new" (nothing to diff against), not a meaningful user-facing
 * story.
 *
 * Redesign correction (2026-08-15, owner feedback): this used to be a
 * full-width panel listing up to 8 rows, dominating the page between
 * the metadata strip and the primary intelligence grid. It is secondary
 * information, not a primary dashboard band — now a compact strip
 * capped at 3 items with a "View details" expand for the rest, entirely
 * in-place (same bounded `changes` array, never fetches more).
 */
export function WeekendChangesSincePrior({
  changes,
  version,
}: {
  changes: WeekendChangeSincePrior[];
  version: number;
}) {
  const [expanded, setExpanded] = useState(false);
  if (version <= 1 || changes.length === 0) return null;

  const visible = expanded ? changes : changes.slice(0, VISIBLE_LIMIT);
  const hasMore = changes.length > VISIBLE_LIMIT;

  return (
    <section className="flex flex-wrap items-center gap-x-5 gap-y-1.5 rounded-xl border border-surface-border/7 bg-surface-card px-4 py-3 text-[12px] sm:px-5">
      <h2 className="text-[11px] font-bold uppercase tracking-wide text-text-muted">Since Our Last Update</h2>
      {visible.map((c, i) => {
        const style = c.direction ? sectorDirectionStyle(c.direction) : null;
        return (
          <span key={`${c.entity_type}-${c.entity_id}-${i}`} className="text-text-secondary">
            <span className="font-bold text-text-primary">{c.entity_id}</span>{" "}
            {style && <span aria-hidden="true" className={style.textClass}>{style.symbol} </span>}
            {shortCopyFor(c)}
          </span>
        );
      })}
      {hasMore && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="ml-auto shrink-0 rounded font-semibold text-violet-500 transition duration-200 hover:text-violet-400 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
        >
          {expanded ? "Show fewer" : "View details →"}
        </button>
      )}
    </section>
  );
}
