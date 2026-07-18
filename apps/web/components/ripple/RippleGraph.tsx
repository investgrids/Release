"use client";

import "reactflow/dist/style.css";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  MarkerType,
  getBezierPath,
  useNodesState,
  useEdgesState,
  type NodeProps,
  type EdgeProps,
  type Node,
  type Edge,
} from "reactflow";
import { useEffect, useMemo, useCallback } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────
export interface RippleNodeData {
  id: string;
  label: string;
  type: "event" | "commodity" | "sector" | "company" | "currency" | "policy" | "indicator";
  impact: "positive" | "negative" | "neutral" | "mixed";
  impact_strength: number | null;
  depth: number;
  icon: string;
  change_direction: "up" | "down" | "neutral";
  subtitle?: string;
  ticker?: string;
}

export interface RippleEdgeData {
  source: string;
  target: string;
  relationship: string;
  impact_strength: number | null;
  confidence: number | null;
  explanation: string;
  time_horizon: string;
}

// ── Color config ──────────────────────────────────────────────────────────────
const NODE_STYLES: Record<string, { border: string; bg: string; label: string; glow: string }> = {
  event:     { border: "border-indigo-500/60",  bg: "bg-[#1a1040]",  label: "text-indigo-400",  glow: "shadow-indigo-900/40" },
  commodity: { border: "border-amber-500/50",   bg: "bg-[#1a1200]",  label: "text-amber-400",   glow: "shadow-amber-900/30" },
  sector:    { border: "border-sky-500/50",     bg: "bg-[#001a2a]",  label: "text-sky-400",     glow: "shadow-sky-900/30" },
  company:   { border: "border-emerald-500/40", bg: "bg-[#001a10]",  label: "text-emerald-400", glow: "shadow-emerald-900/20" },
  currency:  { border: "border-teal-500/50",    bg: "bg-[#001a1a]",  label: "text-teal-400",    glow: "shadow-teal-900/30" },
  policy:    { border: "border-violet-500/50",  bg: "bg-[#14001a]",  label: "text-violet-400",  glow: "shadow-violet-900/30" },
  indicator: { border: "border-orange-500/40",  bg: "bg-[#1a0d00]",  label: "text-orange-400",  glow: "shadow-orange-900/20" },
};

const IMPACT_COLORS: Record<string, string> = {
  positive: "text-emerald-400",
  negative: "text-rose-400",
  neutral:  "text-slate-400",
  mixed:    "text-amber-400",
};

const EDGE_COLORS: Record<string, string> = {
  causes:     "#475569",
  hurts:      "#f43f5e",
  benefits:   "#10b981",
  influences: "#38bdf8",
  supports:   "#a78bfa",
  risk:       "#f59e0b",
  opportunity:"#22c55e",
};

// ── Layout algorithm ──────────────────────────────────────────────────────────
function computeRadialLayout(
  nodes: RippleNodeData[]
): Record<string, { x: number; y: number }> {
  const RADII: Record<number, number> = { 0: 0, 1: 260, 2: 490, 3: 720, 4: 950 };
  const groups: Record<number, string[]> = {};

  nodes.forEach((n) => {
    const d = n.depth ?? 1;
    groups[d] = groups[d] || [];
    groups[d].push(n.id);
  });

  const pos: Record<string, { x: number; y: number }> = {};
  nodes.forEach((n) => {
    const d = n.depth ?? 1;
    if (d === 0 || n.id === "event_center") {
      pos[n.id] = { x: 0, y: 0 };
      return;
    }
    const radius = RADII[d] ?? d * 240;
    const siblings = groups[d] || [];
    const idx = siblings.indexOf(n.id);
    const total = Math.max(siblings.length, 1);
    // Spread evenly, offset by depth so rings don't overlap
    const startAngle = d % 2 === 0 ? -Math.PI / 4 : -Math.PI / 2;
    const angle = startAngle + (2 * Math.PI * idx) / total;

    // Deterministic jitter based on node ID chars
    let seed = 0;
    for (let i = 0; i < n.id.length; i++) seed += n.id.charCodeAt(i) * (i + 1);
    const jx = ((seed % 50) - 25);
    const jy = (((seed * 17) % 50) - 25);

    pos[n.id] = {
      x: Math.round(Math.cos(angle) * radius + jx),
      y: Math.round(Math.sin(angle) * radius + jy),
    };
  });

  return pos;
}

