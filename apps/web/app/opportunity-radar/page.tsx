"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { AreaChart, Area, ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import { Target, ClipboardList } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface RadarItem {
  id: string | number;
  theme: string;
  score: number;
  reason: string;
  confidence: number;
  beneficiaries: string[];
  sectors?: string[];
}

interface GmpPoint { label: string; value: number }
interface IPO {
  id: string; name: string; sector: string; type: "Mainboard" | "SME";
  priceMin: number; priceMax: number; issueSize: string;
  freshIssue: string; offerForSale: string; lotSize: number; listingOn: string;
  openDate: string; closeDate: string; allotmentDate: string;
  refundDate: string; creditDate: string; listingDate: string;
  status: "Upcoming" | "Ongoing" | "Listed";
  gmp: number; gmpPct: number; gmpTrend: GmpPoint[];
  description: string; founded: string; headquarters: string;
  promoters: string; website: string; highlights: string[];
  aiSummary: string; aiRating: string;
  subscriptionRetail: number | null; subscriptionHNI: number | null; subscriptionQIB: number | null;
}
interface SectorTrend { name: string; count: number; pct: number; color: string }
interface Sentiment { score: number; label: string; retail: string; hni: string; volatility: string; overall: string }
interface IPOData {
  ipos: IPO[]; stats: { upcoming: number; ongoing: number; listed: number; avg_listing_gain: number };
  sector_trends: SectorTrend[]; sentiment: Sentiment; ai_insight: string;
}

// ── Static fallback data ──────────────────────────────────────────────────────

const SECTORS_FILTER = ["All Sectors", "Infrastructure", "Energy", "Technology", "Banking", "Manufacturing", "Healthcare", "FMCG"];
const THEMES_FILTER  = ["All Themes", "AI & Automation", "Green Energy", "Infrastructure", "Defence", "EV", "Pharma"];
const HORIZONS       = ["All", "Short Term", "Medium Term", "Long Term"];

const STATIC_RADAR: RadarItem[] = [
  { id: "r1", theme: "AI Infrastructure Boom",    score: 95, reason: "Surging demand for AI data centres and capacity expansion driving massive investments", confidence: 0.92, beneficiaries: ["TATASTEEL","RVNL","LT","BEML","IRCON"], sectors: ["Infrastructure","Technology"]  },
  { id: "r2", theme: "Railway Modernization",     score: 94, reason: "Government focus on railway modernisation and capacity expansion driving massive investments", confidence: 0.91, beneficiaries: ["RVNL","IRCON","LT","BEML","TATASTEEL"], sectors: ["Railways","Infrastructure"] },
  { id: "r3", theme: "Green Energy Transition",   score: 92, reason: "Renewable energy adoption and green hydrogen initiatives driving clean energy revolution", confidence: 0.88, beneficiaries: ["ADANI","TATA","NTPC","RPOWER","SJVN"],    sectors: ["Energy","Sustainability"]   },
  { id: "r4", theme: "Defence Manufacturing",     score: 89, reason: "India's push for defence indigenisation creating multi-year tailwinds for manufacturers", confidence: 0.86, beneficiaries: ["HAL","BEL","BHEL","MIL","GRSE"],          sectors: ["Defence","Aerospace"]       },
  { id: "r5", theme: "Digital Banking Wave",      score: 87, reason: "Rapid digitalisation of banking creating structural growth opportunities for fintech", confidence: 0.84, beneficiaries: ["HDFCBANK","ICICIBANK","SBIN","AXIS","KOTAKBANK"], sectors: ["Banking","FinTech"]          },
  { id: "r6", theme: "EV Supply Chain Build-out", score: 85, reason: "Electric vehicle adoption driving demand across the entire EV supply chain ecosystem", confidence: 0.82, beneficiaries: ["TATAMOTORS","MM","HERO","BAJAJ","MARUTI"],   sectors: ["Automotive","Energy"]       },
];

const TOP_SECTORS = [
  { name: "Infrastructure", score: 95, color: "from-violet-500 to-indigo-500" },
  { name: "Energy",         score: 92, color: "from-sky-500 to-blue-500"     },
  { name: "Technology",     score: 90, color: "from-blue-500 to-cyan-500"    },
  { name: "Manufacturing",  score: 88, color: "from-emerald-500 to-teal-500" },
  { name: "Healthcare",     score: 85, color: "from-amber-500 to-orange-500" },
];

