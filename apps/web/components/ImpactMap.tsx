import Link from "next/link";
import { AlertTriangle, ChevronRight } from "lucide-react";
import { cleanText, isRealSymbol } from "@/lib/text";
import type { DevelopmentImpactV2 } from "@/app/opportunity-radar/[id]/types";

// Evidence-backed Impact Map (2026-09-20 UX integrity fix, replaces the
// V1 bubble/node "Ripple Analysis" graph entirely — not a restyle).
//
// 2026-09-20 canary review follow-up: per-Development attribution is now
// a first-class field computed server-side
// (read_service.py::_build_development_impacts) rather than reconstructed
// here from the pooled `ripple` field. This component just renders what
// it's given — no client-side graph-walking, no risk of this presentation
// logic drifting from what the backend's own tests already verify.
//
// Every row is derived from real graph edges, never a fabricated or
// generic sector/company pairing: app/services/development_memory/
// graph_link.py writes exactly this real vocabulary when a Development
// links to the graph --
//   node_type: "development" | "company" | "sector" | "theme" | "policy"
//   edge_type: "benefits" | "hurts" | "influences" (direction-derived,
//              always development -> target; the reversed "triggered_by"
//              policy -> development edge is excluded server-side)
// Company chips carry the real confirms_thesis/contradicts_thesis signal,
// the same real per-company confirmation already shown in the Companies
// Connected table elsewhere on this page.
type EdgeDirection = "benefits" | "hurts" | "influences";

const DIRECTION_LABEL: Record<EdgeDirection, string> = {
  benefits: "Positive", hurts: "Negative", influences: "Neutral",
};
const DIRECTION_CLASS: Record<EdgeDirection, string> = {
  benefits: "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  hurts: "border-rose-500/30 bg-rose-500/12 text-rose-700 dark:text-rose-300",
  // 2026-09-20 canary review fix: raised from /15+/5 -- read as washed-out,
  // low-contrast on the live canary review.
  influences: "border-surface-border/25 bg-surface-border/10 text-text-primary",
};

// Server-supplied direction is a plain string in the shared V2 type; this
// narrows it defensively rather than trusting it's always one of the 3
// known real values (never crash the page on an unexpected server value).
function directionOrFallback(v: string): EdgeDirection {
  return v === "benefits" || v === "hurts" ? v : "influences";
}

export function ImpactMap({ developmentImpacts }: { developmentImpacts: DevelopmentImpactV2[] }) {
  // Omitted entirely when no evidence-backed relationship exists --
  // never a placeholder or empty table.
  if (developmentImpacts.length === 0) return null;

  return (
    <div className="rounded-[20px] border border-surface-border/10 bg-text-primary/[0.03] p-5">
      <h3 className="text-[13px] font-semibold text-text-primary">Evidence-Backed Impact Map</h3>
      {/* 2026-09-20 canary review fix: a per-catalyst direction (e.g.
          "Benefits") is that ONE development's own real graph edge --
          independent of, and can legitimately differ from, the
          opportunity's overall thesis direction shown in the hero above
          (a majority-vote across every linked development). Shown side by
          side with zero context read as an unexplained contradiction on
          the live canary review -- this line makes the distinction explicit. */}
      <p className="mt-1 mb-4 text-[11px] leading-4 text-text-muted">
        Each row shows one real linked development's own direct effect — this can differ from the opportunity's overall thesis direction above.
      </p>

      {/* Desktop: compact three-column flow with a directional chevron
          between each stage. Mobile: stacked cards (chevrons hidden --
          vertical order already reads as a flow). */}
      <div className="space-y-3">
        {developmentImpacts.map((row) => (
          <div
            key={row.development_id}
            className="grid grid-cols-1 gap-3 rounded-xl border border-surface-border/7 bg-text-primary/[0.02] p-3.5 md:grid-cols-[1.2fr_auto_0.9fr_auto_0.9fr] md:items-center"
          >
            {/* Catalyst */}
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">Catalyst</p>
              <p className="mt-1 line-clamp-2 text-[12.5px] font-semibold text-text-primary">{cleanText(row.canonical_title)}</p>
              <p className="mt-1 text-[10.5px] text-text-muted">
                {row.evidence_count} evidence item{row.evidence_count === 1 ? "" : "s"}
                {row.source_types.length > 0 && ` · ${row.source_types.join(", ")}`}
              </p>
            </div>

            <ChevronRight className="hidden h-4 w-4 shrink-0 text-text-muted/50 md:block" aria-hidden="true" />

            {/* Sector impact */}
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">Sector Impact</p>
              {row.sector_impacts.length === 0 ? (
                <p className="mt-1 text-[11px] text-text-muted">—</p>
              ) : (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {row.sector_impacts.map((s, i) => {
                    const dir = directionOrFallback(s.direction);
                    return (
                      <span key={i} className={`rounded-full border px-2 py-0.5 text-[10.5px] font-semibold ${DIRECTION_CLASS[dir]}`}>
                        {s.sector} · {DIRECTION_LABEL[dir]}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>

            <ChevronRight className="hidden h-4 w-4 shrink-0 text-text-muted/50 md:block" aria-hidden="true" />

            {/* Company impact */}
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">Company Impact</p>
              {row.company_impacts.length === 0 ? (
                <p className="mt-1 text-[11px] text-text-muted">—</p>
              ) : (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {row.company_impacts.map((c) => {
                    const dir = directionOrFallback(c.direction);
                    return (
                      <Link
                        key={c.symbol}
                        href={`/companies/${c.symbol}`}
                        className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold transition hover:opacity-80 ${DIRECTION_CLASS[dir]}`}
                        title={c.contradicts_thesis ? "A real company signal disagrees with this thesis" : undefined}
                      >
                        {c.contradicts_thesis && <AlertTriangle className="h-2.5 w-2.5" />}
                        {isRealSymbol(c.symbol) ? c.symbol : cleanText(c.company_name)}
                        {" · "}
                        {c.contradicts_thesis ? "At Risk" : c.confirms_thesis ? "Benefits" : "Monitor"}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