// ── Custom: Event Center Node ─────────────────────────────────────────────────
function EventCenterNode({ data }: NodeProps<RippleNodeData>) {
  return (
    <div className="relative flex flex-col items-center justify-center rounded-full border-2 border-indigo-500 bg-[#120833] shadow-2xl shadow-indigo-900/60"
      style={{ width: 130, height: 130 }}>
      {/* Pulsing ring */}
      <div className="absolute inset-[-6px] rounded-full border border-indigo-500/20 animate-ping" style={{ animationDuration: "3s" }}/>
      <Handle type="source" position={Position.Top}    className="!opacity-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Left}   className="!opacity-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Right}  className="!opacity-0 !w-1 !h-1" />
      <Handle type="target" position={Position.Top}    className="!opacity-0 !w-1 !h-1" />
      <Handle type="target" position={Position.Bottom} className="!opacity-0 !w-1 !h-1" />
      <Handle type="target" position={Position.Left}   className="!opacity-0 !w-1 !h-1" />
      <Handle type="target" position={Position.Right}  className="!opacity-0 !w-1 !h-1" />
      <span className="text-2xl mb-1 select-none">{data.icon}</span>
      <p className="text-[10px] font-bold text-white text-center leading-snug px-3 line-clamp-2">
        {data.label}
      </p>
      <span className="mt-0.5 text-[9px] text-indigo-300 tabular-nums">{data.subtitle}</span>
    </div>
  );
}

// ── Custom: Standard Ripple Node ──────────────────────────────────────────────
function StandardRippleNode({ data }: NodeProps<RippleNodeData>) {
  const style = NODE_STYLES[data.type] || NODE_STYLES.indicator;
  const impactColor = IMPACT_COLORS[data.impact] || "text-slate-400";
  const arrow = data.change_direction === "up" ? "↑" : data.change_direction === "down" ? "↓" : "→";

  // Company nodes: color by impact
  const borderClass = data.type === "company"
    ? data.impact === "positive" ? "border-emerald-500/50" : "border-rose-500/50"
    : style.border;
  const bgClass = data.type === "company"
    ? data.impact === "positive" ? "bg-[#001a10]" : "bg-[#1a0008]"
    : style.bg;

  return (
    <div className={`relative rounded-xl border ${borderClass} ${bgClass} px-3 py-2.5 min-w-[108px] max-w-[148px]`}>
      <Handle type="target" position={Position.Top}    className="!opacity-0 !w-1 !h-1" />
      <Handle type="target" position={Position.Left}   className="!opacity-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Right}  className="!opacity-0 !w-1 !h-1" />
      <Handle type="target" position={Position.Right}  className="!opacity-0 !w-1 !h-1" />
      <Handle type="source" position={Position.Left}   className="!opacity-0 !w-1 !h-1" />
      {/* Icon + type label */}
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-sm select-none leading-none">{data.icon}</span>
        <span className={`text-[8px] font-bold uppercase tracking-widest ${style.label}`}>
          {data.type}
        </span>
      </div>
      {/* Main label */}
      <p className="text-[11px] font-semibold text-white leading-tight truncate">{data.label}</p>
      {/* Subtitle with direction arrow */}
      {data.subtitle && (
        <p className={`mt-1 text-[10px] font-bold tabular-nums ${impactColor}`}>
          {arrow} {data.subtitle}
        </p>
      )}
      {/* Impact bar — omitted entirely when unscored, rather than drawn at a fabricated midpoint */}
      <div className="mt-2 h-0.5 rounded-full bg-white/5 overflow-hidden">
        {data.impact_strength !== null && data.impact_strength !== undefined && (
          <div
            className={`h-full rounded-full transition-all ${
              data.impact === "positive" ? "bg-emerald-400" :
              data.impact === "negative" ? "bg-rose-400" : "bg-slate-400"
            }`}
            style={{ width: `${data.impact_strength * 100}%` }}
          />
        )}
      </div>
    </div>
  );
}

