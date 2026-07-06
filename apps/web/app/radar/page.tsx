"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Telescope } from "lucide-react";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";

const API = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface RadarItem {
  id: string | number;
  theme: string;
  score: number;
  reason: string;
  confidence: number;
  beneficiaries: string[];
  sectors?: string[];
}

const SECTORS_FILTER = ["All Sectors", "Infrastructure", "Energy", "Technology", "Banking", "Manufacturing", "Healthcare", "FMCG"];
const THEMES_FILTER  = ["All Themes", "AI & Automation", "Green Energy", "Infrastructure", "Defence", "EV", "Pharma"];
const HORIZONS       = ["All", "Short Term", "Medium Term", "Long Term"];

const STATIC_RADAR: RadarItem[] = [
  { id: "r1", theme: "AI Infrastructure Boom",    score: 95, reason: "Surging demand for AI data centres and capacity expansion driving massive investments", confidence: 0.92, beneficiaries: ["TATASTEEL","RVNL","L&T","BEML","IRCON"], sectors: ["Infrastructure","Technology"]  },
  { id: "r2", theme: "Railway Modernization",     score: 94, reason: "Government focus on railway modernisation and capacity expansion driving massive investments", confidence: 0.91, beneficiaries: ["RVNL","IRCON","L&T","BEML","TATASTEEL"], sectors: ["Railways","Infrastructure"] },
  { id: "r3", theme: "Green Energy Transition",   score: 92, reason: "Renewable energy adoption and green hydrogen initiatives driving clean energy revolution", confidence: 0.88, beneficiaries: ["ADANI","TATA","NTPC","RPOWER","SJVN"],    sectors: ["Energy","Sustainability"]   },
  { id: "r4", theme: "Defence Manufacturing",     score: 89, reason: "India's push for defence indigenisation creating multi-year tailwinds for manufacturers", confidence: 0.86, beneficiaries: ["HAL","BEL","BHEL","MIL","GRSE"],          sectors: ["Defence","Aerospace"]       },
  { id: "r5", theme: "Digital Banking Wave",      score: 87, reason: "Rapid digitalisation of banking creating structural growth opportunities for fintech", confidence: 0.84, beneficiaries: ["HDFCBANK","ICICIBANK","SBIN","AXIS","KOTAKBANK"], sectors: ["Banking","FinTech"]          },
  { id: "r6", theme: "EV Supply Chain Build-out", score: 85, reason: "Electric vehicle adoption driving demand across the entire EV supply chain ecosystem", confidence: 0.82, beneficiaries: ["TATAMOTORS","M&M","HERO","BAJAJ","MARUTI"],   sectors: ["Automotive","Energy"]       },
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
        <circle cx={size/2} cy={size/2} r={r}
          stroke="currentColor"
          className={cc.fill}
          strokeWidth={4} fill="none"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}/>
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

