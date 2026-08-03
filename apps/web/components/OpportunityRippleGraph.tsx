"use client";

import { motion } from "framer-motion";

interface Node { node_id: string; label: string; node_type: string; }
interface Edge { source: string; target: string; relationship: string; }

const TYPE_COLOR: Record<string, string> = {
  opportunity: "#a78bfa",
  sector: "#34d399",
  company: "#818cf8",
  policy: "#38bdf8",
  concept: "rgb(var(--text-muted))",
};

/**
 * Ripple Analysis (Opportunity Radar 2.0) — renders OpportunityGraphNode/
 * Edge, real pipeline-populated data (verified live: a real opportunity ->
 * sector/company star graph) that existed in the API response all along
 * but was never rendered by any frontend component before this. No
 * coordinates come from the backend (unlike AISearchGraphReveal's ripple
 * data), so this computes its own simple radial layout — center node in
 * the middle, everything else spaced evenly around it — rather than
 * pulling in a full graph-layout library for a handful of nodes.
 */
export function OpportunityRippleGraph({ nodes, edges }: { nodes: Node[]; edges: Edge[] }) {
  if (nodes.length < 2) return null;

  const center = nodes.find(n => n.node_type === "opportunity") ?? nodes[0];
  const outer = nodes.filter(n => n.node_id !== center.node_id);

  const W = 520, H = 320, cx = W / 2, cy = H / 2, r = Math.min(W, H) / 2 - 60;
  const pos = new Map<string, { x: number; y: number }>();
  pos.set(center.node_id, { x: cx, y: cy });
  outer.forEach((n, i) => {
    const angle = (i / outer.length) * 2 * Math.PI - Math.PI / 2;
    pos.set(n.node_id, { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) });
  });

  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-surface-card p-4">
      <p className="mb-2 text-[9px] font-black uppercase tracking-[0.14em] text-text-muted">Ripple Analysis</p>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
        {edges.map((e, i) => {
          const s = pos.get(e.source), t = pos.get(e.target);
          if (!s || !t) return null;
          return (
            <motion.line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y}
              stroke="#334155" strokeWidth={1.2}
              initial={{ opacity: 0 }} animate={{ opacity: 0.5 }}
              transition={{ delay: 0.15 + i * 0.03, duration: 0.3 }} />
          );
        })}
        {[center, ...outer].map((n, i) => {
          const p = pos.get(n.node_id)!;
          const color = TYPE_COLOR[n.node_type] ?? TYPE_COLOR.concept;
          const isCenter = n.node_id === center.node_id;
          const rad = isCenter ? 14 : 8;
          return (
            <motion.g key={n.node_id}
              initial={{ opacity: 0, scale: 0.4 }} animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.05, duration: 0.35, ease: "easeOut" }}
              style={{ transformOrigin: `${p.x}px ${p.y}px` }}>
              <circle cx={p.x} cy={p.y} r={rad + 5} fill={color} fillOpacity={0.15} />
              <circle cx={p.x} cy={p.y} r={rad} fill={color} fillOpacity={0.9} />
              <text x={p.x} y={p.y + rad + 12} textAnchor="middle" fontSize={isCenter ? 10 : 9}
                fontWeight={isCenter ? 700 : 500} fill="#e2e8f0">
                {n.label.length > 16 ? n.label.slice(0, 14) + "…" : n.label}
              </text>
            </motion.g>
          );
        })}
      </svg>
    </div>
  );
}