// ── Custom: Animated Edge ─────────────────────────────────────────────────────
function AnimatedRippleEdge({
  id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition, data,
}: EdgeProps<RippleEdgeData>) {
  const [path] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  const color = EDGE_COLORS[data?.relationship ?? "causes"] || "#475569";

  return (
    <g>
      {/* Base path — faint */}
      <path d={path} fill="none" stroke={color} strokeWidth={1.5} strokeOpacity={0.25} />
      {/* Animated dashes */}
      <path
        id={id}
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeOpacity={0.75}
        strokeDasharray="8 6"
        className="ripple-edge-animate"
      />
      {/* Arrowhead */}
      <defs>
        <marker id={`arrow-${id}`} markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill={color} fillOpacity={0.7} />
        </marker>
      </defs>
      <path d={path} fill="none" stroke="none" markerEnd={`url(#arrow-${id})`} />
    </g>
  );
}

// ── Node + Edge type maps ─────────────────────────────────────────────────────
const NODE_TYPES = {
  "event-center": EventCenterNode,
  "commodity":    StandardRippleNode,
  "sector":       StandardRippleNode,
  "company":      StandardRippleNode,
  "currency":     StandardRippleNode,
  "policy":       StandardRippleNode,
  "indicator":    StandardRippleNode,
  "event":        StandardRippleNode,
};

const EDGE_TYPES = {
  ripple: AnimatedRippleEdge,
};

// ── Depth ring overlay node ───────────────────────────────────────────────────
function DepthRingNode({ data }: NodeProps<{ radius: number; label: string }>) {
  const d = data.radius * 2;
  return (
    <div style={{ width: d, height: d, marginLeft: -data.radius, marginTop: -data.radius }}
      className="pointer-events-none select-none">
      <div className="absolute inset-0 rounded-full border border-white/[0.04]" />
      <span className="absolute top-2 left-1/2 -translate-x-1/2 text-[9px] text-slate-600 whitespace-nowrap">
        {data.label}
      </span>
    </div>
  );
}

// ── Main RippleGraph component ────────────────────────────────────────────────
interface RippleGraphProps {
  graphData: { nodes: RippleNodeData[]; edges: RippleEdgeData[] };
  depthFilter?: number | null;   // null = show all
  selectedNodeId?: string | null;
  onNodeClick?: (node: RippleNodeData) => void;
}

