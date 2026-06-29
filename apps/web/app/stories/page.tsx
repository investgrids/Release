"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface StoryListItem {
  id: number;
  slug: string;
  title: string;
  summary: string;
  opportunity_score: number;
  confidence: number;
  trend: string;
  risk_level: string;
  time_horizon: string;
  sectors: string[];
  company_count: number;
  event_count: number;
}

interface AISummary {
  matters: string;
  benefits: string;
  risks: string[];
  invalidate: string;
  why_bullets: string[];
}

interface MetricSchema {
  revenue_potential: string;
  expected_cagr: string;
  eps_growth: string;
  investment_cycle: string;
  market_size: string;
}

interface EventSchema {
  event_id: string;
  title: string;
  event_date: string;
  tag: string;
  description: string;
  importance: number;
}

interface CompanySchema {
  symbol: string;
  company_name: string;
  impact_score: number;
  impact_label: string;
  trend: string;
  confidence: number;
  reason: string;
}

interface StoryDetail {
  id: number;
  slug: string;
  title: string;
  summary: string;
  opportunity_score: number;
  confidence: number;
  trend: string;
  risk_level: string;
  time_horizon: string;
  sectors: string[];
  ai_summary: AISummary | null;
  metrics: MetricSchema | null;
  events: EventSchema[];
  companies: CompanySchema[];
}

interface SectorScore {
  sector: string;
  score: number;
}

