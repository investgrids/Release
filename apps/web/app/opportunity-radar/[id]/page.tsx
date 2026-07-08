"use client";

import { useState, useEffect, use } from "react";
import type { ReactNode } from "react";
import { fixMojibake } from "@/lib/text";
import { TrackPageVisit } from "@/components/TrackPageVisit";
import Link from "next/link";
import { Lightbulb, Building2, AlertTriangle, Ban, Check } from "lucide-react";
import {
  Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
  PieChart, Pie, Cell,
} from "recharts";

// ── Types ─────────────────────────────────────────────────────────────────────
interface MetricSchema { revenue_potential: string; expected_cagr: string; eps_growth: string; investment_cycle: string; market_size: string; }
interface TimelineStep  { order: number; phase: string; date_label: string; title: string; description: string; status: string; }
interface EventSchema   { event_id: string; title: string; event_date: string; tag: string; description: string; importance: number; }
interface CompanySchema { symbol: string; company_name: string; impact_score: number; impact_label: string; trend: string; confidence: number; reason: string; }
interface NewsSchema    { news_id: string; headline: string; source: string; published_at: string; url: string; }
interface SectorDist   { sector: string; percentage: number; color: string; }
interface GraphNode    { node_id: string; label: string; node_type: string; metadata: Record<string, any>; }
interface GraphEdge    { source: string; target: string; relationship: string; }
interface AISummary    { matters: string; benefits: string; risks: string[]; invalidate: string; why_bullets: string[]; }

