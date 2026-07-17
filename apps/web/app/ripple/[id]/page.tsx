"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Zap, Network, BarChart2, Clock, Telescope, X } from "lucide-react";
import { AITransparencyPanel } from "@/components/ai/AITransparencyPanel";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { InvestmentThesisCard, OpportunityLifecycleCard, MonitoringChecklist, ScenarioAnalysis, PatternIntelligenceCard, MultiHorizonOutlookCard } from "@/components/intelligence";
import { IntelligenceBlock } from "@/components/intelligence/IntelligenceBlock";
import { useIntelligence } from "@/hooks/useIntelligence";
import { ShareInsightCard } from "@/components/ShareInsightCard";
import { SmartCTA } from "@/components/SmartCTA";
import { RelatedContent } from "@/components/RelatedContent";
import { API_BASE_URL as API } from "@/lib/api";


// Dynamic import — ReactFlow requires browser APIs
const RippleGraphCanvas = dynamic(
  () => import("@/components/ripple/RippleGraph").then(m => ({
    default: ({ graphData, depthFilter, selectedNodeId, onNodeClick }: any) => (
      <m.RippleGraph graphData={graphData} depthFilter={depthFilter} selectedNodeId={selectedNodeId} onNodeClick={onNodeClick} />
    )
  })),
  { ssr: false, loading: () => <GraphSkeleton /> }
);

const RippleLegendDynamic = dynamic(
  () => import("@/components/ripple/RippleGraph").then(m => ({ default: m.RippleLegend })),
  { ssr: false, loading: () => null }
);

function GraphSkeleton() {
  return (
    <div className="flex h-full items-center justify-center bg-[#060912]">
      <div className="space-y-3 text-center">
        <div className="mx-auto h-16 w-16 rounded-full border-2 border-indigo-500/30 bg-indigo-500/10 flex items-center justify-center text-indigo-400 animate-pulse"><Zap className="h-7 w-7" /></div>
        <p className="text-[13px] text-slate-500">Generating Ripple Graph…</p>
        <p className="text-[11px] text-slate-700">AI is tracing dependency chains</p>
      </div>
    </div>
  );
}

