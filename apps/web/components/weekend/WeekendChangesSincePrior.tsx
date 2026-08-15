import type { WeekendChangeSincePrior } from "@/types/weekendIntelligence";

const TYPE_VERB: Record<string, string> = {
  strengthened: "strengthened",
  weakened: "weakened",
  state_changed: "moved",
  new: "newly appeared",
};

/**
 * Builds clean, user-facing copy from STRUCTURED fields only — the
 * backend's free-text `reason` field is deliberately never read here.
 * It is NOT safe to show verbatim for "strengthened"/"weakened": the
 * backend's own template
 * (changes.py) embeds the raw internal per-sector confidence float
 * transition, e.g. "(0.80 -> 0.65)" — a 0-1 internal score with no
 * explained meaning to a user (not the same scale as the 0-100%
 * production_confidence shown elsewhere on this page), confirmed as a
 * real leak by real local-data verification. "new" and "state_changed"
 * reason strings only ever contain sector/company/state NAMES (verified
 * against the exact backend templates), so those remain safe to show.
 * Rather than trust that invariant to hold silently forever, every
 * change type here is built from STRUCTURED fields
 * (type/entity_id/direction/strength) — reason is not read at all — so
 * a future backend wording change can never reintroduce a raw-number
 * leak here without a corresponding frontend review.
 */
function copyFor(c: WeekendChangeSincePrior): string {
  const verb = TYPE_VERB[c.type] ?? c.type;
  if (c.type === "new" && c.direction) {
    return `${verb} with a ${c.direction} signal`;
  }
  if (c.type === "state_changed" && c.strength) {
    return `state changed (now ${c.strength} strength)`;
  }
  return `signal ${verb}`;
}

/**
 * "Since Our Last Update" — brief §12, a distinct, secondary concept
 * from WeekendChanges: version-to-version drift within the SAME
 * weekend (Saturday v1 -> v2, etc.), not "what's new since Friday".
 * Only rendered when there is a REAL prior version to have changed
 * from (version > 1) — on v1, changes_since_prior is trivially "every
 * top entity is new" (nothing to diff against), which is correct
 * backend behavior but not a meaningful user-facing story, so brief
 * §12 explicitly says not to show this block on v1.
 */
export function WeekendChangesSincePrior({
  changes,
  version,
}: {
  changes: WeekendChangeSincePrior[];
  version: number;
}) {
  if (version <= 1 || changes.length === 0) return null;

  return (
    <section className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <h2 className="mb-3 text-[13px] font-black text-text-primary">Since Our Last Update</h2>
      <ul className="space-y-1.5">
        {changes.slice(0, 8).map((c, i) => (
          <li key={`${c.entity_type}-${c.entity_id}-${i}`} className="text-[12px] leading-relaxed text-text-secondary">
            <span className="font-bold text-text-primary">{c.entity_id}</span> {copyFor(c)}
          </li>
        ))}
      </ul>
    </section>
  );
}
