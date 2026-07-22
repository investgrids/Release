"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Shield, Train, Leaf, Zap, FlaskConical, Sparkles, Flame, BarChart2 } from "lucide-react";
import { useIntelligence } from "@/hooks/useIntelligence";
import { IntelligenceBlock } from "@/components/intelligence/IntelligenceBlock";
import { API_BASE_URL as API } from "@/lib/api";
import { averageScores } from "@/lib/scoring";


/* ── Types ───────────────────────────────────────────────── */
// Mirrors GET /api/radar/ items directly — every field here is real,
// backend-computed data. Nothing in this page is fabricated or randomised;
// sections with no real backing (historical sparklines, per-theme timelines,
// per-company price moves) were removed rather than filled with placeholder
// numbers — see the C1 finding in the Wave 1 audit for why that mattered.
interface RadarItem {
  id: number; slug: string; title: string; summary: string;
  opportunity_score: number | null; confidence: number | null;
  trend: string; risk_level: string; time_horizon: string;
  sectors: string[]; company_count: number; event_count: number;
}

/* ── Constants ───────────────────────────────────────────── */
const BADGE_COLOR: Record<string, string> = {
  Hot:    "bg-rose-500/15 text-rose-300 border border-rose-500/30",
  High:   "bg-amber-500/15 text-amber-300 border border-amber-500/30",
  Medium: "bg-sky-500/15  text-sky-300  border border-sky-500/30",
};
// Derived from the real opportunity_score — a classification of real data,
// not a fabricated value itself.
function scoreBadge(score: number | null): "Hot" | "High" | "Medium" {
  if (score === null) return "Medium";
  if (score >= 90) return "Hot";
  if (score >= 75) return "High";
  return "Medium";
}

const SECTOR_ICON: Record<string, ReactNode> = {
  Defence:        <Shield className="h-10 w-10 text-amber-400" />,
  Technology:     <Bot className="h-10 w-10 text-blue-400" />,
  Electronics:    <Bot className="h-10 w-10 text-blue-400" />,
  Energy:         <Zap className="h-10 w-10 text-teal-400" />,
  Utilities:      <Zap className="h-10 w-10 text-teal-400" />,
  Infrastructure: <Train className="h-10 w-10 text-sky-400" />,
  Chemicals:      <FlaskConical className="h-10 w-10 text-violet-400" />,
  Manufacturing:  <FlaskConical className="h-10 w-10 text-violet-400" />,
  Automotive:     <Zap className="h-10 w-10 text-teal-400" />,
};
function themeIcon(sectors: string[]): ReactNode {
  for (const s of sectors) if (SECTOR_ICON[s]) return SECTOR_ICON[s];
  return <Leaf className="h-10 w-10 text-emerald-400" />;
}
const GRADIENTS = [
  "from-blue-950 via-indigo-900 to-slate-900",
  "from-stone-900 via-amber-950 to-slate-900",
  "from-slate-800 via-blue-900 to-slate-900",
  "from-emerald-950 via-green-900 to-slate-900",
  "from-teal-950 via-cyan-900 to-slate-900",
  "from-purple-950 via-violet-900 to-slate-900",
];

const TABS = ["Overview", "Companies", "Events", "News", "Analysis", "Historical", "Risks"] as const;
type Tab = typeof TABS[number];

