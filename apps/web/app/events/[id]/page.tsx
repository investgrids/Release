"use client";

import { useEffect, useState, useCallback } from "react";
import type { ReactNode } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { TrackPageVisit } from "@/components/TrackPageVisit";
import { Target, Building2, BarChart2, Sparkles, MailX, ArrowRight } from "lucide-react";
import { MarketContextStrip } from "@/components/MarketContextStrip";
import { NextSteps } from "@/components/NextSteps";
import { AITransparencyPanel } from "@/components/ai/AITransparencyPanel";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { InvestmentThesisCard, OpportunityLifecycleCard, ScenarioAnalysis, MonitoringChecklist, PatternIntelligenceCard, MultiHorizonOutlookCard } from "@/components/intelligence";
import { ShareInsightCard } from "@/components/ShareInsightCard";
import { SmartCTA } from "@/components/SmartCTA";
import { RelatedContent } from "@/components/RelatedContent";
import { HistoricalMemory } from "@/components/HistoricalMemory";
import { useIntelligence } from "@/hooks/useIntelligence";
import { IntelligenceBlock } from "@/components/intelligence/IntelligenceBlock";
import { API_BASE_URL as API } from "@/lib/api";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";

const ReactFlow  = dynamic(() => import("reactflow").then(m => m.default),     { ssr: false });
const Background = dynamic(() => import("reactflow").then(m => m.Background),  { ssr: false });
const Controls   = dynamic(() => import("reactflow").then(m => m.Controls),    { ssr: false });


// ── Types ─────────────────────────────────────────────────────────────────────
interface Company  { symbol: string; name: string; impact_type: string; impact_score: number; reason: string }
interface Sector   { sector: string; impact: string; impact_score: number }
interface Step     { date: string; title: string; description: string; order: number }
interface Policy   { id: number; title: string; ministry: string; announcement_date: string; summary: string; url: string }
interface HistEvt  { id: string; title: string; event_date: string; impact_score: number; similarity_score: number; reason: string }
interface NewsItem { id: string; headline: string; source: string; published_at: string; summary: string; url: string }
interface GNode    { id: string; label: string; type: string; metadata: Record<string, unknown> }
interface GEdge    { source: string; target: string; relationship: string }
interface MarketIndex { name: string; ticker: string; value: string; pct_change: number; positive: boolean; change_str: string }
interface MarketStatus { is_open: boolean; status: string; time_ist: string; date: string }
interface MarketData   { marketStatus: MarketStatus; marketIndices: MarketIndex[] }
interface ChartPoint   { label: string; value: number }

interface EventDetail {
  event: { id: string; slug?: string; title: string; description: string; source: string; event_type: string; event_date: string; enrichment_status: string };
  summary: { text: string; why_it_matters: string; key_bullets: string[]; immediate_impact: string; long_term_impact: string; risk_factors: string[]; opportunities: string[] };
  impactScore: number;
  confidence: number;
  companies: Company[];
  beneficiaries: Company[];
  losers: Company[];
  affectedSectors: Sector[];
  timeline: Step[];
  governmentPolicies: Policy[];
  historicalEvents: HistEvt[];
  relatedNews: NewsItem[];
  graph: { nodes: GNode[]; edges: GEdge[] };
  marketReaction: { short_term?: string; medium_term?: string; volatility?: string; sentiment?: string };
  aiAnalysis: { bull_case?: string; bear_case?: string; base_case?: string; key_risks?: string[]; catalysts?: string[] };
}

// ── Constants ─────────────────────────────────────────────────────────────────
const TABS = ["Overview", "Companies", "Sectors", "Timeline", "Historical", "Related News", "Market", "Graph"] as const;
type Tab = typeof TABS[number];

const COMPANY_PALETTE = ["bg-violet-500","bg-sky-500","bg-emerald-500","bg-amber-500","bg-rose-500"];
const DONUT_COLORS    = ["#f43f5e","#f97316","#eab308","#22c55e"];

// ── Helpers ───────────────────────────────────────────────────────────────────
function scoreColor(s: number) {
  if (s >= 85) return { text: "text-rose-400",  ring: "#f43f5e", border: "border-rose-500",  bg: "bg-rose-500/15"  };
  if (s >= 70) return { text: "text-amber-400", ring: "#f59e0b", border: "border-amber-400", bg: "bg-amber-500/15" };
  if (s >= 50) return { text: "text-sky-400",   ring: "#38bdf8", border: "border-sky-400",   bg: "bg-sky-500/15"   };
  return               { text: "text-slate-400", ring: "#64748b", border: "border-slate-500", bg: "bg-slate-700/20" };
}

function scoreLabel(s: number) {
  if (s >= 85) return "Very High Impact";
  if (s >= 70) return "High Impact";
  if (s >= 50) return "Medium Impact";
  return "Low Impact";
}

function impactBg(v?: string) {
  if (!v) return "bg-slate-700/40 text-slate-400 border-slate-600/30";
  if (v === "positive" || v === "bullish") return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
  if (v === "negative" || v === "bearish") return "bg-rose-500/20 text-rose-300 border-rose-500/30";
  return "bg-amber-500/20 text-amber-300 border-amber-500/30";
}

function fmt(s?: string) {
  if (!s) return "";
  try { return new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); }
  catch { return s.slice(0, 10); }
}

function srcInitials(src: string) {
  return src.split(/[\s\-_]/g).slice(0, 2).map(w => w[0] || "").join("").toUpperCase() || "N";
}

function mapCategory(cat: string): string {
  const m: Record<string, string> = {
    "Government": "Regulatory",
    "Policy": "Regulatory",
    "RBI": "Monetary",
    "Macro": "Fiscal",
    "Global": "Global",
    "Corporate": "Corporate",
    "Results": "Earnings",
  };
  return m[cat] ?? cat;
}

