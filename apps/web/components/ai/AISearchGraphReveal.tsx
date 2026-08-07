"use client";

import { motion } from "framer-motion";

interface RevealGraphNode { id: string; label: string; type: string; x: number; y: number; }
interface RevealGraphEdge { id: string; source: string; target: string; label: string; }

interface Props {
  nodes: RevealGraphNode[];
  edges: RevealGraphEdge[];
  className?: string;
}

// Phase 2A — extended for the deep ripple graph (real macro causal chain
// + companies/competitors/historical/risks/opportunities, see the
// backend's ripple_graph.py). Colors grouped by "kind": macro-chain nodes
// (policy/event/theme/commodity/index/currency) in warm/cool blues-greens,
// entity nodes (sector/company/competitor) in the original palette,
// evidence nodes (historical/risk/opportunity) in amber/rose/emerald so
// they read as "outcomes" at a glance rather than more chain links.
const NODE_COLORS: Record<string, string> = {
  query:       "#a78bfa",
  policy:      "#38bdf8",
  event:       "#38bdf8",
  sector:      "#34d399",
  theme:       "#c084fc",
  commodity:   "#fb923c",
  index:       "#facc15",
  currency:    "#2dd4bf",
  company:     "#818cf8",
  competitor:  "#6366f1",
  historical:  "#94a3b8",
  risk:        "#fb7185",
  opportunity: "#4ade80",
  default:     "rgb(var(--text-muted))",
};

const TYPE_LABELS: Record<string, string> = {
  query: "Query", policy: "Policy", event: "Event", sector: "Sector", theme: "Theme",
  commodity: "Commodity", index: "Index", currency: "Currency", company: "Company",
  competitor: "Competitor", historical: "Historical", risk: "Risk", opportunity: "Opportunity",
};

const GROUP_ORDER: Record<string, number> = {
  query: 0, policy: 1, event: 1, theme: 1, commodity: 1, sector: 2, index: 2, currency: 2,
  company: 3, competitor: 4, historical: 4, risk: 5, opportunity: 5,
};

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

  // Row-ordered reveal (by real Y position, not a hardcoded 3-type list) —
  // the ripple graph can now be 6-7 rows deep with heterogeneous types per
  // row (a "sector" can appear at row 2 in one response and row 4 in
  // another), so staggering by type no longer makes sense; staggering by
  // the backend's own layout row does, and generalizes to any depth.
  const rowOf = (n: RevealGraphNode) => Math.round(n.y / 130);
  const rows = [...new Set(nodes.map(rowOf))].sort((a, b) => a - b);
  const delayOf: Record<string, number> = {};
  for (const n of nodes) {
    const rowIndex = rows.indexOf(rowOf(n));
    const withinRow = nodes.filter(m => rowOf(m) === rowOf(n)).findIndex(m => m.id === n.id);
    delayOf[n.id] = rowIndex * 0.15 + withinRow * 0.05;
  }

  const uniqueTypes = [...new Set(nodes.map(n => n.type))].sort(
    (a, b) => (GROUP_ORDER[a] ?? 9) - (GROUP_ORDER[b] ?? 9)
  );

  return (
    <div className={`rounded-xl border border-[#1e293b] bg-surface-card p-4 ${className}`}>
      <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-text-muted">Intelligence Graph</p>

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
              {/* Phase 1 UI fix #6: was a hardcoded #e2e8f0 (light gray) —
                  readable on this component's own dark card background but
                  near-invisible if that assumption ever breaks, and not a
                  real theme-aware token. rgb(var(--text-primary)) matches
                  the theme-variable pattern this file already uses for
                  NODE_COLORS.default, so labels stay legible in both
                  themes. Truncation loosened (11/16 -> 18/24) — the old
                  limit cut most real company/policy names mid-word. */}
              <text x={p.x} y={p.y + r + 12} textAnchor="middle" fontSize={isQuery ? 9 : 8}
                fontWeight={isQuery ? 600 : 400} fill="rgb(var(--text-primary))" className="select-none">
                {truncate(n.label, isQuery ? 24 : 18)}
              </text>
            </motion.g>
          );
        })}
      </svg>

      {/* Phase 1 UI fix #6: dropped the developer-facing "Nn · Ne" node/edge
          count (raw internal metadata, meaningless to a user) that used to
          sit here. */}
      <div className="mt-1 flex flex-wrap gap-2">
        {uniqueTypes.map(t => (
          <span key={t} className="flex items-center gap-1 text-[10px] text-text-muted">
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: NODE_COLORS[t] || NODE_COLORS.default }} />
            {TYPE_LABELS[t] || t}
          </span>
        ))}
      </div>
    </div>
  );
}
