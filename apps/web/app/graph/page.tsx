import type { Metadata } from "next";
import { GraphCanvas } from "./GraphCanvas";

export const metadata: Metadata = {
  title: "Market Intelligence Map · InvestGrids",
  description: "See how today's events ripple through sectors, companies and the market.",
};

export const revalidate = 300;

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TYPE_RANK: Record<string, number> = { event: 4, policy: 3, theme: 2, commodity: 1 };

interface RawNode  { id: string; node_type: string; }
interface RawEdge  { source: string; target: string; }

async function fetchGraph() {
  try {
    const fullRes = await fetch(`${API}/api/graph/full`, { next: { revalidate: 300 } });
    if (!fullRes.ok) return null;
    const full = await fullRes.json() as { nodes: RawNode[]; edges: RawEdge[] };
    if (!full.nodes.length) return null;

    const deg: Record<string, number> = {};
    for (const n of full.nodes) deg[n.id] = 0;
    for (const e of full.edges) {
      deg[e.source] = (deg[e.source] ?? 0) + 1;
      deg[e.target] = (deg[e.target] ?? 0) + 1;
    }

    const pool = full.nodes.filter(n => (deg[n.id] ?? 0) >= 2);
    const candidates = pool.length > 0 ? pool : full.nodes;
    const center = [...candidates].sort((a, b) =>
      ((TYPE_RANK[b.node_type] ?? 0) * 12 + (deg[b.id] ?? 0)) -
      ((TYPE_RANK[a.node_type] ?? 0) * 12 + (deg[a.id] ?? 0))
    )[0];
    if (!center) return full;

    const subRes = await fetch(
      `${API}/api/graph/subgraph/${encodeURIComponent(center.id)}?hops=2`,
      { next: { revalidate: 300 } }
    );
    if (subRes.ok) {
      const sub = await subRes.json() as { nodes: unknown[]; edges: unknown[] };
      if (sub.nodes.length >= 5) return sub;
    }
    return full;
  } catch {
    return null;
  }
}

export default async function GraphPage() {
  const graph = await fetchGraph();
  return <GraphCanvas initialGraph={graph} />;
}
