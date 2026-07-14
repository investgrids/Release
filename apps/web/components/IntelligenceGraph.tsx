"use client";

import "reactflow/dist/style.css";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background, BackgroundVariant, MiniMap,
  Node, Edge, Handle, MarkerType,
  NodeProps, NodeTypes, Position,
  useEdgesState, useNodesState, useReactFlow,
  ReactFlowProvider, BaseEdge, EdgeLabelRenderer,
  getBezierPath, type EdgeProps,
} from "reactflow";
import {
  Search, Share2, Download, RefreshCw, HelpCircle, X,
  Zap, Building2, BarChart2,
  Network, Briefcase, BookOpen, ChevronRight, Plus, Minus,
  Maximize2,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────
interface RawNode {
  id: string; node_type: string; label: string;
  ticker?: string; description?: string;
  extra?: Record<string, unknown>; auto_added?: boolean;
}
interface RawEdge {
  id: string; source: string; target: string;
  edge_type: string; weight: number; confidence: number;
  lag_days?: number; description?: string;
  source_event?: string; auto_added?: boolean;
}
interface GraphData { nodes: RawNode[]; edges: RawEdge[]; }
interface RippleImpact {
  node: RawNode; depth: number;
  impact_direction: "positive" | "negative" | "uncertain";
  accumulated_weight: number; edge_type: string; lag_days: number;
  description?: string;
}
interface RippleResult {
  source: RawNode; change: string;
  total_impacted: number; impacts: RippleImpact[];
}
interface IGNodeData {
  raw: RawNode; selected: boolean;
  rippleDir?: "positive" | "negative" | "uncertain";
  rippleWeight?: number; isSource?: boolean; isDimmed: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ─── Design constants ─────────────────────────────────────────────────────────
const NODE_META: Record<string, { border: string; bg: string; iconBg: string; text: string; icon: string; label: string; darkBg: string }> = {
  commodity: { border: "#f97316", bg: "rgba(249,115,22,0.09)", iconBg: "rgba(249,115,22,0.18)", text: "#fdba74", icon: "🛢",  label: "Commodity", darkBg: "#1a0d02" },
  sector:    { border: "#22c55e", bg: "rgba(34,197,94,0.07)",  iconBg: "rgba(34,197,94,0.18)",  text: "#86efac", icon: "📊",  label: "Sector",    darkBg: "#021a0a" },
  theme:     { border: "#8b5cf6", bg: "rgba(139,92,246,0.09)", iconBg: "rgba(139,92,246,0.18)", text: "#c4b5fd", icon: "💡",  label: "Theme",     darkBg: "#0f0a1e" },
  event:     { border: "#f59e0b", bg: "rgba(245,158,11,0.09)", iconBg: "rgba(245,158,11,0.18)", text: "#fcd34d", icon: "⚡",  label: "Event",     darkBg: "#1a1002" },
  policy:    { border: "#7c3aed", bg: "rgba(124,58,237,0.12)", iconBg: "rgba(124,58,237,0.25)", text: "#c4b5fd", icon: "🏛",  label: "Policy",    darkBg: "#150c30" },
  country:   { border: "#f43f5e", bg: "rgba(244,63,94,0.08)",  iconBg: "rgba(244,63,94,0.18)",  text: "#fda4af", icon: "🌍",  label: "Country",   darkBg: "#1a0208" },
  index:     { border: "#06b6d4", bg: "rgba(6,182,212,0.08)",  iconBg: "rgba(6,182,212,0.18)",  text: "#67e8f9", icon: "📈",  label: "Index",     darkBg: "#021218" },
  currency:  { border: "#84cc16", bg: "rgba(132,204,22,0.08)", iconBg: "rgba(132,204,22,0.18)", text: "#bef264", icon: "💱",  label: "Currency",  darkBg: "#0a1202" },
  company:   { border: "#6366f1", bg: "rgba(99,102,241,0.09)", iconBg: "rgba(99,102,241,0.18)", text: "#a5b4fc", icon: "🏢",  label: "Company",   darkBg: "#080a1e" },
};

const EDGE_META: Record<string, { color: string; label: string; positive: boolean }> = {
  benefits:      { color: "#22c55e", label: "Benefits",      positive: true  },
  hurts:         { color: "#ef4444", label: "Hurts",         positive: false },
  supplies:      { color: "#f97316", label: "Supplies",      positive: true  },
  depends_on:    { color: "#60a5fa", label: "Depends On",    positive: true  },
  competes_with: { color: "#a78bfa", label: "Competes With", positive: false },
  influences:    { color: "#64748b", label: "Influences",    positive: true  },
  triggered_by:  { color: "#fbbf24", label: "Triggered By",  positive: true  },
};

const TYPE_CLUSTER: Record<string, { x: number; y: number }> = {
  commodity: { x: 0, y: -700 }, theme: { x: 700, y: -400 },
  country:   { x: 1000, y: 0 }, index: { x: 700, y: 400 },
  currency:  { x: 0, y: 700 },  policy: { x: -800, y: 350 },
  sector:    { x: -750, y: -200 }, company: { x: -350, y: -650 },
  event:     { x: 200, y: 0 },
};

const FILTER_TABS = ["All", "Events", "Sectors", "Companies", "Themes", "Macro", "Commodities", "Geography"];


// ─── Layout ───────────────────────────────────────────────────────────────────
function computeInitialPositions(nodes: RawNode[]): Map<string, { x: number; y: number }> {
  const groups: Record<string, string[]> = {};
  for (const n of nodes) (groups[n.node_type] ??= []).push(n.id);
  const pos = new Map<string, { x: number; y: number }>();
  for (const [type, ids] of Object.entries(groups)) {
    const center = TYPE_CLUSTER[type] ?? { x: 0, y: 0 };
    ids.forEach((id, i) => {
      if (ids.length === 1) { pos.set(id, { ...center }); return; }
      const angle  = (i / ids.length) * 2 * Math.PI - Math.PI / 2;
      const radius = Math.min(40 + ids.length * 22, 200);
      pos.set(id, { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius });
    });
  }
  return pos;
}

// ─── Strength label helper ────────────────────────────────────────────────────
function strengthLabel(weight: number, positive: boolean): string {
  const abs = Math.abs(weight);
  const prefix = positive ? "+" : "−";
  const desc = abs >= 0.8 ? "Strong" : abs >= 0.5 ? "Moderate" : "Mild";
  return `${desc} ${prefix}${abs.toFixed(2)}`;
}

// ─── Custom edge ──────────────────────────────────────────────────────────────
function LabeledEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd, style }: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style}/>
      {data?.showLabel && (
        <EdgeLabelRenderer>
          <div style={{
            position: "absolute",
            transform: `translate(-50%,-50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: "none", textAlign: "center",
          }}>
            <p style={{ fontSize: 9, color: "#cbd5e1", fontWeight: 600, lineHeight: 1.3, textShadow: "0 1px 6px rgba(0,0,0,0.95)" }}>{data.label}</p>
            <p style={{ fontSize: 9, fontWeight: 800, lineHeight: 1.3, textShadow: "0 1px 6px rgba(0,0,0,0.95)", color: data.color }}>{data.sublabel}</p>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
const edgeTypes = { labeledEdge: LabeledEdge };

// ─── Custom node ──────────────────────────────────────────────────────────────
const IGNodeComponent = memo(({ data, selected }: NodeProps<IGNodeData>) => {
  const meta = NODE_META[data.raw.node_type] ?? NODE_META.sector;
  let borderColor = meta.border;
  let glow = "none";
  if (data.isSource) {
    borderColor = "#f59e0b";
    glow = "0 0 0 3px rgba(245,158,11,0.3), 0 0 20px rgba(245,158,11,0.2)";
  } else if (data.rippleDir === "positive") {
    borderColor = "#22c55e";
    glow = "0 0 0 2px rgba(34,197,94,0.25), 0 0 12px rgba(34,197,94,0.15)";
  } else if (data.rippleDir === "negative") {
    borderColor = "#ef4444";
    glow = "0 0 0 2px rgba(239,68,68,0.25), 0 0 12px rgba(239,68,68,0.15)";
  } else if (selected) {
    glow = `0 0 0 2.5px ${meta.border}50, 0 0 16px ${meta.border}20`;
  }

  return (
    <div style={{ opacity: data.isDimmed ? 0.18 : 1, transition: "opacity 0.25s" }}>
      <Handle type="target" position={Position.Top}    style={{ opacity: 0, width: 6, height: 6 }}/>
      <Handle type="target" position={Position.Left}   style={{ opacity: 0, width: 6, height: 6 }}/>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, width: 6, height: 6 }}/>
      <Handle type="source" position={Position.Right}  style={{ opacity: 0, width: 6, height: 6 }}/>
      <div style={{
        background: `linear-gradient(135deg, ${meta.darkBg} 0%, ${meta.bg.replace("0.09","0.12")} 100%)`,
        border: `1.5px solid ${borderColor}`,
        borderRadius: 13, padding: "9px 13px",
        minWidth: 150, maxWidth: 190,
        boxShadow: glow, transition: "box-shadow 0.2s, border-color 0.2s",
        cursor: "pointer",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ background: meta.iconBg, borderRadius: 8, padding: "5px 6px", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <span style={{ fontSize: 12, lineHeight: 1 }}>{meta.icon}</span>
          </div>
          <div style={{ minWidth: 0 }}>
            <p style={{ fontSize: 11.5, fontWeight: 700, color: "#f1f5f9", lineHeight: 1.25, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 118 }}>
              {data.raw.label}
            </p>
            {data.raw.ticker && (
              <p style={{ fontSize: 9.5, color: meta.text, marginTop: 1.5, opacity: 0.8 }}>{data.raw.ticker}</p>
            )}
          </div>
        </div>
        {data.rippleDir && data.rippleWeight !== undefined && (
          <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 5, paddingTop: 5, borderTop: `1px solid ${borderColor}25` }}>
            <span style={{ fontSize: 10, color: data.rippleDir === "positive" ? "#22c55e" : data.rippleDir === "negative" ? "#ef4444" : "#f59e0b", fontWeight: 800 }}>
              {data.rippleDir === "positive" ? "▲" : data.rippleDir === "negative" ? "▼" : "~"}
            </span>
            <span style={{ fontSize: 10, color: "#94a3b8", fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>
              {(data.rippleWeight * 100).toFixed(0)}% impact
            </span>
          </div>
        )}
      </div>
    </div>
  );
});
IGNodeComponent.displayName = "IGNodeComponent";
const nodeTypes: NodeTypes = { igNode: IGNodeComponent };

// ─── Edge builder ─────────────────────────────────────────────────────────────
function buildEdges(
  raw: RawEdge[], rippleEdgeKeys: Set<string>, hasRipple: boolean,
  selectedId: string | null, visibleTypes: Set<string>,
): Edge[] {
  const adjacentToSelected = new Set<string>();
  if (selectedId) {
    for (const e of raw) {
      if (e.source === selectedId || e.target === selectedId) {
        adjacentToSelected.add(e.source); adjacentToSelected.add(e.target);
      }
    }
  }
  return raw.filter(e => visibleTypes.has(e.edge_type)).map(e => {
    const ekey      = `${e.source}|${e.edge_type}|${e.target}`;
    const isRipple  = rippleEdgeKeys.has(ekey);
    const isAdj     = !!selectedId && (e.source === selectedId || e.target === selectedId);
    const isDimmed  = hasRipple && !isRipple;
    const meta      = EDGE_META[e.edge_type] ?? { color: "#475569", label: e.edge_type, positive: true };
    const color     = isRipple ? meta.color : isDimmed ? "#1a2235" : `${meta.color}70`;
    return {
      id: e.id, source: e.source, target: e.target,
      type: "labeledEdge",
      animated: isRipple,
      style: { stroke: color, strokeWidth: isRipple ? 2.5 : 1.5, opacity: isDimmed ? 0.12 : 0.9 },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
      data: {
        label: meta.label,
        sublabel: strengthLabel(e.weight, meta.positive),
        color: meta.color,
        showLabel: isRipple || isAdj,
      },
    } as Edge;
  });
}

// ─── Right detail panel ───────────────────────────────────────────────────────
function NodeDetailPanel({ node, neighbours, ripple, rippleLoading, onRipple, onClearRipple, onClose, onSelectNode }: {
  node: RawNode;
  neighbours: { out: Array<{ edge: RawEdge; node: RawNode }>; in: Array<{ edge: RawEdge; node: RawNode }> };
  ripple: RippleResult | null;
  rippleLoading: boolean;
  onRipple: (c: "rise" | "fall" | "shock") => void;
  onClearRipple: () => void;
  onClose: () => void;
  onSelectNode: (n: RawNode) => void;
}) {
  const meta = NODE_META[node.node_type] ?? NODE_META.sector;

  // Derived impact score from connection weights
  const allConns = [...neighbours.out, ...neighbours.in];
  const impactScore = allConns.length > 0
    ? Math.min(10, (allConns.reduce((s, c) => s + Math.abs(c.edge.weight), 0) / allConns.length) * 10 + 4).toFixed(1)
    : "6.0";
  const confidence = allConns.length > 0
    ? Math.round(60 + allConns.reduce((s,c) => s + c.edge.confidence, 0) / allConns.length * 40)
    : 70;

  const descStr = node.description ?? "This node is connected to multiple market entities and plays a role in the broader market intelligence graph.";

  return (
    <div style={{ width: 320, flexShrink: 0, height: "100%", display: "flex", flexDirection: "column", borderLeft: "1px solid rgba(255,255,255,0.06)", background: "#080c18", overflowY: "auto" }}>

      {/* Header */}
      <div style={{ padding: "16px 16px 12px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
          <button onClick={onClose} style={{ background: "rgba(255,255,255,0.06)", border: "none", borderRadius: 8, width: 27, height: 27, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "#475569" }}>
            <X width={13} height={13}/>
          </button>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 12 }}>
          <div style={{ width: 42, height: 42, borderRadius: 11, background: meta.iconBg, border: `1.5px solid ${meta.border}`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 18 }}>
            {meta.icon}
          </div>
          <div>
            <h2 style={{ fontSize: 13.5, fontWeight: 800, color: "#fff", lineHeight: 1.35, margin: 0 }}>{node.label}{node.ticker ? ` (${node.ticker})` : ""}</h2>
            <p style={{ fontSize: 10.5, color: "#475569", marginTop: 3 }}>{meta.label}</p>
          </div>
        </div>
        <span style={{ display: "inline-flex", padding: "3px 10px", borderRadius: 999, fontSize: 10, fontWeight: 700, background: `${meta.border}18`, color: meta.text, border: `1px solid ${meta.border}30` }}>
          {allConns.length >= 5 ? "High Impact" : allConns.length >= 3 ? "Medium Impact" : "Connected"} Node
        </span>
      </div>

      {/* Content */}
      <div style={{ padding: "14px 16px", flex: 1, display: "flex", flexDirection: "column", gap: 14 }}>

        {/* AI Summary */}
        <div>
          <p style={{ fontSize: 10, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>AI Summary</p>
          <p style={{ fontSize: 11.5, color: "#94a3b8", lineHeight: 1.65 }}>{descStr}</p>
        </div>

        {/* Impact Score */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 7 }}>
            <p style={{ fontSize: 10, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.07em" }}>Impact Score</p>
            <span style={{ fontSize: 21, fontWeight: 900, color: "#22c55e" }}>{impactScore}<span style={{ fontSize: 11, color: "#334155", fontWeight: 500 }}>/10</span></span>
          </div>
          <div style={{ height: 5, borderRadius: 999, background: "rgba(255,255,255,0.07)", overflow: "hidden" }}>
            <div style={{ height: "100%", borderRadius: 999, background: `linear-gradient(90deg, ${meta.border}, #22c55e)`, width: `${parseFloat(impactScore) * 10}%`, transition: "width 0.6s" }}/>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 7 }}>
            <div>
              <p style={{ fontSize: 9.5, color: "#334155" }}>Confidence</p>
              <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b" }}>{confidence >= 80 ? "High" : confidence >= 65 ? "Moderate" : "Low"} ({confidence}%)</p>
            </div>
            <div style={{ textAlign: "right" }}>
              <p style={{ fontSize: 9.5, color: "#334155" }}>Connections</p>
              <p style={{ fontSize: 11, fontWeight: 700, color: "#64748b" }}>{allConns.length} direct</p>
            </div>
          </div>
        </div>

        {/* Key Connections */}
        {allConns.length > 0 && (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 8 }}>
              <Network width={11} height={11} style={{ color: "#475569" }}/>
              <p style={{ fontSize: 10, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.07em" }}>Key Connections</p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {[...neighbours.out.slice(0,3), ...neighbours.in.slice(0,2)].map(({ edge, node: n }) => {
                const em = EDGE_META[edge.edge_type] ?? { color: "#475569", label: edge.edge_type, positive: true };
                const nm = NODE_META[n.node_type] ?? NODE_META.sector;
                return (
                  <button key={edge.id} onClick={() => onSelectNode(n)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", cursor: "pointer", textAlign: "left", width: "100%" }}>
                    <span style={{ fontSize: 13 }}>{nm.icon}</span>
                    <p style={{ fontSize: 11.5, color: "#e2e8f0", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{n.label}</p>
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                      <p style={{ fontSize: 9.5, color: "#475569" }}>{em.label}</p>
                      <p style={{ fontSize: 10.5, fontWeight: 800, color: em.color }}>{em.positive ? "+" : "−"}{edge.weight.toFixed(2)}</p>
                    </div>
                  </button>
                );
              })}
            </div>
            <button style={{ marginTop: 8, fontSize: 11, color: "#a78bfa", background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 4, padding: 0 }}>
              View all {allConns.length} connections <ChevronRight width={11} height={11}/>
            </button>
          </div>
        )}

        {/* Ripple simulation */}
        <div style={{ borderRadius: 14, border: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)", padding: "13px 14px" }}>
          <p style={{ fontSize: 10, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 5 }}>Trace Market Ripple</p>
          <p style={{ fontSize: 11, color: "#334155", lineHeight: 1.55, marginBottom: 10 }}>Simulate a price shock and trace all downstream impacts.</p>
          <div style={{ display: "flex", gap: 6 }}>
            {(["rise", "fall", "shock"] as const).map(c => (
              <button key={c} onClick={() => onRipple(c)} disabled={rippleLoading}
                style={{
                  flex: 1, padding: "7px 0", borderRadius: 9, fontSize: 11, fontWeight: 700, cursor: "pointer",
                  background: c === "rise" ? "rgba(34,197,94,0.12)" : c === "fall" ? "rgba(239,68,68,0.12)" : "rgba(245,158,11,0.12)",
                  border: c === "rise" ? "1px solid rgba(34,197,94,0.3)" : c === "fall" ? "1px solid rgba(239,68,68,0.3)" : "1px solid rgba(245,158,11,0.3)",
                  color: c === "rise" ? "#22c55e" : c === "fall" ? "#ef4444" : "#f59e0b",
                  opacity: rippleLoading ? 0.5 : 1,
                }}>
                {rippleLoading ? "…" : c === "rise" ? "▲ Rise" : c === "fall" ? "▼ Fall" : "⚡ Shock"}
              </button>
            ))}
          </div>
          {ripple && (
            <div style={{ marginTop: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 11, color: "#64748b" }}>{ripple.total_impacted} entities impacted</span>
              <button onClick={onClearRipple} style={{ fontSize: 10, color: "#475569", background: "none", border: "none", cursor: "pointer" }}>Clear ×</button>
            </div>
          )}
        </div>

        {/* Ripple impacts */}
        {ripple && ripple.impacts.length > 0 && (
          <div>
            <p style={{ fontSize: 10, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 7 }}>
              Impact Cascade · {ripple.change}
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {ripple.impacts.slice(0, 15).map((imp, i) => {
                const nm = NODE_META[imp.node.node_type] ?? NODE_META.sector;
                const isPos = imp.impact_direction === "positive";
                const isNeg = imp.impact_direction === "negative";
                return (
                  <button key={imp.node.id} onClick={() => onSelectNode(imp.node)}
                    style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", borderRadius: 10, cursor: "pointer", textAlign: "left", width: "100%", background: "rgba(255,255,255,0.015)", border: `1px solid ${isPos ? "rgba(34,197,94,0.14)" : isNeg ? "rgba(239,68,68,0.14)" : "rgba(245,158,11,0.1)"}` }}>
                    <span style={{ fontSize: 10, color: "#334155", width: 16, textAlign: "right" }}>{i+1}</span>
                    <span style={{ fontSize: 12 }}>{nm.icon}</span>
                    <span style={{ flex: 1, fontSize: 11, color: "#cbd5e1", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{imp.node.label}</span>
                    <div style={{ flexShrink: 0, textAlign: "right" }}>
                      <p style={{ fontSize: 11, fontWeight: 800, color: isPos ? "#22c55e" : isNeg ? "#ef4444" : "#f59e0b" }}>
                        {isPos ? "▲" : isNeg ? "▼" : "~"} {(imp.accumulated_weight * 100).toFixed(0)}%
                      </p>
                      {imp.lag_days > 0 && <p style={{ fontSize: 9, color: "#334155" }}>+{imp.lag_days}d</p>}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Custom zoom controls ─────────────────────────────────────────────────────
function CustomControls() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const btn = { width: 30, height: 30, borderRadius: 8, background: "rgba(15,20,35,0.95)", border: "1px solid rgba(255,255,255,0.1)", cursor: "pointer", color: "#64748b", display: "flex", alignItems: "center", justifyContent: "center", padding: 0 } as const;
  return (
    <div style={{ position: "absolute", left: 14, top: 14, display: "flex", flexDirection: "column", gap: 5, zIndex: 5 }}>
      <button style={btn} onClick={() => zoomIn({ duration: 200 })}><Plus width={13} height={13}/></button>
      <button style={btn} onClick={() => zoomOut({ duration: 200 })}><Minus width={13} height={13}/></button>
      <button style={btn} onClick={() => fitView({ padding: 0.15, duration: 400 })}><Maximize2 width={12} height={12}/></button>
      <button style={{ ...btn, marginTop: 2, cursor: "default" }}>
        <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      </button>
    </div>
  );
}

// ─── Main inner graph ─────────────────────────────────────────────────────────
function GraphInner({ initialGraph }: { initialGraph: GraphData | null }) {
  const empty: GraphData = { nodes: [], edges: [] };
  const [graphData, setGraphData]       = useState<GraphData>(initialGraph ?? empty);
  const [nodes, setNodes, onNodesChange] = useNodesState<IGNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode]  = useState<RawNode | null>(null);
  const [ripple, setRipple]              = useState<RippleResult | null>(null);
  const [rippleLoading, setRippleLoading]= useState(false);
  const [activeFilter, setActiveFilter]  = useState("All");
  const [search, setSearch]              = useState("");
  const [nifty, setNifty]                = useState<{ value: string; change: string; positive: boolean } | null>(null);
  const [visibleNodeTypes, setVisibleNodeTypes] = useState<Set<string>>(() => new Set(Object.keys(NODE_META)));
  const [visibleEdgeTypes, setVisibleEdgeTypes] = useState<Set<string>>(() => new Set(Object.keys(EDGE_META)));
  const posRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  const { fitView } = useReactFlow();

  // Fetch Nifty
  useEffect(() => {
    fetch(`${API_BASE}/api/indices/`)
      .then(r => r.ok ? r.json() : null)
      .then((d: any[] | null) => {
        const idx = d?.find((i: any) => /nifty 50/i.test(i.title ?? i.name ?? ""));
        if (idx) setNifty({ value: idx.value, change: idx.change, positive: idx.positive !== false });
      }).catch(() => {});
  }, []);

  // Filter tab → node type visibility
  useEffect(() => {
    const map: Record<string, string[]> = {
      All:         Object.keys(NODE_META),
      Events:      ["event"],
      Sectors:     ["sector"],
      Companies:   ["company"],
      Themes:      ["theme"],
      Macro:       ["index", "country"],
      Commodities: ["commodity", "currency"],
      Geography:   ["country"],
    };
    setVisibleNodeTypes(new Set(map[activeFilter] ?? Object.keys(NODE_META)));
  }, [activeFilter]);

  // Ripple state
  const rippleNodeMap = useMemo<Map<string, RippleImpact>>(() => {
    if (!ripple) return new Map();
    const m = new Map<string, RippleImpact>();
    for (const imp of ripple.impacts) m.set(imp.node.id, imp);
    return m;
  }, [ripple]);

  const rippleEdgeKeys = useMemo<Set<string>>(() => {
    if (!ripple) return new Set();
    const s = new Set<string>();
    for (const imp of ripple.impacts) {
      for (const seg of (imp as any).path ?? []) s.add(`${seg.from}|${seg.edge_type}|${seg.to}`);
    }
    return s;
  }, [ripple]);

  // Rebuild graph
  useEffect(() => {
    const searchLow = search.toLowerCase();
    const newPos = computeInitialPositions(graphData.nodes);
    newPos.forEach((p, id) => { if (!posRef.current.has(id)) posRef.current.set(id, p); });
    const hasRipple = rippleNodeMap.size > 0;
    const rfNodes: Node<IGNodeData>[] = graphData.nodes.filter(n => visibleNodeTypes.has(n.node_type)).map(n => {
      const pos    = posRef.current.get(n.id) ?? { x: 0, y: 0 };
      const imp    = rippleNodeMap.get(n.id);
      const match  = searchLow ? n.label.toLowerCase().includes(searchLow) : true;
      const isDimmed = (hasRipple && !imp && n.id !== ripple?.source?.id) || (!!searchLow && !match);
      return { id: n.id, type: "igNode", position: pos, data: { raw: n, selected: selectedNode?.id === n.id, rippleDir: imp?.impact_direction, rippleWeight: imp?.accumulated_weight, isSource: n.id === ripple?.source?.id, isDimmed }, draggable: true };
    });
    setNodes(rfNodes);
    setEdges(buildEdges(graphData.edges, rippleEdgeKeys, hasRipple, selectedNode?.id ?? null, visibleEdgeTypes));
  }, [graphData, visibleNodeTypes, visibleEdgeTypes, rippleNodeMap, rippleEdgeKeys, ripple, selectedNode, search]);

  // Auto-refresh
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/graph/full`);
        if (!res.ok) return;
        const fresh: GraphData = await res.json();
        setGraphData(prev => (fresh.nodes.length !== prev.nodes.length || fresh.edges.length !== prev.edges.length) ? fresh : prev);
      } catch { /**/ }
    }, 90_000);
    return () => clearInterval(id);
  }, []);

  // Handlers
  const handleNodeClick = useCallback((_: any, node: Node<IGNodeData>) => {
    const raw = graphData.nodes.find(n => n.id === node.id) ?? null;
    setSelectedNode(prev => prev?.id === node.id ? null : raw);
    if (!raw || raw.id !== selectedNode?.id) setRipple(null);
  }, [graphData.nodes, selectedNode]);

  const handleNodeDragStop = useCallback((_: any, node: Node) => {
    posRef.current.set(node.id, node.position);
  }, []);

  const handleRipple = useCallback(async (change: "rise" | "fall" | "shock") => {
    if (!selectedNode) return;
    setRippleLoading(true); setRipple(null);
    try {
      const res = await fetch(`${API_BASE}/api/graph/ripple/${encodeURIComponent(selectedNode.id)}?change=${change}&max_depth=5`);
      if (res.ok) setRipple(await res.json());
    } catch { /**/ }
    finally { setRippleLoading(false); }
  }, [selectedNode]);

  // Neighbours
  const neighbours = useMemo(() => {
    if (!selectedNode) return { out: [] as Array<{ edge: RawEdge; node: RawNode }>, in: [] as Array<{ edge: RawEdge; node: RawNode }> };
    const nMap = new Map(graphData.nodes.map(n => [n.id, n]));
    return {
      out: graphData.edges.filter(e => e.source === selectedNode.id).map(e => ({ edge: e, node: nMap.get(e.target)! })).filter(x => x.node),
      in:  graphData.edges.filter(e => e.target === selectedNode.id).map(e => ({ edge: e, node: nMap.get(e.source)! })).filter(x => x.node),
    };
  }, [selectedNode, graphData]);

  // Stats
  const stats = useMemo(() => {
    const byType: Record<string, number> = {};
    for (const n of graphData.nodes) byType[n.node_type] = (byType[n.node_type] ?? 0) + 1;
    return { total: graphData.nodes.length, edges: graphData.edges.length, byType };
  }, [graphData]);

  const statRows = [
    { label: "Events",            value: stats.byType.event   ?? 0, icon: Zap },
    { label: "Sectors",           value: stats.byType.sector  ?? 0, icon: Building2 },
    { label: "Companies",         value: stats.byType.company ?? 0, icon: Briefcase },
    { label: "Themes",            value: stats.byType.theme   ?? 0, icon: BookOpen },
    { label: "Macro",             value: (stats.byType.index ?? 0) + (stats.byType.country ?? 0), icon: BarChart2 },
    { label: "Total Connections", value: stats.edges,               icon: Network },
  ];

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 100, display: "flex", background: "#080c18" }}>

      {/* Main area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>

        {/* Top bar */}
        <div style={{ flexShrink: 0, borderBottom: "1px solid rgba(255,255,255,0.06)", background: "#080c18" }}>
          <div style={{ display: "flex", alignItems: "center", padding: "10px 18px", gap: 10 }}>
            {/* Breadcrumb + title */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 3 }}>
                <span style={{ fontSize: 10.5, color: "#334155" }}>Knowledge Graph</span>
                <ChevronRight width={10} height={10} style={{ color: "#1e2a3a" }}/>
                <span style={{ fontSize: 10.5, color: "#475569" }}>Intelligence Graph</span>
              </div>
              <h1 style={{ fontSize: 18, fontWeight: 900, color: "#fff", lineHeight: 1, margin: 0 }}>Intelligence Graph</h1>
              <p style={{ fontSize: 10.5, color: "#334155", marginTop: 3 }}>Explore how events, sectors, companies and themes are connected and influence each other.</p>
            </div>

            {/* Search */}
            <div style={{ display: "flex", alignItems: "center", gap: 7, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)", borderRadius: 11, padding: "6px 11px", width: 250 }}>
              <Search width={13} height={13} style={{ color: "#475569", flexShrink: 0 }}/>
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search nodes (e.g. RBI, Oil, HDFC Bank)"
                style={{ flex: 1, background: "none", border: "none", outline: "none", fontSize: 11, color: "#e2e8f0" }}/>
              <kbd style={{ fontSize: 9, color: "#334155", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 4, padding: "1px 5px" }}>⌘K</kbd>
            </div>

            {/* Date + actions */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <p style={{ fontSize: 10.5, color: "#334155" }}>
                  {new Date().toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })} · {new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} IST
                </p>
                <RefreshCw width={12} height={12} style={{ color: "#334155", cursor: "pointer" }}
                  onClick={() => fetch(`${API_BASE}/api/graph/full`).then(r => r.json()).then(d => setGraphData(d)).catch(() => {})}/>
              </div>
              {[{ label: "Share", icon: <Share2 width={11} height={11}/> }, { label: "Export", icon: <Download width={11} height={11}/> }].map(b => (
                <button key={b.label} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 11px", borderRadius: 9, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)", cursor: "pointer", color: "#64748b", fontSize: 11, fontWeight: 600 }}>
                  {b.icon}{b.label}
                </button>
              ))}
              {/* Nifty live price */}
              {nifty && (
                <div style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 9, padding: "5px 10px" }}>
                  <p style={{ fontSize: 9.5, color: "#475569", fontWeight: 700 }}>NIFTY 50</p>
                  <p style={{ fontSize: 12, fontWeight: 900, color: "#fff" }}>{nifty.value}</p>
                  <p style={{ fontSize: 10.5, fontWeight: 700, color: nifty.positive ? "#22c55e" : "#ef4444" }}>{nifty.change}</p>
                </div>
              )}
            </div>
          </div>

          {/* Filter tabs */}
          <div style={{ display: "flex", alignItems: "center", padding: "0 18px 9px", gap: 5 }}>
            {FILTER_TABS.map(tab => (
              <button key={tab} onClick={() => setActiveFilter(tab)} style={{
                padding: "5px 13px", borderRadius: 999, border: "1px solid",
                fontSize: 11, fontWeight: 600, cursor: "pointer", transition: "all 0.15s",
                background: activeFilter === tab ? "rgba(124,58,237,0.2)" : "rgba(255,255,255,0.04)",
                color: activeFilter === tab ? "#c4b5fd" : "#475569",
                borderColor: activeFilter === tab ? "rgba(124,58,237,0.45)" : "rgba(255,255,255,0.07)",
              }}>{tab}</button>
            ))}
            <button style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4, fontSize: 10.5, color: "#334155", background: "none", border: "none", cursor: "pointer" }}>
              <HelpCircle width={11} height={11}/>How to read this graph?
            </button>
          </div>

          {/* Legend */}
          <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "0 18px 9px" }}>
            {[{ dot: "#22c55e", label: "Positive Influence" }, { dot: "#ef4444", label: "Negative Influence" }, { dot: "#475569", label: "Neutral Influence" }].map(l => (
              <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <div style={{ width: 7, height: 7, borderRadius: "50%", background: l.dot }}/>
                <span style={{ fontSize: 10.5, color: "#475569" }}>{l.label}</span>
              </div>
            ))}
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <svg width={22} height={7}><line x1={0} y1={3.5} x2={22} y2={3.5} stroke="#334155" strokeWidth={1.5} strokeDasharray="4 3"/></svg>
              <span style={{ fontSize: 10.5, color: "#475569" }}>Related</span>
            </div>
          </div>
        </div>

        {/* Graph canvas */}
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick} onNodeDragStop={handleNodeDragStop}
            onPaneClick={() => { setSelectedNode(null); setRipple(null); }}
            nodeTypes={nodeTypes} edgeTypes={edgeTypes}
            fitView fitViewOptions={{ padding: 0.15 }}
            minZoom={0.06} maxZoom={2.5}
            style={{ background: "#080c18" }}
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} color="#111827" gap={24} size={1}/>
            <MiniMap
              nodeColor={n => NODE_META[(n.data as IGNodeData)?.raw?.node_type]?.border ?? "#1e293b"}
              style={{ background: "#0a0f1c", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12 }}
              maskColor="rgba(8,12,24,0.7)"
            />
            {stats.total === 0 && (
              <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", pointerEvents: "none", zIndex: 3 }}>
                <div style={{ fontSize: 36, marginBottom: 12, opacity: 0.2 }}>⚡</div>
                <p style={{ color: "#334155", fontSize: 14, fontWeight: 700 }}>Graph is building…</p>
                <p style={{ color: "#1e2a3a", fontSize: 12, marginTop: 4 }}>Backend is seeding nodes and edges on first boot</p>
              </div>
            )}
          </ReactFlow>
          {/* Custom controls — outside ReactFlow so pointer-events work correctly */}
          <div style={{ position: "absolute", left: 14, top: 14, zIndex: 5 }}>
            <CustomControls/>
          </div>
        </div>

        {/* Bottom stats */}
        <div style={{ flexShrink: 0, borderTop: "1px solid rgba(255,255,255,0.06)", background: "#080c18", padding: "9px 18px", display: "flex", alignItems: "center", gap: 0 }}>
          {statRows.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, paddingRight: i < statRows.length - 1 ? 16 : 0, marginRight: i < statRows.length - 1 ? 16 : 0, borderRight: i < statRows.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none" }}>
                <div style={{ width: 27, height: 27, borderRadius: 8, background: "rgba(124,58,237,0.14)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Icon width={12} height={12} style={{ color: "#7c3aed" }}/>
                </div>
                <div>
                  <p style={{ fontSize: 15, fontWeight: 900, color: "#fff", lineHeight: 1 }}>{s.value}</p>
                  <p style={{ fontSize: 9, color: "#334155" }}>{s.label}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right panel */}
      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode} neighbours={neighbours}
          ripple={ripple} rippleLoading={rippleLoading}
          onRipple={handleRipple} onClearRipple={() => setRipple(null)}
          onClose={() => { setSelectedNode(null); setRipple(null); }}
          onSelectNode={n => { setSelectedNode(n); setRipple(null); }}
        />
      )}
    </div>
  );
}

// ─── Public export ────────────────────────────────────────────────────────────
export function IntelligenceGraph({ initialGraph }: { initialGraph: GraphData | null }) {
  return (
    <ReactFlowProvider>
      <GraphInner initialGraph={initialGraph}/>
    </ReactFlowProvider>
  );
}