interface ChartPoint {
  year: string;
  value: number;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const CATEGORIES = [
  "All Stories", "Infrastructure", "Technology", "Energy",
  "Manufacturing", "Financial Services", "Healthcare",
  "Consumer", "Defense", "Agriculture",
];

const CARD_GRAD: Record<string, string> = {
  Technology:     "from-blue-900 via-indigo-900 to-violet-900",
  Infrastructure: "from-slate-800 via-indigo-900 to-blue-950",
  Energy:         "from-amber-900 via-orange-950 to-slate-900",
  Defence:        "from-slate-900 via-zinc-900 to-slate-800",
  Defense:        "from-slate-900 via-zinc-900 to-slate-800",
  Railways:       "from-indigo-900 via-blue-950 to-slate-900",
  Banking:        "from-emerald-900 via-teal-950 to-slate-900",
  Manufacturing:  "from-orange-900 via-amber-950 to-slate-900",
  Semiconductor:  "from-cyan-900 via-teal-950 to-slate-900",
  Healthcare:     "from-teal-900 via-emerald-950 to-slate-900",
};
const DEFAULT_GRAD = "from-violet-900 via-indigo-950 to-slate-900";

const CAT_BADGE: Record<string, string> = {
  Technology:          "border-blue-500/30 bg-blue-500/10 text-blue-300",
  Infrastructure:      "border-violet-500/30 bg-violet-500/10 text-violet-300",
  Energy:              "border-amber-500/30 bg-amber-500/10 text-amber-300",
  Defence:             "border-slate-500/30 bg-slate-500/10 text-slate-300",
  Defense:             "border-slate-500/30 bg-slate-500/10 text-slate-300",
  Manufacturing:       "border-orange-500/30 bg-orange-500/10 text-orange-300",
  Healthcare:          "border-teal-500/30 bg-teal-500/10 text-teal-300",
  "Financial Services":"border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  Consumer:            "border-rose-500/30 bg-rose-500/10 text-rose-300",
  Agriculture:         "border-lime-500/30 bg-lime-500/10 text-lime-300",
};
const DEFAULT_CAT_BADGE = "border-sky-500/30 bg-sky-500/10 text-sky-300";

const STATIC_STORIES: StoryListItem[] = [
  { id: 1, slug: "india-infra-supercycle", title: "India Infrastructure Supercycle", summary: "India's infrastructure spending is entering a multi-decade supercycle driven by government initiatives and private sector participation.", opportunity_score: 92, confidence: 0.91, trend: "up", risk_level: "Medium", time_horizon: "3-5 Years", sectors: ["Infrastructure"], company_count: 12, event_count: 8 },
  { id: 2, slug: "defence-manufacturing-boom", title: "Defence Manufacturing Boom", summary: "India is emerging as a major defence manufacturing hub with record exports and indigenisation drive.", opportunity_score: 89, confidence: 0.88, trend: "up", risk_level: "Medium", time_horizon: "5-7 Years", sectors: ["Defense"], company_count: 9, event_count: 6 },
  { id: 3, slug: "green-energy-transition", title: "Green Energy Transition", summary: "Renewable energy adoption and green hydrogen initiatives driving India's clean energy revolution.", opportunity_score: 88, confidence: 0.86, trend: "up", risk_level: "Low", time_horizon: "5-10 Years", sectors: ["Energy"], company_count: 11, event_count: 7 },
  { id: 4, slug: "ai-automation-impact", title: "AI & Automation Wave", summary: "How artificial intelligence and automation are reshaping India's $250 billion IT sector.", opportunity_score: 85, confidence: 0.84, trend: "up", risk_level: "High", time_horizon: "2-3 Years", sectors: ["Technology"], company_count: 15, event_count: 10 },
  { id: 5, slug: "pli-manufacturing", title: "PLI Schemes & Manufacturing", summary: "Production-linked incentive schemes are transforming India's manufacturing landscape.", opportunity_score: 82, confidence: 0.82, trend: "up", risk_level: "Medium", time_horizon: "3-5 Years", sectors: ["Manufacturing"], company_count: 8, event_count: 5 },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreLabel(s: number) {
  return s >= 85 ? "Very High" : s >= 70 ? "High" : s >= 55 ? "Moderate" : "Neutral";
}

function scoreLabelColor(s: number) {
  return s >= 85 ? "text-emerald-400" : s >= 70 ? "text-sky-400" : s >= 55 ? "text-amber-400" : "text-slate-400";
}

function heatColor(s: number) {
  return s >= 85
    ? "bg-emerald-900/60 border-emerald-700/40 text-emerald-300"
    : s >= 70
    ? "bg-emerald-950/60 border-emerald-800/30 text-emerald-400"
    : s >= 55
    ? "bg-amber-950/60 border-amber-800/30 text-amber-300"
    : "bg-slate-900/60 border-slate-700/30 text-slate-400";
}

function genChartData(score: number): ChartPoint[] {
  const years = ["2023", "2024", "2025", "2026E", "2027E", "2028E"];
  const base = Math.max(20, score - 55);
  return years.map((year, i) => ({
    year,
    value: Math.round(base + (score - base) * (i / (years.length - 1)) * (0.9 + (((score * 7 + i * 13) % 10) / 50))),
  }));
}

function gradForSectors(sectors: string[]): string {
  for (const s of sectors) {
    if (CARD_GRAD[s]) return CARD_GRAD[s];
  }
  return DEFAULT_GRAD;
}

function catBadge(cat: string): string {
  return CAT_BADGE[cat] ?? DEFAULT_CAT_BADGE;
}

function Sparkline({ trend, score }: { trend: string; score: number }) {
  const base = Math.max(30, score - 40);
  const pts = [base, base + 8, base + 5, base + 15, score];
  const maxV = Math.max(...pts);
  const minV = Math.min(...pts);
  const range = maxV - minV || 1;
  const W = 60, H = 20;
  const coords = pts.map((v, i) => {
    const x = (i / (pts.length - 1)) * W;
    const y = H - ((v - minV) / range) * (H - 2) - 1;
    return `${x},${y}`;
  });
  const color = trend === "up" ? "#10b981" : "#f43f5e";
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      <polyline points={coords.join(" ")} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// ── ScoreRing ─────────────────────────────────────────────────────────────────

function ScoreRing({ score }: { score: number }) {
  const r = 26, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 85 ? "#10b981" : score >= 70 ? "#3b82f6" : "#f59e0b";
  return (
    <div className="relative flex items-center justify-center w-16 h-16">
      <svg width={64} height={64} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={32} cy={32} r={r} stroke="rgba(255,255,255,0.08)" strokeWidth={4} fill="none"/>
        <circle cx={32} cy={32} r={r} stroke={color} strokeWidth={4} fill="none"
          strokeLinecap="round" strokeDasharray={`${dash} ${circ}`}/>
      </svg>
      <div className="absolute text-center">
        <div className="text-[15px] font-black text-white">{score}</div>
        <div className="text-[8px] text-slate-400">{scoreLabel(score)}</div>
      </div>
    </div>
  );
}

// ── StoryCard ─────────────────────────────────────────────────────────────────

function StoryCard({ story, selected, onClick }: { story: StoryListItem; selected: boolean; onClick: () => void }) {
  const category = story.sectors[0] ?? "General";
  const grad = gradForSectors(story.sectors);
  const score = Math.round(story.opportunity_score);

  return (
    <button
      onClick={onClick}
      className={`group relative flex-shrink-0 w-64 rounded-[20px] overflow-hidden border transition text-left
        ${selected ? "border-sky-500/50 ring-1 ring-sky-500/30" : "border-white/10 hover:border-white/20"}`}
    >
      {/* Gradient bg */}
      <div className={`h-36 w-full bg-gradient-to-br ${grad} relative`}>
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent"/>
        {/* Category badge */}
        <div className="absolute top-3 left-3">
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${catBadge(category)}`}>
            {category}
          </span>
        </div>
        {/* Score */}
        <div className="absolute bottom-3 right-3">
          <ScoreRing score={score}/>
        </div>
      </div>

      {/* Content */}
      <div className="bg-white/[0.02] p-3">
        <h3 className="text-[12px] font-bold leading-snug text-white line-clamp-2 group-hover:text-sky-200 transition">
          {story.title}
        </h3>
        <p className="mt-1 text-[11px] leading-4 text-slate-400 line-clamp-2">{story.summary}</p>
        <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-500">
          <span>{story.company_count} companies</span>
          <span>·</span>
          <span>{story.event_count} events</span>
        </div>
      </div>
    </button>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function StoriesPage() {
  const [stories, setStories] = useState<StoryListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("All Stories");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<StoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Fetch list
  useEffect(() => {
    fetch(`${API}/api/radar/?page=1&page_size=20`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        const raw: StoryListItem[] = Array.isArray(d) ? d : (d?.items ?? []);
        if (raw.length === 0) {
          setStories(STATIC_STORIES);
        } else {
          setStories(raw);
        }
      })
      .catch(() => setStories(STATIC_STORIES))
      .finally(() => setLoading(false));
  }, []);

  // Auto-select first story
  useEffect(() => {
    if (stories.length > 0 && selectedId === null) {
      setSelectedId(stories[0].id);
    }
  }, [stories, selectedId]);

  // Fetch detail when selection changes
  useEffect(() => {
    if (selectedId === null) return;
    setDetailLoading(true);
    setDetail(null);
    fetch(`${API}/api/radar/${selectedId}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setDetail(d); })
      .catch(() => {})
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  // Sector heatmap
  const sectorScores = useMemo<SectorScore[]>(() => {
    const acc: Record<string, { sum: number; n: number }> = {};
    for (const s of stories) {
      for (const sec of s.sectors) {
        acc[sec] = acc[sec] ?? { sum: 0, n: 0 };
        acc[sec].sum += s.opportunity_score;
        acc[sec].n += 1;
      }
    }
    const DEFAULTS: Record<string, number> = {
      Infrastructure: 90, Technology: 88, Energy: 85, Manufacturing: 82,
      Defense: 81, "Financial Services": 75, Healthcare: 72, Consumer: 68, Agriculture: 62,
    };
    const fromDB = Object.entries(acc)
      .map(([sector, { sum, n }]) => ({ sector, score: Math.round(sum / n) }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 9);
    if (fromDB.length >= 3) return fromDB;
    return Object.entries(DEFAULTS).map(([sector, score]) => ({ sector, score }));
  }, [stories]);

  // Filter stories
  const filtered = useMemo(() => {
    let list = stories;
    if (category !== "All Stories") {
      list = list.filter(s => s.sectors.some(sec =>
        sec.toLowerCase().includes(category.toLowerCase()) ||
        category.toLowerCase().includes(sec.toLowerCase())
      ));
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(s =>
        s.title.toLowerCase().includes(q) || s.summary.toLowerCase().includes(q)
      );
    }
    return list;
  }, [stories, category, search]);

  const selected = stories.find(s => s.id === selectedId) ?? null;
  const selectedScore = selected ? Math.round(selected.opportunity_score) : 0;
  const chartData = selected ? genChartData(selectedScore) : [];

  // Theme performance table data
  const themeTableData = useMemo(() => {
    return filtered.slice(0, 8).map(s => ({
      id: s.id,
      title: s.title.length > 30 ? s.title.slice(0, 30) + "…" : s.title,
      score: Math.round(s.opportunity_score),
      trend: s.trend,
      sectors: s.sectors,
      momentum: s.opportunity_score >= 85 ? "Strong" : s.opportunity_score >= 70 ? "Moderate" : "Weak",
      topGainer: s.sectors[0] ?? "—",
    }));
  }, [filtered]);

  return (
    <main className="min-w-0 pb-10">
      {/* Header */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Stories</h1>
          <p className="mt-1 text-sm text-slate-400">
            Deep insights on key investment themes and market narratives
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search stories…"
              className="h-9 w-52 rounded-xl border border-white/10 bg-white/[0.03] pl-8 pr-3 text-[13px] text-slate-300 outline-none placeholder:text-slate-600 hover:border-white/20 focus:border-sky-500/40"
            />
          </div>
          <button className="flex items-center gap-1.5 rounded-xl border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-[12px] font-medium text-sky-300 hover:bg-sky-500/15 transition">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.347a3.001 3.001 0 00-.853 1.718V19a2 2 0 11-4 0v-1.159c0-.621-.24-1.2-.663-1.63l-.347-.348z"/>
            </svg>
            AI Summary
          </button>
        </div>
      </div>

      {/* Category tabs */}
      <div className="mb-5 flex gap-1 overflow-x-auto pb-1 scrollbar-hide">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={`flex-shrink-0 rounded-lg px-3.5 py-1.5 text-[12px] font-medium transition whitespace-nowrap ${
              category === cat
                ? "bg-sky-500/15 text-sky-300 border border-sky-500/30"
                : "text-slate-500 hover:text-slate-300 border border-transparent"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* 2-col layout */}
      <div className="grid grid-cols-[1fr_340px] gap-5 items-start">

        {/* ── LEFT ──────────────────────────────────────────────────────────── */}
        <div className="min-w-0 space-y-6">

          {/* Top Stories horizontal scroll */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-[13px] font-semibold text-white">Top Stories</h2>
              <span className="text-[11px] text-slate-500">{filtered.length} stories</span>
            </div>
            {loading ? (
              <div className="flex gap-3 overflow-x-auto pb-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex-shrink-0 w-64 h-52 animate-pulse rounded-[20px] border border-white/10 bg-white/[0.02]"/>
                ))}
              </div>
            ) : (
              <div className="flex gap-3 overflow-x-auto pb-2">
                {(filtered.length > 0 ? filtered : STATIC_STORIES).map(s => (
                  <StoryCard
                    key={s.id}
                    story={s}
                    selected={s.id === selectedId}
                    onClick={() => setSelectedId(s.id)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Theme Performance Overview table */}
          <div>
            <h2 className="mb-3 text-[13px] font-semibold text-white">Theme Performance Overview</h2>
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] overflow-hidden">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-white/5 text-[10px] uppercase tracking-wider text-slate-500">
                    <th className="px-4 py-3 text-left">Theme</th>
                    <th className="px-4 py-3 text-center">Impact Score</th>
                    <th className="px-4 py-3 text-center">Trend (30D)</th>
                    <th className="px-4 py-3 text-center">Momentum</th>
                    <th className="px-4 py-3 text-left">Top Sector</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {themeTableData.map(row => (
                    <tr
                      key={row.id}
                      onClick={() => setSelectedId(row.id)}
                      className={`cursor-pointer transition hover:bg-white/[0.03] ${row.id === selectedId ? "bg-sky-500/5" : ""}`}
                    >
                      <td className="px-4 py-3">
                        <span className="text-[12px] font-medium text-slate-200">{row.title}</span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`font-bold ${scoreLabelColor(row.score)}`}>{row.score}</span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-center">
                          <Sparkline trend={row.trend} score={row.score}/>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          row.momentum === "Strong"
                            ? "bg-emerald-500/15 text-emerald-400"
                            : row.momentum === "Moderate"
                            ? "bg-sky-500/15 text-sky-400"
                            : "bg-amber-500/15 text-amber-400"
                        }`}>
                          {row.momentum}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400">{row.topGainer}</td>
                    </tr>
                  ))}
                  {themeTableData.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-[12px] text-slate-500">
                        No themes match the current filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Sector Heatmap */}
          <div>
            <h2 className="mb-3 text-[13px] font-semibold text-white">Sector Heatmap</h2>
            <div className="grid grid-cols-3 gap-2">
              {sectorScores.map(({ sector, score }) => (
                <div
                  key={sector}
                  className={`rounded-[16px] border p-4 ${heatColor(score)}`}
                >
                  <p className="text-[12px] font-semibold">{sector}</p>
                  <p className="mt-1 text-2xl font-black">{score}</p>
                  <p className="mt-0.5 text-[10px] opacity-70">{scoreLabel(score)}</p>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* ── RIGHT: Detail panel ────────────────────────────────────────────── */}
        <aside className="sticky top-[84px]">
          {detailLoading ? (
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 space-y-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className={`animate-pulse rounded bg-white/[0.05] ${i === 0 ? "h-6 w-3/4" : i === 1 ? "h-4 w-1/2" : "h-4 w-full"}`}/>
              ))}
            </div>
          ) : selected ? (
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] overflow-hidden">

              {/* Top gradient hero */}
              <div className={`relative bg-gradient-to-br ${gradForSectors(selected.sectors)} p-5`}>
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent"/>
                <div className="relative flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <span className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold mb-2 ${catBadge(selected.sectors[0] ?? "General")}`}>
                      {selected.sectors[0] ?? "General"}
                    </span>
                    <h2 className="text-[16px] font-bold leading-snug text-white line-clamp-3">
                      {selected.title}
                    </h2>
                  </div>
                  <div className="flex-shrink-0">
                    <ScoreRing score={Math.round(selected.opportunity_score)}/>
                  </div>
                </div>
              </div>

              {/* Body */}
              <div className="p-5 space-y-5">

                {/* Description */}
                <p className="text-[12px] leading-5 text-slate-300">
                  {detail?.ai_summary?.matters || selected.summary}
                </p>

                {/* Stats row */}
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: "Companies", value: detail ? detail.companies.length : selected.company_count },
                    { label: "Events", value: detail ? detail.events.length : selected.event_count },
                    {
                      label: "Investments",
                      value: detail?.metrics?.revenue_potential || "₹2.4 Lakh Cr",
                    },
                    { label: "Time Horizon", value: selected.time_horizon || "3-5 Years" },
                  ].map(stat => (
                    <div key={stat.label} className="rounded-[12px] border border-white/5 bg-white/[0.02] p-3">
                      <p className="text-[9px] uppercase tracking-widest text-slate-500">{stat.label}</p>
                      <p className="mt-0.5 text-[13px] font-bold text-white">{stat.value}</p>
                    </div>
                  ))}
                </div>

                {/* Key Beneficiaries */}
                {detail && detail.companies.length > 0 && (
                  <div>
                    <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Key Beneficiaries</p>
                    <div className="flex flex-wrap gap-1.5">
                      {detail.companies.slice(0, 8).map(c => (
                        <Link
                          key={c.symbol}
                          href={`/stocks/${c.symbol}`}
                          className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-0.5 text-[11px] font-medium text-slate-200 hover:border-sky-500/40 hover:text-sky-300 transition"
                        >
                          {c.symbol}
                        </Link>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recent Key Events */}
                {detail && detail.events.length > 0 && (
                  <div>
                    <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Recent Key Events</p>
                    <div className="space-y-2">
                      {detail.events.slice(0, 4).map((ev, i) => (
                        <div key={i} className="flex items-start gap-2.5">
                          <div className={`mt-0.5 flex-shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${
                            ev.importance >= 4
                              ? "bg-rose-500/15 text-rose-400"
                              : ev.importance >= 3
                              ? "bg-amber-500/15 text-amber-400"
                              : "bg-slate-700/40 text-slate-400"
                          }`}>
                            {ev.tag || "Event"}
                          </div>
                          <div className="min-w-0">
                            <p className="text-[11px] font-medium text-slate-200 line-clamp-1">{ev.title}</p>
                            {ev.event_date && (
                              <p className="text-[10px] text-slate-500">{ev.event_date}</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Impact Over Time chart */}
                <div>
                  <p className="mb-2 text-[11px] font-semibold text-white">Impact Over Time</p>
                  <div className="h-[120px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 4, right: 4, left: -25, bottom: 0 }}>
                        <XAxis
                          dataKey="year"
                          tick={{ fill: "#64748b", fontSize: 9 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          domain={[0, 100]}
                          tick={{ fill: "#64748b", fontSize: 9 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "#0f172a",
                            border: "1px solid rgba(255,255,255,0.08)",
                            borderRadius: 10,
                            fontSize: 11,
                          }}
                          itemStyle={{ color: "#22c55e" }}
                          labelStyle={{ color: "#94a3b8" }}
                        />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke="#22c55e"
                          strokeWidth={2}
                          dot={{ fill: "#22c55e", r: 2 }}
                          activeDot={{ r: 4 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* CTA */}
                <Link
                  href={`/radar/${selected.id}`}
                  className="flex items-center justify-center gap-1.5 rounded-xl bg-sky-500/10 border border-sky-500/25 py-2.5 text-[13px] font-medium text-sky-300 hover:bg-sky-500/15 transition"
                >
                  Explore {detail ? detail.companies.length : selected.company_count} Companies
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
                  </svg>
                </Link>

              </div>
            </div>
          ) : (
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-8 text-center">
              <p className="text-[13px] text-slate-500">Select a story to see details</p>
            </div>
          )}
        </aside>

      </div>
    </main>
  );
}
