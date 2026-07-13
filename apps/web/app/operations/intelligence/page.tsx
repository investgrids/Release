"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Activity, Zap, CheckCircle2, XCircle, Clock, RefreshCw,
  Eye, ChevronLeft, ChevronRight, AlertTriangle, Sparkles,
  BarChart3, Brain, Database, Network, BookOpen, TrendingUp,
  GitBranch, Shield, RotateCcw, Layers, FileText, Timer,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/* ─── Types ─────────────────────────────────────────────── */
interface EngineStatus {
  engine: { status: string; running: boolean; last_run: string | null; avg_publish_time_s: number; errors: number; articles_waiting: number };
  market_story: { status: string; mie_hash: string | null };
  today: { published: number; updated: number; generated: number; validation_failures: number; max_per_day: number; remaining_slots: number };
  totals: { total: number; published: number };
  quality: { avg_confidence: number; avg_seo_score: number };
  subsystems: Record<string, string>;
}

interface Article {
  id: string; slug: string; article_type: string; story_id: string | null;
  story_version: number; lifecycle_status: string; status: string;
  headline: string; key_takeaway: string | null; executive_summary: string | null;
  sectors_affected: any[]; companies_affected: any[]; update_count: number;
  validation_passed: boolean; validation_failures: number; event_score: number;
  confidence_score: number; quality_score: number; seo_score: number;
  trigger_type: string | null; trigger_event_id: string | null;
  published_at: string | null; last_updated: string | null; created_at: string | null;
}

/* ─── Label maps ─────────────────────────────────────────── */
const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  morning_intelligence:     { label: "Morning",     color: "bg-amber-500/15 text-amber-400 border-amber-500/25" },
  breaking_intelligence:    { label: "Breaking",    color: "bg-rose-500/15 text-rose-400 border-rose-500/25" },
  company_intelligence:     { label: "Company",     color: "bg-sky-500/15 text-sky-400 border-sky-500/25" },
  sector_intelligence:      { label: "Sector",      color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25" },
  theme_intelligence:       { label: "Theme",       color: "bg-violet-500/15 text-violet-400 border-violet-500/25" },
  policy_intelligence:      { label: "Policy",      color: "bg-teal-500/15 text-teal-400 border-teal-500/25" },
  ripple_intelligence:      { label: "Ripple",      color: "bg-orange-500/15 text-orange-400 border-orange-500/25" },
  opportunity_intelligence: { label: "Opportunity", color: "bg-lime-500/15 text-lime-400 border-lime-500/25" },
  market_wrap:              { label: "Wrap",        color: "bg-indigo-500/15 text-indigo-400 border-indigo-500/25" },
  weekly_intelligence:      { label: "Weekly",      color: "bg-purple-500/15 text-purple-400 border-purple-500/25" },
  monthly_intelligence:     { label: "Monthly",     color: "bg-cyan-500/15 text-cyan-400 border-cyan-500/25" },
  educational_intelligence: { label: "Education",   color: "bg-slate-500/15 text-slate-400 border-slate-600/30" },
};

const LC_CFG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  published:  { icon: CheckCircle2, color: "text-emerald-400",  label: "Published" },
  updated:    { icon: RotateCcw,    color: "text-sky-400",      label: "Updated" },
  generated:  { icon: Sparkles,     color: "text-violet-400",   label: "Generated" },
  validated:  { icon: Shield,       color: "text-teal-400",     label: "Validated" },
  failed:     { icon: XCircle,      color: "text-rose-400",     label: "Failed" },
  merged:     { icon: GitBranch,    color: "text-amber-400",    label: "Merged" },
  archived:   { icon: Layers,       color: "text-slate-500",    label: "Archived" },
};

/* ─── Sub-components ─────────────────────────────────────── */
function StatusDot({ active }: { active: boolean }) {
  return (
    <span className={`inline-block h-2 w-2 rounded-full ${active ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`} />
  );
}

