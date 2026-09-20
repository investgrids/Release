import type { Metadata } from "next";
import { GraphCanvas } from "./GraphCanvas";
import { API_BASE_URL as API } from "@/lib/api";

export const metadata: Metadata = {
  title: "Market Intelligence Map · InvestGrids",
  description: "See how today's events ripple through sectors, companies and the market.",
};

export const revalidate = 300;

// Real production egress finding (2026-09-20): this used to fetch the
// ENTIRE intelligence graph (8.34MB) purely to compute a center node
// client-side, then discard it in ~97% of real cases in favor of a
// 232KB bounded subgraph. The backend now computes the same
// deterministic center choice server-side (against the same cached full
// graph, at zero extra DB/compute cost) via /api/graph/default-subgraph
// and returns only the bounded result -- one request instead of two,
// and the full graph is never transferred to the client at all.
async function fetchGraph() {
  try {
    const res = await fetch(`${API}/api/graph/default-subgraph?hops=2`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    const data = await res.json() as { nodes: unknown[]; edges: unknown[]; center_id: string | null };
    if (!data.nodes?.length) return null;
    return data;
  } catch {
    return null;
  }
}

export default async function GraphPage() {
  const graph = await fetchGraph();
  return (
    // Full-viewport pan/zoom canvas — deliberately breaks out of the root
    // layout's PageContainer (max-w-[1600px] + horizontal padding), which
    // would otherwise squeeze the graph and misalign its viewport-relative
    // overlays. Standard full-bleed break-out: 100vw width, re-centered
    // with a negative margin, independent of the parent's own padding.
    <div className="relative left-1/2 right-1/2 -mx-[50vw] w-screen">
      <GraphCanvas initialGraph={graph} />
    </div>
  );
}
