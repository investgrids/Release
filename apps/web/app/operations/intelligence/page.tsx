"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import Link from "next/link";
import { API_BASE_URL as API } from "@/lib/api";
import { useAlerts } from "@/components/AlertProvider";
import {
  Activity, Zap, CheckCircle2, XCircle, Clock, RefreshCw,
  Eye, ChevronLeft, ChevronRight, AlertTriangle, Sparkles,
  BarChart3, Brain, Database, Network, BookOpen, TrendingUp,
  GitBranch, Shield, RotateCcw, Layers, FileText, Timer,
  Search, X, DollarSign, Server, Radio, ListChecks, Users,
  Newspaper, CalendarClock, PlayCircle, AlertOctagon, ExternalLink,
} from "lucide-react";


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

interface CampaignArticle {
  slug: string; headline: string; article_type: string; angle: string;
  angle_entity: string | null; status: string; update_count: number; published_at: string | null;
}
interface Campaign {
  event_group_id: string; headline: string; article_type: string;
  article_count: number; published_count: number; failed_count: number;
  created_at: string | null; last_updated: string | null; articles: CampaignArticle[];
}

interface EngineHealthRow {
  name: string;
  health_status: "healthy" | "degraded" | "busy" | "critical" | "offline";
  health_label: string; health_score: number; success_rate: number | null;
  last_execution: string | null; last_success: string | null;
  errors: number; queue_size: number; latency_ms: number | null; version: string;
}
interface TodaysCampaign {
  event_group_id: string; headline: string; article_count: number;
  companies: number; sectors: number; status: string; published: number; failed: number;
}
interface OpsOverview {
  generated_at: string;
  engine_health: EngineHealthRow[];
  coverage_today: {
    events_processed: number; companies_covered: number; sectors_covered: number;
    themes_generated: number; articles_published: number; campaigns_generated: number;
    historical_pages_updated: number; evergreen_pages_updated: number; ai_searches_served: number;
  };
  todays_campaigns: TodaysCampaign[];
  queue: {
    events_waiting: number; articles_waiting: number; campaign_queue: number;
    historical_queue: number; retry_queue: number; failed_queue: number;
  };
  database_health: {
    published_articles: number; historical_pages: number; campaigns: number;
    events: number; opportunities: number; historical_events: number;
    score_history: number; queue_size: number;
  };
  ai_usage_today: {
    llm_calls: number; tokens_used: number; avg_response_ms: number;
    cache_hit_rate: number; failures: number; retries: number; cost_usd: number;
  };
  ai_search_metrics: {
    total_searches_today: number; cache_hit_rate: number; avg_tokens: number;
    avg_llm_time_ms: number; provider_used: string | null; timeout_count: number;
    retry_count: number; success_rate: number | null;
  };
  performance: {
    avg_validation_time_s: number; avg_campaign_time_s: number;
    avg_update_time_s: number; avg_publish_time_s: number;
  };
  scheduler_jobs: { id: string; name: string; running: boolean; trigger: string; next_run: string | null }[];
  recent_activity: { at: string | null; type: string; label: string; slug: string | null; angle: string }[];
  failures: { id: string; headline: string; article_type: string; created_at: string | null; validation_failures: number; validation_results: any }[];
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
  historical_intelligence:  { label: "Historical",  color: "bg-fuchsia-500/15 text-fuchsia-400 border-fuchsia-500/25" },
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

const FILTER_TABS: { key: string; label: string; params: Record<string, string> }[] = [
  { key: "published", label: "Published",  params: { lifecycle: "published" } },
  { key: "updated",   label: "Updated",    params: { lifecycle: "updated" } },
  { key: "generated", label: "Generating", params: { lifecycle: "generated" } },
  { key: "failed",    label: "Failed",     params: { status: "failed" } },
  { key: "historical",label: "Historical", params: { article_type: "historical_intelligence" } },
  { key: "archived",  label: "Archived",   params: { lifecycle: "archived" } },
  { key: "all",       label: "All",        params: {} },
  { key: "campaigns", label: "Campaigns",  params: {} },
];

const ANGLE_LABELS: Record<string, string> = {
  primary: "Primary", per_company: "Company", sector_rollup: "Sector",
  theme: "Theme", question: "Q&A", evergreen: "Evergreen", historical: "Historical",
};
const ANGLE_SECTION_ORDER = ["primary", "per_company", "sector_rollup", "theme", "historical", "question", "evergreen"];
const ANGLE_SECTION_LABELS: Record<string, string> = {
  primary: "Parent Event", per_company: "Company Articles", sector_rollup: "Sector Articles",
  theme: "Theme Articles", historical: "Historical Pages", question: "Questions Answered", evergreen: "Evergreen Pages",
};

/* ─── Time helpers ───────────────────────────────────────── */
// Backend timestamps are frequently naive ISO strings (SQLite storage) that
// represent UTC without an explicit offset — treat any offset-less string as
// UTC so client-side "time ago" math matches the server's own _age_minutes().
function parseTs(iso: string | null): number | null {
  if (!iso) return null;
  const hasOffset = /[zZ]|[+-]\d\d:\d\d$/.test(iso);
  const t = new Date(hasOffset ? iso : iso + "Z").getTime();
  return Number.isNaN(t) ? null : t;
}
function relTime(iso: string | null): string {
  const t = parseTs(iso);
  if (t === null) return "—";
  const diffMin = Math.floor((Date.now() - t) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const hr = Math.floor(diffMin / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

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

// Datadog/k8s-style operational states — never a binary healthy/error flag.
// The backend computes health_status from multiple weighted signals
// (success rate, queue, latency, retries, heartbeat, provider availability);
// the frontend only renders what it's told, it never recomputes health.
const HEALTH_CFG: Record<string, { color: string; dot: string; border: string; bg: string; emoji: string }> = {
  healthy:  { color: "text-emerald-400", dot: "bg-emerald-400", border: "border-emerald-500/20", bg: "bg-emerald-500/[0.03]", emoji: "🟢" },
  degraded: { color: "text-amber-400",   dot: "bg-amber-400",   border: "border-amber-500/20",   bg: "bg-amber-500/[0.03]",   emoji: "🟡" },
  busy:     { color: "text-orange-400",  dot: "bg-orange-400",  border: "border-orange-500/25",  bg: "bg-orange-500/[0.03]",  emoji: "🟠" },
  critical: { color: "text-rose-400",    dot: "bg-rose-400",    border: "border-rose-500/30",    bg: "bg-rose-500/[0.04]",    emoji: "🔴" },
  offline:  { color: "text-slate-500",   dot: "bg-slate-600",   border: "border-white/[0.06]",   bg: "",                      emoji: "⚫" },
};

function HealthPill({ status, label }: { status: string; label: string }) {
  const cfg = HEALTH_CFG[status] ?? HEALTH_CFG.offline;
  return (
    <span className={`flex items-center gap-1.5 rounded-full border ${cfg.border} bg-white/[0.02] px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide ${cfg.color}`}>
      <span aria-hidden>{cfg.emoji}</span>
      {label}
    </span>
  );
}

function EngineHealthCard({ e }: { e: EngineHealthRow }) {
  const cfg = HEALTH_CFG[e.health_status] ?? HEALTH_CFG.offline;
  return (
    <div className={`rounded-2xl border ${cfg.border} ${cfg.bg} bg-white/[0.02] p-4`}>
      <div className="flex items-center justify-between gap-2 mb-3">
        <span className="text-[12px] font-bold text-white leading-tight">{e.name}</span>
        <HealthPill status={e.health_status} label={e.health_label} />
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-1.5 text-[10px]">
        <div className="text-slate-600">Success Rate <span className="block text-slate-300 font-medium tabular-nums">{e.success_rate != null ? `${e.success_rate}%` : "—"}</span></div>
        <div className="text-slate-600">Queue <span className={`block font-medium tabular-nums ${e.health_status === "busy" ? "text-orange-400" : "text-slate-300"}`}>{e.queue_size}</span></div>
        <div className="text-slate-600">Latency <span className="block text-slate-300 font-medium tabular-nums">{e.latency_ms != null ? `${Math.round(e.latency_ms)}ms` : "—"}</span></div>
        <div className="text-slate-600">Last Run <span className="block text-slate-300 font-medium">{relTime(e.last_execution)}</span></div>
        <div className="text-slate-600">Errors Today <span className={`block font-medium tabular-nums ${e.errors > 0 ? "text-rose-400" : "text-slate-300"}`}>{e.errors}</span></div>
        <div className="text-slate-600">Version <span className="block text-slate-300 font-medium">{e.version}</span></div>
      </div>
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

function PerfBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-slate-400">{label}</span>
        <span className="text-[11px] font-bold text-white tabular-nums">{value.toFixed(2)}s</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
        <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function campaignStatusColor(status: string) {
  if (status === "Completed") return "border-emerald-500/25 bg-emerald-500/10 text-emerald-400";
  if (status === "Partial Failure") return "border-rose-500/25 bg-rose-500/10 text-rose-400";
  return "border-violet-500/25 bg-violet-500/10 text-violet-400";
}

/* ─── Campaign drill-down modal ──────────────────────────── */
function CampaignDrilldown({ campaign, onClose }: { campaign: Campaign; onClose: () => void }) {
  const grouped: Record<string, CampaignArticle[]> = {};
  for (const a of campaign.articles) {
    (grouped[a.angle] ??= []).push(a);
  }
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 backdrop-blur-sm px-4 py-10" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-2xl border border-white/[0.1] bg-[#0a0e1a] p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-violet-400 mb-1">Campaign Relationship Graph</div>
            <h2 className="text-[16px] font-bold text-white leading-snug">{campaign.headline}</h2>
            <div className="mt-1 text-[10px] font-mono text-slate-600">{campaign.event_group_id}</div>
          </div>
          <button onClick={onClose} className="shrink-0 flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.08] text-slate-500 hover:text-white transition">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4">
          {ANGLE_SECTION_ORDER.filter(k => grouped[k]?.length).map(key => (
            <div key={key}>
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600 mb-2">
                {ANGLE_SECTION_LABELS[key]} <span className="text-slate-700">({grouped[key].length})</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {grouped[key].map(a => (
                  <Link
                    key={a.slug}
                    href={a.status === "published" ? (`/insights/${a.slug}` as any) : (`/intelligence/${a.slug}` as any)}
                    target="_blank"
                    className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-medium transition ${
                      a.status === "published"
                        ? "border-white/10 bg-white/[0.03] text-slate-300 hover:border-violet-500/30 hover:text-violet-300"
                        : "border-rose-500/20 bg-rose-500/5 text-rose-500/70"
                    }`}
                  >
                    {a.angle_entity && <span className="font-semibold">{a.angle_entity}:</span>}
                    <span className="line-clamp-1 max-w-[220px]">{a.headline}</span>
                    <ExternalLink className="h-2.5 w-2.5 shrink-0 opacity-60" />
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Main page ──────────────────────────────────────────── */
export default function OperationsIntelligence() {
  const [status, setStatus]     = useState<EngineStatus | null>(null);
  const [ops, setOps]           = useState<OpsOverview | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignsTotal, setCampaignsTotal] = useState(0);
  const [total, setTotal]       = useState(0);
  const [page, setPage]         = useState(1);
  const [tab, setTab]           = useState("published");
  const [loading, setLoading]   = useState(true);
  const [lastRefresh, setLast]  = useState<Date | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [drilldown, setDrilldown] = useState<Campaign | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const PAGE = 12;

  const { intelligenceEvents, scoreUpdates } = useAlerts();

  useEffect(() => {
    const t = setTimeout(() => { setSearchQuery(searchInput.trim()); setPage(1); }, 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  const loadStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/publishing/status`);
      if (r.ok) setStatus(await r.json());
    } catch {}
  }, []);

  const loadOps = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/publishing/ops-overview`);
      if (r.ok) setOps(await r.json());
    } catch {}
  }, []);

  const loadArticles = useCallback(async () => {
    setLoading(true);
    try {
      const cfg = FILTER_TABS.find(t => t.key === tab);
      const qp = new URLSearchParams({ limit: String(PAGE), offset: String((page - 1) * PAGE) });
      Object.entries(cfg?.params ?? {}).forEach(([k, v]) => qp.set(k, v));
      if (searchQuery) qp.set("search", searchQuery);
      const r = await fetch(`${API}/api/publishing/articles?${qp.toString()}`);
      if (r.ok) {
        const d = await r.json();
        setArticles(d.articles || []);
        setTotal(d.total || 0);
      }
    } catch {} finally {
      setLoading(false);
      setLast(new Date());
    }
  }, [page, tab, searchQuery]);

  const loadCampaigns = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/publishing/campaigns?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      if (r.ok) {
        const d = await r.json();
        setCampaigns(d.campaigns || []);
        setCampaignsTotal(d.total || 0);
      }
    } catch {} finally {
      setLoading(false);
      setLast(new Date());
    }
  }, [page]);

  const refreshAll = useCallback(() => {
    loadStatus(); loadOps();
    if (tab === "campaigns") loadCampaigns(); else loadArticles();
  }, [loadStatus, loadOps, loadCampaigns, loadArticles, tab]);

  useEffect(() => {
    refreshAll();
    const id = setInterval(refreshAll, 30_000);
    return () => clearInterval(id);
  }, [refreshAll]);

  // Live updating — reuse the app-wide SSE connection (AlertProvider) instead
  // of opening a second EventSource; any new intelligence/score event means
  // real state changed, so refresh immediately rather than waiting for the
  // 30s poll.
  const seenEventCount = useRef(0);
  useEffect(() => {
    const count = intelligenceEvents.length + scoreUpdates.length;
    if (count > seenEventCount.current) {
      seenEventCount.current = count;
      refreshAll();
    }
  }, [intelligenceEvents.length, scoreUpdates.length, refreshAll]);

  const openCampaignDrilldown = useCallback(async (eventGroupId: string) => {
    const existing = campaigns.find(c => c.event_group_id === eventGroupId);
    if (existing) { setDrilldown(existing); return; }
    try {
      const r = await fetch(`${API}/api/publishing/campaigns?limit=50`);
      if (r.ok) {
        const d = await r.json();
        const found = (d.campaigns || []).find((c: Campaign) => c.event_group_id === eventGroupId);
        if (found) setDrilldown(found);
      }
    } catch {}
  }, [campaigns]);

  const handleRetry = useCallback(async (id: string) => {
    setRetrying(id);
    try {
      const r = await fetch(`${API}/api/publishing/articles/${id}/retry`, { method: "POST" });
      if (r.ok) refreshAll();
    } catch {} finally {
      setRetrying(null);
    }
  }, [refreshAll]);

  const totalPages = Math.max(1, Math.ceil((tab === "campaigns" ? campaignsTotal : total) / PAGE));
  const engineRunning = status?.engine.running ?? false;
  const perfMax = ops ? Math.max(
    ops.performance.avg_validation_time_s, ops.performance.avg_campaign_time_s,
    ops.performance.avg_update_time_s, ops.performance.avg_publish_time_s, 0.01,
  ) : 1;

  return (
    <div className="min-h-screen bg-[#020617] pb-16">
      {drilldown && <CampaignDrilldown campaign={drilldown} onClose={() => setDrilldown(null)} />}
      <div className="mx-auto max-w-[1440px] px-6 py-8">

        {/* ── Header ────────────────────────────────────────────────────────── */}
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-500/25">
                <Brain className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-[20px] font-bold text-white leading-tight">AI Operations Control Center</h1>
                <p className="text-[11px] text-slate-500">Internal only — health, throughput &amp; status of the intelligence platform</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-600" />
              <input
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                placeholder="Search events, companies, sectors, themes…"
                className="w-64 rounded-xl border border-white/[0.08] bg-white/[0.02] py-2 pl-9 pr-8 text-[11px] text-white placeholder:text-slate-600 outline-none focus:border-violet-500/40"
              />
              {searchInput && (
                <button onClick={() => setSearchInput("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-600 hover:text-white">
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
            {lastRefresh && (
              <span className="text-[10px] text-slate-600">
                {lastRefresh.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
            )}
            <div className="flex items-center gap-2 rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-1.5 text-[11px] font-semibold text-sky-400">
              <Radio className="h-3 w-3 animate-pulse" /> Live
            </div>
            <div className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold ${
              engineRunning
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-slate-600/40 bg-slate-800/40 text-slate-400"
            }`}>
              <StatusDot active={engineRunning} />
              {engineRunning ? "Engine Running" : "Engine Idle"}
            </div>
            <button onClick={refreshAll}
              className="flex items-center gap-1.5 rounded-xl border border-white/[0.08] bg-white/[0.02] px-3 py-2 text-[11px] text-slate-400 hover:text-white transition">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </button>
          </div>
        </div>

        {/* ── Engine Health ─────────────────────────────────────────────────── */}
        <section className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Server className="h-4 w-4 text-slate-500" />
            <span className="text-[12px] font-bold uppercase tracking-widest text-slate-500">Engine Health</span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {ops
              ? ops.engine_health.map(e => <EngineHealthCard key={e.name} e={e} />)
              : Array.from({ length: 9 }).map((_, i) => (
                  <div key={i} className="animate-pulse rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 h-[110px]" />
                ))
            }
          </div>

          {/* AI Search is user-facing, so it gets extra detail beyond the generic engine card */}
          {ops && (
            <div className="mt-3 rounded-2xl border border-white/[0.07] bg-white/[0.015] p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600 mb-3">AI Search — Special Metrics</div>
              <div className="flex flex-wrap gap-3">
                <MetricPill label="Searches Today" value={ops.ai_search_metrics.total_searches_today} />
                <MetricPill label="Avg Tokens"     value={ops.ai_search_metrics.avg_tokens} />
                <MetricPill label="Avg LLM Time"   value={`${Math.round(ops.ai_search_metrics.avg_llm_time_ms)}ms`} />
                <MetricPill label="Cache Hit Rate" value={`${ops.ai_search_metrics.cache_hit_rate}%`} />
                <MetricPill label="Provider Used"  value={ops.ai_search_metrics.provider_used ?? "—"} />
                <MetricPill label="Timeouts"       value={ops.ai_search_metrics.timeout_count} warn={ops.ai_search_metrics.timeout_count > 0} />
                <MetricPill label="Retries"        value={ops.ai_search_metrics.retry_count} warn={ops.ai_search_metrics.retry_count > 0} />
                <MetricPill label="Success Rate"   value={ops.ai_search_metrics.success_rate != null ? `${ops.ai_search_metrics.success_rate}%` : "—"} />
              </div>
            </div>
          )}
        </section>

        {/* ── Today's Intelligence Coverage ────────────────────────────────── */}
        <section className="mb-6 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="h-4 w-4 text-slate-500" />
            <span className="text-[12px] font-bold uppercase tracking-widest text-slate-500">Today's Intelligence Coverage</span>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <MetricPill label="Events Processed"      value={ops?.coverage_today.events_processed ?? "—"} />
            <MetricPill label="Companies Covered"     value={ops?.coverage_today.companies_covered ?? "—"} />
            <MetricPill label="Sectors Covered"       value={ops?.coverage_today.sectors_covered ?? "—"} />
            <MetricPill label="Themes Generated"      value={ops?.coverage_today.themes_generated ?? "—"} />
            <MetricPill label="Articles Published"    value={ops?.coverage_today.articles_published ?? "—"} />
            <MetricPill label="Campaigns Generated"   value={ops?.coverage_today.campaigns_generated ?? "—"} />
            <MetricPill label="Historical Updated"    value={ops?.coverage_today.historical_pages_updated ?? "—"} />
            <MetricPill label="Evergreen Updated"     value={ops?.coverage_today.evergreen_pages_updated ?? "—"} />
            <MetricPill label="AI Searches Served"    value={ops?.coverage_today.ai_searches_served ?? "—"} />
          </div>
        </section>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
          {/* ── Left — main monitoring area ─────────────────────────────────── */}
          <div className="space-y-6">

            {/* Today's Campaigns + Queue Monitor */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_260px]">
              <section className="rounded-2xl border border-white/[0.07] bg-white/[0.015] overflow-hidden">
                <div className="flex items-center gap-2 px-5 py-3.5 border-b border-white/[0.06] bg-white/[0.02]">
                  <Zap className="h-3.5 w-3.5 text-slate-500" />
                  <span className="text-[12px] font-bold text-white">Today's Campaigns</span>
                </div>
                <div className="max-h-[340px] overflow-y-auto">
                  {!ops ? (
                    <div className="px-5 py-8 text-center text-[11px] text-slate-600">Loading…</div>
                  ) : ops.todays_campaigns.length === 0 ? (
                    <div className="px-5 py-8 text-center text-[11px] text-slate-600">No campaigns generated yet today.</div>
                  ) : ops.todays_campaigns.map((c, i) => (
                    <button key={c.event_group_id} onClick={() => openCampaignDrilldown(c.event_group_id)}
                      className={`w-full text-left px-5 py-3.5 hover:bg-white/[0.02] transition-colors ${i < ops.todays_campaigns.length - 1 ? "border-b border-white/[0.04]" : ""}`}>
                      <div className="flex items-start justify-between gap-3">
                        <span className="text-[12px] font-semibold text-white leading-snug line-clamp-1">{c.headline}</span>
                        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-bold ${campaignStatusColor(c.status)}`}>{c.status}</span>
                      </div>
                      <div className="mt-1.5 flex items-center gap-3 text-[10px] text-slate-600">
                        <span>{c.article_count} articles</span>
                        <span className="flex items-center gap-1"><Users className="h-2.5 w-2.5" /> {c.companies} companies</span>
                        <span>{c.sectors} sectors</span>
                        {c.failed > 0 && <span className="text-rose-400">{c.failed} failed</span>}
                      </div>
                    </button>
                  ))}
                </div>
              </section>

              <section className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
                <div className="flex items-center gap-2 mb-3">
                  <ListChecks className="h-3.5 w-3.5 text-slate-500" />
                  <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">Queue Monitor</span>
                  <span className="ml-auto flex items-center gap-1 text-[9px] text-emerald-400"><Radio className="h-2.5 w-2.5 animate-pulse" />Live</span>
                </div>
                <div className="space-y-2">
                  {[
                    ["Events Waiting",   ops?.queue.events_waiting],
                    ["Articles Waiting", ops?.queue.articles_waiting],
                    ["Campaign Queue",   ops?.queue.campaign_queue],
                    ["Historical Queue", ops?.queue.historical_queue],
                    ["Retry Queue",      ops?.queue.retry_queue],
                    ["Failed Queue",     ops?.queue.failed_queue],
                  ].map(([label, val]) => (
                    <div key={label as string} className="flex items-center justify-between">
                      <span className="text-[11px] text-slate-400">{label}</span>
                      <span className={`text-[12px] font-bold tabular-nums ${(val as number) > 0 ? "text-amber-400" : "text-slate-300"}`}>{val ?? "—"}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            {/* AI Usage + Engine Performance */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <section className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="h-4 w-4 text-slate-500" />
                  <span className="text-[12px] font-bold uppercase tracking-widest text-slate-500">Today's AI Usage</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <MetricPill label="LLM Calls"       value={ops?.ai_usage_today.llm_calls ?? "—"} />
                  <MetricPill label="Tokens Used"     value={ops?.ai_usage_today.tokens_used ?? "—"} />
                  <MetricPill label="Avg Response"    value={ops ? `${ops.ai_usage_today.avg_response_ms}ms` : "—"} />
                  <MetricPill label="Cache Hit Rate"  value={ops ? `${ops.ai_usage_today.cache_hit_rate}%` : "—"} />
                  <MetricPill label="Cost"            value={ops ? `$${ops.ai_usage_today.cost_usd.toFixed(2)}` : "—"} />
                  <MetricPill label="Failures"        value={ops?.ai_usage_today.failures ?? "—"} warn={(ops?.ai_usage_today.failures ?? 0) > 0} />
                </div>
                <div className="mt-2 text-[9px] text-slate-700">Free-tier providers (Gemini / Groq / OpenRouter / Cerebras) — real spend is $0.</div>
              </section>

              <section className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Timer className="h-4 w-4 text-slate-500" />
                  <span className="text-[12px] font-bold uppercase tracking-widest text-slate-500">Engine Performance</span>
                </div>
                <div className="space-y-3.5">
                  <PerfBar label="Publish"    value={ops?.performance.avg_publish_time_s ?? 0}    max={perfMax} />
                  <PerfBar label="Validation" value={ops?.performance.avg_validation_time_s ?? 0} max={perfMax} />
                  <PerfBar label="Campaign"   value={ops?.performance.avg_campaign_time_s ?? 0}   max={perfMax} />
                  <PerfBar label="Update"     value={ops?.performance.avg_update_time_s ?? 0}     max={perfMax} />
                </div>
              </section>
            </div>

            {/* Recent Activity + Failure Center */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <section className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
                <div className="flex items-center gap-2 mb-4">
                  <CalendarClock className="h-4 w-4 text-slate-500" />
                  <span className="text-[12px] font-bold uppercase tracking-widest text-slate-500">Recent Activity</span>
                </div>
                <div className="space-y-0 max-h-[280px] overflow-y-auto">
                  {!ops || ops.recent_activity.length === 0 ? (
                    <div className="text-[11px] text-slate-600">No activity in the last 6 hours.</div>
                  ) : ops.recent_activity.map((ev, i) => (
                    <div key={i} className="relative flex gap-3 pb-4 last:pb-0">
                      <div className="flex flex-col items-center">
                        <span className={`h-2 w-2 rounded-full shrink-0 mt-1 ${ev.type === "published" ? "bg-emerald-400" : "bg-rose-400"}`} />
                        {i < ops.recent_activity.length - 1 && <span className="w-px flex-1 bg-white/[0.06] mt-1" />}
                      </div>
                      <div className="min-w-0 pb-0.5">
                        <div className="text-[11px] text-slate-300 leading-snug line-clamp-2">{ev.label}</div>
                        <div className="text-[9px] text-slate-600 mt-0.5">{relTime(ev.at)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
                <div className="flex items-center gap-2 mb-4">
                  <AlertOctagon className="h-4 w-4 text-rose-500/70" />
                  <span className="text-[12px] font-bold uppercase tracking-widest text-slate-500">Failure Center</span>
                </div>
                <div className="space-y-2 max-h-[280px] overflow-y-auto">
                  {!ops || ops.failures.length === 0 ? (
                    <div className="text-[11px] text-slate-600">No recent failures.</div>
                  ) : ops.failures.map(f => (
                    <div key={f.id} className="flex items-start justify-between gap-2 rounded-xl border border-rose-500/10 bg-rose-500/[0.03] px-3 py-2.5">
                      <div className="min-w-0">
                        <div className="text-[11px] text-slate-300 leading-snug line-clamp-2">{f.headline}</div>
                        <div className="mt-1 flex items-center gap-2 text-[9px] text-slate-600">
                          <span>{relTime(f.created_at)}</span>
                          <span className="text-rose-500">{f.validation_failures} validation failure(s)</span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleRetry(f.id)}
                        disabled={retrying === f.id}
                        className="shrink-0 flex items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-2 py-1 text-[10px] font-semibold text-slate-300 hover:border-violet-500/30 hover:text-violet-300 transition disabled:opacity-40"
                      >
                        {retrying === f.id ? <RotateCcw className="h-3 w-3 animate-spin" /> : <PlayCircle className="h-3 w-3" />}
                        Retry
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            {/* Articles / Campaigns table */}
            <section className="rounded-2xl border border-white/[0.07] bg-white/[0.015] overflow-hidden">
              {/* Table header */}
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.06] bg-white/[0.02] flex-wrap gap-2">
                <span className="text-[13px] font-bold text-white">
                  {tab === "campaigns" ? "Publishing Campaigns" : "Intelligence Articles"}
                </span>
                <div className="flex items-center gap-1 flex-wrap">
                  {FILTER_TABS.map(t => (
                    <button key={t.key} onClick={() => { setTab(t.key); setPage(1); }}
                      className={`rounded-full px-2.5 py-1 text-[10px] font-semibold transition-all ${
                        tab === t.key ? "bg-violet-600 text-white" : "text-slate-500 hover:text-white hover:bg-white/[0.05]"
                      }`}>{t.label}</button>
                  ))}
                </div>
              </div>

              {tab === "campaigns" ? (
                <>
                  {loading ? (
                    Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="animate-pulse px-5 py-4 border-b border-white/[0.03]">
                        <div className="h-3 w-2/3 rounded-full bg-white/[0.05] mb-2" />
                        <div className="h-2 w-1/3 rounded-full bg-white/[0.03]" />
                      </div>
                    ))
                  ) : campaigns.length === 0 ? (
                    <div className="py-20 text-center">
                      <GitBranch className="h-8 w-8 text-slate-700 mx-auto mb-3" />
                      <div className="text-[13px] text-slate-600">
                        No campaigns yet — a campaign forms once an event fans out into multiple angle articles.
                      </div>
                    </div>
                  ) : campaigns.map((c, i) => (
                    <button key={c.event_group_id} onClick={() => setDrilldown(c)}
                      className={`w-full text-left px-5 py-4 hover:bg-white/[0.02] transition-colors ${i < campaigns.length - 1 ? "border-b border-white/[0.04]" : ""}`}>
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <Layers className="h-3.5 w-3.5 text-violet-400 shrink-0" />
                            <span className="text-[13px] font-semibold text-white leading-snug">{c.headline}</span>
                          </div>
                          <div className="mt-1 flex items-center gap-3 text-[10px] text-slate-600">
                            <span className="font-mono">{c.event_group_id}</span>
                            {c.last_updated && (
                              <span>Last updated {new Date(c.last_updated).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
                            )}
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-400">
                            {c.published_count} published
                          </span>
                          {c.failed_count > 0 && (
                            <span className="rounded-full border border-rose-500/25 bg-rose-500/10 px-2 py-0.5 text-[10px] font-bold text-rose-400">
                              {c.failed_count} failed
                            </span>
                          )}
                          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-bold text-slate-400">
                            {c.article_count} total
                          </span>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {c.articles.map(a => (
                          <span
                            key={a.slug}
                            className={`flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-medium ${
                              a.status === "published"
                                ? "border-white/10 bg-white/[0.03] text-slate-300"
                                : "border-rose-500/20 bg-rose-500/5 text-rose-500/70"
                            }`}
                          >
                            {ANGLE_LABELS[a.angle] ?? a.angle}{a.angle_entity ? `: ${a.angle_entity}` : ""}
                          </span>
                        ))}
                      </div>
                    </button>
                  ))}
                </>
              ) : (
              <>
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
                    {searchQuery ? `No articles matching "${searchQuery}".` : "No intelligence articles yet. The engine runs every 5 minutes."}
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
                        : art.status === "failed"
                          ? (
                            <button onClick={() => handleRetry(art.id)} disabled={retrying === art.id}
                              className="text-violet-400 hover:text-violet-300 disabled:opacity-40">
                              {retrying === art.id ? "Retrying…" : "Retry"}
                            </button>
                          )
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
              </>
              )}

              {/* Pagination */}
              {(tab === "campaigns" ? campaignsTotal : total) > PAGE && (() => {
                const t = tab === "campaigns" ? campaignsTotal : total;
                return (
                <div className="flex items-center justify-between px-5 py-3 border-t border-white/[0.05] bg-white/[0.01]">
                  <span className="text-[10px] text-slate-600">
                    {Math.min((page - 1) * PAGE + 1, t)}–{Math.min(page * PAGE, t)} of {t}
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
                );
              })()}
            </section>
          </div>

          {/* ── Right sidebar ────────────────────────────────────────────────── */}
          <div className="space-y-4">

            {/* Scheduler Status */}
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600 mb-3">Scheduler Status</div>
              <div className="space-y-2 max-h-[420px] overflow-y-auto">
                {!ops || ops.scheduler_jobs.length === 0 ? (
                  <div className="text-[11px] text-slate-600">Loading…</div>
                ) : ops.scheduler_jobs.map(job => (
                  <div key={job.id} className="flex items-start justify-between gap-2 py-1.5 border-b border-white/[0.04] last:border-0">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <StatusDot active={job.running} />
                        <span className="text-[11px] text-slate-300 leading-snug truncate">{job.name}</span>
                      </div>
                      <div className="text-[9px] text-slate-600 mt-0.5 truncate">{job.trigger}</div>
                    </div>
                    <span className="shrink-0 text-[9px] text-slate-500 text-right">
                      {job.next_run ? new Date(job.next_run).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—"}
                    </span>
                  </div>
                ))}
              </div>
              {/* Legacy slot bar — daily publish quota */}
              <div className="mt-3 pt-3 border-t border-white/[0.04]">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] text-slate-500">Slots used today</span>
                  <span className="text-[10px] font-bold text-violet-400">{status?.today.published ?? 0}/{status?.today.max_per_day ?? 8}</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
                  <div className="h-full rounded-full bg-violet-500 transition-all"
                    style={{ width: `${((status?.today.published ?? 0) / (status?.today.max_per_day ?? 8)) * 100}%` }} />
                </div>
              </div>
            </div>

            {/* Database Health */}
            <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-3">
                <Database className="h-3.5 w-3.5 text-slate-500" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">Database Health</span>
              </div>
              <div className="space-y-1.5">
                {[
                  ["Published Articles", ops?.database_health.published_articles],
                  ["Historical Pages",   ops?.database_health.historical_pages],
                  ["Campaigns",          ops?.database_health.campaigns],
                  ["Events",             ops?.database_health.events],
                  ["Opportunities",      ops?.database_health.opportunities],
                  ["Historical Events",  ops?.database_health.historical_events],
                  ["Score History",      ops?.database_health.score_history],
                  ["Queue Size",         ops?.database_health.queue_size],
                ].map(([label, val]) => (
                  <div key={label as string} className="flex items-center justify-between">
                    <span className="text-[11px] text-slate-400">{label}</span>
                    <span className="text-[11px] font-bold text-white tabular-nums">{val ?? "—"}</span>
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