// ── ScoreRing ─────────────────────────────────────────────────────────────────
function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const sc   = scoreColor(score);
  const r    = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgba(255,255,255,0.06)" strokeWidth={6} fill="none"/>
        <circle cx={size/2} cy={size/2} r={r} stroke={sc.ring} strokeWidth={6} fill="none"
          strokeLinecap="round" strokeDasharray={`${dash} ${circ}`}
          style={{ filter: `drop-shadow(0 0 5px ${sc.ring}80)` }}/>
      </svg>
      <div className="absolute text-center">
        <div className={`text-xl font-black leading-none ${sc.text}`}>{Math.round(score)}</div>
        <div className="text-[8px] text-slate-500 mt-0.5">/ 100</div>
      </div>
    </div>
  );
}

// ── KpiCard ───────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, icon, color, border }: {
  label: string; value: string | number; sub: string; icon: ReactNode; color: string; border: string;
}) {
  return (
    <div className={`rounded-[20px] border bg-white/[0.025] p-4 transition hover:-translate-y-0.5 hover:shadow-lg ${border}`}>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</p>
        <span className="text-slate-400">{icon}</span>
      </div>
      <p className={`text-2xl font-black leading-none ${color}`}>{value}</p>
      <p className="mt-1.5 text-[10px] text-slate-500">{sub}</p>
    </div>
  );
}