/* ── Left panel: Theme card ──────────────────────────────── */
function ThemeCard({ t, selected, onClick }: { t: RadarItem; selected: boolean; onClick: () => void }) {
  const badge = scoreBadge(t.opportunity_score);
  const gradient = GRADIENTS[t.id % GRADIENTS.length];
  const confPct = t.confidence === null ? null : Math.round(t.confidence * 100);
  return (
    <button onClick={onClick} className={`w-full text-left rounded-[20px] border p-4 transition ${
      selected
        ? "border-indigo-500/40 bg-indigo-500/[0.07] ring-1 ring-indigo-500/20"
        : "border-white/8 bg-white/[0.025] hover:border-white/15 hover:bg-white/[0.04]"
    }`}>
      <div className="flex gap-3">
        {/* Thumbnail */}
        <div className={`relative h-20 w-24 shrink-0 overflow-hidden rounded-[14px] bg-gradient-to-br ${gradient} flex items-center justify-center text-white/80`}>
          {themeIcon(t.sectors)}
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate text-sm font-semibold text-white">{t.title}</span>
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${BADGE_COLOR[badge]}`}>
              {badge === "Hot" ? <><Flame className="inline h-3 w-3 mr-0.5" />Hot</> : badge}
            </span>
          </div>
          <p className="mt-1 text-[11px] leading-4 text-slate-400 line-clamp-2">{t.summary}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {t.sectors.slice(0, 3).map(s => (
              <span key={s} className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">{s}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Score row */}
      <div className="mt-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] text-slate-500">Opportunity Score</p>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-white">{t.opportunity_score ?? "—"}</span>
            <span className="text-[10px] text-slate-500">{t.trend}</span>
          </div>
          {/* AI Confidence bar */}
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1 w-20 overflow-hidden rounded-full bg-white/5">
              {confPct !== null && (
                <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
                  style={{ width: `${confPct}%` }} />
              )}
            </div>
            <span className="text-[10px] text-slate-500">{confPct === null ? "AI Unscored" : `AI ${confPct}%`}</span>
          </div>
          <p className="mt-1 text-[10px] font-medium text-slate-400">
            {t.company_count} companies · {t.event_count} events
          </p>
        </div>
      </div>
    </button>
  );
}

/* ── Right panel: Detail ─────────────────────────────────── */
function ThemeDetail({ t, onBack }: { t: RadarItem; onBack: () => void }) {
  const [tab, setTab] = useState<Tab>("Overview");
  const badge = scoreBadge(t.opportunity_score);
  const gradient = GRADIENTS[t.id % GRADIENTS.length];
  const confPct = t.confidence === null ? null : Math.round(t.confidence * 100);

  return (
    <div className="flex flex-col gap-0 rounded-[24px] border border-white/10 bg-[#080910]/80 overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-3 border-b border-white/8 px-5 py-3">
        <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          Back to Themes
        </button>
      </div>

      {/* Hero image */}
      <div className={`relative h-36 w-full bg-gradient-to-br ${gradient} flex items-center justify-center overflow-hidden`}>
        <span className="opacity-30 text-white [&_svg]:h-20 [&_svg]:w-20">{themeIcon(t.sectors)}</span>
        <div className="absolute inset-0 bg-gradient-to-t from-[#080910]/80 via-transparent to-transparent" />
      </div>

      {/* Title block */}
      <div className="flex items-start justify-between gap-3 px-5 pt-4 pb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${BADGE_COLOR[badge]}`}>
              {badge === "Hot" ? <><Flame className="inline h-3 w-3 mr-0.5" />Hot Theme</> : `${badge} Theme`}
            </span>
          </div>
          <h2 className="text-xl font-bold text-white leading-tight">{t.title}</h2>
          <p className="mt-1.5 text-[12px] leading-5 text-slate-400 max-w-sm">{t.summary}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Link href={`/ai-search?q=${encodeURIComponent(t.title)}`}
            className="flex items-center gap-1.5 rounded-[12px] border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/10 transition">
            <Sparkles className="h-3.5 w-3.5"/>
            Ask AI
          </Link>
        </div>
      </div>

      {/* Metrics row — all four fields come straight from the radar item */}
      <div className="grid grid-cols-4 gap-px border-t border-b border-white/8 bg-white/5 mx-5 rounded-[14px] overflow-hidden mb-3">
        {[
          { label: "Opportunity Score", value: t.opportunity_score === null ? "Unscored" : `${t.opportunity_score}/100`, color: "text-violet-300" },
          { label: "AI Confidence",     value: confPct === null ? "Unscored" : `${confPct}%`, color: "text-sky-300" },
          { label: "Risk Level",        value: t.risk_level || "—", color: "text-amber-300" },
          { label: "Time Horizon",      value: t.time_horizon || "—", color: "text-emerald-300" },
        ].map(m => (
          <div key={m.label} className="flex flex-col items-center py-3 px-2 bg-[#080910]/80">
            <p className="text-[10px] text-slate-500 mb-1">{m.label}</p>
            <span className={`text-sm font-bold ${m.color}`}>{m.value}</span>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 overflow-x-auto border-b border-white/8 px-5 scrollbar-none">
        {TABS.map(tb => (
          <button key={tb} onClick={() => setTab(tb)}
            className={`shrink-0 border-b-2 px-3 py-2.5 text-xs font-medium transition ${
              tab === tb
                ? "border-indigo-500 text-white"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}>
            {tb}
          </button>
        ))}
      </div>

      {/* Tab content — scrollable */}
      <div className="overflow-y-auto flex-1 sidebar-scroll" style={{ maxHeight: "calc(100vh - 560px)", minHeight: 300 }}>
        {tab === "Overview" && <OverviewTab t={t} />}
        {tab !== "Overview" && (
          <div className="flex flex-col items-center justify-center py-16 text-center text-slate-500 gap-2">
            <BarChart2 className="h-10 w-10 text-slate-500" />
            <p className="text-sm">{tab} data loads from backend</p>
            <Link href={`/opportunity-radar`} className="mt-2 text-xs text-indigo-400 hover:text-indigo-300 transition">
              Explore on Opportunity Radar →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

function OverviewTab({ t }: { t: RadarItem }) {
  const { data: intelligence, loading: intelLoading } = useIntelligence("theme", t.slug);
  const hasIntel = !!(intelligence && (intelligence.market_story || intelligence.key_takeaway || intelligence.opportunities?.length || intelligence.risks?.length));

  return (
    <div className="space-y-5 p-5">
      {/* Sectors */}
      <div>
        <p className="mb-3 text-[10px] font-bold tracking-[0.18em] uppercase text-slate-500">Sectors</p>
        <div className="flex flex-wrap gap-2">
          {t.sectors.map(s => (
            <span key={s} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300">
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* Companies / events — real counts, real destination */}
      <div className="rounded-[14px] border border-white/8 bg-white/[0.02] p-4 flex items-center justify-between">
        <div>
          <p className="text-xs text-slate-300">{t.company_count} companies · {t.event_count} events feed this theme's score</p>
          <p className="mt-0.5 text-[10.5px] text-slate-500">Full company-level and event-level breakdown lives on Opportunity Radar.</p>
        </div>
        <Link href="/opportunity-radar" className="shrink-0 rounded-[12px] border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] text-indigo-300 hover:bg-white/10 transition whitespace-nowrap">
          View on Radar →
        </Link>
      </div>

      {/* Real AI intelligence — same MIE-sourced block used across the app,
          rather than this page computing its own narrative independently. */}
      {intelLoading ? (
        <div className="h-24 animate-pulse rounded-2xl border border-white/[0.06] bg-white/[0.02]" />
      ) : hasIntel && intelligence ? (
        <IntelligenceBlock data={intelligence} label="AI Insight" />
      ) : (
        <div className="rounded-[16px] border border-white/10 bg-white/[0.02] p-4 text-center">
          <p className="text-xs text-slate-500">No AI narrative available yet for this theme.</p>
          <Link href={`/ai-search?q=${encodeURIComponent(t.title)}`} className="mt-2 inline-block text-[11px] text-indigo-400 hover:text-indigo-300 transition">
            Ask AI directly →
          </Link>
        </div>
      )}
    </div>
  );
}

/* ── Stats bar ───────────────────────────────────────────── */
function StatsBar({ themes }: { themes: RadarItem[] }) {
  // averageScores ignores unscored themes rather than treating a null
  // score as 0, which would silently drag the sitewide average down
  // every time a theme's score is still being computed.
  const avgScoreReal = averageScores(themes.map(t => t.opportunity_score));
  const avgScore = avgScoreReal === null ? null : Math.round(avgScoreReal);
  const totalEvents = themes.reduce((a, t) => a + (t.event_count || 0), 0);
  const totalCompanies = themes.reduce((a, t) => a + (t.company_count || 0), 0);
  const avgConfReal = averageScores(themes.map(t => t.confidence === null ? null : t.confidence * 100));
  const avgConf = avgConfReal === null ? null : Math.round(avgConfReal);

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
      {[
        { label: "Active Themes",          value: themes.length,                      color: "text-white" },
        { label: "Avg. Opportunity Score", value: avgScore ?? "—",                    color: "text-emerald-400" },
        { label: "Total Events",           value: totalEvents,                        color: "text-white" },
        { label: "AI Confidence",          value: avgConf === null ? "—" : `${avgConf}%`, color: "text-violet-300" },
        { label: "Companies Tracked",      value: totalCompanies,                     color: "text-sky-300" },
      ].map(s => (
        <div key={s.label} className="rounded-[18px] border border-white/8 bg-white/[0.025] px-4 py-3">
          <p className="text-[10px] text-slate-500 mb-1">{s.label}</p>
          <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
        </div>
      ))}
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────── */
export default function ThemesPage() {
  const [themes, setThemes]   = useState<RadarItem[]>([]);
  const [selected, setSelected] = useState<RadarItem | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/radar/`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.items?.length) {
          setThemes(d.items);
          setSelected(d.items[0]);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-w-0 space-y-5 pb-10">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Top Themes</h1>
          <p className="mt-1 text-sm text-slate-400">AI-powered investment themes driving the market</p>
        </div>
        <Link href="/ai-search?q=top investment themes India"
          className="flex items-center gap-2 rounded-[14px] bg-gradient-to-r from-violet-600 to-sky-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-500/20 hover:opacity-90 transition">
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
          AI Theme Analysis
        </Link>
      </div>

      {/* Stats */}
      {loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
          {[1,2,3,4,5].map(i => <div key={i} className="h-[74px] animate-pulse rounded-[18px] border border-white/[0.06] bg-white/[0.02]" />)}
        </div>
      ) : (
        <StatsBar themes={themes} />
      )}

      {/* Two-panel layout */}
      <div className="grid gap-4 xl:grid-cols-[1fr_440px]">
        {/* Left: theme list */}
        <div className="min-w-0 space-y-3">
          {loading ? (
            [1,2,3,4].map(i => <div key={i} className="h-[132px] animate-pulse rounded-[20px] border border-white/[0.06] bg-white/[0.02]" />)
          ) : themes.length === 0 ? (
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] py-16 text-center">
              <p className="text-sm text-slate-500">No themes available right now.</p>
            </div>
          ) : (
            themes.map(t => (
              <ThemeCard key={t.id} t={t} selected={selected?.id === t.id} onClick={() => setSelected(t)} />
            ))
          )}
        </div>

        {/* Right: detail */}
        <div className="hidden xl:block space-y-4">
          {selected && <ThemeDetail t={selected} onBack={() => {}} />}
        </div>
      </div>
    </main>
  );
}
