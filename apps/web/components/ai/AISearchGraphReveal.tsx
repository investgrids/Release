"use client";

import { motion } from "framer-motion";

interface RevealGraphNode { id: string; label: string; type: string; x: number; y: number; }
interface RevealGraphEdge { id: string; source: string; target: string; label: string; }

interface Props {
  nodes: RevealGraphNode[];
  edges: RevealGraphEdge[];
  className?: string;
}

const NODE_COLORS: Record<string, string> = {
  query:   "#a78bfa",
  sector:  "#34d399",
  company: "#818cf8",
  default: "#64748b",
};

const TYPE_LABELS: Record<string, string> = {
  query:   "Query",
  sector:  "Sector",
  company: "Company",
};

const GROUP_ORDER: Record<string, number> = { query: 0, sector: 1, company: 2 };

function truncate(s: string, n: number) {
  return s && s.length > n ? s.slice(0, n) + "…" : (s || "");
}

/**
 * Animates the AI search response's own graph.nodes/edges into place —
 * real data that already exists on every response but, before this
 * component, was only ever surfaced as a numeric "N nodes" stat. Trusts
 * the backend-provided x/y (unlike MiniIntelligenceGraph, which computes a
 * radial layout client-side because its data has no coordinates) and only
 * normalizes them into an SVG viewBox.
 */
export function AISearchGraphReveal({ nodes, edges, className = "" }: Props) {
  if (nodes.length < 2) return null;

  const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const PAD = 30;
  const W = (maxX - minX) + PAD * 2 || 280;
  const H = (maxY - minY) + PAD * 2 || 160;
  const pos = (n: RevealGraphNode) => ({ x: n.x - minX + PAD, y: n.y - minY + PAD });

  // Group-ordered reveal: query first, then sectors, then companies.
  const byGroup: Record<string, RevealGraphNode[]> = { query: [], sector: [], company: [] };
  for (const n of nodes) (byGroup[n.type] ?? (byGroup[n.type] = [])).push(n);

  const delayOf: Record<string, number> = {};
  (byGroup.query ?? []).forEach(n => { delayOf[n.id] = 0; });
  (byGroup.sector ?? []).forEach((n, i) => { delayOf[n.id] = 0.15 + i * 0.06; });
  (byGroup.company ?? []).forEach((n, i) => { delayOf[n.id] = 0.35 + i * 0.05; });

  const uniqueTypes = [...new Set(nodes.map(n => n.type))].sort(
    (a, b) => (GROUP_ORDER[a] ?? 9) - (GROUP_ORDER[b] ?? 9)
  );

  return (
    <div className={`rounded-xl border border-[#1e293b] bg-[#0f172a] p-4 ${className}`}>
      <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-500">Intelligence Graph</p>

      <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible" aria-label="Intelligence graph of this search's findings">
        {edges.map((e) => {
          const s = nodes.find(n => n.id === e.source);
          const t = nodes.find(n => n.id === e.target);
          if (!s || !t) return null;
          const sp = pos(s), tp = pos(t);
          const edgeDelay = Math.max(delayOf[s.id] ?? 0, delayOf[t.id] ?? 0) + 0.12;
          return (
            <motion.line key={e.id} x1={sp.x} y1={sp.y} x2={tp.x} y2={tp.y}
              stroke="#334155" strokeWidth={1.2}
              initial={{ opacity: 0 }} animate={{ opacity: 0.4 }}
              transition={{ delay: edgeDelay, duration: 0.25 }} />
          );
        })}

        {nodes.map((n) => {
          const p = pos(n);
          const color = NODE_COLORS[n.type] || NODE_COLORS.default;
          const isQuery = n.type === "query";
          const r = isQuery ? 15 : 8;
          return (
            <motion.g key={n.id}
              initial={{ opacity: 0, scale: 0.3 }} animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: delayOf[n.id] ?? 0, duration: 0.35, ease: "easeOut" }}
              style={{ transformOrigin: `${p.x}px ${p.y}px` }}>
              <circle cx={p.x} cy={p.y} r={r + 6} fill={color} fillOpacity={0.15} />
              <circle cx={p.x} cy={p.y} r={r} fill={color} fillOpacity={0.85} />
              <text x={p.x} y={p.y + r + 12} textAnchor="middle" fontSize={isQuery ? 9 : 8}
                fontWeight={isQuery ? 600 : 400} fill="#e2e8f0" className="select-none">
                {truncate(n.label, isQuery ? 16 : 11)}
              </text>
            </motion.g>
          );
        })}
      </svg>

      <div className="mt-1 flex items-center justify-between">
        <div className="flex flex-wrap gap-2">
          {uniqueTypes.map(t => (
            <span key={t} className="flex items-center gap-1 text-[10px] text-slate-500">
              <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: NODE_COLORS[t] || NODE_COLORS.default }} />
              {TYPE_LABELS[t] || t}
            </span>
          ))}
        </div>
        <span className="text-[10px] text-slate-600">{nodes.length}n · {edges.length}e</span>
      </div>
    </div>
  );
}