const CHIP_COLORS = [
  "bg-violet-500/25 text-violet-200",
  "bg-sky-500/25 text-sky-200",
  "bg-emerald-500/25 text-emerald-200",
  "bg-amber-500/25 text-amber-200",
  "bg-rose-500/25 text-rose-200",
  "bg-teal-500/25 text-teal-200",
];

const STATUS_BADGE: Record<string, string> = {
  Upcoming: "bg-sky-500/10 text-sky-300 border border-sky-500/20",
  Ongoing:  "bg-amber-500/10 text-amber-300 border border-amber-500/20",
  Listed:   "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20",
};

const RATING_COLOR: Record<string, string> = {
  Bullish: "text-emerald-400", Neutral: "text-amber-400", Bearish: "text-rose-400",
};

// ── Sub-components ────────────────────────────────────────────────────────────

function confidenceColor(c: number) {
  if (c >= 0.9) return { ring: "ring-emerald-500/40", text: "text-emerald-400", fill: "stroke-emerald-500" };
  if (c >= 0.8) return { ring: "ring-sky-500/40",     text: "text-sky-400",     fill: "stroke-sky-500"     };
  return               { ring: "ring-amber-500/40",   text: "text-amber-400",   fill: "stroke-amber-500"   };
}

function ConfidenceCircle({ value, size = 64 }: { value: number; size?: number }) {
  const pct = Math.round(value * 100);
  const r   = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  const cc   = confidenceColor(value);
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgba(255,255,255,0.06)" strokeWidth={4} fill="none"/>
        <circle cx={size/2} cy={size/2} r={r} stroke="currentColor" className={cc.fill} strokeWidth={4} fill="none" strokeLinecap="round" strokeDasharray={`${dash} ${circ}`}/>
      </svg>
      <div className="absolute text-center">
        <div className={`text-[11px] font-bold ${cc.text}`}>{pct}%</div>
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const bg = score >= 90 ? "from-emerald-500 to-teal-400"
           : score >= 80 ? "from-sky-500 to-blue-400"
           : "from-amber-500 to-yellow-400";
  return (
    <div className={`flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br ${bg} shadow-lg`}>
      <span className="text-xl font-black text-white">{score}</span>
    </div>
  );
}

