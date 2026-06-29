"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTip,
  ResponsiveContainer,
} from "recharts";

const ReactFlow = dynamic(() => import("reactflow").then(m => m.default), { ssr: false });
const Background = dynamic(() => import("reactflow").then(m => m.Background), { ssr: false });
const Controls   = dynamic(() => import("reactflow").then(m => m.Controls),   { ssr: false });

const API = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────────
interface Company  { symbol: string; name: string; impact_type: string; impact_score: number; reason: string }
interface Sector   { sector: string; impact: string; impact_score: number }
interface Step     { date: string; title: string; description: string; order: number }
interface Policy   { id: number; title: string; ministry: string; announcement_date: string; summary: string; url: string }
interface HistEvt  { id: string; title: string; event_date: string; impact_score: number; similarity_score: number; reason: string }
interface NewsItem { id: string; headline: string; source: string; published_at: string; summary: string; url: string }
interface GNode    { id: string; label: string; type: string; metadata: Record<string, unknown> }
interface GEdge    { source: string; target: string; relationship: string }

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

interface MarketIndex { name: string; ticker: string; value: string; pct_change: number; positive: boolean; change_str: string }
interface MarketStatus { is_open: boolean; status: string; time_ist: string; date: string }
interface MarketData { marketStatus: MarketStatus; marketIndices: MarketIndex[] }
interface ChartPoint { label: string; value: number }

// ── Helpers ────────────────────────────────────────────────────────────────────
const TABS = ["Overview", "Timeline", "Impact Analysis", "Companies", "Sectors", "Historical Events", "Related News", "Graph"] as const;
type TabName = typeof TABS[number];

function scoreColor(s: number) {
  if (s >= 85) return { text: "text-rose-400",    ring: "#f43f5e", glow: "shadow-rose-500/20" };
  if (s >= 70) return { text: "text-amber-400",   ring: "#f59e0b", glow: "shadow-amber-500/20" };
  if (s >= 50) return { text: "text-sky-400",     ring: "#38bdf8", glow: "shadow-sky-500/20" };
  return          { text: "text-slate-400",    ring: "#64748b", glow: "" };
}

function scoreLabel(s: number) {
  if (s >= 85) return "Very High Impact";
  if (s >= 70) return "High Impact";
  if (s >= 50) return "Medium Impact";
  return "Low Impact";
}

function impactBg(v?: string) {
  if (!v) return "bg-slate-700/40 text-slate-400";
  if (v === "positive" || v === "bullish") return "bg-emerald-500/20 text-emerald-300";
  if (v === "negative" || v === "bearish") return "bg-rose-500/20 text-rose-300";
  return "bg-amber-500/20 text-amber-300";
}

function formatDate(s?: string) {
  if (!s) return "";
  try { return new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); }
  catch { return s.slice(0, 10); }
}

function sourceInitials(src: string) {
  return src.split(/[\s\-_]/g).slice(0, 2).map(w => w[0] || "").join("").toUpperCase() || "N";
}

// ── Sub-components ─────────────────────────────────────────────────────────────
function ScoreRing({ score, size = 88 }: { score: number; size?: number }) {
  const sc = scoreColor(score);
  const r  = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgba(255,255,255,0.06)" strokeWidth={6} fill="none"/>
        <circle cx={size/2} cy={size/2} r={r} stroke={sc.ring} strokeWidth={6} fill="none"
          strokeLinecap="round" strokeDasharray={`${dash} ${circ}`}
          style={{ filter: `drop-shadow(0 0 6px ${sc.ring}80)` }}/>
      </svg>
      <div className="absolute text-center">
        <div className={`text-2xl font-black leading-none ${sc.text}`}>{Math.round(score)}</div>
        <div className="text-[8px] text-slate-500 mt-0.5">/ 100</div>
      </div>
    </div>
  );
}