export default function RadarPage() {
  // Start with static data so the page renders immediately on mount
  const [items, setItems] = useState<RadarItem[]>(STATIC_RADAR);
  const [sectorFilter, setSectorFilter] = useState("All Sectors");
  const [themeFilter, setThemeFilter]   = useState("All Themes");
  const [horizon, setHorizon]           = useState("All");
  const [minScore, setMinScore]         = useState(0);

  // Silently fetch live data in the background and swap when ready
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
      .catch(() => {/* keep static fallback */});
  }, []);

  const displayed = items.filter(i => {
    if (i.score < minScore) return false;
    if (sectorFilter !== "All Sectors" && !(i.sectors ?? []).some(s =>
      s.toLowerCase().includes(sectorFilter.toLowerCase())
    )) return false;
    if (themeFilter !== "All Themes" && !i.theme.toLowerCase().includes(
      themeFilter.toLowerCase().replace("ai & automation", "ai").replace("green energy", "energy")
    )) return false;
    return true;
  });

  return (
    <main className="min-w-0 pb-10">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Opportunity Radar</h1>
        <p className="mt-1 text-sm text-slate-400">AI-powered investment opportunities discovery</p>
      </div>

      {/* Filter row */}
      <div className="mb-6 flex flex-wrap gap-2">
        {/* Sector */}
        <select value={sectorFilter} onChange={e => setSectorFilter(e.target.value)}
          className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-slate-300 outline-none hover:border-white/20 focus:border-sky-500/40">
          {SECTORS_FILTER.map(s => <option key={s} value={s} className="bg-slate-900">{s}</option>)}
        </select>

        {/* Theme */}
        <select value={themeFilter} onChange={e => setThemeFilter(e.target.value)}
          className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-slate-300 outline-none hover:border-white/20 focus:border-sky-500/40">
          {THEMES_FILTER.map(t => <option key={t} value={t} className="bg-slate-900">{t}</option>)}
        </select>

        {/* Time Horizon */}
        <select value={horizon} onChange={e => setHorizon(e.target.value)}
          className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-slate-300 outline-none hover:border-white/20 focus:border-sky-500/40">
          {HORIZONS.map(h => <option key={h} value={h} className="bg-slate-900">{h}</option>)}
        </select>

        {/* Min Score */}
        <select onChange={e => setMinScore(Number(e.target.value))}
          className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-slate-300 outline-none hover:border-white/20 focus:border-sky-500/40">
          <option value={0} className="bg-slate-900">Min Score</option>
          <option value={80} className="bg-slate-900">80+</option>
          <option value={85} className="bg-slate-900">85+</option>
          <option value={90} className="bg-slate-900">90+</option>
        </select>

        <button className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-slate-400 hover:border-white/20 hover:text-white transition">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z"/>
          </svg>
          More Filters
        </button>
      </div>

      {/* 2-col: cards + sector sidebar */}
      <div className="grid grid-cols-[1fr_220px] gap-5 items-start">

        {/* ── LEFT: Radar cards ─────────────────────────── */}
        {displayed.length === 0 ? (
          <div className="col-span-full flex flex-col items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20 text-center">
            <Telescope className="h-8 w-8 text-slate-500" />
            <p className="mt-3 text-sm font-semibold text-white">No opportunities match these filters</p>
            <p className="mt-1 text-xs text-slate-500">Try adjusting the sector, theme, or minimum score filter</p>
            <button onClick={() => { setSectorFilter("All Sectors"); setThemeFilter("All Themes"); setMinScore(0); }}
              className="mt-4 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-xs text-slate-300 hover:border-white/20 hover:text-white transition">
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {displayed.map((item, i) => {
              const conf = item.confidence ?? 0.9;
              const cc   = confidenceColor(conf);
              const beneficiaries = Array.isArray(item.beneficiaries) ? item.beneficiaries : [];
              const sectors = Array.isArray(item.sectors) ? item.sectors : [];

              return (
                <div key={item.id}
                  className="flex flex-col rounded-[20px] border border-white/10 bg-white/[0.03] p-4 hover:border-white/20 hover:-translate-y-0.5 transition">

                  {/* Score + theme */}
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div>
                      <ScoreBadge score={item.score}/>
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-[13px] font-bold leading-snug text-white">{item.theme}</h3>
                      {sectors.length > 0 && (
                        <p className="mt-0.5 text-[11px] text-slate-500">{sectors.join(" • ")}</p>
                      )}
                    </div>
                  </div>

                  {/* Confidence meter */}
                  <div className="mb-3 flex items-center gap-3">
                    <ConfidenceCircle value={conf} size={52}/>
                    <div className="min-w-0">
                      <p className="text-[10px] text-slate-500">Confidence</p>
                      <p className={`text-base font-bold ${cc.text}`}>{Math.round(conf * 100)}%</p>
                    </div>
                    <div className="flex-1">
                      <div className="mb-1 flex justify-between">
                        <span className="text-[10px] text-slate-500">Signal</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div className={`h-full rounded-full ${cc.ring.replace("ring-","bg-").replace("/40","")}`}
                          style={{ width: `${Math.round(conf * 100)}%` }}/>
                      </div>
                    </div>
                  </div>

                  {/* Reason */}
                  <p className="mb-3 text-[12px] leading-4 text-slate-400 line-clamp-2">{item.reason}</p>

                  {/* Beneficiaries */}
                  {beneficiaries.length > 0 && (
                    <div className="mb-3">
                      <p className="mb-1.5 text-[9px] uppercase tracking-widest text-slate-600">Top Beneficiaries</p>
                      <div className="flex items-center gap-1">
                        {beneficiaries.slice(0, 5).map((b, bi) => (
                          <Link key={bi} href={`/stocks/${b.replace(/[&\s]/g, "")}`} title={b}
                            className={`flex h-7 w-7 items-center justify-center rounded-full border border-white/10 text-[9px] font-bold hover:scale-110 transition ${CHIP_COLORS[bi % CHIP_COLORS.length]}`}>
                            {b.slice(0, 2).toUpperCase()}
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* CTA */}
                  <div className="mt-auto pt-2 border-t border-white/5">
                    {typeof item.id === "number" ? (
                      <Link href={`/radar/${item.id}`} className="flex items-center gap-1 text-[12px] font-medium text-sky-400 hover:text-sky-300 transition">
                        View Details
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
                        </svg>
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

        {/* ── RIGHT: Top Sectors sidebar ────────────────── */}
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
                  <div className={`h-full rounded-full bg-gradient-to-r ${s.color}`}
                    style={{ width: `${s.score}%` }}/>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 border-t border-white/5 pt-4">
            <p className="mb-3 text-[9px] uppercase tracking-widest text-slate-500">AI Signal Strength</p>
            <div className="space-y-2">
              {[
                { label: "Bullish",  pct: 72, color: "bg-emerald-500" },
                { label: "Neutral",  pct: 18, color: "bg-amber-500"   },
                { label: "Bearish",  pct: 10, color: "bg-rose-500"    },
              ].map(s => (
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
      <div className="mt-4">
        <AIDisclaimer />
      </div>
    </main>
  );
}