// ── EmptyState ────────────────────────────────────────────────────────────────
function Empty({ msg }: { msg: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-white/[0.04]">
        <svg className="h-4 w-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
      </div>
      <p className="text-[12px] text-slate-600">{msg}</p>
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────
function Card({ title, action, children, className = "" }: {
  title?: string; action?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <div className={`rounded-[20px] border border-white/8 bg-white/[0.025] p-4 ${className}`}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between">
          {title && <h3 className="text-[12px] font-semibold uppercase tracking-wider text-slate-500">{title}</h3>}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

// ── Tab: Overview ─────────────────────────────────────────────────────────────
function OverviewTab({ data, goTab }: { data: EventDetail; goTab: (t: Tab) => void }) {
  const [deepOpen, setDeepOpen] = useState(false);
  const isPending = data.event.enrichment_status !== "done";
  const evidenceItems = (data.relatedNews ?? []).slice(0, 6).map(n => ({
    type: "news" as const,
    title: n.headline,
    source: n.source ?? "News",
    date: n.published_at ?? "",
    relevance: 75,
  }));
  return (
    <div className="space-y-4">
      {isPending && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-amber-400 border-t-transparent"/>
          <div>
            <span className="text-[13px] font-semibold text-amber-300">AI enrichment in progress</span>
            <span className="ml-2 text-[11px] text-amber-400/70">Companies, sectors, timeline will populate automatically.</span>
          </div>
        </div>
      )}

      {/* Level 1: What happened */}
      {data.summary.text && (
        <Card>
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-violet-500/20">
              <svg className="h-4 w-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-violet-400">What Happened</p>
              <p className="text-[13px] leading-5 text-slate-300">{data.summary.text}</p>
              {data.summary.key_bullets?.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {data.summary.key_bullets.slice(0, 3).map((b, i) => (
                    <li key={i} className="flex items-start gap-2 text-[12px] text-slate-400">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400"/>
                      {b}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Level 1: Who's affected — most actionable */}
      <div className="grid grid-cols-3 gap-3">
        <Card title="Beneficiaries"
          action={data.beneficiaries.length > 3
            ? <button onClick={() => goTab("Companies")} className="text-[11px] text-sky-400 hover:text-sky-300">View All →</button>
            : undefined}>
          {data.beneficiaries.length === 0 ? <Empty msg="No beneficiaries identified yet"/> : (
            <div className="space-y-2">
              {data.beneficiaries.slice(0, 5).map((c, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-4 text-[10px] text-slate-600 text-right">{i + 1}</span>
                  <Link href={`/companies/${c.symbol}`} className="flex-1 min-w-0 text-[12px] font-medium text-slate-200 hover:text-emerald-300 transition truncate">{c.name || c.symbol}</Link>
                  <span className="shrink-0 text-[12px] font-bold text-emerald-400">+{Math.round(c.impact_score)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="At Risk"
          action={data.losers.length > 3
            ? <button onClick={() => goTab("Companies")} className="text-[11px] text-sky-400 hover:text-sky-300">View All →</button>
            : undefined}>
          {data.losers.length === 0 ? <Empty msg="No negatively affected companies yet"/> : (
            <div className="space-y-2">
              {data.losers.slice(0, 5).map((c, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-4 text-[10px] text-slate-600 text-right">{i + 1}</span>
                  <Link href={`/companies/${c.symbol}`} className="flex-1 min-w-0 text-[12px] font-medium text-slate-200 hover:text-rose-300 transition truncate">{c.name || c.symbol}</Link>
                  <span className="shrink-0 text-[12px] font-bold text-rose-400">{Math.round(c.impact_score)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Affected Sectors"
          action={data.affectedSectors.length > 3
            ? <button onClick={() => goTab("Sectors")} className="text-[11px] text-sky-400 hover:text-sky-300">View All →</button>
            : undefined}>
          {data.affectedSectors.length === 0 ? <Empty msg="No sectors identified yet"/> : (
            <div className="space-y-2">
              {data.affectedSectors.slice(0, 5).map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="flex-1 text-[12px] text-slate-300 truncate">{s.sector}</span>
                  <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold capitalize ${impactBg(s.impact)}`}>
                    {s.impact === "positive" ? "Positive" : s.impact === "negative" ? "Negative" : "Neutral"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Level 2: Context — timeline + historical comparison */}
      <div className="grid grid-cols-2 gap-3">
        <Card title="Timeline"
          action={data.timeline.length > 3
            ? <button onClick={() => goTab("Timeline")} className="text-[11px] text-sky-400 hover:text-sky-300">Full Timeline →</button>
            : undefined}>
          {data.timeline.length === 0 ? <Empty msg="Timeline not yet generated"/> : (
            <div>
              {data.timeline.slice(0, 4).map((t, i) => (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <div className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${i === 0 ? "bg-violet-400" : "bg-slate-600"}`}/>
                    {i < Math.min(data.timeline.length - 1, 3) && <div className="w-0.5 flex-1 bg-white/[0.05] my-1 min-h-[16px]"/>}
                  </div>
                  <div className="pb-3">
                    <p className="text-[10px] text-slate-500">{t.date}</p>
                    <p className="text-[12px] font-semibold text-slate-200">{t.title}</p>
                    {t.description && <p className="text-[11px] text-slate-500 line-clamp-2">{t.description}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Historical Similar Events"
          action={data.historicalEvents.length > 2
            ? <button onClick={() => goTab("Historical")} className="text-[11px] text-sky-400 hover:text-sky-300">View All →</button>
            : undefined}>
          {data.historicalEvents.length === 0 ? <Empty msg="No similar historical events found"/> : (
            <div className="space-y-3">
              {data.historicalEvents.slice(0, 3).map((he, i) => (
                <Link key={i} href={`/events/${he.id}`}
                  className="flex items-start gap-3 rounded-xl border border-white/[0.05] p-2.5 hover:border-sky-500/20 hover:bg-sky-500/[0.04] transition block">
                  <div className="flex h-9 w-9 shrink-0 flex-col items-center justify-center rounded-xl bg-white/[0.05]">
                    <span className="text-[14px] font-black text-slate-200">{Math.round(he.impact_score)}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-medium text-slate-200 line-clamp-2">{he.title}</p>
                    {he.similarity_score > 0 && (
                      <div className="mt-1 flex items-center gap-1">
                        <div className="h-1 flex-1 rounded bg-white/[0.05]">
                          <div className="h-1 rounded bg-violet-500" style={{ width: `${Math.round(he.similarity_score * 100)}%` }}/>
                        </div>
                        <span className="text-[9px] text-slate-500">{Math.round(he.similarity_score * 100)}% similar</span>
                      </div>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Level 3: Deep Research — collapsed by default */}
      <div className="overflow-hidden rounded-[20px] border border-white/[0.06] bg-white/[0.01]">
        <button
          onClick={() => setDeepOpen(o => !o)}
          className="flex w-full items-center gap-3 px-5 py-4 text-left transition hover:bg-white/[0.03]"
        >
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-semibold text-slate-300">Deep Research</p>
            <p className="mt-0.5 text-[11px] text-slate-500">Thesis · Scenarios · Patterns · Monitoring · Multi-horizon outlook</p>
          </div>
          <svg className={`h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 ${deepOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
          </svg>
        </button>

        {deepOpen && (
          <div className="space-y-4 border-t border-white/[0.06] p-4">
            {data.confidence > 0 && (
              <AITransparencyPanel
                confidence={data.confidence}
                reasoning={data.summary.why_it_matters || data.summary.text || "AI-generated event analysis based on available market data and historical precedents."}
                summary={data.summary.text}
                evidence={evidenceItems}
                companies={data.companies.slice(0, 6).map(c => ({ name: c.name || c.symbol, symbol: c.symbol, href: `/companies/${c.symbol}` }))}
                limitations={data.summary.risk_factors?.length ? data.summary.risk_factors.slice(0, 3) : ["Analysis based on available public data.", "Market conditions may change rapidly.", "Historical patterns may not repeat."]}
                whyReason={`This event is shown because it has an impact score of ${Math.round(data.impactScore)}/100 and affects ${data.affectedSectors.length} sectors.`}
                whyChain={data.affectedSectors.slice(0, 4).map(s => s.sector)}
                compact
                title={data.event.title}
              />
            )}
            <InvestmentThesisCard
              entityType="event"
              entityId={data.event.id}
              entityTitle={data.event.title}
              entityDescription={data.event.description}
              entitySector={data.affectedSectors?.[0]?.sector}
              thesis={data.summary.text}
              whyItMatters={data.summary.why_it_matters}
              businessImpact={data.summary.immediate_impact}
              keyDrivers={(data.summary.opportunities ?? []).slice(0, 4)}
              riskFactors={(data.summary.risk_factors ?? []).slice(0, 3)}
              confidence={data.confidence}
              timeHorizon="Near-term (1–3 months)"
            />
            <OpportunityLifecycleCard
              stage={(() => {
                const score = data.impactScore ?? 50;
                const status = data.event.enrichment_status;
                if (score > 80) return "strong-momentum" as const;
                if (score > 65) return "developing" as const;
                if (status !== "done") return "emerging" as const;
                return "emerging" as const;
              })()}
              description={data.summary.text?.slice(0, 180) || "Event impact is being analysed."}
              whyAssigned={data.summary.why_it_matters || `This event has an impact score of ${Math.round(data.impactScore)}/100 across ${data.affectedSectors?.length ?? 0} sectors.`}
              historicalComparison={`Events of type "${data.event.event_type}" with similar impact scores have historically caused 2–8% sector-level price moves within 5 trading sessions.`}
              confidence={data.confidence}
              expectedEvolution={data.summary.long_term_impact || "Watch for sector re-rating and earnings guidance revisions in the 30–90 day window post-event."}
              risks={(data.summary.risk_factors ?? []).slice(0, 3)}
            />
            <ScenarioAnalysis
              entityType="event"
              entityId={String(data.event.id)}
              entityTitle={data.event.title}
              entityDescription={data.event.description}
              entitySector={data.affectedSectors?.[0]?.sector}
            />
            <MonitoringChecklist
              entityType="event"
              entityId={String(data.event.id)}
              entityTitle={data.event.title}
              entityDescription={data.event.description}
              entitySector={data.affectedSectors?.[0]?.sector}
            />
            <PatternIntelligenceCard
              entityType="event"
              entityId={String(data.event.id)}
              entityTitle={data.event.title}
              entityDescription={data.event.description}
              entitySector={data.affectedSectors?.[0]?.sector}
            />
            <MultiHorizonOutlookCard
              fetchContext={{
                type:       "event",
                title:      data.event.title,
                context:    data.summary.text,
                sectors:    data.affectedSectors.slice(0, 4).map(s => s.sector),
                context_id: `event:${data.event.id}`,
              }}
            />
            <RelatedContent
              entityType="event"
              entityId={data.event.id}
              title={data.event.title}
              sector={data.affectedSectors?.[0]?.sector}
            />
          </div>
        )}
      </div>

      <AIDisclaimer />
    </div>
  );
}

// ── Tab: Companies ────────────────────────────────────────────────────────────
function CompaniesTab({ data }: { data: EventDetail }) {
  if (!data.companies.length) return <Empty msg="Company analysis not yet available."/>;
  return (
    <div className="space-y-4">
      {[
        { list: data.beneficiaries, label: "Beneficiaries",      color: "emerald", tag: "↑ BENEFIT" },
        { list: data.losers,        label: "Negatively Affected", color: "rose",    tag: "↓ RISK"    },
      ].filter(g => g.list.length > 0).map(group => (
        <Card key={group.label} title={group.label}>
          <div className="space-y-2">
            {group.list.map((c, i) => (
              <div key={i} className={`flex items-center gap-3 rounded-xl border px-3 py-2.5
                ${group.color === "emerald" ? "border-emerald-500/10 bg-emerald-500/[0.04]" : "border-rose-500/10 bg-rose-500/[0.04]"}`}>
                <Link href={`/companies/${c.symbol}`}
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[11px] font-bold transition
                    ${group.color === "emerald" ? "bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30" : "bg-rose-500/20 text-rose-300 hover:bg-rose-500/30"}`}>
                  {c.symbol.slice(0, 3)}
                </Link>
                <div className="min-w-0 flex-1">
                  <Link href={`/companies/${c.symbol}`} className="text-[13px] font-semibold text-white hover:text-sky-300 transition">
                    {c.name || c.symbol}
                  </Link>
                  {c.reason && <p className="text-[11px] text-slate-500 line-clamp-1">{c.reason}</p>}
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-[10px] text-slate-500">Impact</p>
                  <p className={`text-[14px] font-black ${group.color === "emerald" ? "text-emerald-400" : "text-rose-400"}`}>
                    {c.impact_score.toFixed(0)}
                  </p>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold
                  ${group.color === "emerald" ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"}`}>
                  {group.tag}
                </span>
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── Tab: Sectors ──────────────────────────────────────────────────────────────
function SectorsTab({ data }: { data: EventDetail }) {
  if (!data.affectedSectors.length) return <Empty msg="Sector analysis not yet available."/>;
  const maxScore = Math.max(...data.affectedSectors.map(s => s.impact_score), 1);
  return (
    <Card title="Affected Sectors">
      <div className="space-y-3">
        {data.affectedSectors.map((s, i) => (
          <div key={i}>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[13px] font-medium text-slate-200">{s.sector}</span>
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize ${impactBg(s.impact)}`}>{s.impact}</span>
            </div>
            <div className="h-1.5 rounded-full bg-white/[0.06]">
              <div className={`h-1.5 rounded-full ${s.impact === "positive" ? "bg-emerald-500" : s.impact === "negative" ? "bg-rose-500" : "bg-amber-500"}`}
                style={{ width: `${(s.impact_score / maxScore) * 100}%` }}/>
            </div>
            <p className="mt-0.5 text-[10px] text-slate-500">Score: {s.impact_score.toFixed(1)}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Tab: Timeline ─────────────────────────────────────────────────────────────
function TimelineTab({ data }: { data: EventDetail }) {
  if (!data.timeline.length) return <Empty msg="Timeline will be generated once AI enrichment completes."/>;
  return (
    <Card title="Full Event Timeline">
      <div>
        {data.timeline.map((t, i) => (
          <div key={i} className="flex gap-4">
            <div className="flex flex-col items-center">
              <div className={`mt-1 h-3 w-3 shrink-0 rounded-full border-2 ${i === 0 ? "border-violet-400 bg-violet-400" : "border-slate-600 bg-transparent"}`}/>
              {i < data.timeline.length - 1 && <div className="w-0.5 flex-1 bg-white/[0.06] my-1 min-h-[24px]"/>}
            </div>
            <div className="pb-5">
              <p className="text-[11px] text-slate-500 mb-0.5">{t.date}</p>
              <p className="text-[14px] font-semibold text-white">{t.title}</p>
              {t.description && <p className="mt-1 text-[13px] leading-5 text-slate-400">{t.description}</p>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Tab: Historical ───────────────────────────────────────────────────────────
function HistoricalTab({ data }: { data: EventDetail }) {
  const sectors   = data.affectedSectors.slice(0, 4).map(s => s.sector);
  const sentiment = data.marketReaction?.sentiment ?? undefined;
  const category  = data.event.event_type ?? undefined;

  return (
    <HistoricalMemory
      category={category}
      sectors={sectors}
      sentiment={sentiment}
      limit={10}
    />
  );
}

// ── Tab: Related News ─────────────────────────────────────────────────────────
function NewsTab({ data }: { data: EventDetail }) {
  if (!data.relatedNews.length) return <Empty msg="No related news articles linked to this event yet."/>;
  return (
    <div className="space-y-3">
      {data.relatedNews.map((n, i) => (
        <div key={i} className="flex items-start gap-3 rounded-[20px] border border-white/[0.06] bg-white/[0.02] p-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/20 text-[13px] font-bold text-sky-300">
            {srcInitials(n.source)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[14px] font-semibold text-white">{n.headline}</p>
            <p className="mt-0.5 text-[11px] text-slate-500">{n.source} · {n.published_at?.slice(0, 10)}</p>
            {n.summary && <p className="mt-1.5 text-[12px] text-slate-400 line-clamp-2">{n.summary}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Tab: Market Impact ────────────────────────────────────────────────────────
function MarketTab({ data }: { data: EventDetail }) {
  const ai = data.aiAnalysis;
  const mr = data.marketReaction;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Bull Case", v: ai.bull_case, color: "text-emerald-400", border: "border-emerald-500/20", prob: 30 },
          { label: "Base Case", v: ai.base_case, color: "text-amber-400",   border: "border-amber-500/20",  prob: 50 },
          { label: "Bear Case", v: ai.bear_case, color: "text-rose-400",    border: "border-rose-500/20",   prob: 20 },
        ].filter(x => x.v).map(x => (
          <div key={x.label} className={`rounded-[20px] border bg-white/[0.02] p-4 ${x.border}`}>
            <div className="mb-2 flex items-center justify-between">
              <p className={`text-[10px] font-bold uppercase tracking-wider ${x.color}`}>{x.label}</p>
              <span className={`rounded-full border px-1.5 py-0.5 text-[9px] font-semibold ${x.color} border-current/20`}>
                {x.prob}%
              </span>
            </div>
            <p className="text-[13px] leading-5 text-slate-300">{x.v}</p>
          </div>
        ))}
      </div>

      {Object.values(mr).some(Boolean) && (
        <Card title="Market Outlook">
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Short Term",  v: mr.short_term  },
              { label: "Medium Term", v: mr.medium_term },
              { label: "Volatility",  v: mr.volatility  },
              { label: "Sentiment",   v: mr.sentiment   },
            ].map(row => (
              <div key={row.label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-center">
                <p className="text-[10px] text-slate-500">{row.label}</p>
                <span className={`mt-1.5 inline-block rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize ${impactBg(row.v)}`}>
                  {row.v || "—"}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3">
        {ai.key_risks && ai.key_risks.length > 0 && (
          <Card title="Key Risks">
            <ul className="space-y-2">
              {ai.key_risks.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px] text-slate-300">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400"/>{r}
                </li>
              ))}
            </ul>
          </Card>
        )}
        {ai.catalysts && ai.catalysts.length > 0 && (
          <Card title="Growth Catalysts">
            <ul className="space-y-2">
              {ai.catalysts.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px] text-slate-300">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400"/>{c}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  );
}

// ── Tab: Graph ────────────────────────────────────────────────────────────────
function GraphTab({ data }: { data: EventDetail }) {
  if (!data.graph.nodes.length) return <Empty msg="Knowledge graph will be generated after AI enrichment."/>;
  const rfNodes = data.graph.nodes.map((n, i) => ({
    id: n.id, data: { label: n.label },
    position: { x: 100 + (i % 4) * 200, y: 80 + Math.floor(i / 4) * 140 },
    style: { background: n.type === "event" ? "#6366f1" : n.type === "company" ? "#22c55e" : "#f59e0b", color: "#fff", border: "none", borderRadius: 10, fontSize: 11, padding: "6px 10px" },
  }));
  const rfEdges = data.graph.edges.map((e, i) => ({
    id: `e${i}`, source: e.source, target: e.target, label: e.relationship,
    style: { stroke: "rgba(255,255,255,0.15)" }, labelStyle: { fill: "#94a3b8", fontSize: 9 },
  }));
  return (
    <div className="h-[600px] w-full overflow-hidden rounded-[20px] border border-white/10">
      <ReactFlow nodes={rfNodes} edges={rfEdges} fitView>
        <Background color="#1e293b" gap={16}/>
        <Controls style={{ background: "rgba(255,255,255,0.05)" }}/>
      </ReactFlow>
    </div>
  );
}

// ── Right Panel ───────────────────────────────────────────────────────────────
function RightPanel({
  data, marketData, chartData, chartPeriod, onPeriod,
}: {
  data: EventDetail;
  marketData: MarketData | null;
  chartData: ChartPoint[];
  chartPeriod: string;
  onPeriod: (p: string) => void;
}) {
  const sc = scoreColor(data.impactScore);
  const status  = marketData?.marketStatus;
  const indices = marketData?.marketIndices ?? [];
  const periods = ["1D", "5D", "1M", "3M", "6M"];

  // Mini donut for sector distribution
  const sectorData = data.affectedSectors.slice(0, 4).map((s, i) => ({
    name: s.sector, value: Math.max(1, s.impact_score), color: DONUT_COLORS[i],
  }));

  return (
    <div className="space-y-4">

      {/* Impact breakdown */}
      <Card title="Impact Breakdown">
        <div className="flex items-center justify-center py-2">
          <ScoreRing score={data.impactScore > 0 ? data.impactScore : 0} size={96} />
        </div>
        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-500">Impact Score</span>
            <span className={`text-[12px] font-bold ${sc.text}`}>{Math.round(data.impactScore)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-500">Confidence</span>
            <span className="text-[12px] font-bold text-slate-200">{Math.round(data.confidence)}%</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-500">Assessment</span>
            <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold ${sc.text} border-current/30`}>
              {scoreLabel(data.impactScore)}
            </span>
          </div>
        </div>
      </Card>

      {/* Sector distribution mini donut */}
      {sectorData.length > 0 && (
        <Card title="Sector Distribution">
          <div className="relative h-[100px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={sectorData} cx="50%" cy="50%" innerRadius={28} outerRadius={44} paddingAngle={2} dataKey="value" strokeWidth={0}>
                  {sectorData.map((e, i) => <Cell key={i} fill={e.color}/>)}
                </Pie>
                <RechartsTip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 10 }}/>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 space-y-1.5">
            {sectorData.map((s, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <div className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }}/>
                <span className="flex-1 text-[10px] text-slate-400 truncate">{s.name}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Market Chart */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[12px] font-semibold uppercase tracking-wider text-slate-500">Market Reaction</h3>
          <div className="flex items-center gap-1.5">
            <div className={`h-1.5 w-1.5 rounded-full ${status?.is_open ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`}/>
            <span className="text-[10px] text-slate-500 capitalize">{status?.status ?? "—"}</span>
          </div>
        </div>
        <div className="mb-2 flex gap-1">
          {periods.map(p => (
            <button key={p} onClick={() => onPeriod(p)}
              className={`flex-1 rounded-lg py-1 text-[10px] font-semibold transition ${chartPeriod === p ? "bg-white/[0.10] text-white" : "text-slate-500 hover:text-slate-300"}`}>
              {p}
            </button>
          ))}
        </div>
        <div className="h-[90px] -mx-1">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
                <defs>
                  <linearGradient id="aGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3}/>
                    <stop offset="100%" stopColor="#6366f1" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="label" hide/>
                <YAxis domain={["auto","auto"]} hide/>
                <RechartsTip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, fontSize: 10, padding: "4px 8px" }} formatter={(v: number) => [v.toLocaleString("en-IN"), ""]}/>
                <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={1.5} fill="url(#aGrad)"/>
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-[11px] text-slate-600">Fetching market data…</p>
            </div>
          )}
        </div>
        {indices.length > 0 && (
          <div className="mt-3 space-y-2 border-t border-white/[0.06] pt-3">
            {indices.map((idx, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-[11px] text-slate-400 truncate">{idx.name}</span>
                <span className={`text-[12px] font-bold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.change_str || "—"}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Related News quick list */}
      {data.relatedNews.length > 0 && (
        <Card title="Related News">
          <div className="space-y-3">
            {data.relatedNews.slice(0, 3).map((n, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-[10px] font-bold text-slate-400">
                  {srcInitials(n.source)}
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-slate-200 line-clamp-2 leading-4">{n.headline}</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">{n.source} · {n.published_at?.slice(0, 10)}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Gov Policies */}
      {data.governmentPolicies.length > 0 && (
        <Card title="Government Policies">
          <div className="space-y-3">
            {data.governmentPolicies.map((p, i) => (
              <div key={i} className="flex items-start gap-2.5 border-b border-white/[0.05] pb-3 last:border-0 last:pb-0">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/20">
                  <svg className="h-3.5 w-3.5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-1">
                    <p className="text-[12px] font-medium text-slate-200 line-clamp-2">{p.title}</p>
                    {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="shrink-0 text-[9px] text-sky-400">↗</a>}
                  </div>
                  <p className="text-[10px] text-slate-500">{p.ministry} · {p.announcement_date?.slice(0, 10)}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Historical Memory sidebar preview */}
      <HistoricalMemory
        category={data.event.event_type ?? undefined}
        sectors={data.affectedSectors.slice(0, 4).map(s => s.sector)}
        sentiment={data.marketReaction?.sentiment ?? undefined}
        limit={3}
      />

    </div>
  );
}

// ── VerdictCard ───────────────────────────────────────────────────────────────
function VerdictCard({ data }: { data: EventDetail }) {
  const score = data.impactScore;
  const topBen = data.beneficiaries[0];
  const topRisk = data.losers[0];

  const verdict =
    score >= 85 ? "This event is actively moving markets. Take notice." :
    score >= 70 ? "Notable market implications — relevant if you hold related stocks." :
    score >= 50 ? "Moderate impact. Monitor if you are exposed to the affected sectors." :
    "Low broad impact — unlikely to affect diversified portfolios significantly.";

  const whyLine = data.summary.why_it_matters
    ? data.summary.why_it_matters.split(/[.!?]/)[0]?.trim()
    : data.summary.immediate_impact
      ? data.summary.immediate_impact.split(/[.!?]/)[0]?.trim()
      : null;

  const sc = scoreColor(score);

  return (
    <div className="mb-5 rounded-[20px] border border-sky-500/[0.15] bg-gradient-to-r from-[#06101f] to-[#080d1c] p-5">
      <div className="flex items-start gap-5">
        {/* Verdict */}
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-center gap-2">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-sky-400">AI Verdict</p>
          </div>
          <p className="text-[15px] font-semibold leading-snug text-white">{verdict}</p>
          {whyLine && (
            <p className="mt-1.5 text-[13px] leading-5 text-slate-400">{whyLine}.</p>
          )}
        </div>

        {/* Top pick + risk */}
        <div className="flex shrink-0 gap-6 text-right">
          {topBen && (
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-500">Top Pick</p>
              <Link href={`/companies/${topBen.symbol}`}
                className="block text-[14px] font-bold text-emerald-300 transition hover:text-emerald-200">
                {topBen.name || topBen.symbol}
              </Link>
              <p className="text-[10px] text-slate-500">↑ Benefits most</p>
            </div>
          )}
          {topRisk && (
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-rose-500">Caution</p>
              <Link href={`/companies/${topRisk.symbol}`}
                className="block text-[14px] font-bold text-rose-300 transition hover:text-rose-200">
                {topRisk.name || topRisk.symbol}
              </Link>
              <p className="text-[10px] text-slate-500">↓ At risk</p>
            </div>
          )}
        </div>
      </div>

      {/* Action row */}
      <div className="mt-4 flex items-center gap-3 border-t border-white/[0.05] pt-3">
        <Link
          href={`/ai-search?q=${encodeURIComponent(`What should I do about: ${data.event.title}`)}`}
          className="inline-flex items-center gap-1.5 rounded-xl bg-violet-600 px-4 py-2 text-[13px] font-bold text-white transition hover:bg-violet-500"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Ask AI what this means for me
        </Link>
        {topBen && (
          <Link href={`/companies/${topBen.symbol}`}
            className="text-[12px] font-medium text-emerald-400 transition hover:text-emerald-300">
            Research {topBen.name || topBen.symbol} →
          </Link>
        )}
        <Link href={`/ripple/${data.event.id}`}
          className="ml-auto text-[12px] font-medium text-slate-500 transition hover:text-slate-300">
          See ripple chain →
        </Link>
      </div>
    </div>
  );
}

// ── WhatNextSection ───────────────────────────────────────────────────────────
function WhatNextSection({ data }: { data: EventDetail }) {
  const q         = (s: string) => encodeURIComponent(s);
  const topBen    = data.beneficiaries[0];
  const topRisk   = data.losers[0];
  const topSec    = data.affectedSectors[0]?.sector;
  const title     = data.event.title;
  const benCount  = data.beneficiaries.length;
  const riskCount = data.losers.length;

  return (
    <NextSteps config={{
      takeaway: `${benCount} ${benCount === 1 ? "company stands" : "companies stand"} to benefit and ${riskCount} face headwinds — the market may not have fully priced this in yet.`,
      primary: topBen ? {
        label: `Research ${topBen.name || topBen.symbol}`,
        why:   `Because they're the highest-conviction beneficiary — this event directly improves their order book and revenue outlook.`,
        href:  `/companies/${topBen.symbol}`,
      } : {
        label: `Ask AI: Who benefits most from this event?`,
        why:   `Because identifying specific winners is the first step toward an actionable investment thesis.`,
        href:  `/ai-search?q=${q(`Which companies benefit most from "${title}"?`)}`,
      },
      groups: [
        {
          label: "Understand More",
          actions: [
            {
              label: `Ask AI: How long will this impact last?`,
              why:   `Because duration determines whether to buy now or wait for a better entry after the initial market reaction.`,
              href:  `/ai-search?q=${q(`How long will the market impact of "${title}" last and what should investors do?`)}`,
            },
            topSec ? {
              label: `Trace the ripple across ${topSec}`,
              why:   `Because indirect effects in adjacent sectors often create the best risk-adjusted opportunities.`,
              href:  `/ripple/${data.event.id}`,
            } : {
              label: "Trace the full ripple chain",
              why:   "Because second-order effects compound — the real opportunity is often two steps removed from the headline.",
              href:  `/ripple/${data.event.id}`,
            },
          ],
        },
        ...(topRisk ? [{
          label: "Monitor",
          actions: [{
            label: `Watch ${topRisk.name || topRisk.symbol}`,
            why:   `Because they face the most direct headwind — when the risk is fully priced in, that signals a potential entry.`,
            href:  `/companies/${topRisk.symbol}`,
          }],
        }] : []),
      ],
      path: [data.event.event_type || "Event", topSec || "Sector", topBen?.name || topBen?.symbol || "Company", "Investment Thesis"].filter(Boolean) as string[],
    }} />
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
function Skeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-8 w-48 rounded-xl bg-white/[0.04]"/>
      <div className="h-28 rounded-[20px] bg-white/[0.04]"/>
      <div className="grid grid-cols-4 gap-3">
        {[1,2,3,4].map(i => <div key={i} className="h-24 rounded-[20px] bg-white/[0.04]"/>)}
      </div>
      <div className="h-10 rounded-xl bg-white/[0.04]"/>
      <div className="grid grid-cols-[1fr_280px] gap-4">
        <div className="space-y-3">
          {[160,200,140].map((h,i) => <div key={i} className="rounded-[20px] bg-white/[0.04]" style={{ height: h }}/>)}
        </div>
        <div className="space-y-3">
          {[140,180,120].map((h,i) => <div key={i} className="rounded-[20px] bg-white/[0.04]" style={{ height: h }}/>)}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function EventExplorerPage() {
  const { id } = useParams<{ id: string }>();
  const [data,        setData]        = useState<EventDetail | null>(null);
  const [marketData,  setMarketData]  = useState<MarketData | null>(null);
  const [chartData,   setChartData]   = useState<ChartPoint[]>([]);
  const [chartPeriod, setChartPeriod] = useState("1D");
  const [activeTab,   setActiveTab]   = useState<Tab>("Overview");
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState("");

  const { data: intelligence } = useIntelligence("event", id || undefined);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      fetch(`${API}/api/events/${id}`).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); }),
      fetch(`${API}/api/events/${id}/market-data`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/events/${id}/market-chart?period=1D`).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([evtData, mkt, chart]) => {
      setData(evtData);
      if (mkt)   setMarketData(mkt);
      if (chart) setChartData(chart.data ?? []);
    }).catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handlePeriod = useCallback(async (period: string) => {
    setChartPeriod(period);
    if (!id) return;
    try {
      const r = await fetch(`${API}/api/events/${id}/market-chart?period=${period}`);
      if (r.ok) { const j = await r.json(); setChartData(j.data ?? []); }
    } catch { /* silent */ }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const iv = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/events/${id}/market-data`);
        if (r.ok) setMarketData(await r.json());
      } catch { /* silent */ }
    }, 60_000);
    return () => clearInterval(iv);
  }, [id]);

  if (loading) return <main className="min-w-0 pb-10"><Skeleton/></main>;

  if (error || !data) return (
    <main className="min-w-0 pb-10 flex flex-col items-center justify-center py-32">
      <MailX className="h-8 w-8 text-slate-500 mb-3" />
      <p className="text-xl font-bold text-slate-400">Event not found</p>
      <p className="mt-1 text-[13px] text-slate-600">{error}</p>
      <Link href="/events" className="mt-5 flex items-center gap-1.5 text-sm text-sky-400 hover:text-sky-300 transition">
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
        </svg>
        Back to Events
      </Link>
    </main>
  );

  const ev = data.event;
  const sc = scoreColor(data.impactScore);

  const CATEGORY_PILL: Record<string,string> = {
    Government: "bg-violet-500/20 text-violet-300 border-violet-500/30",
    Policy:     "bg-sky-500/20 text-sky-300 border-sky-500/30",
    Corporate:  "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    RBI:        "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
    Macro:      "bg-amber-500/20 text-amber-300 border-amber-500/30",
    Global:     "bg-slate-500/30 text-slate-300 border-slate-500/30",
    Results:    "bg-teal-500/20 text-teal-300 border-teal-500/30",
  };
  const catPill = CATEGORY_PILL[ev.event_type] ?? "bg-slate-500/20 text-slate-300 border-slate-500/30";

  return (
    <main className="min-w-0 pb-10">
      <TrackPageVisit type="event" id={ev.id} title={ev.title} subtitle={ev.event_type} href={`/events/${ev.id}`} />
      <MarketContextStrip />

      {/* ── Breadcrumb + actions ───────────────────────────────────────── */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-[12px] text-slate-500">
          <Link href="/events" className="flex items-center gap-1 hover:text-slate-300 transition">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
            </svg>
            Events
          </Link>
          <span className="text-slate-700">/</span>
          <span className="text-slate-400 truncate max-w-[320px]">{ev.title}</span>
        </div>
        <div className="flex items-center gap-2">
          <ShareInsightCard
            entityType="event"
            entityId={ev.id}
            title={ev.title}
            summary={data.summary?.text}
          />
          <button className="flex items-center gap-1.5 rounded-xl border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-[12px] text-violet-300 hover:bg-violet-500/20 transition">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
            </svg>
            Watchlist
          </button>
        </div>
      </div>

      {/* ── Contextual quick links ────────────────────────────────────── */}
      <div className="mb-4 flex flex-wrap gap-2">
        <Link href="/market-intelligence"
          className="flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-[11px] font-semibold text-violet-300 hover:bg-violet-500/20 transition">
          ✦ Intelligence Feed
        </Link>
        <SmartCTA variant="ask-ai" href={`/ai-search?q=${encodeURIComponent(`What are the investment implications of: ${ev.title}`)}`} />
        {data.beneficiaries?.[0] && (
          <SmartCTA variant="see-companies" href={`/companies/${data.beneficiaries[0].symbol}`} context={data.beneficiaries[0].name || data.beneficiaries[0].symbol} />
        )}
        <SmartCTA variant="view-ripple" href={`/ripple/${ev.id}`} />
      </div>

      {/* ── Page title + event header ──────────────────────────────────── */}
      <div className="mb-5">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-600">Event Explorer</p>
        <div className="rounded-[24px] border border-white/8 bg-white/[0.025] p-5">
          <div className="flex items-start gap-5">
            <div className="min-w-0 flex-1">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-medium ${catPill}`}>{mapCategory(ev.event_type || "Event")}</span>
                {data.impactScore > 0 && (
                  <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${sc.text} border-current/20`}>
                    {scoreLabel(data.impactScore)}
                  </span>
                )}
                {ev.enrichment_status !== "done" && (
                  <span className="flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-300">
                    <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400"/>
                    AI enriching…
                  </span>
                )}
              </div>
              <h1 className="text-xl font-bold leading-snug text-white">{ev.title}</h1>
              {data.summary.text && (
                <p className="mt-2 text-[13px] leading-5 text-slate-400 line-clamp-2">{data.summary.text}</p>
              )}
              <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-600">
                {ev.event_date && <span>{fmt(ev.event_date)}</span>}
                {ev.source && <><span>·</span><span>{ev.source}</span></>}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-4">
              <div className="text-center">
                <ScoreRing score={data.impactScore > 0 ? data.impactScore : 0} size={80}/>
                <p className="mt-1 text-[10px] text-slate-500">Impact</p>
              </div>
              <div className="text-center">
                <ScoreRing score={data.confidence > 0 ? data.confidence : 0} size={80}/>
                <p className="mt-1 text-[10px] text-slate-500">Confidence</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── KPI cards ─────────────────────────────────────────────────────── */}
      <div className="mb-5 grid grid-cols-4 gap-3">
        <KpiCard label="Impact Score"       value={data.impactScore > 0 ? Math.round(data.impactScore) : "—"} sub={data.impactScore > 0 ? scoreLabel(data.impactScore) : "Pending analysis"} icon={<Target className="h-4 w-4" />} color={sc.text} border={`${sc.border}/20`}/>
        <KpiCard label="Companies Affected" value={data.companies.length || "—"} sub={`${data.beneficiaries.length} benefit · ${data.losers.length} at risk`} icon={<Building2 className="h-4 w-4" />} color="text-sky-400"     border="border-sky-500/15"/>
        <KpiCard label="Sectors Impacted"   value={data.affectedSectors.length || "—"} sub={data.affectedSectors[0]?.sector ?? "Analyzing…"} icon={<BarChart2 className="h-4 w-4" />} color="text-emerald-400" border="border-emerald-500/15"/>
        <KpiCard label="Confidence Level"   value={data.confidence > 0 ? `${Math.round(data.confidence)}%` : "—"} sub={data.confidence >= 80 ? "High Confidence" : data.confidence >= 60 ? "Moderate" : "Low Confidence"} icon={<Sparkles className="h-4 w-4" />} color="text-violet-400" border="border-violet-500/15"/>
      </div>

      {/* ── Verdict card ─────────────────────────────────────────────────── */}
      {data.impactScore > 0 && <VerdictCard data={data} />}

      {/* ── AI Intelligence Block — unified intelligence layer ────────────── */}
      {intelligence && (
        <div className="mb-5">
          <IntelligenceBlock data={intelligence} label="Event Intelligence" compact={true} />
        </div>
      )}

      {/* ── Tab bar ───────────────────────────────────────────────────────── */}
      <div className="mb-5 flex items-center border-b border-white/[0.06]" role="tablist">
        {TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            role="tab"
            aria-selected={activeTab === tab}
            id={`tab-${tab.toLowerCase().replace(/\s+/g, "-")}`}
            className={`-mb-px whitespace-nowrap px-4 py-2.5 text-[13px] font-medium transition border-b-2 ${
              activeTab === tab
                ? "border-violet-500 text-white"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}>
            {tab}
            {tab === "Companies" && data.companies.length > 0 && (
              <span className="ml-1.5 rounded-full bg-white/[0.08] px-1.5 py-0.5 text-[9px] text-slate-400">{data.companies.length}</span>
            )}
            {tab === "Related News" && data.relatedNews.length > 0 && (
              <span className="ml-1.5 rounded-full bg-white/[0.08] px-1.5 py-0.5 text-[9px] text-slate-400">{data.relatedNews.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Content + Right panel ─────────────────────────────────────────── */}
      <div className="grid grid-cols-[1fr_280px] items-start gap-5">
        <div className="min-w-0" role="tabpanel" aria-labelledby={`tab-${activeTab.toLowerCase().replace(/\s+/g, "-")}`}>
          {activeTab === "Overview"      && <OverviewTab   data={data} goTab={setActiveTab}/>}
          {activeTab === "Companies"     && <CompaniesTab  data={data}/>}
          {activeTab === "Sectors"       && <SectorsTab    data={data}/>}
          {activeTab === "Timeline"      && <TimelineTab   data={data}/>}
          {activeTab === "Historical"    && <HistoricalTab data={data}/>}
          {activeTab === "Related News"  && <NewsTab       data={data}/>}
          {activeTab === "Market"        && <MarketTab     data={data}/>}
          {activeTab === "Graph"         && <GraphTab      data={data}/>}

          <WhatNextSection data={data} />
        </div>

        <aside className="sticky top-[84px]">
          <RightPanel
            data={data}
            marketData={marketData}
            chartData={chartData}
            chartPeriod={chartPeriod}
            onPeriod={handlePeriod}
          />
        </aside>
      </div>
    </main>
  );
}