// ── Types ─────────────────────────────────────────────────────────────────────
interface RippleNode {
  id: string; label: string; type: string; impact: string;
  impact_strength: number; depth: number; icon: string;
  change_direction: "up" | "down" | "neutral"; subtitle?: string;
}
interface RippleEdge {
  source: string; target: string; relationship: string;
  impact_strength: number; confidence: number;
  explanation: string; time_horizon: string;
}
interface Beneficiary {
  name: string; ticker: string; confidence: number; impact: string; reason: string;
}
interface Commodity {
  name: string; current_price: string; change_pct: number; positive: boolean;
}
interface Sector { name: string; strength: string; positive: boolean; }
interface RippleInsights {
  summary: string;
  key_drivers: string[];
  ripple_strength: { direct: string; indirect: string; long_term: string };
  market_volatility: string;
  inflation_risk: string;
  growth_impact: string;
  beneficiaries: Beneficiary[];
  losers: Beneficiary[];
  impacted_commodities: Commodity[];
  impacted_sectors: Sector[];
  ripple_timeline: { period: string; description: string }[];
}
interface RippleData {
  event_title: string;
  event_impact: number;
  graph_data: { nodes: RippleNode[]; edges: RippleEdge[] };
  insights: RippleInsights;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function strengthColor(s: string) {
  if (s === "Very High") return "text-rose-400";
  if (s === "High")      return "text-amber-400";
  if (s === "Medium")    return "text-sky-400";
  return "text-slate-400";
}
function strengthWidth(s: string) {
  if (s === "Very High") return "w-full";
  if (s === "High")      return "w-3/4";
  if (s === "Medium")    return "w-1/2";
  return "w-1/4";
}
function impactBadge(impact: string) {
  if (impact.toLowerCase().includes("very positive")) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
  if (impact.toLowerCase().includes("positive"))      return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
  if (impact.toLowerCase().includes("very negative")) return "text-rose-400 bg-rose-500/10 border-rose-500/20";
  if (impact.toLowerCase().includes("negative"))      return "text-rose-400 bg-rose-500/10 border-rose-500/20";
  return "text-slate-400 bg-white/[0.04] border-white/10";
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function RipplePage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<RippleData | null>(null);
  const [originalData, setOriginalData] = useState<RippleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"graph" | "table" | "timeline" | "scenario">("graph");
  const [depthFilter, setDepthFilter] = useState<number | null>(null);
  const [selectedNode, setSelectedNode] = useState<RippleNode | null>(null);
  const [scenario, setScenario] = useState("");
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [scenarioData, setScenarioData] = useState<RippleData | null>(null);

  // Fetch ripple graph
  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetch(`${API}/api/ripple/event/${id}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { setData(d); setOriginalData(d); })
      .catch(e => setError(e === 404 ? "Event not found" : "Failed to load ripple analysis"))
      .finally(() => setLoading(false));
  }, [id]);

  const handleNodeClick = useCallback((node: RippleNode) => {
    setSelectedNode(prev => prev?.id === node.id ? null : node);
  }, []);

  const runScenario = useCallback(async () => {
    if (!scenario.trim() || scenarioLoading) return;
    setScenarioLoading(true);
    try {
      const r = await fetch(`${API}/api/ripple/scenario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: scenario.trim() }),
      });
      if (r.ok) {
        const d = await r.json();
        setScenarioData(d);
        setActiveTab("scenario");
      }
    } catch {}
    setScenarioLoading(false);
  }, [scenario, scenarioLoading]);

  const graphData = useMemo(() => data?.graph_data || { nodes: [], edges: [] }, [data]);
  const insights: RippleInsights | null = data?.insights as RippleInsights ?? null;

  const { data: intelligence } = useIntelligence("event", id || undefined);

  // ── Loading state ───────────────────────────────────────────────────────
  if (loading) return (
    <div className="flex items-center justify-center h-[60vh]">
      <div className="text-center space-y-3">
        <div className="mx-auto h-20 w-20 rounded-full border-2 border-indigo-500/40 bg-indigo-500/10 flex items-center justify-center text-indigo-400 animate-pulse"><Zap className="h-8 w-8" /></div>
        <p className="text-[14px] font-semibold text-white">Ripple Engine Starting…</p>
        <p className="text-[12px] text-slate-500">AI is tracing market dependency chains</p>
        <div className="flex gap-1 justify-center mt-2">
          {[0,1,2].map(i => (
            <div key={i} className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </div>
      </div>
    </div>
  );

  if (error) return (
    <div className="flex items-center justify-center h-[60vh]">
      <div className="text-center">
        <p className="text-[14px] text-slate-400">{error}</p>
        <Link href="/ripple" className="mt-3 inline-block text-[12px] text-sky-400 hover:text-sky-300">← Back to Ripple Engine</Link>
      </div>
    </div>
  );

  const eventTitle   = data?.event_title || "Market Event";
  const eventImpact  = data?.event_impact ?? 0;
  const rs           = insights?.ripple_strength;
  const totalNodes   = graphData.nodes.filter(n => n.id !== "event_center").length;

  return (
    <div className="space-y-4 pb-12">

      {/* ── Breadcrumb + share ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-[11px] text-slate-600">
          <Link href="/ripple" className="hover:text-slate-400 transition">Ripple Engine</Link>
          <span>/</span>
          <span className="text-slate-400 truncate max-w-xs">{eventTitle}</span>
        </div>
        <ShareInsightCard
          entityType="ripple"
          entityId={id}
          title={eventTitle}
          summary={insights?.summary}
        />
      </div>

      {/* Smart CTAs */}
      <div className="flex flex-wrap gap-2">
        <SmartCTA variant="ask-ai" href={`/ai-search?q=${encodeURIComponent(eventTitle.slice(0, 100))}`} />
        <SmartCTA variant="view-event" href="/events" />
        <SmartCTA variant="explore-opportunity" href="/radar" />
      </div>

      {/* ── Intelligence Block ──────────────────────────────────────────── */}
      {intelligence && (
        <IntelligenceBlock data={intelligence} label="Ripple Intelligence" compact={true} />
      )}

      {/* ── Event Header ────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-white/[0.07] bg-[#080c14] p-6">
        <div className="flex flex-col sm:flex-row items-start justify-between gap-4 sm:gap-6">
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-0.5 text-[10px] font-bold text-indigo-400">
                <svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg> RIPPLE ENGINE
              </span>
              <span className="text-[11px] text-slate-600">Market Dependency Analysis</span>
            </div>
            <h1 className="text-[22px] font-black text-white leading-tight truncate">{eventTitle}</h1>
          </div>
          {/* Scores */}
          <div className="shrink-0 flex items-center gap-3">
            <div className="text-center">
              <p className="text-[28px] font-black text-rose-400 tabular-nums leading-none">{eventImpact?.toFixed(1)}</p>
              <p className="text-[9px] text-slate-600 mt-0.5 uppercase tracking-wider">Impact Score</p>
            </div>
            {rs && (
              <>
                <div className="w-px h-10 bg-white/[0.06]" />
                {[
                  { label: "Direct", val: rs.direct },
                  { label: "Indirect", val: rs.indirect },
                  { label: "Long-term", val: rs.long_term },
                ].map(r => (
                  <div key={r.label} className="text-center">
                    <div className={`rounded-full border px-3 py-1 text-[10px] font-bold ${
                      r.val === "Very High" ? "border-rose-500/30 bg-rose-500/10 text-rose-400" :
                      r.val === "High"      ? "border-amber-500/30 bg-amber-500/10 text-amber-400" :
                                              "border-sky-500/30 bg-sky-500/10 text-sky-400"
                    }`}>{r.val}</div>
                    <p className="text-[9px] text-slate-600 mt-0.5">{r.label}</p>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
        {/* Quick stats */}
        <div className="mt-4 flex flex-wrap gap-4 pt-4 border-t border-white/[0.05]">
          {[
            { label: "Nodes Mapped", value: totalNodes, color: "text-indigo-400" },
            { label: "Dependencies",  value: graphData.edges.length,  color: "text-sky-400" },
            { label: "Beneficiaries", value: insights?.beneficiaries?.length ?? 0, color: "text-emerald-400" },
            { label: "At Risk",       value: insights?.losers?.length ?? 0,        color: "text-rose-400" },
            { label: "Depth Levels",  value: 4,                                    color: "text-amber-400" },
          ].map(s => (
            <div key={s.label} className="flex items-center gap-2">
              <span className={`text-[18px] font-black tabular-nums ${s.color}`}>{s.value}</span>
              <span className="text-[11px] text-slate-600">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Tab Bar ─────────────────────────────────────────────────────── */}
      <div className="flex gap-0.5 overflow-x-auto rounded-xl border border-white/[0.07] bg-[#080c14] p-1 scrollbar-hide">
        {(["graph", "table", "timeline", "scenario"] as const).map(t => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`flex-1 min-w-max rounded-xl px-4 py-2.5 text-[12px] font-semibold transition capitalize ${
              activeTab === t
                ? "bg-gradient-to-r from-indigo-600/25 to-violet-600/15 text-white border border-indigo-500/20"
                : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]"
            }`}
          >
            {t === "graph" ? <><Network className="inline h-3.5 w-3.5 mr-1" />Ripple Graph</> :
             t === "table" ? <><BarChart2 className="inline h-3.5 w-3.5 mr-1" />Impact Table</> :
             t === "timeline" ? <><Clock className="inline h-3.5 w-3.5 mr-1" />Timeline View</> :
             <><Telescope className="inline h-3.5 w-3.5 mr-1" />Scenario Simulator</>}
          </button>
        ))}
      </div>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row gap-5" style={{ minHeight: 640 }}>

        {/* ── Left: Graph / Table / Timeline / Scenario ───────────────── */}
        <div className="flex-1 min-w-0">

          {activeTab === "graph" && (
            <div className="flex flex-col rounded-xl border border-white/[0.07] bg-[#060912] overflow-hidden" style={{ height: "min(640px, 70vw)" }}>
              {/* Graph controls */}
              <div className="flex items-center justify-between gap-4 px-4 py-2.5 border-b border-white/[0.05] bg-[#080c14]">
                <div className="flex items-center gap-1">
                  <span className="text-[11px] text-slate-500 mr-2">Depth:</span>
                  {[null, 1, 2, 3].map(d => (
                    <button
                      key={String(d)}
                      onClick={() => setDepthFilter(d)}
                      className={`rounded-lg px-2.5 py-1 text-[10px] font-semibold transition ${
                        depthFilter === d
                          ? "bg-indigo-600/30 text-white border border-indigo-500/30"
                          : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
                      }`}
                    >
                      {d === null ? "All" : d === 1 ? "Direct" : d === 2 ? "Secondary" : "Tertiary"}
                    </button>
                  ))}
                </div>
                {selectedNode && (
                  <div className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-[#0a0d16] px-3 py-1.5">
                    <div>
                      <p className="text-[11px] font-semibold text-white">{selectedNode.label}</p>
                      <p className="text-[9px] text-slate-500 capitalize">{selectedNode.type} · Depth {selectedNode.depth}</p>
                    </div>
                    <button onClick={() => setSelectedNode(null)} className="text-slate-600 hover:text-slate-400 ml-2"><X className="h-3.5 w-3.5" /></button>
                  </div>
                )}
                <span className="text-[10px] text-slate-700">Scroll to zoom · Drag to pan · Click node for details</span>
              </div>
              {/* Canvas */}
              <div className="flex-1" style={{ touchAction: "none" }}>
                {graphData.nodes.length > 0 ? (
                  <RippleGraphCanvas
                    graphData={graphData}
                    depthFilter={depthFilter}
                    selectedNodeId={selectedNode?.id}
                    onNodeClick={handleNodeClick}
                  />
                ) : (
                  <GraphSkeleton />
                )}
              </div>
              {/* Legend */}
              <RippleLegendDynamic />
            </div>
          )}

          {activeTab === "table" && (
            <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] overflow-hidden">
              <div className="px-5 py-4 border-b border-white/[0.05]">
                <h3 className="text-[14px] font-bold text-white">Impact Analysis Table</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">All affected entities ranked by impact strength</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="border-b border-white/[0.05]">
                      <th className="text-left px-5 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Entity</th>
                      <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Type</th>
                      <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Impact</th>
                      <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Strength</th>
                      <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Depth</th>
                      <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...graphData.nodes]
                      .filter(n => n.id !== "event_center")
                      .sort((a, b) => (b.impact_strength ?? 0) - (a.impact_strength ?? 0))
                      .map(node => (
                        <tr key={node.id} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition">
                          <td className="px-5 py-3">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-white">{node.label}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className="rounded border border-white/[0.06] bg-white/[0.03] px-2 py-0.5 text-[9px] capitalize text-slate-400">
                              {node.type}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`font-semibold capitalize ${
                              node.impact === "positive" ? "text-emerald-400" :
                              node.impact === "negative" ? "text-rose-400" : "text-slate-400"
                            }`}>{node.impact}</span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className="w-20 h-1.5 rounded-full bg-white/[0.05]">
                                <div className={`h-full rounded-full ${
                                  node.impact === "positive" ? "bg-emerald-400" :
                                  node.impact === "negative" ? "bg-rose-400" : "bg-slate-400"
                                }`} style={{ width: `${(node.impact_strength || 0.5) * 100}%` }} />
                              </div>
                              <span className="text-slate-500 tabular-nums">{Math.round((node.impact_strength || 0.5) * 100)}%</span>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-slate-500">
                              {node.depth === 1 ? "Direct" : node.depth === 2 ? "Secondary" : node.depth === 3 ? "Tertiary" : "Long-term"}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`font-bold tabular-nums ${
                              node.change_direction === "up" ? "text-emerald-400" :
                              node.change_direction === "down" ? "text-rose-400" : "text-slate-400"
                            }`}>
                              {node.change_direction === "up" ? "↑" : node.change_direction === "down" ? "↓" : "→"}{" "}
                              {node.subtitle || "—"}
                            </span>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === "timeline" && (
            <div className="space-y-4">
              <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-5">
                <h3 className="text-[14px] font-bold text-white mb-5">Ripple Effect Timeline</h3>
                {insights?.ripple_timeline?.length ? (
                  <div className="relative pl-6">
                    <div className="absolute left-2 top-2 bottom-2 w-0.5 bg-gradient-to-b from-indigo-500 via-sky-500 to-slate-700/50" />
                    {insights.ripple_timeline.map((step, i) => (
                      <div key={i} className="relative mb-6 last:mb-0">
                        <div className={`absolute -left-4 top-1 h-3 w-3 rounded-full border-2 border-[#0a0d16] ${
                          i === 0 ? "bg-rose-400" : i === 1 ? "bg-amber-400" : i === 2 ? "bg-sky-400" : "bg-slate-500"
                        }`} />
                        <div className="rounded-xl border border-white/[0.06] bg-[#080c14] p-4">
                          <div className={`mb-2 text-[10px] font-black uppercase tracking-widest ${
                            i === 0 ? "text-rose-400" : i === 1 ? "text-amber-400" : i === 2 ? "text-sky-400" : "text-slate-500"
                          }`}>{step.period}</div>
                          <p className="text-[13px] text-slate-300 leading-6">{step.description}</p>
                        </div>
                        {(() => {
                          const depth = i + 1;
                          const depthNodes = graphData.nodes.filter(n => n.depth === depth && n.id !== "event_center");
                          if (!depthNodes.length) return null;
                          return (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {depthNodes.slice(0, 5).map(n => (
                                <span key={n.id} className={`rounded-full border px-2 py-0.5 text-[9px] ${
                                  n.impact === "positive" ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400" :
                                  n.impact === "negative" ? "border-rose-500/20 bg-rose-500/10 text-rose-400" :
                                  "border-slate-500/20 bg-slate-500/10 text-slate-400"
                                }`}>{n.label}</span>
                              ))}
                              {depthNodes.length > 5 && <span className="text-[9px] text-slate-600">+{depthNodes.length - 5} more</span>}
                            </div>
                          );
                        })()}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[12px] text-slate-600">Timeline data not available</p>
                )}
              </div>

              {/* Edge dependency list */}
              <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-5">
                <h3 className="text-[14px] font-bold text-white mb-4">Dependency Chain Details</h3>
                <div className="space-y-2">
                  {graphData.edges.slice(0, 15).map((edge, i) => {
                    const srcNode = graphData.nodes.find(n => n.id === edge.source);
                    const tgtNode = graphData.nodes.find(n => n.id === edge.target);
                    const relColor = edge.relationship === "hurts" ? "text-rose-400" :
                                     edge.relationship === "benefits" ? "text-emerald-400" :
                                     edge.relationship === "causes" ? "text-sky-400" : "text-slate-400";
                    return (
                      <div key={i} className="rounded-xl border border-white/[0.04] bg-white/[0.02] px-4 py-3">
                        <div className="flex items-start gap-3">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span className="text-[11px] font-semibold text-white truncate">{srcNode?.label || edge.source}</span>
                            <span className={`text-[10px] font-bold shrink-0 ${relColor}`}>→ {edge.relationship}</span>
                            <span className="text-[11px] font-semibold text-white truncate">{tgtNode?.label || edge.target}</span>
                          </div>
                          <div className="shrink-0 text-right">
                            <span className="text-[10px] text-slate-500 tabular-nums">{Math.round((edge.confidence || 0.8) * 100)}% conf.</span>
                            {edge.time_horizon && <span className="text-[9px] text-slate-600 mt-0.5 block">{edge.time_horizon}</span>}
                          </div>
                        </div>
                        {edge.explanation && (
                          <p className="mt-1.5 text-[10px] text-slate-500 leading-4">{edge.explanation}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <InvestmentThesisCard
                entityType="ripple"
                entityId={id}
                entityTitle={data?.event_title}
                entityDescription={data?.insights?.summary}
                entitySector={data?.insights?.impacted_sectors?.[0]?.name}
                thesis={data?.insights?.summary}
                businessImpact={data?.insights?.growth_impact}
                keyDrivers={(data?.insights?.key_drivers ?? []).slice(0, 4)}
                riskFactors={[
                  `Market volatility: ${data?.insights?.market_volatility ?? "Moderate"}`,
                  data?.insights?.inflation_risk ? `Inflation risk: ${data.insights.inflation_risk}` : "Indirect sector contagion beyond initial impact",
                  "Policy response timing uncertainty",
                ]}
                timeHorizon={data?.insights?.ripple_timeline?.[0]?.period ?? "Short-term (1–3 months)"}
              />

              <OpportunityLifecycleCard
                stage={(() => {
                  const strength = data?.insights?.ripple_strength;
                  const directStr = (strength?.direct ?? "").toLowerCase();
                  const impact = data?.event_impact ?? 50;
                  if (impact > 80 || directStr.includes("high")) return "strong-momentum" as const;
                  if (impact > 60 || directStr.includes("medium")) return "developing" as const;
                  return "emerging" as const;
                })()}
                description={data?.insights?.ripple_timeline?.[0]?.description}
                whyAssigned={`Ripple strength — Direct: ${data?.insights?.ripple_strength?.direct ?? "N/A"} · Indirect: ${data?.insights?.ripple_strength?.indirect ?? "N/A"} · Long-term: ${data?.insights?.ripple_strength?.long_term ?? "N/A"}`}
                historicalComparison="Events with this ripple profile typically see sector-level re-pricing within 10–15 trading sessions followed by earnings guidance revisions in the next quarter."
                confidence={data?.event_impact != null ? Math.min(90, Math.round(data.event_impact * 0.85)) : 55}
                expectedEvolution={data?.insights?.ripple_timeline?.[data.insights.ripple_timeline.length - 1]?.description ?? "Expect ripple effects to peak in the near term and gradually dissipate as markets price in the new information."}
                risks={[
                  `Volatility regime: ${data?.insights?.market_volatility ?? "Moderate"} — amplifies both upside and downside`,
                  "Policy response could accelerate or dampen the ripple",
                  "Correlation breakdown with historical analogues during stress events",
                ]}
              />

              <ScenarioAnalysis
                entityType="ripple"
                entityId={id}
                entityTitle={data?.event_title}
                entityDescription={data?.insights?.summary}
                entitySector={data?.insights?.impacted_sectors?.[0]?.name}
              />

              {/* What to monitor as ripple effects play out */}
              <MonitoringChecklist
                entityType="ripple"
                entityId={id}
                entityTitle={data?.event_title}
                entityDescription={data?.insights?.summary}
                entitySector={data?.insights?.impacted_sectors?.[0]?.name}
              />
              <PatternIntelligenceCard
                entityType="ripple"
                entityId={id}
                entityTitle={data?.event_title}
                entityDescription={data?.insights?.summary}
                entitySector={data?.insights?.impacted_sectors?.[0]?.name}
              />

              <RelatedContent
                entityType="ripple"
                entityId={id}
                title={data?.event_title}
                sector={data?.insights?.impacted_sectors?.[0]?.name}
              />

              <MultiHorizonOutlookCard
                fetchContext={{
                  type:       "ripple",
                  title:      data?.event_title ?? "Market Event",
                  context:    data?.insights?.summary ?? "",
                  sectors:    (data?.insights?.impacted_sectors ?? []).slice(0, 4).map((s: { name: string }) => s.name),
                  context_id: `ripple:${id}`,
                }}
              />
            </div>
          )}

          {activeTab === "scenario" && (
            <div className="space-y-4">
              <div className="rounded-xl border border-indigo-500/15 bg-[#0a0d16] p-6">
                <div className="flex items-center gap-3 mb-4">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-400"><Telescope className="h-4 w-4" /></span>
                  <div>
                    <h3 className="text-[15px] font-bold text-white">Scenario Simulator</h3>
                    <p className="text-[11px] text-slate-500">Ask "What if…" and get an AI-generated ripple graph</p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <input
                    value={scenario}
                    onChange={e => setScenario(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && runScenario()}
                    placeholder="e.g. What if crude oil reaches $100? What if RBI cuts rates by 75 bps?"
                    className="flex-1 rounded-xl border border-white/[0.08] bg-[#080c14] px-4 py-3 text-[13px] text-white placeholder-slate-600 outline-none focus:border-indigo-500/40 transition"
                  />
                  <button
                    onClick={runScenario}
                    disabled={!scenario.trim() || scenarioLoading}
                    className="rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 px-5 py-3 text-[12px] font-bold text-white transition"
                  >
                    {scenarioLoading ? "Analysing…" : "Run Scenario"}
                  </button>
                </div>
                {/* Quick scenario suggestions */}
                <div className="mt-3 flex flex-wrap gap-2">
                  {[
                    "What if crude oil reaches $100?",
                    "What if RBI cuts rates by 75 bps?",
                    "What if USD/INR crosses 90?",
                    "What if inflation rises to 8%?",
                    "What if FIIs sell ₹1 lakh crore?",
                  ].map(s => (
                    <button
                      key={s}
                      onClick={() => setScenario(s)}
                      className="rounded-full border border-white/[0.07] bg-white/[0.03] px-3 py-1 text-[10px] text-slate-500 hover:text-slate-300 hover:border-white/[0.12] transition"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {scenarioData && (
                <div className="space-y-4">
                  <div className="rounded-xl border border-emerald-500/15 bg-[#0a0d16] p-5">
                    <p className="text-[12px] font-bold text-emerald-400 mb-2 flex items-center gap-1.5">
                      <svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg> Scenario Analysis Ready
                    </p>
                    <p className="text-[13px] text-slate-300 leading-6">{scenarioData.insights?.summary || "Scenario analysis complete."}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {/* Original analysis column */}
                    <div className="rounded-xl border border-white/[0.07] bg-[#080c14] p-4">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-3">Original Analysis</p>
                      <p className="text-[28px] font-black text-rose-400 tabular-nums leading-none">{originalData?.event_impact?.toFixed(1)}</p>
                      <p className="text-[9px] text-slate-600 mt-0.5 uppercase tracking-wider mb-3">Impact Score</p>
                      {(originalData?.insights?.beneficiaries?.length ?? 0) > 0 && (
                        <div className="mb-3">
                          <p className="text-[9px] text-slate-600 uppercase tracking-wider mb-1.5">Top Beneficiaries</p>
                          <div className="space-y-1">
                            {originalData?.insights.beneficiaries.slice(0, 3).map((b, i) => (
                              <p key={i} className="text-[10px] text-emerald-400 truncate">{b.name}</p>
                            ))}
                          </div>
                        </div>
                      )}
                      {(originalData?.insights?.impacted_sectors?.length ?? 0) > 0 && (
                        <div>
                          <p className="text-[9px] text-slate-600 uppercase tracking-wider mb-1.5">Key Sectors</p>
                          <div className="space-y-1">
                            {originalData?.insights.impacted_sectors.slice(0, 3).map((s, i) => (
                              <p key={i} className={`text-[10px] truncate ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.name}</p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    {/* Scenario analysis column */}
                    <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/[0.04] p-4">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 mb-3 truncate">Scenario: {scenario}</p>
                      <p className="text-[28px] font-black text-rose-400 tabular-nums leading-none">{scenarioData.event_impact?.toFixed(1)}</p>
                      <p className="text-[9px] text-slate-600 mt-0.5 uppercase tracking-wider mb-3">Impact Score</p>
                      {(scenarioData.insights?.beneficiaries?.length ?? 0) > 0 && (
                        <div className="mb-3">
                          <p className="text-[9px] text-slate-600 uppercase tracking-wider mb-1.5">Top Beneficiaries</p>
                          <div className="space-y-1">
                            {scenarioData.insights.beneficiaries.slice(0, 3).map((b, i) => (
                              <p key={i} className="text-[10px] text-emerald-400 truncate">{b.name}</p>
                            ))}
                          </div>
                        </div>
                      )}
                      {(scenarioData.insights?.impacted_sectors?.length ?? 0) > 0 && (
                        <div>
                          <p className="text-[9px] text-slate-600 uppercase tracking-wider mb-1.5">Key Sectors</p>
                          <div className="space-y-1">
                            {scenarioData.insights.impacted_sectors.slice(0, 3).map((s, i) => (
                              <p key={i} className={`text-[10px] truncate ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.name}</p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  <p className="text-[10px] text-slate-600 text-center">
                    Switch to Graph tab to view the original dependency map
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Right: Insights Sidebar ───────────────────────────────────── */}
        {(activeTab === "graph" || activeTab === "table") && insights && (
          <div className="w-full lg:w-[300px] shrink-0 space-y-4 overflow-y-auto lg:max-h-[640px] scrollbar-hide">

            {/* AI Insight Summary */}
            <div className="rounded-xl border border-violet-500/15 bg-[#0a0d16] p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-500/20 text-violet-400"><svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg></span>
                <p className="text-[11px] font-bold text-violet-400 uppercase tracking-wider">AI Insight Summary</p>
              </div>
              <p className="text-[12px] text-slate-300 leading-5">{insights.summary}</p>
              <AITransparencyPanel
                confidence={data ? Math.min(100, Math.round((data.event_impact ?? 7) * 10)) : 70}
                reasoning={data?.insights?.summary ?? "AI-generated ripple impact analysis based on event data and market relationships."}
                events={data?.event_title ? [{ title: data.event_title }] : []}
              />
              <AIDisclaimer />
              {/* Risk gauges */}
              <div className="mt-4 grid grid-cols-3 gap-2">
                {[
                  { label: "Market Volatility", val: insights.market_volatility, color: "text-rose-400" },
                  { label: "Inflation Risk",    val: insights.inflation_risk,    color: "text-amber-400" },
                  { label: "Growth Impact",     val: insights.growth_impact,     color: insights.growth_impact?.toLowerCase() === "positive" ? "text-emerald-400" : "text-rose-400" },
                ].map(g => (
                  <div key={g.label} className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-2 text-center">
                    <p className={`text-[11px] font-black ${g.color}`}>{g.val}</p>
                    <p className="text-[8px] text-slate-600 mt-0.5 leading-tight">{g.label}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Key Drivers */}
            {insights.key_drivers?.length > 0 && (
              <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-4">
                <p className="text-[11px] font-bold text-white mb-3 uppercase tracking-wider">Key Drivers</p>
                <div className="space-y-2">
                  {insights.key_drivers.slice(0, 3).map((d, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
                      <p className="text-[11px] text-slate-400 leading-4">{d}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Top Beneficiaries */}
            {insights.beneficiaries?.length > 0 && (
              <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-4">
                <p className="text-[11px] font-bold text-white mb-3 uppercase tracking-wider">Top Beneficiaries</p>
                <div className="space-y-2">
                  {insights.beneficiaries.slice(0, 5).map((b, i) => (
                    <div key={i} className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <Link href={`/companies/${b.ticker}`} className="text-[11px] font-bold text-white hover:text-emerald-300 transition truncate">
                            {b.name}
                          </Link>
                        </div>
                        <p className="text-[9px] text-slate-600 truncate">{b.reason}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <span className={`rounded border px-1.5 py-0.5 text-[9px] font-bold ${impactBadge(b.impact)}`}>
                          {b.impact}
                        </span>
                        <p className="text-[8px] text-slate-700 mt-0.5 tabular-nums">{Math.round(b.confidence * 100)}%</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Most at Risk */}
            {insights.losers?.length > 0 && (
              <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-4">
                <p className="text-[11px] font-bold text-white mb-3 uppercase tracking-wider">Most at Risk</p>
                <div className="space-y-2">
                  {insights.losers.slice(0, 5).map((b, i) => (
                    <div key={i} className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <Link href={`/companies/${b.ticker}`} className="text-[11px] font-bold text-white hover:text-rose-300 transition truncate">
                            {b.name}
                          </Link>
                        </div>
                        <p className="text-[9px] text-slate-600 truncate">{b.reason}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <span className={`rounded border px-1.5 py-0.5 text-[9px] font-bold ${impactBadge(b.impact)}`}>
                          {b.impact}
                        </span>
                        <p className="text-[8px] text-slate-700 mt-0.5 tabular-nums">{Math.round(b.confidence * 100)}%</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Impacted Commodities */}
            {insights.impacted_commodities?.length > 0 && (
              <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-4">
                <p className="text-[11px] font-bold text-white mb-3 uppercase tracking-wider">Impacted Commodities</p>
                <div className="space-y-2.5">
                  {insights.impacted_commodities.map((c, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <div>
                        <p className="text-[11px] font-semibold text-white">{c.name}</p>
                        <p className="text-[10px] text-slate-500 tabular-nums">{c.current_price}</p>
                      </div>
                      <span className={`text-[12px] font-black tabular-nums ${c.positive ? "text-emerald-400" : "text-rose-400"}`}>
                        {c.positive ? "+" : ""}{c.change_pct?.toFixed(2)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Impacted Sectors */}
            {insights.impacted_sectors?.length > 0 && (
              <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-4">
                <p className="text-[11px] font-bold text-white mb-3 uppercase tracking-wider">Impacted Sectors</p>
                <div className="space-y-2.5">
                  {insights.impacted_sectors.slice(0, 6).map((s, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <div className={`h-2 w-2 shrink-0 rounded-full ${s.positive ? "bg-emerald-400" : "bg-rose-400"}`} />
                      <p className="flex-1 text-[11px] text-slate-300 truncate">{s.name}</p>
                      <div className="w-16 h-1 rounded-full bg-white/[0.05]">
                        <div className={`h-full rounded-full ${s.positive ? "bg-emerald-400" : "bg-rose-400"} ${strengthWidth(s.strength)}`} />
                      </div>
                      <span className={`text-[9px] font-bold shrink-0 ${strengthColor(s.strength)}`}>{s.strength}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Timeline mini */}
            {insights.ripple_timeline?.length > 0 && (
              <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-4">
                <p className="text-[11px] font-bold text-white mb-3 uppercase tracking-wider">Timeline of Effects</p>
                <div className="space-y-3">
                  {insights.ripple_timeline.map((t, i) => (
                    <div key={i} className="flex gap-3">
                      <div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                        i === 0 ? "bg-rose-400" : i === 1 ? "bg-amber-400" : i === 2 ? "bg-sky-400" : "bg-slate-600"
                      }`} />
                      <div>
                        <p className={`text-[9px] font-black uppercase tracking-wide mb-0.5 ${
                          i === 0 ? "text-rose-400" : i === 1 ? "text-amber-400" : i === 2 ? "text-sky-400" : "text-slate-600"
                        }`}>{t.period}</p>
                        <p className="text-[10px] text-slate-400 leading-4">{t.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Mini scenario box */}
            <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-4">
              <p className="text-[11px] font-bold text-white mb-2 uppercase tracking-wider flex items-center gap-1.5"><Telescope className="h-3.5 w-3.5 text-slate-400" /> Scenario Simulator</p>
              <div className="flex gap-2">
                <input
                  value={scenario}
                  onChange={e => setScenario(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && runScenario()}
                  placeholder="What if crude hits $100?"
                  className="flex-1 rounded-xl border border-white/[0.07] bg-[#080c14] px-3 py-2 text-[11px] text-white placeholder-slate-700 outline-none focus:border-indigo-500/30 transition"
                />
                <button
                  onClick={runScenario}
                  disabled={!scenario.trim() || scenarioLoading}
                  className="rounded-xl bg-indigo-600/80 hover:bg-indigo-600 disabled:opacity-40 px-3 py-2 text-[11px] font-bold text-white transition"
                >
                  {scenarioLoading ? "…" : "→"}
                </button>
              </div>
            </div>

          </div>
        )}
      </div>

      {/* ── Back link ────────────────────────────────────────────────────── */}
      <div className="pt-4 flex items-center justify-between">
        <Link href="/ripple" className="text-[12px] text-slate-600 hover:text-slate-400 transition">
          ← Back to Ripple Engine Hub
        </Link>
        <Link href={`/events/${id}`} className="text-[12px] text-sky-400 hover:text-sky-300 transition">
          View Full Event Details →
        </Link>
      </div>

    </div>
  );
}