function MetricPill({ label, value, warn = false }: { label: string; value: string | number; warn?: boolean }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-white/[0.06] bg-white/[0.02] px-4 py-3 min-w-[100px]">
      <div className={`text-[22px] font-bold tabular-nums ${warn ? "text-rose-400" : "text-white"}`}>{value}</div>
      <div className="text-[10px] font-medium uppercase tracking-widest text-slate-600 mt-0.5 text-center">{label}</div>
    </div>
  );
}

function SubsystemRow({ name, status }: { name: string; status: string }) {
  const icons: Record<string, React.ElementType> = {
    knowledge_graph: Network, historical_memory: Database, learning_engine: Brain,
    mie: Activity, duplicate_detector: GitBranch,
  };
  const Icon = icons[name] || Shield;
  const ok = status === "active";
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/[0.04] last:border-0">
      <div className="flex items-center gap-2">
        <Icon className={`h-3.5 w-3.5 ${ok ? "text-slate-400" : "text-rose-400"}`} />
        <span className="text-[12px] text-slate-400 capitalize">{name.replace(/_/g, " ")}</span>
      </div>
      <span className={`text-[10px] font-bold uppercase ${ok ? "text-emerald-400" : "text-rose-400"}`}>{status}</span>
    </div>
  );
}

function SeoRing({ score }: { score: number }) {
  const r = 14, c = 16, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 80 ? "#34d399" : score >= 60 ? "#818cf8" : score > 0 ? "#fb923c" : "#374151";
  if (!score) return <span className="text-[11px] text-slate-600">—</span>;
  return (
    <div className="relative flex items-center justify-center" style={{ width: 36, height: 36 }}>
      <svg width={36} height={36} viewBox="0 0 32 32">
        <circle cx={16} cy={16} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={2.5} />
        <circle cx={16} cy={16} r={r} fill="none" stroke={color} strokeWidth={2.5}
          strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round"
          transform="rotate(-90 16 16)" />
      </svg>
      <span className="absolute text-[9px] font-bold" style={{ color }}>{score}</span>
    </div>
  );
}

