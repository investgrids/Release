import Link from "next/link";
import { AlertTriangle, ChevronRight } from "lucide-react";
import { cleanText, isRealSymbol } from "@/lib/text";
import type {
  RippleV2, SupportingEvidenceV2, CompanyConnectedV2,
} from "@/app/opportunity-radar/[id]/types";

// Evidence-backed Impact Map (2026-09-20 UX integrity fix, replaces the
// V1 bubble/node "Ripple Analysis" graph entirely — not a restyle).
//
// Every row here is derived from real graph edges, never a fabricated or
// generic sector/company pairing: app/services/development_memory/
// graph_link.py writes exactly this real vocabulary when a Development
// links to the graph --
//   node_type: "development" | "company" | "sector" | "theme" | "policy"
//   edge_type: "benefits" | "hurts" | "influences" (direction-derived,
//              always development -> target; a reversed "triggered_by"
//              policy -> development edge exists too but is deliberately
//              excluded below, since that's a different relationship
//              shape than "this development impacts this sector/company")
// A row's Catalyst is one linked Development (real canonical_title/
// evidence_count/first_observed_at/source_types from supporting_evidence);
// its Sector/Company impact chips are only the real sector/company nodes
// that Development has an ACTUAL graph edge to, with the edge's own real
// direction -- never every sector/company the opportunity happens to
// mention. Company chips also carry the real confirms_thesis/
// contradicts_thesis signal from companies_connected (matched by ticker),
// the same real per-company confirmation already shown in the Companies
// Connected table elsewhere on this page.
type EdgeDirection = "benefits" | "hurts" | "influences";

interface ImpactMapRow {
  developmentId: string;
  catalyst: string;
  evidenceCount: number;
  firstObservedAt: string | null;
  sourceTypes: string[];
  sectorImpacts: { sector: string; direction: EdgeDirection }[];
  companyImpacts: {
    symbol: string; companyName: string; direction: EdgeDirection;
    confirms: boolean; contradicts: boolean;
  }[];
}

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

function isEdgeDirection(v: string): v is EdgeDirection {
  return v === "benefits" || v === "hurts" || v === "influences";
}

function buildRows(
  ripple: RippleV2,
  supportingEvidence: SupportingEvidenceV2[],
  companiesConnected: CompanyConnectedV2[],
): ImpactMapRow[] {
  const nodesById = new Map(ripple.nodes.map((n) => [n.id, n]));
  const companyBySymbol = new Map(companiesConnected.map((c) => [c.symbol, c]));
  const rows: ImpactMapRow[] = [];

  for (const dev of supportingEvidence) {
    const devNodeId = `development:${dev.development_id}`;
    if (!nodesById.has(devNodeId)) continue; // no real graph presence for this Development -- nothing to show

    const sectorImpacts: ImpactMapRow["sectorImpacts"] = [];
    const companyImpacts: ImpactMapRow["companyImpacts"] = [];

    for (const edge of ripple.edges) {
      if (edge.source !== devNodeId) continue; // only real outgoing impact edges, never the reversed policy->development ones
      if (!isEdgeDirection(edge.edge_type)) continue;
      const target = nodesById.get(edge.target);
      if (!target) continue;

      if (target.node_type === "sector") {
        sectorImpacts.push({ sector: target.label, direction: edge.edge_type });
      } else if (target.node_type === "company" && target.ticker) {
        const real = companyBySymbol.get(target.ticker);
        companyImpacts.push({
          symbol: target.ticker,
          companyName: real?.company_name ?? target.label,
          direction: edge.edge_type,
          confirms: real?.confirms_thesis ?? false,
          contradicts: real?.contradicts_thesis ?? false,
        });
      }
    }

    if (sectorImpacts.length === 0 && companyImpacts.length === 0) continue; // never an empty row
    rows.push({
      developmentId: dev.development_id,
      catalyst: dev.canonical_title,
      evidenceCount: dev.evidence_count,
      firstObservedAt: dev.first_observed_at,
      sourceTypes: dev.source_types,
      sectorImpacts,
      companyImpacts,
    });
  }

  return rows;
}

export function ImpactMap({ ripple, supportingEvidence, companiesConnected }: {
  ripple: RippleV2; supportingEvidence: SupportingEvidenceV2[]; companiesConnected: CompanyConnectedV2[];
}) {
  const rows = buildRows(ripple, supportingEvidence, companiesConnected);
  // Omitted entirely when no evidence-backed relationship exists --
  // never a placeholder or empty table.
  if (rows.length === 0) return null;

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
        {rows.map((row) => (
          <div
            key={row.developmentId}
            className="grid grid-cols-1 gap-3 rounded-xl border border-surface-border/7 bg-text-primary/[0.02] p-3.5 md:grid-cols-[1.2fr_auto_0.9fr_auto_0.9fr] md:items-center"
          >
            {/* Catalyst */}
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">Catalyst</p>
              <p className="mt-1 line-clamp-2 text-[12.5px] font-semibold text-text-primary">{cleanText(row.catalyst)}</p>
              <p className="mt-1 text-[10.5px] text-text-muted">
                {row.evidenceCount} evidence item{row.evidenceCount === 1 ? "" : "s"}
                {row.sourceTypes.length > 0 && ` · ${row.sourceTypes.join(", ")}`}
              </p>
            </div>

            <ChevronRight className="hidden h-4 w-4 shrink-0 text-text-muted/50 md:block" aria-hidden="true" />

            {/* Sector impact */}
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">Sector Impact</p>
              {row.sectorImpacts.length === 0 ? (
                <p className="mt-1 text-[11px] text-text-muted">—</p>
              ) : (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {row.sectorImpacts.map((s, i) => (
                    <span key={i} className={`rounded-full border px-2 py-0.5 text-[10.5px] font-semibold ${DIRECTION_CLASS[s.direction]}`}>
                      {s.sector} · {DIRECTION_LABEL[s.direction]}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <ChevronRight className="hidden h-4 w-4 shrink-0 text-text-muted/50 md:block" aria-hidden="true" />

            {/* Company impact */}
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">Company Impact</p>
              {row.companyImpacts.length === 0 ? (
                <p className="mt-1 text-[11px] text-text-muted">—</p>
              ) : (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {row.companyImpacts.map((c) => (
                    <Link
                      key={c.symbol}
                      href={`/companies/${c.symbol}`}
                      className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold transition hover:opacity-80 ${DIRECTION_CLASS[c.direction]}`}
                      title={c.contradicts ? "A real company signal disagrees with this thesis" : undefined}
                    >
                      {c.contradicts && <AlertTriangle className="h-2.5 w-2.5" />}
                      {isRealSymbol(c.symbol) ? c.symbol : cleanText(c.companyName)}
                      {" · "}
                      {c.contradicts ? "At Risk" : c.confirms ? "Benefits" : "Monitor"}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