function Card({ title, action, children, className = "" }: {
  title?: string; action?: React.ReactNode; children: React.ReactNode; className?: string
}) {
  return (
    <div className={`rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl ${className}`}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between">
          {title && <h3 className="text-[12px] font-semibold uppercase tracking-wider text-slate-400">{title}</h3>}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

function EmptyState({ msg }: { msg: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center">
      <div className="mb-2 h-8 w-8 rounded-full bg-white/[0.04] flex items-center justify-center">
        <svg className="h-4 w-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
      </div>
      <p className="text-[12px] text-slate-600">{msg}</p>
    </div>
  );
}

function PendingBanner() {
  return (
    <div className="mb-4 flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3">
      <div className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-amber-400 border-t-transparent"/>
      <div>
        <span className="text-[13px] font-semibold text-amber-300">AI enrichment in progress</span>
        <span className="ml-2 text-[11px] text-amber-400/70">Companies, sectors, timeline will populate automatically.</span>
      </div>
    </div>
  );
}

// ── Overview ───────────────────────────────────────────────────────────────────
function OverviewTab({ data, goTab }: { data: EventDetail; goTab: (t: TabName) => void }) {
  const isPending = data.event.enrichment_status !== "done";

  return (
    <div className="space-y-4">
      {isPending && <PendingBanner/>}

      {/* AI Summary */}
      {data.summary.text && (
        <Card>
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-violet-500/20">
              <svg className="h-4 w-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-violet-400">AI Summary</p>
              <p className="text-[13px] leading-5 text-slate-300">{data.summary.text}</p>
              {data.summary.key_bullets?.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {data.summary.key_bullets.map((b, i) => (
                    <li key={i} className="flex items-start gap-2 text-[12px] text-slate-400">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400"/>
                      {b}
                    </li>
                  ))}
                </ul>
              )}
              <button onClick={() => goTab("Impact Analysis")}
                className="mt-3 flex items-center gap-1 text-[12px] font-medium text-violet-400 hover:text-violet-300 transition">
                Read Full AI Analysis
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
                </svg>
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Three columns */}
      <div className="grid grid-cols-3 gap-3">
        {/* Beneficiaries */}
        <Card title="Beneficiary Companies"
          action={data.beneficiaries.length > 3 && (
            <button onClick={() => goTab("Companies")} className="text-[11px] text-sky-400 hover:text-sky-300">View All →</button>
          )}>
          {data.beneficiaries.length === 0 ? (
            <EmptyState msg="No beneficiaries identified yet"/>
          ) : (
            <div className="space-y-2">
              {data.beneficiaries.slice(0, 5).map((c, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-4 text-[10px] text-slate-600 font-medium text-right">{i + 1}</span>
                  <Link href={`/stocks/${c.symbol}`}
                    className="flex-1 min-w-0 text-[12px] font-medium text-slate-200 hover:text-emerald-300 transition truncate">
                    {c.name || c.symbol}
                  </Link>
                  <span className="shrink-0 text-[12px] font-bold text-emerald-400">
                    {c.impact_score > 0 ? `+${Math.round(c.impact_score)}` : Math.round(c.impact_score)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Negatively Affected */}
        <Card title="Negatively Affected"
          action={data.losers.length > 3 && (
            <button onClick={() => goTab("Companies")} className="text-[11px] text-sky-400 hover:text-sky-300">View All →</button>
          )}>
          {data.losers.length === 0 ? (
            <EmptyState msg="No negatively affected companies identified yet"/>
          ) : (
            <div className="space-y-2">
              {data.losers.slice(0, 5).map((c, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-4 text-[10px] text-slate-600 font-medium text-right">{i + 1}</span>
                  <Link href={`/stocks/${c.symbol}`}
                    className="flex-1 min-w-0 text-[12px] font-medium text-slate-200 hover:text-rose-300 transition truncate">
                    {c.name || c.symbol}
                  </Link>
                  <span className="shrink-0 text-[12px] font-bold text-rose-400">
                    {Math.round(c.impact_score)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Affected Sectors */}
        <Card title="Affected Sectors"
          action={data.affectedSectors.length > 3 && (
            <button onClick={() => goTab("Sectors")} className="text-[11px] text-sky-400 hover:text-sky-300">View All →</button>
          )}>
          {data.affectedSectors.length === 0 ? (
            <EmptyState msg="No sectors identified yet"/>
          ) : (
            <div className="space-y-2">
              {data.affectedSectors.slice(0, 5).map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="flex-1 text-[12px] text-slate-300 truncate">{s.sector}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-semibold capitalize ${impactBg(s.impact)}`}>
                    {s.impact === "positive" ? "Very High" : s.impact === "negative" ? "High" : "Medium"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Timeline + Historical side-by-side */}
      <div className="grid grid-cols-2 gap-3">
        {/* Timeline */}
        <Card title="Timeline"
          action={data.timeline.length > 3 && (
            <button onClick={() => goTab("Timeline")} className="flex items-center gap-1 text-[11px] text-sky-400 hover:text-sky-300">
              View Full Timeline →
            </button>
          )}>
          {data.timeline.length === 0 ? (
            <EmptyState msg="Timeline not yet generated"/>
          ) : (
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

        {/* Historical Similar Events */}
        <Card title="Historical Similar Events"
          action={data.historicalEvents.length > 2 && (
            <button onClick={() => goTab("Historical Events")} className="text-[11px] text-sky-400 hover:text-sky-300">View All →</button>
          )}>
          {data.historicalEvents.length === 0 ? (
            <EmptyState msg="No similar historical events found"/>
          ) : (
            <div className="space-y-3">
              {data.historicalEvents.slice(0, 3).map((he, i) => (
                <Link key={i} href={`/events/${he.id}`}
                  className="flex items-start gap-3 rounded-xl border border-white/[0.05] p-2.5 hover:border-sky-500/20 hover:bg-sky-500/[0.04] transition block">
                  <div className="flex h-9 w-9 shrink-0 flex-col items-center justify-center rounded-xl bg-white/[0.05]">
                    <span className="text-[14px] font-black text-slate-200">{Math.round(he.impact_score)}</span>
                    <span className="text-[8px] text-slate-600">score</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-medium text-slate-200 line-clamp-2">{he.title}</p>
                    {he.reason && <p className="mt-0.5 text-[10px] text-slate-500 line-clamp-1">{he.reason}</p>}
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
    </div>
  );
}

// ── Timeline Tab ───────────────────────────────────────────────────────────────
function TimelineTab({ data }: { data: EventDetail }) {
  if (!data.timeline.length) return <EmptyState msg="Timeline will be generated once AI enrichment completes."/>;
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

// ── Impact Analysis Tab ────────────────────────────────────────────────────────
function ImpactTab({ data }: { data: EventDetail }) {
  const ai = data.aiAnalysis;
  const mr = data.marketReaction;
  const hasCases = ai.bull_case || ai.base_case || ai.bear_case;
  const hasMarket = Object.values(mr).some(Boolean);

  if (!hasCases && !hasMarket) return <EmptyState msg="AI impact analysis will be available after enrichment completes."/>;
  return (
    <div className="space-y-4">
      {hasCases && (
        <div className="grid grid-cols-3 gap-3">
          {ai.bull_case && (
            <Card>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-emerald-400">Bull Case</p>
              <p className="text-[13px] leading-5 text-slate-300">{ai.bull_case}</p>
            </Card>
          )}
          {ai.base_case && (
            <Card>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-amber-400">Base Case</p>
              <p className="text-[13px] leading-5 text-slate-300">{ai.base_case}</p>
            </Card>
          )}
          {ai.bear_case && (
            <Card>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-rose-400">Bear Case</p>
              <p className="text-[13px] leading-5 text-slate-300">{ai.bear_case}</p>
            </Card>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {ai.key_risks && ai.key_risks.length > 0 && (
          <Card title="Key Risks">
            <ul className="space-y-2">
              {ai.key_risks.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px] text-slate-300">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400"/>
                  {r}
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
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400"/>
                  {c}
                </li>
              ))}
            </ul>
          </Card>
        )}
        {data.summary.risk_factors?.length > 0 && (
          <Card title="Risk Factors">
            <ul className="space-y-2">
              {data.summary.risk_factors.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px] text-slate-300">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400"/>
                  {r}
                </li>
              ))}
            </ul>
          </Card>
        )}
        {data.summary.opportunities?.length > 0 && (
          <Card title="Opportunities">
            <ul className="space-y-2">
              {data.summary.opportunities.map((o, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px] text-slate-300">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400"/>
                  {o}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {hasMarket && (
        <Card title="Market Outlook">
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Short Term",  v: mr.short_term },
              { label: "Medium Term", v: mr.medium_term },
              { label: "Volatility",  v: mr.volatility },
              { label: "Sentiment",   v: mr.sentiment },
            ].map(row => (
              <div key={row.label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-center">
                <p className="text-[10px] text-slate-500">{row.label}</p>
                <span className={`mt-1.5 inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold capitalize ${impactBg(row.v)}`}>
                  {row.v || "—"}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// ── Companies Tab ──────────────────────────────────────────────────────────────
function CompaniesTab({ data }: { data: EventDetail }) {
  if (!data.companies.length) return <EmptyState msg="Company analysis not yet available."/>;
  return (
    <div className="space-y-3">
      {[
        { list: data.beneficiaries, label: "Beneficiaries",       color: "emerald", tag: "↑ BENEFIT" },
        { list: data.losers,        label: "Negatively Affected",  color: "rose",    tag: "↓ RISK" },
      ].filter(g => g.list.length > 0).map(group => (
        <Card key={group.label} title={group.label}>
          <div className="space-y-2">
            {group.list.map((c, i) => (
              <div key={i}
                className={`flex items-center gap-3 rounded-xl border px-3 py-2.5
                  ${group.color === "emerald"
                    ? "border-emerald-500/10 bg-emerald-500/[0.04]"
                    : "border-rose-500/10 bg-rose-500/[0.04]"}`}>
                <Link href={`/stocks/${c.symbol}`}
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[11px] font-bold transition
                    ${group.color === "emerald"
                      ? "bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
                      : "bg-rose-500/20 text-rose-300 hover:bg-rose-500/30"}`}>
                  {c.symbol.slice(0, 3)}
                </Link>
                <div className="min-w-0 flex-1">
                  <Link href={`/stocks/${c.symbol}`}
                    className={`text-[13px] font-semibold text-white hover:text-${group.color}-300 transition`}>
                    {c.name || c.symbol}
                  </Link>
                  {c.reason && <p className="text-[11px] text-slate-500 line-clamp-1">{c.reason}</p>}
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-[10px] text-slate-500">Impact Score</p>
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

// ── Sectors Tab ────────────────────────────────────────────────────────────────
function SectorsTab({ data }: { data: EventDetail }) {
  if (!data.affectedSectors.length) return <EmptyState msg="Sector analysis not yet available."/>;
  const maxScore = Math.max(...data.affectedSectors.map(s => s.impact_score), 1);
  return (
    <Card title="Affected Sectors">
      <div className="space-y-3">
        {data.affectedSectors.map((s, i) => (
          <div key={i}>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[13px] font-medium text-slate-200">{s.sector}</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize ${impactBg(s.impact)}`}>{s.impact}</span>
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

// ── Historical Tab ─────────────────────────────────────────────────────────────
function HistoricalTab({ data }: { data: EventDetail }) {
  if (!data.historicalEvents.length) return <EmptyState msg="No similar historical events found."/>;
  return (
    <div className="space-y-3">
      {data.historicalEvents.map((he, i) => (
        <Link key={i} href={`/events/${he.id}`}
          className="flex items-start gap-4 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 hover:border-sky-500/20 hover:bg-sky-500/[0.03] transition block">
          <div className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl bg-white/[0.05]">
            <span className="text-[18px] font-black text-slate-200 leading-none">{Math.round(he.impact_score)}</span>
            <span className="text-[8px] text-slate-500 mt-0.5">Impact</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[14px] font-semibold text-white line-clamp-2">{he.title}</p>
            <p className="mt-0.5 text-[11px] text-slate-500">{formatDate(he.event_date)}</p>
            {he.reason && <p className="mt-1.5 text-[12px] text-slate-400 line-clamp-2">{he.reason}</p>}
            {he.similarity_score > 0 && (
              <div className="mt-2 flex items-center gap-2">
                <div className="h-1 w-24 rounded bg-white/[0.06]">
                  <div className="h-1 rounded bg-violet-500" style={{ width: `${Math.round(he.similarity_score * 100)}%` }}/>
                </div>
                <span className="text-[10px] text-slate-500">{Math.round(he.similarity_score * 100)}% similar</span>
              </div>
            )}
          </div>
          <svg className="h-4 w-4 shrink-0 text-slate-600 mt-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
          </svg>
        </Link>
      ))}
    </div>
  );
}

// ── News Tab ───────────────────────────────────────────────────────────────────
function NewsTab({ data }: { data: EventDetail }) {
  if (!data.relatedNews.length) return <EmptyState msg="No related news articles linked to this event yet."/>;
  return (
    <div className="space-y-3">
      {data.relatedNews.map((n, i) => (
        <div key={i} className="flex items-start gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/20 text-[13px] font-bold text-sky-300">
            {sourceInitials(n.source)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[14px] font-semibold text-white">{n.headline}</p>
            <p className="mt-0.5 text-[11px] text-slate-500">{n.source} · {n.published_at}</p>
            {n.summary && <p className="mt-1.5 text-[12px] text-slate-400 line-clamp-2">{n.summary}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Graph Tab ──────────────────────────────────────────────────────────────────
function GraphTab({ data }: { data: EventDetail }) {
  if (!data.graph.nodes.length) return <EmptyState msg="Knowledge graph will be generated after AI enrichment."/>;

  const rfNodes = data.graph.nodes.map((n, i) => ({
    id: n.id, data: { label: n.label },
    position: { x: 100 + (i % 4) * 200, y: 80 + Math.floor(i / 4) * 140 },
    style: {
      background: n.type === "event" ? "#6366f1" : n.type === "company" ? "#22c55e" : "#f59e0b",
      color: "#fff", border: "none", borderRadius: 10, fontSize: 11, padding: "6px 10px",
    },
  }));

  const rfEdges = data.graph.edges.map((e, i) => ({
    id: `e${i}`, source: e.source, target: e.target,
    label: e.relationship,
    style: { stroke: "rgba(255,255,255,0.15)" },
    labelStyle: { fill: "#94a3b8", fontSize: 9 },
  }));

  return (
    <div className="h-[600px] w-full rounded-2xl overflow-hidden border border-white/10">
      <ReactFlow nodes={rfNodes} edges={rfEdges} fitView>
        <Background color="#1e293b" gap={16}/>
        <Controls style={{ background: "rgba(255,255,255,0.05)" }}/>
      </ReactFlow>
    </div>
  );
}

// ── Sidebar cards ──────────────────────────────────────────────────────────────
function NewsSidebar({ news }: { news: NewsItem[] }) {
  if (!news.length) return null;
  return (
    <Card title="Related News" action={<Link href="#" className="text-[11px] text-sky-400 hover:text-sky-300">View All</Link>}>
      <div className="space-y-3">
        {news.slice(0, 4).map((n, i) => (
          <div key={i} className="flex items-start gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-[10px] font-bold text-slate-400">
              {sourceInitials(n.source)}
            </div>
            <div className="min-w-0">
              <p className="text-[12px] font-medium text-slate-200 line-clamp-2 leading-4">{n.headline}</p>
              <p className="mt-0.5 text-[10px] text-slate-500">{n.source} · {n.published_at?.slice(0, 10)}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function PoliciesSidebar({ policies }: { policies: Policy[] }) {
  if (!policies.length) return null;
  return (
    <Card title="Government Policies" action={<Link href="#" className="text-[11px] text-sky-400 hover:text-sky-300">View All →</Link>}>
      <div className="space-y-3">
        {policies.map((p, i) => (
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
  );
}

function MarketSidebar({
  marketData, chartData, chartPeriod, onPeriod,
}: {
  marketData: MarketData | null;
  chartData: ChartPoint[];
  chartPeriod: string;
  onPeriod: (p: string) => void;
}) {
  const periods = ["1D", "5D", "1M", "3M", "6M"];
  const status = marketData?.marketStatus;
  const indices = marketData?.marketIndices ?? [];

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[12px] font-semibold uppercase tracking-wider text-slate-400">Market Reaction</h3>
        <div className="flex items-center gap-1.5">
          <div className={`h-1.5 w-1.5 rounded-full ${status?.is_open ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`}/>
          <span className="text-[10px] text-slate-500 capitalize">{status?.status ?? "—"}</span>
        </div>
      </div>

      {status?.date && (
        <p className="mb-2 text-[11px] text-slate-500">{status.date} · {status.time_ist}</p>
      )}

      {/* Period selector */}
      <div className="mb-3 flex gap-1">
        {periods.map(p => (
          <button key={p} onClick={() => onPeriod(p)}
            className={`flex-1 rounded-lg py-1 text-[10px] font-semibold transition ${
              chartPeriod === p
                ? "bg-white/[0.10] text-white"
                : "text-slate-500 hover:text-slate-300"
            }`}>
            {p}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="h-[100px] -mx-1">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
              <defs>
                <linearGradient id="mktGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3}/>
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="label" hide/>
              <YAxis domain={["auto", "auto"]} hide/>
              <RechartsTip
                contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, fontSize: 10, padding: "4px 8px" }}
                formatter={(v: number) => [v.toLocaleString("en-IN"), ""]}
              />
              <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={1.5} fill="url(#mktGrad)"/>
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-[11px] text-slate-600">Fetching market data…</p>
          </div>
        )}
      </div>

      {/* Index badges */}
      {indices.length > 0 && (
        <div className="mt-3 space-y-2 border-t border-white/[0.06] pt-3">
          {indices.map((idx, i) => (
            <div key={i} className="flex items-center justify-between">
              <span className="text-[11px] text-slate-400 truncate">{idx.name}</span>
              <span className={`text-[12px] font-bold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>
                {idx.change_str || "—"}
              </span>
            </div>
          ))}
        </div>
      )}

      {!status?.is_open && status && (
        <p className="mt-2 text-[10px] text-slate-600 text-center">
          {status.status === "weekend" ? "Market closed (weekend)" : "Market closed · Opens Mon 9:15 AM IST"}
        </p>
      )}
    </Card>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────────────────
function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-36 rounded-2xl bg-white/[0.04]"/>
      <div className="h-8 w-80 rounded-xl bg-white/[0.04]"/>
      <div className="grid grid-cols-[1fr_280px] gap-4">
        <div className="space-y-3">
          {[120, 200, 160, 180].map((h, i) => (
            <div key={i} className="rounded-2xl bg-white/[0.04]" style={{ height: h }}/>
          ))}
        </div>
        <div className="space-y-3">
          {[160, 200, 140].map((h, i) => (
            <div key={i} className="rounded-2xl bg-white/[0.04]" style={{ height: h }}/>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function EventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data,        setData]        = useState<EventDetail | null>(null);
  const [marketData,  setMarketData]  = useState<MarketData | null>(null);
  const [chartData,   setChartData]   = useState<ChartPoint[]>([]);
  const [chartPeriod, setChartPeriod] = useState("1D");
  const [activeTab,   setActiveTab]   = useState<TabName>("Overview");
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState("");

  // Fetch event + market data in parallel on mount
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
    }).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  // Fetch chart when period changes
  const handlePeriod = useCallback(async (period: string) => {
    setChartPeriod(period);
    if (!id) return;
    try {
      const r = await fetch(`${API}/api/events/${id}/market-chart?period=${period}`);
      if (r.ok) { const j = await r.json(); setChartData(j.data ?? []); }
    } catch { /* silent */ }
  }, [id]);

  // Auto-refresh market data every 60s during market hours
  useEffect(() => {
    if (!id) return;
    const interval = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/events/${id}/market-data`);
        if (r.ok) setMarketData(await r.json());
      } catch { /* silent */ }
    }, 60_000);
    return () => clearInterval(interval);
  }, [id]);

  if (loading) return <main className="min-w-0 pb-10"><Skeleton/></main>;
  if (error || !data) return (
    <main className="min-w-0 pb-10 flex flex-col items-center justify-center py-32">
      <p className="text-xl font-bold text-slate-400">Event not found</p>
      <p className="mt-1 text-[13px] text-slate-600">{error}</p>
      <Link href="/events" className="mt-5 text-sm text-sky-400 hover:text-sky-300">← Back to Events</Link>
    </main>
  );

  const ev = data.event;
  const sc = scoreColor(data.impactScore);
  const isPending = ev.enrichment_status !== "done";

  const impactTypeBadge = (score: number) => {
    const color = score >= 85 ? "bg-rose-500/20 text-rose-300 border-rose-500/30" :
                  score >= 70 ? "bg-amber-500/20 text-amber-300 border-amber-500/30" :
                                "bg-sky-500/20 text-sky-300 border-sky-500/30";
    return `rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${color}`;
  };

  const eventTypeBadge = "rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-0.5 text-[11px] text-slate-300 capitalize";

  return (
    <main className="min-w-0 pb-10">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="mb-5">
        <div className="mb-3 flex items-center justify-between">
          <Link href="/events" className="flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-slate-300 transition">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
            </svg>
            Back to Events
          </Link>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12px] text-slate-300 hover:bg-white/[0.08] transition">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/>
              </svg>
              Share
            </button>
            <button className="flex items-center gap-1.5 rounded-xl border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-[12px] text-violet-300 hover:bg-violet-500/20 transition">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>
              </svg>
              Add to Watchlist
            </button>
          </div>
        </div>

        <div className="flex items-start gap-6">
          {/* Left: title + meta */}
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={eventTypeBadge}>{ev.event_type}</span>
              {data.impactScore > 0 && (
                <span className={impactTypeBadge(data.impactScore)}>{scoreLabel(data.impactScore)}</span>
              )}
              {ev.source && (
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-0.5 text-[11px] text-slate-400">
                  {ev.source}
                </span>
              )}
            </div>

            <h1 className="text-2xl font-bold leading-snug text-white">{ev.title}</h1>

            <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
              {ev.event_date && (
                <span className="flex items-center gap-1">
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                  </svg>
                  {formatDate(ev.event_date)}
                </span>
              )}
              {ev.source && (
                <span className="flex items-center gap-1">
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-2 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
                  </svg>
                  {ev.source}
                </span>
              )}
              <span className="flex items-center gap-1">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"/>
                </svg>
                ID: {ev.id}
              </span>
              {isPending && (
                <span className="flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-amber-300">
                  <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400"/>
                  AI enriching…
                </span>
              )}
            </div>
          </div>

          {/* Right: Score + Confidence */}
          <div className="flex shrink-0 items-center gap-4">
            <div className="text-center">
              <ScoreRing score={data.impactScore > 0 ? data.impactScore : 0} size={88}/>
              <p className="mt-1 text-[10px] text-slate-500">Impact Score</p>
              {data.impactScore > 0 && (
                <p className={`mt-0.5 text-[10px] font-semibold ${sc.text}`}>{scoreLabel(data.impactScore)}</p>
              )}
            </div>
            <div className="text-center">
              <ScoreRing score={data.confidence > 0 ? data.confidence : 0} size={88}/>
              <p className="mt-1 text-[10px] text-slate-500">Confidence</p>
              {data.confidence > 0 && (
                <p className={`mt-0.5 text-[10px] font-semibold ${scoreColor(data.confidence).text}`}>
                  {data.confidence >= 85 ? "High Confidence" : data.confidence >= 60 ? "Moderate" : "Low Confidence"}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Tab bar ─────────────────────────────────────────────────────── */}
      <div className="mb-5 flex gap-0.5 overflow-x-auto rounded-xl border border-white/[0.06] bg-white/[0.02] p-1">
        {TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`shrink-0 rounded-lg px-4 py-1.5 text-[12px] font-medium transition ${
              activeTab === tab
                ? "bg-white/[0.10] text-white"
                : "text-slate-500 hover:text-slate-300"
            }`}>
            {tab}
          </button>
        ))}
      </div>

      {/* ── Content + Sidebar ────────────────────────────────────────────── */}
      <div className="grid grid-cols-[1fr_280px] items-start gap-4">

        {/* Main content */}
        <div className="min-w-0">
          {activeTab === "Overview"          && <OverviewTab  data={data} goTab={setActiveTab}/>}
          {activeTab === "Timeline"          && <TimelineTab  data={data}/>}
          {activeTab === "Impact Analysis"   && <ImpactTab    data={data}/>}
          {activeTab === "Companies"         && <CompaniesTab data={data}/>}
          {activeTab === "Sectors"           && <SectorsTab   data={data}/>}
          {activeTab === "Historical Events" && <HistoricalTab data={data}/>}
          {activeTab === "Related News"      && <NewsTab       data={data}/>}
          {activeTab === "Graph"             && <GraphTab      data={data}/>}
        </div>

        {/* Sidebar — always visible */}
        <aside className="sticky top-[80px] space-y-4">
          <NewsSidebar news={data.relatedNews}/>
          <PoliciesSidebar policies={data.governmentPolicies}/>
          <MarketSidebar
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
