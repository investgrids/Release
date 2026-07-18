"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE_URL as API } from "@/lib/api";


// ── Types ─────────────────────────────────────────────────────────────────────

interface RadarItem {
  id: string | number;
  theme: string;
  score: number | null;
  reason: string;
  confidence: number | null;
  beneficiaries: string[];
  sectors?: string[];
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

// ── Sub-components ────────────────────────────────────────────────────────────

function confidenceColor(c: number | null | undefined) {
  if (c === null || c === undefined) return { ring: "ring-slate-600/40", text: "text-slate-500", fill: "stroke-slate-600" };
  if (c >= 0.9) return { ring: "ring-emerald-500/40", text: "text-emerald-400", fill: "stroke-emerald-500" };
  if (c >= 0.8) return { ring: "ring-sky-500/40",     text: "text-sky-400",     fill: "stroke-sky-500"     };
  return               { ring: "ring-amber-500/40",   text: "text-amber-400",   fill: "stroke-amber-500"   };
}

function ConfidenceCircle({ value, size = 64 }: { value: number | null | undefined; size?: number }) {
  const unscored = value === null || value === undefined;
  const pct = unscored ? 0 : Math.round(value * 100);
  const r   = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  const cc   = confidenceColor(value);
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgba(255,255,255,0.06)" strokeWidth={4} fill="none"/>
        {!unscored && (
          <circle cx={size/2} cy={size/2} r={r} stroke="currentColor" className={cc.fill} strokeWidth={4} fill="none" strokeLinecap="round" strokeDasharray={`${dash} ${circ}`}/>
        )}
      </svg>
      <div className="absolute text-center">
        <div className={`text-[11px] font-bold ${cc.text}`}>{unscored ? "N/A" : `${pct}%`}</div>
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number | null | undefined }) {
  const unscored = score === null || score === undefined;
  const bg = unscored ? "from-slate-700 to-slate-600"
           : score >= 90 ? "from-emerald-500 to-teal-400"
           : score >= 80 ? "from-sky-500 to-blue-400"
           : "from-amber-500 to-yellow-400";
  return (
    <div className={`flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br ${bg} shadow-lg`}>
      <span className={`font-black text-white ${unscored ? "text-[9px]" : "text-xl"}`}>{unscored ? "N/A" : score}</span>
    </div>
  );
}

// ── Opportunities ─────────────────────────────────────────────────────────────

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
        const mapped: RadarItem[] = raw.map((o: any) => {
          const rawScore = o.opportunity_score ?? o.score;
          const rawConf = o.confidence;
          return {
            id:           o.id,
            theme:        o.title,
            score:        rawScore === null || rawScore === undefined ? null : Math.round(rawScore),
            reason:       o.summary ?? o.reason ?? "",
            confidence:   typeof rawConf === "number" ? (rawConf > 1 ? rawConf / 100 : rawConf) : null,
            beneficiaries: (o.companies ?? []).map((c: any) => typeof c === "string" ? c : c.symbol),
            sectors:      o.sectors ?? [],
          };
        });
        setItems(mapped);
      })
      .catch(() => {});
  }, []);

  const displayed = items.filter(i => {
    // An unscored item can never be confirmed to meet a positive minimum
    // score threshold, so it's excluded whenever a real filter is active
    // — but it's never hidden by the default (no filter) state.
    if (minScore > 0 && (i.score === null || i.score === undefined || i.score < minScore)) return false;
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
              const conf = item.confidence;
              const unscoredConf = conf === null || conf === undefined;
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
                      <p className={`text-base font-bold ${cc.text}`}>{unscoredConf ? "Unscored" : `${Math.round(conf * 100)}%`}</p>
                    </div>
                    <div className="flex-1">
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        {!unscoredConf && (
                          <div className={`h-full rounded-full ${cc.ring.replace("ring-","bg-").replace("/40","")}`} style={{ width: `${Math.round(conf * 100)}%` }}/>
                        )}
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
          <div className="mt-6 border-t border-white/5 pt-4">
            <Link href="/ai-search?q=top investment opportunities India"
              className="block w-full rounded-xl bg-gradient-to-r from-violet-600/80 to-sky-500/80 py-2 text-center text-[12px] font-semibold text-white hover:opacity-90 transition">
              Ask AI for Analysis
            </Link>
          </div>
        </aside>
      </div>
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function OpportunityRadarPage() {
  return (
    <main className="min-w-0 pb-10">
      {/* Header */}
      <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-400 mb-2">AI-Powered</p>
          <h1 className="text-2xl font-bold text-white">Opportunity Radar</h1>
          <p className="mt-1 text-sm text-slate-400">Themes and market opportunities ranked by AI signal strength</p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/ipo-hub"
            className="flex items-center gap-2 rounded-[14px] border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/[0.07] hover:text-white transition whitespace-nowrap">
            IPO Hub →
          </Link>
          <Link href="/ai-search?q=top investment opportunities India"
            className="flex items-center gap-2 rounded-[14px] bg-gradient-to-r from-violet-600 to-sky-500 px-4 py-2 text-sm font-semibold text-white hover:opacity-90 transition whitespace-nowrap">
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg> AI Analysis
          </Link>
        </div>
      </div>

      <OpportunitiesTab />
    </main>
  );
}