export function RippleGraph({
  graphData,
  depthFilter = null,
  selectedNodeId,
  onNodeClick,
}: RippleGraphProps) {
  const { nodes: rawNodes, edges: rawEdges } = graphData;

  // Filter by depth
  const visibleNodes = useMemo(() => {
    if (!depthFilter) return rawNodes;
    const center = rawNodes.find(n => n.id === "event_center");
    const filtered = rawNodes.filter(n => (n.depth ?? 1) <= depthFilter || n.id === "event_center");
    return filtered;
  }, [rawNodes, depthFilter]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map(n => n.id)), [visibleNodes]);

  const positions = useMemo(() => computeRadialLayout(rawNodes), [rawNodes]);

  // Build ReactFlow nodes
  const rfNodes: Node[] = useMemo(() => {
    // Depth rings as background nodes
    const rings: Node[] = [
      { id: "ring-1", type: "depthRing" as any, position: { x: 0, y: 0 }, data: { radius: 260, label: "Direct Impact · 0-7 Days" }, draggable: false, selectable: false, zIndex: -1 },
      { id: "ring-2", type: "depthRing" as any, position: { x: 0, y: 0 }, data: { radius: 490, label: "Indirect Impact · 1-4 Weeks" }, draggable: false, selectable: false, zIndex: -1 },
      { id: "ring-3", type: "depthRing" as any, position: { x: 0, y: 0 }, data: { radius: 720, label: "Long-term Impact · 1-6 Months" }, draggable: false, selectable: false, zIndex: -1 },
    ];

    const dataNodes: Node[] = visibleNodes.map((n) => ({
      id: n.id,
      type: n.id === "event_center" ? "event-center" : n.type,
      position: positions[n.id] || { x: 0, y: 0 },
      data: n,
      selected: n.id === selectedNodeId,
    }));

    return [...rings, ...dataNodes];
  }, [visibleNodes, positions, selectedNodeId]);

  // Build ReactFlow edges
  const rfEdges: Edge[] = useMemo(() => {
    return (rawEdges || [])
      .filter(e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
      .map((e, i) => ({
        id: `e-${i}`,
        source: e.source,
        target: e.target,
        type: "ripple",
        data: e,
        animated: false,
      }));
  }, [rawEdges, visibleNodeIds]);

  const [nodes, setNodes, onNodesChange] = useNodesState(rfNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(rfEdges);

  // Sync when upstream data changes
  useEffect(() => { setNodes(rfNodes); }, [rfNodes, setNodes]);
  useEffect(() => { setEdges(rfEdges); }, [rfEdges, setEdges]);

  const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.data && onNodeClick) onNodeClick(node.data as RippleNodeData);
  }, [onNodeClick]);

  const fullNodeTypes = useMemo(() => ({
    ...NODE_TYPES,
    depthRing: DepthRingNode as any,
  }), []);

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        nodeTypes={fullNodeTypes}
        edgeTypes={EDGE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.15, includeHiddenNodes: false }}
        minZoom={0.2}
        maxZoom={2.5}
        defaultEdgeOptions={{ type: "ripple" }}
      >
        <Background color="#0d111d" gap={32} size={1} />
        <Controls
          style={{
            background: "rgba(10,13,24,0.95)",
            border: "1px solid rgba(255,255,255,0.07)",
            borderRadius: 10,
          }}
          showInteractive={false}
        />
        <MiniMap
          nodeColor={(node) => {
            if (node.type === "event-center") return "#6366f1";
            const d = (node.data as any);
            if (d?.impact === "positive") return "#10b981";
            if (d?.impact === "negative") return "#f43f5e";
            if (d?.impact === "mixed")    return "#f59e0b";
            return "#334155";
          }}
          maskColor="rgba(6,9,18,0.85)"
          style={{
            background: "rgba(10,13,24,0.95)",
            border: "1px solid rgba(255,255,255,0.07)",
            borderRadius: 10,
          }}
          pannable
          zoomable
        />
      </ReactFlow>
    </div>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────────
export function RippleLegend() {
  const impacts = [
    { color: "bg-emerald-400", label: "Positive Impact" },
    { color: "bg-rose-400",    label: "Negative Impact" },
    { color: "bg-amber-400",   label: "Mixed Impact" },
    { color: "bg-slate-400",   label: "Neutral" },
  ];
  const relations = [
    { color: "bg-sky-400",     label: "Causes / Influences" },
    { color: "bg-rose-400",    label: "Hurts" },
    { color: "bg-emerald-400", label: "Benefits" },
    { color: "bg-violet-400",  label: "Supports" },
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 px-4 py-2.5 border-t border-white/[0.05]">
      {impacts.map(i => (
        <span key={i.label} className="flex items-center gap-1.5 text-[10px] text-slate-500">
          <span className={`h-2 w-2 rounded-full ${i.color}`} />
          {i.label}
        </span>
      ))}
      <span className="text-slate-700">·</span>
      {relations.map(r => (
        <span key={r.label} className="flex items-center gap-1.5 text-[10px] text-slate-500">
          <span className={`h-0.5 w-4 ${r.color} opacity-70`} />
          {r.label}
        </span>
      ))}
    </div>
  );
}
