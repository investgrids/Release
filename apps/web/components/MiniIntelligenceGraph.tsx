"use client";

import { useEffect, useRef, useState } from "react";

interface GraphNode {
  id: string;
  label: string;
  node_type: string;
  ticker?: string;
  score?: number;
}
interface GraphEdge {
  source: string;
  target: string;
  edge_type: string;
  strength?: number;
}
interface SubgraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const NODE_COLORS: Record<string, string> = {
  company:   "#818cf8",
  sector:    "#34d399",
  theme:     "#fb923c",
  macro:     "#f472b6",
  commodity: "#facc15",
  currency:  "#38bdf8",
  index:     "#a78bfa",
  policy:    "#f87171",
  event:     "#94a3b8",
  default:   "#64748b",
};

const TYPE_LABELS: Record<string, string> = {
  company:   "Company",
  sector:    "Sector",
  theme:     "Theme",
  macro:     "Macro",
  commodity: "Commodity",
  currency:  "Currency",
  index:     "Index",
  policy:    "Policy",
};

function truncate(s: string, n: number) {
  return s && s.length > n ? s.slice(0, n) + "…" : (s || "");
}

/** Build node ID from type + label, mirroring backend make_node_id() */
function makeNodeId(nodeType: string, label: string): string {
  const slug = label.toLowerCase().replace(/[^\w]+/g, "-").replace(/^-|-$/g, "");
  return `${nodeType}:${slug}`;
}

interface Props {
  /** Pre-formed node ID like "company:reliance" or "sector:banking" */
  nodeId: string;
  /** Human-readable title for the widget header */
  title?: string;
  className?: string;
}

export default function MiniIntelligenceGraph({ nodeId, title = "Intelligence Graph", className = "" }: Props) {
  const [data, setData] = useState<SubgraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);

  const API = process.env.NEXT_PUBLIC_API_URL || "";

  useEffect(() => {
    if (!nodeId) return;
    setLoading(true);
    setError(false);
    fetch(`${API}/api/graph/subgraph/${encodeURIComponent(nodeId)}?hops=2`)
      .then((r) => {
        if (!r.ok) throw new Error("not ok");
        return r.json();
      })
      .then((d: SubgraphData) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, [nodeId, API]);

  if (loading) {
    return (
      <div className={`rounded-xl border border-[#1e293b] bg-[#0f172a] p-4 ${className}`}>
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">{title}</p>
        <div className="flex items-center justify-center h-36 gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: "0ms" }} />
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: "120ms" }} />
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: "240ms" }} />
        </div>
      </div>
    );
  }

  if (error || !data || data.nodes.length < 2) return null;

  // Radial layout
  const W = 280, H = 190;
  const cx = W / 2, cy = H / 2 - 8;
  const r = 72;

  const center = data.nodes.find((n) => n.id === nodeId) || data.nodes[0];
  const others = data.nodes.filter((n) => n.id !== center.id).slice(0, 8);

  const positions: Record<string, { x: number; y: number }> = {};
  positions[center.id] = { x: cx, y: cy };
  others.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / others.length - Math.PI / 2;
    positions[n.id] = {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  });

  const uniqueTypes = [...new Set(data.nodes.map((n) => n.node_type))].slice(0, 4);

  return (
    <div className={`rounded-xl border border-[#1e293b] bg-[#0f172a] p-4 ${className}`}>
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-1">{title}</p>

      <svg
        ref={svgRef}
        width="100%"
        viewBox={`0 0 ${W} ${H}`}
        className="overflow-visible"
        aria-label="Intelligence graph showing entity relationships"
      >
        {/* Edges */}
        {data.edges.map((e, i) => {
          const s = positions[e.source];
          const t = positions[e.target];
          if (!s || !t) return null;
          const opacity = Math.max(0.15, Math.min(0.5, (e.strength ?? 0.5) * 0.6));
          return (
            <line
              key={i}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke="#334155"
              strokeWidth={1.2}
              strokeOpacity={opacity}
            />
          );
        })}

        {/* Satellite nodes */}
        {others.map((n) => {
          const pos = positions[n.id];
          if (!pos) return null;
          const color = NODE_COLORS[n.node_type] || NODE_COLORS.default;
          return (
            <g key={n.id}>
              <circle cx={pos.x} cy={pos.y} r={9} fill={color} fillOpacity={0.25} />
              <circle cx={pos.x} cy={pos.y} r={6} fill={color} fillOpacity={0.7} />
              <text
                x={pos.x}
                y={pos.y + 18}
                textAnchor="middle"
                fontSize={8}
                fill="#94a3b8"
                className="select-none"
              >
                {truncate(n.label, 11)}
              </text>
            </g>
          );
        })}

        {/* Center node */}
        {(() => {
          const color = NODE_COLORS[center.node_type] || NODE_COLORS.default;
          return (
            <g>
              <circle cx={cx} cy={cy} r={22} fill={color} fillOpacity={0.12} />
              <circle cx={cx} cy={cy} r={15} fill={color} fillOpacity={0.85} />
              <text
                x={cx}
                y={cy + 30}
                textAnchor="middle"
                fontSize={9}
                fill="#e2e8f0"
                fontWeight="600"
                className="select-none"
              >
                {truncate(center.label, 13)}
              </text>
            </g>
          );
        })()}
      </svg>

      {/* Legend + stats */}
      <div className="mt-1 flex items-center justify-between">
        <div className="flex gap-2 flex-wrap">
          {uniqueTypes.map((t) => (
            <span key={t} className="flex items-center gap-1 text-[10px] text-slate-500">
              <span
                className="inline-block w-1.5 h-1.5 rounded-full"
                style={{ background: NODE_COLORS[t] || NODE_COLORS.default }}
              />
              {TYPE_LABELS[t] || t}
            </span>
          ))}
        </div>
        <span className="text-[10px] text-slate-600">
          {data.nodes.length}n · {data.edges.length}e
        </span>
      </div>
    </div>
  );
}