function GmpChart({ data }: { data: GmpPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gmp-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#34d399" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#34d399" stopOpacity={0}   />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="value" stroke="#34d399" strokeWidth={1.5} fill="url(#gmp-grad)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function SentimentGauge({ score, label }: { score: number; label: string }) {
  const segments = [
    { color: "#f43f5e", pct: 25 }, { color: "#f97316", pct: 25 },
    { color: "#fbbf24", pct: 25 }, { color: "#34d399", pct: 25 },
  ];
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-32 h-16 overflow-hidden">
        <svg viewBox="0 0 100 50" className="w-full">
          {segments.map((seg, i) => {
            const start = i * 45 - 90;
            const end = start + 44;
            const r = 40, cx = 50, cy = 50;
            const toRad = (d: number) => (d * Math.PI) / 180;
            const x1 = cx + r * Math.cos(toRad(start));
            const y1 = cy + r * Math.sin(toRad(start));
            const x2 = cx + r * Math.cos(toRad(end));
            const y2 = cy + r * Math.sin(toRad(end));
            return (
              <path key={i} d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2} Z`} fill={seg.color} opacity={0.7}/>
            );
          })}
          {(() => {
            const angle = -90 + (score / 100) * 180;
            const rad = (angle * Math.PI) / 180;
            const nx = 50 + 32 * Math.cos(rad);
            const ny = 50 + 32 * Math.sin(rad);
            return <line x1="50" y1="50" x2={nx} y2={ny} stroke="white" strokeWidth="2" strokeLinecap="round" />;
          })()}
          <circle cx="50" cy="50" r="5" fill="#1e293b" stroke="white" strokeWidth="1.5" />
        </svg>
      </div>
      <p className="text-3xl font-bold text-white mt-1">{score}</p>
      <p className="text-sm font-semibold text-emerald-400">{label}</p>
    </div>
  );
}

// ── Opportunities Tab ─────────────────────────────────────────────────────────

function OpportunitiesTab() {
  const [items, setItems] = useState<RadarItem[]>(STATIC_RADAR);
  const [sectorFilter, setSectorFilter] = useState("All Sectors");
  const [themeFilter, setThemeFilter]   = useState("All Themes");
  const [horizon, setHorizon]           = useState("All");
  const [minScore, setMinScore]         = useState(0);

  useEffect(() => {
    fetch(`${API}/api/radar/?page=1&page_size=20`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        const raw = Array.isArray(d) ? d : (d?.items ?? []);
        if (raw.length === 0) return;
        const mapped: RadarItem[] = raw.map((o: any) => ({
          id:           o.id,
          theme:        o.title,
          score:        Math.round(o.opportunity_score ?? o.score ?? 0),
          reason:       o.summary ?? o.reason ?? "",
          confidence:   typeof o.confidence === "number" ? (o.confidence > 1 ? o.confidence / 100 : o.confidence) : 0.85,
          beneficiaries: (o.companies ?? []).map((c: any) => typeof c === "string" ? c : c.symbol),
          sectors:      o.sectors ?? [],
        }));
        setItems(mapped);
      })
      .catch(() => {});
  }, []);

  const displayed = items.filter(i => {
    if (i.score < minScore) return false;
    if (sectorFilter !== "All Sectors" && !(i.sectors ?? []).some(s => s.toLowerCase().includes(sectorFilter.toLowerCase()))) return false;
    if (themeFilter !== "All Themes" && !i.theme.toLowerCase().includes(themeFilter.toLowerCase().replace("ai & automation", "ai").replace("green energy", "energy"))) return false;
    return true;
  });

  return (
    <>
      {/* Filter row */}
      <div className="mb-6 flex flex-wrap gap-2">
        <select value={sectorFilter} onChange={e => setSectorFilter(e.target.value)} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-slate-300 outline-none hover:border-white/20">
          {SECTORS_FILTER.map(s => <option key={s} value={s} className="bg-slate-900">{s}</option>)}
        </select>
        <select value={themeFilter} onChange={e => setThemeFilter(e.target.value)} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-slate-300 outline-none hover:border-white/20">
          {THEMES_FILTER.map(t => <option key={t} value={t} className="bg-slate-900">{t}</option>)}
        </select>
        <select value={horizon} onChange={e => setHorizon(e.target.value)} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-slate-300 outline-none hover:border-white/20">
          {HORIZONS.map(h => <option key={h} value={h} className="bg-slate-900">{h}</option>)}
        </select>
        <select onChange={e => setMinScore(Number(e.target.value))} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-slate-300 outline-none hover:border-white/20">
          <option value={0} className="bg-slate-900">Min Score</option>
          <option value={80} className="bg-slate-900">80+</option>
          <option value={85} className="bg-slate-900">85+</option>
          <option value={90} className="bg-slate-900">90+</option>
        </select>
      </div>

      {/* 2-col: cards + sidebar */}
      <div className="grid grid-cols-[1fr_220px] gap-5 items-start">
        {displayed.length === 0 ? (
          <div className="col-span-full flex flex-col items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20 text-center">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-8 w-8 text-slate-500"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
            <p className="mt-3 text-sm font-semibold text-white">No opportunities match these filters</p>
            <button onClick={() => { setSectorFilter("All Sectors"); setThemeFilter("All Themes"); setMinScore(0); }}
              className="mt-4 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-xs text-slate-300 hover:border-white/20 hover:text-white transition">
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {displayed.map((item) => {
              const conf = item.confidence ?? 0.9;
              const cc   = confidenceColor(conf);
              const beneficiaries = Array.isArray(item.beneficiaries) ? item.beneficiaries : [];
              const sectors = Array.isArray(item.sectors) ? item.sectors : [];
              return (
                <div key={item.id} className="flex flex-col rounded-[20px] border border-white/10 bg-white/[0.03] p-4 hover:border-white/20 hover:-translate-y-0.5 transition">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <ScoreBadge score={item.score}/>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-[13px] font-bold leading-snug text-white">{item.theme}</h3>
                      {sectors.length > 0 && <p className="mt-0.5 text-[11px] text-slate-500">{sectors.join(" • ")}</p>}
                    </div>
                  </div>
                  <div className="mb-3 flex items-center gap-3">
                    <ConfidenceCircle value={conf} size={52}/>
                    <div className="min-w-0">
                      <p className="text-[10px] text-slate-500">Confidence</p>
                      <p className={`text-base font-bold ${cc.text}`}>{Math.round(conf * 100)}%</p>
                    </div>
                    <div className="flex-1">
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div className={`h-full rounded-full ${cc.ring.replace("ring-","bg-").replace("/40","")}`} style={{ width: `${Math.round(conf * 100)}%` }}/>
                      </div>
                    </div>
                  </div>
                  <p className="mb-3 text-[12px] leading-4 text-slate-400 line-clamp-2">{item.reason}</p>
                  {beneficiaries.length > 0 && (
                    <div className="mb-3">
                      <p className="mb-1.5 text-[9px] uppercase tracking-widest text-slate-600">Top Beneficiaries</p>
                      <div className="flex items-center gap-1">
                        {beneficiaries.slice(0, 5).map((b, bi) => (
                          <Link key={bi} href={`/companies/${b.replace(/[&\s]/g, "")}`} title={b}
                            className={`flex h-7 w-7 items-center justify-center rounded-full border border-white/10 text-[9px] font-bold hover:scale-110 transition ${CHIP_COLORS[bi % CHIP_COLORS.length]}`}>
                            {b.slice(0, 2).toUpperCase()}
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="mt-auto pt-2 border-t border-white/5">
                    {typeof item.id === "number" ? (
                      <Link href={`/opportunity-radar/${item.id}`} className="flex items-center gap-1 text-[12px] font-medium text-sky-400 hover:text-sky-300 transition">
                        View Details
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/></svg>
                      </Link>
                    ) : (
                      <p className="text-[11px] text-slate-600">Sample data — connect backend for live opportunities</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Sidebar */}
        <aside className="sticky top-[84px] rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
          <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Top Sectors</h3>
          <div className="space-y-3.5">
            {TOP_SECTORS.map(s => (
              <div key={s.name}>
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-[13px] font-medium text-slate-200">{s.name}</span>
                  <span className="text-[13px] font-bold text-white">{s.score}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
                  <div className={`h-full rounded-full bg-gradient-to-r ${s.color}`} style={{ width: `${s.score}%` }}/>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-6 border-t border-white/5 pt-4">
            <p className="mb-3 text-[9px] uppercase tracking-widest text-slate-500">AI Signal Strength</p>
            <div className="space-y-2">
              {[{ label: "Bullish", pct: 72, color: "bg-emerald-500" }, { label: "Neutral", pct: 18, color: "bg-amber-500" }, { label: "Bearish", pct: 10, color: "bg-rose-500" }].map(s => (
                <div key={s.label} className="flex items-center gap-2">
                  <span className="w-12 text-[11px] text-slate-400">{s.label}</span>
                  <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                    <div className={`h-full rounded-full ${s.color}`} style={{ width: `${s.pct}%` }}/>
                  </div>
                  <span className="w-7 text-right text-[11px] font-semibold text-white">{s.pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </>
  );
}

// ── IPO Tab ───────────────────────────────────────────────────────────────────

function IPOTab() {
  const [data, setData] = useState<IPOData | null>(null);
  const [filter, setFilter] = useState<"all"|"upcoming"|"ongoing"|"listed">("all");
  const [selected, setSelected] = useState<IPO | null>(null);

  useEffect(() => {
    fetch(`${API}/api/ipo/`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) { setData(d); setSelected(d.ipos[0] ?? null); } })
      .catch(() => {});
  }, []);

  const ipos = data?.ipos ?? [];
  const stats = data?.stats ?? { upcoming: 0, ongoing: 0, listed: 0, avg_listing_gain: 0 };
  const sectorTrends = data?.sector_trends ?? [];
  const sentiment = data?.sentiment ?? { score: 78, label: "Bullish", retail: "High", hni: "High", volatility: "Moderate", overall: "Bullish" };
  const displayed = filter === "all" ? ipos : ipos.filter(i => i.status.toLowerCase() === filter);

  return (
    <div className="space-y-5">
      {/* AI Insight */}
      {data?.ai_insight && (
        <div className="rounded-[20px] border border-violet-500/20 bg-violet-500/[0.06] p-4">
          <div className="flex items-center gap-2 mb-1.5">
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5 shrink-0 text-violet-300"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
            <p className="text-[10px] font-bold tracking-widest text-violet-300 uppercase">AI Daily Insight</p>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">{data.ai_insight}</p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Upcoming IPOs",      value: stats.upcoming, sub: "+3 this week",      color: "text-sky-400",     dot: "bg-sky-400" },
          { label: "Ongoing IPOs",       value: stats.ongoing,  sub: "2 closing soon",    color: "text-amber-400",   dot: "bg-amber-400" },
          { label: "Listed This Month",  value: stats.listed,   sub: `Avg. Gain ${stats.avg_listing_gain}%`, color: "text-emerald-400", dot: "bg-emerald-400" },
        ].map(s => (
          <div key={s.label} className="rounded-[18px] border border-white/10 bg-white/[0.02] p-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-white">{s.value}</span>
              <span className={`h-2 w-2 rounded-full ${s.dot} animate-pulse`}/>
            </div>
            <p className="text-xs font-semibold text-white mt-0.5">{s.label}</p>
            <p className={`text-[11px] mt-0.5 ${s.color}`}>{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Filter + List + Detail */}
      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <div className="rounded-[24px] border border-white/10 bg-white/[0.02] p-4">
          <p className="text-sm font-semibold text-white mb-3">IPO Overview</p>
          <div className="flex gap-1 mb-3">
            {(["all", "upcoming", "ongoing", "listed"] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`rounded-[10px] px-3 py-1.5 text-[11px] font-medium capitalize transition ${filter === f ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"}`}>
                {f === "all" ? `All (${ipos.length})` : `${f.charAt(0).toUpperCase() + f.slice(1)} (${ipos.filter(i => i.status.toLowerCase() === f).length})`}
              </button>
            ))}
          </div>
          <div className="space-y-0.5 max-h-[480px] overflow-y-auto pr-1">
            {displayed.length === 0 ? (
              <p className="text-center text-sm text-slate-500 py-8">No IPOs in this category</p>
            ) : displayed.map(ipo => (
              <button key={ipo.id} onClick={() => setSelected(ipo)}
                className={`w-full text-left px-3 py-3 rounded-[14px] transition hover:bg-white/[0.04] border ${selected?.id === ipo.id ? "border-violet-500/30 bg-violet-500/[0.05]" : "border-transparent"}`}>
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-white/[0.06] text-base font-bold text-white">
                    {ipo.name.charAt(0)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <p className="text-xs font-semibold text-white truncate">{ipo.name}</p>
                      <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${ipo.type === "SME" ? "bg-amber-500/15 text-amber-300" : "bg-indigo-500/15 text-indigo-300"}`}>{ipo.type}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <p className="text-[10px] text-slate-500">{ipo.sector}</p>
                      <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${STATUS_BADGE[ipo.status]}`}>{ipo.status}</span>
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-xs font-semibold text-white">₹{ipo.priceMin}–{ipo.priceMax}</p>
                    <p className="text-[10px] text-emerald-400">₹{ipo.gmp} ({ipo.gmpPct > 0 ? "+" : ""}{ipo.gmpPct.toFixed(2)}%)</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        <div className="min-h-[400px]">
          {selected ? (
            <div className="rounded-[24px] border border-white/10 bg-white/[0.02] p-4 h-full">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-[14px] bg-gradient-to-br from-violet-500/20 to-sky-500/20 text-xl font-bold text-white border border-white/10">
                    {selected.name.charAt(0)}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-white">{selected.name}</p>
                    <p className="text-xs text-slate-400">{selected.sector}</p>
                    <div className="flex items-center gap-1.5 mt-1">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[selected.status]}`}>{selected.status} IPO</span>
                    </div>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[10px] text-slate-500">Price Band</p>
                  <p className="text-lg font-bold text-white">₹{selected.priceMin} – ₹{selected.priceMax}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 mb-4">
                {[["Issue Size", selected.issueSize], ["Lot Size", `${selected.lotSize} Shares`], ["Listing On", selected.listingOn], ["GMP", `₹${selected.gmp} (${selected.gmpPct.toFixed(2)}%)`]].map(([k, v]) => (
                  <div key={k as string} className="rounded-[12px] border border-white/8 bg-white/[0.02] p-2.5">
                    <p className="text-[10px] text-slate-500">{k as string}</p>
                    <p className="text-xs font-semibold text-white mt-0.5">{v as string}</p>
                  </div>
                ))}
              </div>

              <div className="space-y-1.5 text-[11px] mb-4">
                {[["Open", selected.openDate], ["Close", selected.closeDate], ["Allotment", selected.allotmentDate], ["Listing", selected.listingDate]].map(([k, v]) => (
                  <div key={k as string} className="flex justify-between">
                    <span className="text-slate-500">{k as string}</span>
                    <span className="text-white font-medium">{v as string}</span>
                  </div>
                ))}
              </div>

              <div className="rounded-[16px] border border-violet-500/15 bg-violet-500/[0.04] p-3">
                <div className="flex items-center gap-2 mb-2">
                  <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5 shrink-0 text-violet-300"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
                  <div className="flex items-center justify-between flex-1">
                    <p className="text-[10px] font-bold tracking-widest text-violet-300 uppercase">AI IPO Rating</p>
                    <span className={`text-[11px] font-bold ${RATING_COLOR[selected.aiRating] ?? "text-white"}`}>{selected.aiRating}</span>
                  </div>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">{selected.aiSummary}</p>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center rounded-[24px] border border-white/10 bg-white/[0.02]">
              <p className="text-sm text-slate-500">Select an IPO to view details</p>
            </div>
          )}
        </div>
      </div>

      {/* Bottom: Sentiment + Sector Trends */}
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="rounded-[24px] border border-white/10 bg-white/[0.02] p-5">
          <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-4">IPO Market Sentiment</p>
          <div className="flex items-start gap-6">
            <SentimentGauge score={sentiment.score} label={sentiment.label} />
            <div className="space-y-2 flex-1">
              {[["Retail Interest", sentiment.retail, "text-emerald-400"], ["Institutional Interest", sentiment.hni, "text-emerald-400"], ["Market Volatility", sentiment.volatility, "text-amber-400"], ["Overall Sentiment", sentiment.overall, "text-emerald-400"]].map(([label, val, color]) => (
                <div key={label as string} className="flex items-center justify-between">
                  <span className="text-[11px] text-slate-400">{label as string}</span>
                  <span className={`text-[11px] font-semibold ${color as string}`}>{val as string}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {sectorTrends.length > 0 && (
          <div className="rounded-[24px] border border-white/10 bg-white/[0.02] p-5">
            <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-1">IPO Sector Trends</p>
            <div className="flex items-center gap-4 mt-3">
              <div className="h-36 w-36 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={sectorTrends} dataKey="count" cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={2}>
                      {sectorTrends.map((s, i) => <Cell key={i} fill={s.color} />)}
                    </Pie>
                    <Tooltip contentStyle={{ background: "#020617", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }} formatter={(v: number) => [`${v} IPOs`]}/>
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex-1 space-y-1.5">
                {sectorTrends.map(s => (
                  <div key={s.name} className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full shrink-0" style={{ background: s.color }}/>
                      <span className="text-[11px] text-slate-400">{s.name}</span>
                    </div>
                    <span className="text-[11px] font-medium text-white">{s.count} ({s.pct}%)</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "opportunities" | "ipo";

export default function OpportunityRadarPage() {
  const [tab, setTab] = useState<Tab>("opportunities");

  const tabs: { id: Tab; label: string; icon: ReactNode }[] = [
    { id: "opportunities", label: "Opportunities", icon: <Target className="h-3.5 w-3.5" /> },
    { id: "ipo",           label: "IPO Hub",       icon: <ClipboardList className="h-3.5 w-3.5" /> },
  ];

  return (
    <main className="min-w-0 pb-10">
      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Opportunity Radar</h1>
          <p className="mt-1 text-sm text-slate-400">AI-powered investment opportunities · IPO pipeline · Market themes</p>
        </div>
        <Link href="/ai-search?q=top investment opportunities India"
          className="flex items-center gap-2 rounded-[14px] bg-gradient-to-r from-violet-600 to-sky-500 px-4 py-2 text-sm font-semibold text-white hover:opacity-90 transition whitespace-nowrap">
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg> AI Analysis
        </Link>
      </div>

      {/* Tab bar */}
      <div className="mb-6 flex gap-1 border-b border-white/8 pb-0">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition ${
              tab === t.id
                ? "border-sky-500 text-white"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === "opportunities" && <OpportunitiesTab />}
      {tab === "ipo"           && <IPOTab />}
    </main>
  );
}