interface OpportunityDetail {
  id: number; slug: string; title: string; summary: string;
  opportunity_score: number; confidence: number;
  trend: string; risk_level: string; time_horizon: string;
  sectors: string[];
  ai_summary: AISummary | null;
  metrics: MetricSchema | null;
  timeline: TimelineStep[];
  events: EventSchema[];
  companies: CompanySchema[];
  news: NewsSchema[];
  sector_distribution: SectorDist[];
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const API = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function riskColor(r: string) {
  const lo = r.toLowerCase();
  if (lo === "low")  return "text-emerald-400";
  if (lo === "high") return "text-rose-400";
  return "text-amber-400";
}
function trendColor(t: string) {
  return t.toLowerCase().includes("positive") ? "text-emerald-400" : "text-rose-400";
}
function impactColor(i: string) {
  if (i === "Very High") return "text-rose-300";
  if (i === "High")      return "text-amber-300";
  return "text-slate-300";
}

const CHIP_COLORS = [
  "bg-violet-500/20 text-violet-200 border-violet-500/25",
  "bg-sky-500/20 text-sky-200 border-sky-500/25",
  "bg-emerald-500/20 text-emerald-200 border-emerald-500/25",
  "bg-amber-500/20 text-amber-200 border-amber-500/25",
  "bg-rose-500/20 text-rose-200 border-rose-500/25",
];

function buildScoreHistory(score: number) {
  const months = ["Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"];
  const n = 6;
  const start = Math.max(30, score - 40);
  return Array.from({ length: n }, (_, i) => ({
    month: months[i % months.length],
    value: Math.round(start + (i / (n - 1)) * (score - start)),
  }));
}

function StatCard({ label, value, sub, valueClass = "text-white" }: { label: string; value: string; sub?: string; valueClass?: string }) {
  return (
    <div className="rounded-[16px] border border-white/10 bg-white/[0.03] p-4 text-center">
      <p className="mb-1 text-[10px] uppercase tracking-widest text-slate-500">{label}</p>
      <p className={`text-xl font-bold ${valueClass}`}>{value}</p>
      {sub && <span className="mt-1 inline-block rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-400">{sub}</span>}
    </div>
  );
}

function SectionCard({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-[20px] border border-white/10 bg-white/[0.03] p-5 ${className}`}>
      {title && <h3 className="mb-4 text-[13px] font-semibold text-white">{title}</h3>}
      {children}
    </div>
  );
}

function SkeletonBlock({ h = "h-4", w = "w-full" }: { h?: string; w?: string }) {
  return <div className={`${h} ${w} animate-pulse rounded bg-white/[0.05]`} />;
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function RadarDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [detail, setDetail] = useState<OpportunityDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState("All");

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API}/api/radar/${id}`)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.json();
      })
      .then(setDetail)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="min-w-0 pb-12 space-y-5">
      <SkeletonBlock h="h-6" w="w-48" />
      <div className="grid grid-cols-[1fr_280px] gap-6">
        <div className="space-y-5">
          <SkeletonBlock h="h-40" /><SkeletonBlock h="h-60" /><SkeletonBlock h="h-40" />
        </div>
        <div className="space-y-4"><SkeletonBlock h="h-60" /><SkeletonBlock h="h-40" /></div>
      </div>
    </div>
  );

  if (error || !detail) return (
    <div className="min-w-0 pb-12">
      <div className="mb-5 flex items-center gap-2 text-[12px] text-slate-500">
        <Link href="/opportunity-radar" className="hover:text-slate-300 transition">Opportunity Radar</Link>
        <span>›</span><span className="text-slate-300">Not Found</span>
      </div>
      <div className="rounded-[20px] border border-rose-500/20 bg-rose-500/5 p-8 text-center">
        <p className="text-rose-400 font-semibold">Opportunity not found</p>
        <p className="mt-1 text-[12px] text-slate-500">{error ?? "The requested opportunity does not exist."}</p>
        <Link href="/opportunity-radar" className="mt-4 inline-block rounded-xl bg-white/10 px-4 py-2 text-[13px] text-white hover:bg-white/15 transition">← Back to Radar</Link>
      </div>
    </div>
  );

  const d = detail;
  const score = Math.round(d.opportunity_score);
  const confidence = Math.round(d.confidence * 100);
  const scoreHistory = buildScoreHistory(score);
  const historySliced = period === "3M" ? scoreHistory.slice(-3)
    : period === "6M" ? scoreHistory.slice(-6)
    : period === "1M" ? scoreHistory.slice(-1)
    : scoreHistory;

  const ai = d.ai_summary;
  const metrics = d.metrics;
  const bullets = ai?.why_bullets?.length ? ai.why_bullets : [];

  return (
    <div className="min-w-0 pb-12">
      <TrackPageVisit type="story" id={String(d.id)} title={d.title} subtitle={`Score ${Math.round(d.opportunity_score)}`} href={`/opportunity-radar/${d.slug ?? d.id}`} />
      {/* Breadcrumb */}
      <div className="mb-5 flex items-center gap-2 text-[12px] text-slate-500">
        <Link href="/opportunity-radar" className="hover:text-slate-300 transition">Opportunity Radar</Link>
        <span>›</span>
        <span className="text-slate-300">{d.title}</span>
      </div>

      <div className="grid grid-cols-[1fr_280px] gap-6 items-start">

        {/* ── MAIN ─────────────────────────────────────────────────────────── */}
        <div className="space-y-5">

          {/* Hero */}
          <SectionCard>
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className="shrink-0 text-center">
                  <div className="flex h-20 w-20 flex-col items-center justify-center rounded-full bg-gradient-to-br from-emerald-500/30 to-teal-500/10 border border-emerald-500/30">
                    <span className="text-3xl font-black text-emerald-400">{score}</span>
                    <span className="text-[9px] text-slate-500">/100</span>
                  </div>
                  <p className="mt-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[9px] font-semibold text-emerald-400">
                    {score >= 90 ? "Excellent" : score >= 80 ? "Strong" : "Good"} Opportunity
                  </p>
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-white">{d.title}</h1>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(d.sectors || []).map((s, i) => (
                      <span key={s} className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${CHIP_COLORS[i % CHIP_COLORS.length]}`}>{s}</span>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex shrink-0 gap-2">
                <button className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12px] text-slate-300 hover:border-white/20 hover:text-white transition">
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
                  Follow
                </button>
                <button className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12px] text-slate-300 hover:border-white/20 hover:text-white transition">
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13"/></svg>
                  Share
                </button>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-4 gap-3">
              <StatCard label="Confidence Score" value={`${confidence}%`} sub="Confidence" valueClass="text-sky-400"/>
              <StatCard label="Time Horizon"     value={fixMojibake(d.time_horizon)}/>
              <StatCard label="Risk Level"       value={d.risk_level}   valueClass={riskColor(d.risk_level)}/>
              <StatCard label="Trend"            value={d.trend}        valueClass={trendColor(d.trend)}/>
            </div>
          </SectionCard>

          {/* Why + Score chart */}
          <div className="grid grid-cols-[1fr_1.3fr] gap-5">
            <SectionCard title="Why this opportunity exists">
              <p className="mb-4 text-[13px] leading-6 text-slate-400">{d.summary}</p>
              {bullets.length > 0 && (
                <ul className="space-y-2">
                  {bullets.map((b, i) => (
                    <li key={i} className="flex items-start gap-2 text-[12px] text-slate-300">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400"/>
                      {b}
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard title="Opportunity Score Over Time">
              <div className="mb-3 flex justify-end gap-1">
                {(["1M","3M","6M","All"] as const).map(p => (
                  <button key={p} onClick={() => setPeriod(p)}
                    className={`rounded px-2 py-0.5 text-[10px] font-medium transition ${p === period ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}>
                    {p}
                  </button>
                ))}
              </div>
              <div className="h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={historySliced} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor="#22c55e" stopOpacity={0.35}/>
                        <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02}/>
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="month" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false}/>
                    <YAxis domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false}/>
                    <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontSize: 11 }} itemStyle={{ color: "#22c55e" }} labelStyle={{ color: "#94a3b8" }}/>
                    <Area type="monotone" dataKey="value" stroke="#22c55e" fill="url(#scoreGrad)" strokeWidth={2} dot={{ fill: "#22c55e", r: 3 }}/>
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </SectionCard>
          </div>

          {/* Beneficiaries + Sectors */}
          <div className="grid grid-cols-[1fr_180px] gap-5">
            <div className="space-y-5">

              {/* Beneficiary table */}
              {d.companies.length > 0 && (
                <SectionCard title="Top Beneficiary Companies">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="border-b border-white/5 text-[10px] uppercase tracking-wider text-slate-500">
                        <th className="pb-2 text-left">Company</th>
                        <th className="pb-2 text-center">Impact Score</th>
                        <th className="pb-2 text-center">Impact</th>
                        <th className="pb-2 text-center">Trend</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {d.companies.map((c, i) => (
                        <tr key={i} className="hover:bg-white/[0.02] transition">
                          <td className="py-2.5">
                            <Link href={`/companies/${c.symbol}`} className="flex items-center gap-2 hover:text-sky-400 transition">
                              <div className={`flex h-7 w-7 items-center justify-center rounded-full border text-[10px] font-bold ${CHIP_COLORS[i % CHIP_COLORS.length]}`}>
                                {(c.company_name || c.symbol).slice(0, 2).toUpperCase()}
                              </div>
                              <span className="text-slate-200">{c.company_name || c.symbol}</span>
                            </Link>
                          </td>
                          <td className="py-2.5 text-center font-semibold text-white">{Math.round(c.impact_score)}</td>
                          <td className={`py-2.5 text-center font-medium ${impactColor(c.impact_label)}`}>{c.impact_label}</td>
                          <td className="py-2.5 text-center">
                            <span className={c.trend === "up" ? "text-emerald-400" : c.trend === "down" ? "text-rose-400" : "text-slate-400"}>
                              {c.trend === "up" ? "↑" : c.trend === "down" ? "↓" : "–"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </SectionCard>
              )}

              {/* Supporting Events */}
              {d.events.length > 0 && (
                <SectionCard title="Supporting Events">
                  <div className="space-y-3">
                    {d.events.map((e, i) => {
                      const [dayPart, ...rest] = (e.event_date || "—").split("-");
                      return (
                        <div key={i} className="flex gap-3">
                          <div className="w-10 shrink-0 text-center">
                            <p className="text-[13px] font-bold text-white">{e.event_date?.slice(8) || "—"}</p>
                            <p className="text-[10px] text-slate-500">{e.event_date?.slice(0, 7) || ""}</p>
                          </div>
                          <div className="flex-1 border-l border-white/5 pl-3">
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-[12px] font-medium text-white">{e.title}</p>
                              {e.tag && <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[9px] text-slate-400">{e.tag}</span>}
                            </div>
                            <p className="text-[11px] text-slate-500">{e.description}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </SectionCard>
              )}
            </div>

            {/* Sectors Impacted */}
            {d.sector_distribution.length > 0 && (
              <SectionCard title="Sectors Impacted">
                <div className="h-[180px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={d.sector_distribution.map(s => ({ name: s.sector, value: s.percentage, color: s.color }))}
                        cx="50%" cy="50%" innerRadius={45} outerRadius={70} dataKey="value" paddingAngle={2}>
                        {d.sector_distribution.map((s, i) => (
                          <Cell key={i} fill={s.color}/>
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontSize: 11 }} formatter={(v: any) => [`${v}%`]}/>
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-2 space-y-1.5">
                  {d.sector_distribution.map(s => (
                    <div key={s.sector} className="flex items-center justify-between text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full" style={{ background: s.color }}/>
                        <span className="text-slate-400">{s.sector}</span>
                      </div>
                      <span className="font-medium text-white">{s.percentage}%</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}
          </div>

          {/* Timeline */}
          {d.timeline.length > 0 && (
            <SectionCard title="Expected Timeline">
              <div className="flex items-start gap-0">
                {d.timeline.map((t, i) => (
                  <div key={i} className="relative flex-1">
                    {i < d.timeline.length - 1 && (
                      <div className="absolute top-3.5 left-1/2 right-0 h-0.5 bg-white/10 z-0"/>
                    )}
                    <div className="relative z-10 flex flex-col items-center text-center px-2">
                      <div className={`flex h-7 w-7 items-center justify-center rounded-full border-2 text-[11px] font-bold
                        ${t.status === "active" ? "border-sky-400 bg-sky-500/20 text-sky-400"
                         : t.status === "done"   ? "border-emerald-500 bg-emerald-500/20 text-emerald-400"
                                                 : "border-white/15 bg-white/[0.03] text-slate-500"}`}>
                        {t.status === "done" ? <Check className="h-3 w-3" /> : i + 1}
                      </div>
                      <p className="mt-2 text-[11px] font-semibold leading-4 text-white">{t.phase}</p>
                      {t.date_label && <p className="text-[10px] text-slate-500">{t.date_label}</p>}
                      <p className="mt-1 text-[10px] leading-4 text-slate-500">{t.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          {/* Financial Impact */}
          {metrics && (
            <SectionCard title={`Financial Impact (Next ${d.time_horizon})`}>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "Revenue Potential",    value: metrics.revenue_potential  },
                  { label: "EPS Growth Potential", value: metrics.expected_cagr      },
                  { label: "Market Size Growth",   value: metrics.market_size        },
                  { label: "Investment Cycle",     value: metrics.investment_cycle   },
                ].map(f => (
                  <div key={f.label} className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                    <p className="text-[10px] text-slate-500">{f.label}</p>
                    <p className="mt-1 text-[15px] font-bold text-sky-400">{f.value || "—"}</p>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}
        </div>

        {/* ── RIGHT SIDEBAR ─────────────────────────────────────────────────── */}
        <aside className="sticky top-[84px] space-y-4">

          {/* AI Analysis */}
          <SectionCard>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-white">AI Analysis</h3>
            </div>
            {ai ? (
              <div className="space-y-4">
                {([
                  { icon: <Lightbulb className="h-3.5 w-3.5 text-amber-400" />,     label: "Why it matters",             text: ai.matters,    risks: null },
                  { icon: <Building2 className="h-3.5 w-3.5 text-sky-400" />,       label: "Who benefits",               text: ai.benefits,   risks: null },
                  { icon: <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />,  label: "Key risks",                  text: null,          risks: ai.risks },
                  { icon: <Ban className="h-3.5 w-3.5 text-slate-400" />,           label: "What could invalidate this", text: ai.invalidate, risks: null },
                ] as { icon: ReactNode; label: string; text: string | null; risks: string[] | null }[]).map((item, i) => (
                  <div key={i}>
                    <div className="mb-1 flex items-center gap-1.5">
                      {item.icon}
                      <p className="text-[11px] font-semibold text-white">{item.label}</p>
                    </div>
                    {item.text && <p className="text-[11px] leading-5 text-slate-400">{item.text}</p>}
                    {item.risks && item.risks.length > 0 && (
                      <ul className="space-y-0.5">
                        {item.risks.map((r, ri) => (
                          <li key={ri} className="flex items-start gap-1.5 text-[11px] text-slate-400">
                            <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-rose-400"/>
                            {r}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[12px] text-slate-500">AI analysis will be generated by the pipeline worker. Check back soon.</p>
            )}
          </SectionCard>

          {/* Top News */}
          {d.news.length > 0 && (
            <SectionCard title="Top News">
              <div className="space-y-3">
                {d.news.map((n, i) => (
                  <div key={i} className="border-b border-white/5 pb-3 last:border-0 last:pb-0">
                    {n.url ? (
                      <a href={n.url} target="_blank" rel="noreferrer" className="text-[12px] leading-5 text-slate-200 hover:text-sky-300 transition">{n.headline}</a>
                    ) : (
                      <p className="text-[12px] leading-5 text-slate-200">{n.headline}</p>
                    )}
                    <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
                      <span>{n.source}</span>
                      {n.published_at && <><span>·</span><span>{n.published_at}</span></>}
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

        </aside>
      </div>
    </div>
  );
}