/* ─── Main page ──────────────────────────────────────────── */
export default function OperationsIntelligence() {
  const [status, setStatus]     = useState<EngineStatus | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [total, setTotal]       = useState(0);
  const [page, setPage]         = useState(1);
  const [tab, setTab]           = useState("published");
  const [loading, setLoading]   = useState(true);
  const [lastRefresh, setLast]  = useState<Date | null>(null);
  const PAGE = 12;

  const loadStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/publishing/status`);
      if (r.ok) setStatus(await r.json());
    } catch {}
  }, []);

  const loadArticles = useCallback(async () => {
    setLoading(true);
    try {
      const lc = tab !== "all" ? `&lifecycle=${tab}` : "";
      const r = await fetch(`${API}/api/publishing/articles?limit=${PAGE}&offset=${(page - 1) * PAGE}${lc}`);
      if (r.ok) {
        const d = await r.json();
        setArticles(d.articles || []);
        setTotal(d.total || 0);
      }
    } catch {} finally {
      setLoading(false);
      setLast(new Date());
    }
  }, [page, tab]);

  useEffect(() => {
    loadStatus(); loadArticles();
    const id = setInterval(() => { loadStatus(); loadArticles(); }, 30_000);
    return () => clearInterval(id);
  }, [loadStatus, loadArticles]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE));
  const engineRunning = status?.engine.running ?? false;

  return (
    <div className="min-h-screen bg-[#020617] pb-16">
      <div className="mx-auto max-w-[1440px] px-6 py-8">

        {/* ── Header ────────────────────────────────────────────────────────── */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-500/25">
                <Brain className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-[20px] font-bold text-white leading-tight">Operations · Intelligence</h1>
                <p className="text-[11px] text-slate-500">Autonomous Market Intelligence Publishing Engine — Phase 8</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {lastRefresh && (
              <span className="text-[10px] text-slate-600">
                {lastRefresh.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
            )}
            <div className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold ${
              engineRunning
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-slate-600/40 bg-slate-800/40 text-slate-400"
            }`}>
              <StatusDot active={engineRunning} />
              {engineRunning ? "Engine Running" : "Engine Idle"}
            </div>
            <button onClick={() => { loadStatus(); loadArticles(); }}
              className="flex items-center gap-1.5 rounded-xl border border-white/[0.08] bg-white/[0.02] px-3 py-2 text-[11px] text-slate-400 hover:text-white transition">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
          {/* ── Left — main monitoring area ─────────────────────────────────── */}
          <div className="space-y-6">

            {/* Publishing Engine Status */}
            <section className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="h-4 w-4 text-slate-500" />
                <span className="text-[12px] font-bold uppercase tracking-widest text-slate-500">Publishing Engine</span>
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <MetricPill label="Published Today" value={status?.today.published ?? "—"} />
                <MetricPill label="Updated Today"   value={status?.today.updated ?? "—"} />
                <MetricPill label="Generated"       value={status?.today.generated ?? "—"} />
                <MetricPill label="Val. Failures"   value={status?.today.validation_failures ?? "—"} warn={(status?.today.validation_failures ?? 0) > 0} />
                <MetricPill label="Slots Remaining" value={status?.today.remaining_slots ?? "—"} />
                <MetricPill label="Waiting"         value={status?.engine.articles_waiting ?? "—"} />

                <div className="ml-auto flex flex-col gap-2 text-right">
                  <div>
                    <div className="text-[10px] text-slate-600 uppercase tracking-widest">Avg Publish Time</div>
                    <div className="text-[18px] font-bold text-white tabular-nums">{status?.engine.avg_publish_time_s ?? "—"}s</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-600 uppercase tracking-widest">Errors</div>
                    <div className={`text-[18px] font-bold tabular-nums ${(status?.engine.errors ?? 0) > 0 ? "text-rose-400" : "text-slate-400"}`}>{status?.engine.errors ?? 0}</div>
                  </div>
                </div>
              </div>
            </section>

            {/* Market Story + Quality */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                { label: "Market Story",    value: status?.market_story.status ?? "—",            icon: TrendingUp,  color: "text-violet-400" },
                { label: "Avg Confidence",  value: `${status?.quality.avg_confidence ?? 0}%`,      icon: Brain,       color: "text-sky-400" },
                { label: "Total Published", value: String(status?.totals.published ?? "—"),         icon: BookOpen,    color: "text-emerald-400" },
                { label: "Last Run",        value: status?.engine.last_run ? new Date(status.engine.last_run).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "—", icon: Timer, color: "text-amber-400" },
              ].map(m => {
                const Icon = m.icon;
                return (
                  <div key={m.label} className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-600">{m.label}</span>
                      <Icon className={`h-4 w-4 ${m.color}`} />
                    </div>
                    <div className={`text-[18px] font-bold ${m.color}`}>{m.value}</div>
                  </div>
                );
              })}
            </div>

            {/* Articles table */}
            <section className="rounded-2xl border border-white/[0.07] bg-white/[0.015] overflow-hidden">
              {/* Table header */}
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.06] bg-white/[0.02]">
                <span className="text-[13px] font-bold text-white">Intelligence Articles</span>
                <div className="flex items-center gap-1">
                  {(["published", "updated", "failed", "all"] as const).map(t => (
                    <button key={t} onClick={() => { setTab(t); setPage(1); }}
                      className={`rounded-full px-2.5 py-1 text-[10px] font-semibold capitalize transition-all ${
                        tab === t ? "bg-violet-600 text-white" : "text-slate-500 hover:text-white hover:bg-white/[0.05]"
                      }`}>{t}</button>
                  ))}
                </div>
              </div>

              {/* Column labels */}
              <div className="grid items-center gap-2 px-5 py-2 border-b border-white/[0.04] bg-white/[0.01]"
                style={{ gridTemplateColumns: "1fr 110px 110px 50px 50px 40px 100px 44px" }}>
                {["ARTICLE", "TYPE", "LIFECYCLE", "CONF.", "QUAL.", "SEO", "PUBLISHED", ""].map(h => (
                  <div key={h} className="text-[9px] font-bold uppercase tracking-widest text-slate-700">{h}</div>
                ))}
              </div>

              {/* Rows */}
              {loading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="grid items-center gap-2 px-5 py-3.5 border-b border-white/[0.03] animate-pulse"
                    style={{ gridTemplateColumns: "1fr 110px 110px 50px 50px 40px 100px 44px" }}>
                    <div className="space-y-1.5"><div className="h-3 rounded-full bg-white/[0.05] w-3/4" /><div className="h-2 rounded-full bg-white/[0.03] w-1/2" /></div>
                    {[1,2,3,4,5,6,7].map(n => <div key={n} className="h-4 rounded-full bg-white/[0.04]" />)}
                  </div>
                ))
              ) : articles.length === 0 ? (
                <div className="py-20 text-center">
                  <Brain className="h-8 w-8 text-slate-700 mx-auto mb-3" />
                  <div className="text-[13px] text-slate-600">
                    No intelligence articles yet. The engine runs every 5 minutes.
                  </div>
                </div>
              ) : articles.map((art, i) => {
                const tc = TYPE_LABELS[art.article_type] ?? { label: art.article_type, color: "bg-slate-700/40 text-slate-400 border-slate-600/30" };
                const lc = LC_CFG[art.lifecycle_status] ?? LC_CFG["generated"];
                const LCIcon = lc.icon;

                return (
                  <div key={art.id}
                    className={`grid items-start gap-2 px-5 py-3.5 transition-colors hover:bg-white/[0.02] ${i < articles.length - 1 ? "border-b border-white/[0.03]" : ""}`}
                    style={{ gridTemplateColumns: "1fr 110px 110px 50px 50px 40px 100px 44px" }}>

                    {/* Article */}
                    <div className="min-w-0">
                      <div className="flex items-start gap-1.5">
                        <Sparkles className="h-3 w-3 text-violet-400 shrink-0 mt-0.5" />
                        <div className="min-w-0">
                          <div className="text-[12px] font-semibold text-white leading-snug line-clamp-2">{art.headline}</div>
                          {art.key_takeaway && (
                            <div className="mt-0.5 text-[10px] text-slate-600 line-clamp-1">{art.key_takeaway}</div>
                          )}
                          <div className="mt-1 flex items-center gap-2 text-[9px] text-slate-600">
                            {art.story_id && <span className="font-mono">story:{art.story_id}</span>}
                            {art.update_count > 0 && (
                              <span className="flex items-center gap-0.5 text-sky-500">
                                <RotateCcw className="h-2.5 w-2.5" /> v{art.story_version} ({art.update_count} updates)
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Type */}
                    <div>
                      <span className={`inline-flex rounded-full border px-2 py-0.5 text-[9px] font-bold ${tc.color}`}>
                        {tc.label}
                      </span>
                    </div>

                    {/* Lifecycle */}
                    <div className={`flex items-center gap-1 text-[10px] font-semibold ${lc.color}`}>
                      <LCIcon className="h-3 w-3 shrink-0" />
                      {lc.label}
                    </div>

                    {/* Confidence */}
                    <div className={`text-[11px] font-bold tabular-nums ${
                      art.confidence_score >= 0.8 ? "text-emerald-400" : art.confidence_score >= 0.65 ? "text-violet-400" : "text-rose-400"
                    }`}>{Math.round(art.confidence_score * 100)}%</div>

                    {/* Quality */}
                    <div className={`text-[11px] font-bold tabular-nums ${
                      art.quality_score >= 0.8 ? "text-emerald-400" : "text-slate-400"
                    }`}>{Math.round(art.quality_score * 100)}%</div>

                    {/* SEO */}
                    <SeoRing score={art.seo_score} />

                    {/* Published */}
                    <div className="text-[10px] text-slate-500 leading-snug">
                      {art.published_at
                        ? new Date(art.published_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
                        : <span className="text-rose-500">—</span>}
                    </div>

                    {/* View */}
                    {art.slug ? (
                      <Link href={`/intelligence/${art.slug}` as any} target="_blank"
                        className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.03] text-slate-500 hover:text-violet-400 hover:border-violet-500/30 transition-all">
                        <Eye className="h-3.5 w-3.5" />
                      </Link>
                    ) : <div />}
                  </div>
                );
              })}

              {/* Pagination */}
              {total > PAGE && (
                <div className="flex items-center justify-between px-5 py-3 border-t border-white/[0.05] bg-white/[0.01]">
                  <span className="text-[10px] text-slate-600">
                    {Math.min((page - 1) * PAGE + 1, total)}–{Math.min(page * PAGE, total)} of {total}
                  </span>
                  <div className="flex items-center gap-1">
                    <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                      className="flex h-6 w-6 items-center justify-center rounded-lg border border-white/[0.07] text-slate-500 disabled:opacity-30 hover:text-white transition">
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    {Array.from({ length: Math.min(totalPages, 5) }).map((_, i) => (
                      <button key={i} onClick={() => setPage(i + 1)}
                        className={`h-6 w-6 rounded-lg text-[10px] font-bold transition ${page === i + 1 ? "bg-violet-600 text-white" : "border border-white/[0.07] text-slate-500 hover:text-white"}`}>
                        {i + 1}
                      </button>
                    ))}
                    <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
                      className="flex h-6 w-6 items-center justify-center rounded-lg border border-white/[0.07] text-slate-500 disabled:opacity-30 hover:text-white transition">
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </section>
          </div>

          {/* ── Right sidebar ────────────────────────────────────────────────── */}
          <div className="space-y-4">

            {/* Scheduler Status */}
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600 mb-3">Scheduler</div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-slate-400">Status</span>
                  <span className={`text-[11px] font-bold ${engineRunning ? "text-emerald-400" : "text-slate-400"}`}>
                    {status?.engine.status ?? "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-slate-400">Cycle interval</span>
                  <span className="text-[11px] font-bold text-white">5 min</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-slate-400">Max per day</span>
                  <span className="text-[11px] font-bold text-white">3–8 stories</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-slate-400">Slots used</span>
                  <span className="text-[11px] font-bold text-violet-400">
                    {status?.today.published ?? 0}/{status?.today.max_per_day ?? 8}
                  </span>
                </div>
              </div>
              {/* Slot bar */}
              <div className="mt-3">
                <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
                  <div className="h-full rounded-full bg-violet-500 transition-all"
                    style={{ width: `${((status?.today.published ?? 0) / (status?.today.max_per_day ?? 8)) * 100}%` }} />
                </div>
              </div>
            </div>

            {/* Subsystems */}
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600 mb-3">Subsystems</div>
              {status?.subsystems
                ? Object.entries(status.subsystems).map(([name, st]) => (
                    <SubsystemRow key={name} name={name} status={st} />
                  ))
                : <div className="text-[11px] text-slate-600">Loading…</div>
              }
            </div>

            {/* Market Coverage */}
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600 mb-3">Today's Coverage</div>
              <div className="space-y-2">
                {articles.filter(a => a.status === "published").slice(0, 6).map(art => {
                  const tc = TYPE_LABELS[art.article_type] ?? { label: art.article_type, color: "bg-slate-700/40 text-slate-400 border-slate-600/30" };
                  return (
                    <div key={art.id} className="flex items-start gap-2">
                      <span className={`mt-0.5 shrink-0 rounded-full border px-1.5 py-0.5 text-[8px] font-bold ${tc.color}`}>{tc.label}</span>
                      <span className="text-[11px] text-slate-400 line-clamp-2 leading-snug">{art.headline}</span>
                    </div>
                  );
                })}
                {articles.filter(a => a.status === "published").length === 0 && (
                  <div className="text-[11px] text-slate-600">No published articles today.</div>
                )}
              </div>
            </div>

            {/* Pipeline */}
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600 mb-3">Pipeline</div>
              <div className="space-y-2">
                {[
                  ["MIE Context",         "violet"],
                  ["Intelligence Filter", "sky"],
                  ["Content Planner",     "teal"],
                  ["Duplicate Detector",  "amber"],
                  ["Article Generator",   "emerald"],
                  ["Quality Validator",   "orange"],
                  ["Auto Publisher",      "rose"],
                  ["Continuous Updater",  "indigo"],
                ].map(([step, color]) => (
                  <div key={step} className="flex items-center gap-2">
                    <div className={`h-1.5 w-1.5 rounded-full bg-${color}-500`} />
                    <span className="text-[11px] text-slate-500">{step}</span>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
