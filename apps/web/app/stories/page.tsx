"use client";

import { useEffect, useState, useMemo } from "react";
import { fixMojibake } from "@/lib/text";
import Link from "next/link";
import {
  LineChart, Line, AreaChart, Area,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Bot, Shield, Train, Leaf, FlaskConical, Zap,
  Sparkles, BookOpen, Flame,
} from "lucide-react";
import type { ReactNode } from "react";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { MultiHorizonOutlookCard } from "@/components/intelligence";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface StoryListItem {
  id: number;
  slug?: string;
  title: string;
  summary?: string;
  description?: string;
  theme?: string;
  image?: string;
  opportunity_score?: number;
  confidence?: number;
  trend?: string;
  risk_level?: string;
  time_horizon?: string;
  sectors?: string[];
  company_count?: number;
  event_count?: number;
}

interface StoryDetail {
  id: number; slug: string; title: string; summary: string;
  opportunity_score: number; confidence: number; trend: string;
  risk_level: string; time_horizon: string; sectors: string[];
  ai_summary: { matters: string; benefits: string; risks: string[]; invalidate: string; why_bullets: string[] } | null;
  metrics: { revenue_potential: string; expected_cagr: string; eps_growth: string; investment_cycle: string; market_size: string } | null;
  events: { event_id: string; title: string; event_date: string; tag: string; description: string; importance: number }[];
  companies: { symbol: string; company_name: string; impact_score: number; impact_label: string; trend: string; confidence: number; reason: string }[];
}

interface Beneficiary { name: string; symbol: string; exposure: "Very High"|"High"|"Medium"|"Low"; score: number; change: string; positive: boolean }
interface Milestone   { date: string; event: string }
interface ChartPt     { label: string; value: number }
interface Theme {
  id: number; title: string; slug: string; badge: "Hot"|"High"|"Medium";
  description: string; opportunity_score: number; vs_yesterday: number; ai_confidence: number;
  market_impact: string; trend: string; companies: number; events: number; news: number;
  sectors: string[]; gradient: string; icon: ReactNode;
  sparkline: ChartPt[]; score_chart: ChartPt[];
  timeline: Milestone[]; beneficiaries: Beneficiary[];
  key_drivers: string[]; related: string[]; ai_insight: string;
}

// ── Static theme data ─────────────────────────────────────────────────────────

const mkSpark = (base: number, n = 8) =>
  Array.from({ length: n }, (_, i) => ({ label: `D${i}`, value: +(base * (1 + (Math.random() - 0.46) * 0.04 * (i + 1))).toFixed(1) }));
const mkScore = (end: number) =>
  ["Dec'24","Jan'25","Feb'25","Mar'25","Apr'25","May'25"].map((label, i) => ({
    label, value: Math.round(end - (5 - i) * ((end - 45) / 5) + (Math.random() - 0.5) * 4),
  }));

const THEMES: Theme[] = [
  {
    id: 1, title: "AI Infrastructure Boom", slug: "story-ai-infra-2026", badge: "Hot",
    description: "Surging investments in AI data centers, cloud infrastructure and associated power demand.",
    opportunity_score: 94, vs_yesterday: 8, ai_confidence: 91, market_impact: "Very High", trend: "Strong Uptrend",
    companies: 12, events: 8, news: 34, sectors: ["Technology","Power","Infrastructure"],
    gradient: "from-blue-950 via-indigo-900 to-slate-900", icon: <Bot className="h-10 w-10" />,
    sparkline: mkSpark(90), score_chart: mkScore(94),
    timeline: [{ date: "May 2024", event: "IndiaAI Mission Announced" }, { date: "Aug 2024", event: "NVIDIA India Partnership" }, { date: "Jan 2025", event: "Data Center Policy Released" }, { date: "Mar 2025", event: "Major Projects Announced" }, { date: "May 2025", event: "Power Demand Outlook Raised" }],
    beneficiaries: [{ name: "Tata Power", symbol: "TATAPOWER", exposure: "Very High", score: 95, change: "+12.4%", positive: true }, { name: "Siemens India", symbol: "SIEMENS", exposure: "High", score: 91, change: "+8.7%", positive: true }, { name: "ABB India", symbol: "ABB", exposure: "High", score: 88, change: "+7.2%", positive: true }],
    key_drivers: ["Rising AI adoption globally","Massive data center investments","Government policy support","Power infrastructure expansion","Cloud & edge computing growth"],
    related: ["Power Demand","Data Centers","Semiconductors","Cloud Computing"],
    ai_insight: "The AI infrastructure theme is expected to remain strong with sustained investments and policy tailwinds.",
  },
  {
    id: 2, title: "Defence Manufacturing Push", slug: "story-defence-2026", badge: "Hot",
    description: "Record defence budget, local manufacturing push and export opportunities.",
    opportunity_score: 92, vs_yesterday: 6, ai_confidence: 90, market_impact: "Very High", trend: "Strong Uptrend",
    companies: 18, events: 11, news: 27, sectors: ["Defence","Aerospace","Engineering"],
    gradient: "from-stone-900 via-amber-950 to-slate-900", icon: <Shield className="h-10 w-10" />,
    sparkline: mkSpark(88), score_chart: mkScore(92),
    timeline: [{ date: "Feb 2024", event: "Defence Budget Hiked 13%" }, { date: "Jun 2024", event: "HAL Gets ₹60,000 Cr Order" }, { date: "Feb 2025", event: "Record Budget Allocation" }, { date: "May 2025", event: "Export Target ₹50,000 Cr" }],
    beneficiaries: [{ name: "HAL", symbol: "HAL", exposure: "Very High", score: 96, change: "+18.2%", positive: true }, { name: "BEL", symbol: "BEL", exposure: "Very High", score: 93, change: "+14.5%", positive: true }, { name: "MTAR Tech", symbol: "MTAR", exposure: "High", score: 87, change: "+11.2%", positive: true }],
    key_drivers: ["Record defence budget","Atmanirbhar Bharat push","Rising geopolitical risk","Export opportunity window","Technology transfer deals"],
    related: ["Aerospace","Public Sector","Infrastructure","Geopolitics"],
    ai_insight: "Defence manufacturing has strong multi-year tailwinds. HAL and BEL remain the primary beneficiaries.",
  },
  {
    id: 3, title: "Railway Modernization", slug: "story-railway-2026", badge: "High",
    description: "Higher capex, new projects, station redevelopment and freight corridor expansion.",
    opportunity_score: 88, vs_yesterday: 5, ai_confidence: 85, market_impact: "High", trend: "Uptrend",
    companies: 14, events: 9, news: 19, sectors: ["Infrastructure","Engineering","Logistics"],
    gradient: "from-slate-800 via-blue-900 to-slate-900", icon: <Train className="h-10 w-10" />,
    sparkline: mkSpark(84), score_chart: mkScore(88),
    timeline: [{ date: "Jan 2024", event: "Vande Bharat Expansion" }, { date: "Apr 2024", event: "Freight Corridor Milestone" }, { date: "Jan 2025", event: "Budget Capex ₹2.65 Lakh Cr" }, { date: "Apr 2025", event: "Kavach Rollout Accelerated" }],
    beneficiaries: [{ name: "RVNL", symbol: "RVNL", exposure: "Very High", score: 92, change: "+16.4%", positive: true }, { name: "IRCON", symbol: "IRCON", exposure: "High", score: 88, change: "+12.1%", positive: true }, { name: "Texmaco Rail", symbol: "TEXRAIL", exposure: "High", score: 83, change: "+9.3%", positive: true }],
    key_drivers: ["Record railway capex","Freight corridor completion","Vande Bharat expansion","Station redevelopment","Kavach safety rollout"],
    related: ["Infrastructure","Logistics","Urban Mobility","Public Sector"],
    ai_insight: "Railway modernisation offers a multi-year growth runway. RVNL and IRCON are best positioned.",
  },
  {
    id: 4, title: "Renewable Energy Acceleration", slug: "story-green-energy-2026", badge: "High",
    description: "Green energy transition, solar & wind capacity additions and storage solutions.",
    opportunity_score: 86, vs_yesterday: 4, ai_confidence: 84, market_impact: "High", trend: "Uptrend",
    companies: 16, events: 10, news: 23, sectors: ["Energy","Utilities","Manufacturing"],
    gradient: "from-emerald-950 via-green-900 to-slate-900", icon: <Leaf className="h-10 w-10" />,
    sparkline: mkSpark(82), score_chart: mkScore(86),
    timeline: [{ date: "Mar 2024", event: "500 GW Target Reaffirmed" }, { date: "Jul 2024", event: "PLI Solar Module Boost" }, { date: "Nov 2024", event: "Green Hydrogen Mission Funded" }, { date: "May 2025", event: "Offshore Wind Auction Launched" }],
    beneficiaries: [{ name: "Adani Green", symbol: "ADANIGREEN", exposure: "Very High", score: 91, change: "+11.8%", positive: true }, { name: "Torrent Power", symbol: "TORNTPOWER", exposure: "High", score: 86, change: "+8.9%", positive: true }, { name: "SJVN", symbol: "SJVN", exposure: "High", score: 82, change: "+7.4%", positive: true }],
    key_drivers: ["500 GW renewable target","PLI scheme for solar","Green hydrogen policy","Battery storage incentives","Global ESG capital flows"],
    related: ["Green Hydrogen","Solar Manufacturing","Wind Energy","Power Grid"],
    ai_insight: "India's renewable push is accelerating with policy support and global capital interest.",
  },
  {
    id: 5, title: "Semiconductor Mission", slug: "story-semiconductor-2026", badge: "Medium",
    description: "Government incentives, new fabs, OSAT units and component manufacturing.",
    opportunity_score: 76, vs_yesterday: 2, ai_confidence: 76, market_impact: "Medium", trend: "Uptrend",
    companies: 11, events: 6, news: 15, sectors: ["Technology","Electronics","Manufacturing"],
    gradient: "from-purple-950 via-violet-900 to-slate-900", icon: <FlaskConical className="h-10 w-10" />,
    sparkline: mkSpark(72), score_chart: mkScore(76),
    timeline: [{ date: "Jun 2023", event: "India Semiconductor Mission Launched" }, { date: "Feb 2024", event: "Micron Fab Approved ₹22,500 Cr" }, { date: "Jan 2025", event: "Tata Semiconductor Plant Begins" }, { date: "Apr 2025", event: "Design-Linked Incentive Expanded" }],
    beneficiaries: [{ name: "Dixon Technologies", symbol: "DIXON", exposure: "Very High", score: 87, change: "+14.7%", positive: true }, { name: "Kaynes Technology", symbol: "KAYNES", exposure: "High", score: 82, change: "+10.3%", positive: true }, { name: "Tata Elxsi", symbol: "TATAELXSI", exposure: "High", score: 78, change: "+7.9%", positive: true }],
    key_drivers: ["India Semiconductor Mission","Production-linked incentives","Global chip diversification","Design talent base","OSAT unit pipeline"],
    related: ["Electronics Manufacturing","PCB","Chip Design","Tech Hardware"],
    ai_insight: "India's semiconductor ambitions are early-stage but gaining credibility with Micron and Tata commitments.",
  },
  {
    id: 6, title: "Electric Vehicles Ecosystem", slug: "story-ev-2026", badge: "High",
    description: "EV adoption, battery manufacturing, charging infrastructure and policy support.",
    opportunity_score: 82, vs_yesterday: 3, ai_confidence: 80, market_impact: "High", trend: "Uptrend",
    companies: 20, events: 13, news: 31, sectors: ["Auto","Manufacturing","Technology"],
    gradient: "from-teal-950 via-cyan-900 to-slate-900", icon: <Zap className="h-10 w-10" />,
    sparkline: mkSpark(78), score_chart: mkScore(82),
    timeline: [{ date: "Apr 2024", event: "PM e-Drive Scheme ₹10,900 Cr" }, { date: "Aug 2024", event: "Battery Gigafactory Investments" }, { date: "Feb 2025", event: "EV Import Duty Reduced" }, { date: "May 2025", event: "Two-Wheeler EV Penetration 8%" }],
    beneficiaries: [{ name: "Tata Motors", symbol: "TATAMOTORS", exposure: "Very High", score: 89, change: "+9.6%", positive: true }, { name: "Exide Industries", symbol: "EXIDEIND", exposure: "High", score: 80, change: "+7.1%", positive: true }, { name: "Motherson Sumi", symbol: "MOTHERSON", exposure: "Medium", score: 73, change: "+4.8%", positive: true }],
    key_drivers: ["PM e-Drive scheme","Battery localisation","Charging infrastructure","Two-wheeler EV surge","Global OEM partnerships"],
    related: ["Battery Storage","Auto Ancillaries","Charging Infrastructure","Clean Mobility"],
    ai_insight: "EV adoption is inflecting with policy support and falling battery costs. Battery supply chain is the next play.",
  },
];

// ── Story list constants ───────────────────────────────────────────────────────

const THEME_CATEGORIES = [
  "All", "AI", "Railways", "Defence", "Semiconductor", "Power", "Infrastructure", "Manufacturing", "Green Energy",
];

const STATIC_STORIES: StoryListItem[] = [
  { id: 1, slug: "india-infra-supercycle", title: "India Infrastructure Supercycle", summary: "India's infrastructure spending is entering a multi-decade supercycle.", opportunity_score: 92, confidence: 0.91, trend: "up", risk_level: "Medium", time_horizon: "3-5 Years", sectors: ["Infrastructure"], company_count: 12, event_count: 8 },
  { id: 2, slug: "defence-manufacturing-boom", title: "Defence Manufacturing Boom", summary: "India is emerging as a major defence manufacturing hub with record exports.", opportunity_score: 89, confidence: 0.88, trend: "up", risk_level: "Medium", time_horizon: "5-7 Years", sectors: ["Defense"], company_count: 9, event_count: 6 },
  { id: 3, slug: "green-energy-transition", title: "Green Energy Transition", summary: "Renewable energy adoption and green hydrogen initiatives.", opportunity_score: 88, confidence: 0.86, trend: "up", risk_level: "Low", time_horizon: "5-10 Years", sectors: ["Energy"], company_count: 11, event_count: 7 },
  { id: 4, slug: "ai-automation-impact", title: "AI & Automation Wave", summary: "How artificial intelligence and automation are reshaping India's IT sector.", opportunity_score: 85, confidence: 0.84, trend: "up", risk_level: "High", time_horizon: "2-3 Years", sectors: ["Technology"], company_count: 15, event_count: 10 },
  { id: 5, slug: "pli-manufacturing", title: "PLI Schemes & Manufacturing", summary: "Production-linked incentive schemes transforming India's manufacturing.", opportunity_score: 82, confidence: 0.82, trend: "up", risk_level: "Medium", time_horizon: "3-5 Years", sectors: ["Manufacturing"], company_count: 8, event_count: 5 },
];

// ── Theme category mapping ─────────────────────────────────────────────────────

function themeMatchesCategory(theme: Theme, cat: string): boolean {
  if (cat === "All") return true;
  const combined = (theme.title + " " + theme.sectors.join(" ")).toLowerCase();
  const mapping: Record<string, string[]> = {
    AI: ["ai","artificial intelligence","automation"],
    Railways: ["railway","rail","metro"],
    Defence: ["defence","defense","aerospace","military"],
    Semiconductor: ["semiconductor","chip","electronics"],
    Power: ["power","energy","electricity"],
    Infrastructure: ["infrastructure","infra","construction"],
    Manufacturing: ["manufacturing","factory","production"],
    "Green Energy": ["green","renewable","solar","wind","ev","electric"],
  };
  const keywords = mapping[cat] ?? [cat.toLowerCase()];
  return keywords.some(k => combined.includes(k));
}

// ── Helper components ─────────────────────────────────────────────────────────

const BADGE_COLOR: Record<string, string> = {
  Hot:    "bg-rose-500/15 text-rose-300 border border-rose-500/30",
  High:   "bg-amber-500/15 text-amber-300 border border-amber-500/30",
  Medium: "bg-sky-500/15 text-sky-300 border border-sky-500/30",
};
const EXPOSURE_COLOR: Record<string, string> = {
  "Very High": "text-emerald-400", High: "text-sky-400", Medium: "text-amber-400", Low: "text-slate-400",
};
const CARD_GRAD: Record<string, string> = {
  Technology: "from-blue-900 via-indigo-900 to-violet-900",
  Infrastructure: "from-slate-800 via-indigo-900 to-blue-950",
  Energy: "from-amber-900 via-orange-950 to-slate-900",
  Defence: "from-slate-900 via-zinc-900 to-slate-800",
  Defense: "from-slate-900 via-zinc-900 to-slate-800",
  Railways: "from-indigo-900 via-blue-950 to-slate-900",
  Manufacturing: "from-orange-900 via-amber-950 to-slate-900",
  Semiconductor: "from-cyan-900 via-teal-950 to-slate-900",
};
const DEFAULT_GRAD = "from-violet-900 via-indigo-950 to-slate-900";

function gradForSectors(sectors: string[]): string {
  for (const s of sectors) { if (CARD_GRAD[s]) return CARD_GRAD[s]; }
  return DEFAULT_GRAD;
}

function scoreLabel(s: number) { return s >= 85 ? "Very High" : s >= 70 ? "High" : s >= 55 ? "Moderate" : "Neutral"; }
function scoreLabelColor(s: number) { return s >= 85 ? "text-emerald-400" : s >= 70 ? "text-sky-400" : s >= 55 ? "text-amber-400" : "text-slate-400"; }

function genChartData(score: number) {
  const years = ["2023","2024","2025","2026E","2027E","2028E"];
  const base = Math.max(20, score - 55);
  return years.map((year, i) => ({ year, value: Math.round(base + (score - base) * (i / (years.length - 1)) * (0.9 + (((score * 7 + i * 13) % 10) / 50))) }));
}

function ScoreRing({ score }: { score: number }) {
  const r = 26, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 85 ? "#10b981" : score >= 70 ? "#3b82f6" : "#f59e0b";
  return (
    <div className="relative flex items-center justify-center w-16 h-16">
      <svg width={64} height={64} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={32} cy={32} r={r} stroke="rgba(255,255,255,0.08)" strokeWidth={4} fill="none"/>
        <circle cx={32} cy={32} r={r} stroke={color} strokeWidth={4} fill="none" strokeLinecap="round" strokeDasharray={`${dash} ${circ}`}/>
      </svg>
      <div className="absolute text-center">
        <div className="text-[15px] font-black text-white">{score}</div>
        <div className="text-[8px] text-slate-400">{scoreLabel(score)}</div>
      </div>
    </div>
  );
}

// ── Theme detail panel ────────────────────────────────────────────────────────

function ThemeDetail({ t }: { t: Theme }) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-[#080910]/80 overflow-hidden">
      <div className={`relative h-32 w-full bg-gradient-to-br ${t.gradient} flex items-center justify-center overflow-hidden`}>
        <span className="text-6xl opacity-40">{t.icon}</span>
        <div className="absolute inset-0 bg-gradient-to-t from-[#080910]/80 via-transparent to-transparent"/>
      </div>
      <div className="p-5 space-y-5">
        <div>
          <span className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-semibold mb-2 ${BADGE_COLOR[t.badge]}`}>
            {t.badge === "Hot" ? <><Flame className="inline h-3 w-3 mr-0.5" />Hot Theme</> : `${t.badge} Theme`}
          </span>
          <h2 className="text-lg font-bold text-white">{t.title}</h2>
          <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{t.description}</p>
        </div>

        <div className="grid grid-cols-2 gap-2 text-center">
          {([["Score", `${t.opportunity_score}/100`], ["AI Confidence", `${t.ai_confidence}%`], ["Impact", t.market_impact], ["Trend", t.trend]] as [string, string][]).map(([label, value]) => (
            <div key={label} className="rounded-[12px] border border-white/8 bg-white/[0.02] p-2">
              <p className="text-[9px] uppercase tracking-wider text-slate-500">{label}</p>
              <p className="text-xs font-bold text-white mt-0.5">{value}</p>
            </div>
          ))}
        </div>

        <div>
          <p className="mb-2 text-[10px] font-bold tracking-widest text-slate-500 uppercase">Theme Timeline</p>
          <div className="space-y-0">
            {t.timeline.map((m, i) => (
              <div key={i} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div className={`h-2.5 w-2.5 shrink-0 rounded-full border-2 mt-0.5 ${i === t.timeline.length - 1 ? "border-indigo-500 bg-indigo-500/30" : "border-slate-600 bg-slate-800"}`}/>
                  {i < t.timeline.length - 1 && <div className="w-px flex-1 bg-white/8 my-1"/>}
                </div>
                <div className="pb-3">
                  <p className="text-[10px] text-slate-500">{m.date}</p>
                  <p className="text-xs text-slate-300">{m.event}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-[10px] font-bold tracking-widest text-slate-500 uppercase">Top Beneficiaries</p>
          <div className="rounded-[14px] border border-white/8 overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/8 bg-white/[0.02]">
                  <th className="px-3 py-2 text-left text-[10px] font-semibold text-slate-500">Company</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold text-slate-500">Exposure</th>
                  <th className="px-3 py-2 text-right text-[10px] font-semibold text-slate-500">1M</th>
                </tr>
              </thead>
              <tbody>
                {t.beneficiaries.map((b, i) => (
                  <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02] transition">
                    <td className="px-3 py-2.5">
                      <Link href={`/companies/${b.symbol}`} className="text-slate-200 hover:text-sky-300 transition">{b.name}</Link>
                    </td>
                    <td className={`px-3 py-2.5 text-[11px] font-medium ${EXPOSURE_COLOR[b.exposure]}`}>{b.exposure}</td>
                    <td className={`px-3 py-2.5 text-right font-medium ${b.positive ? "text-emerald-400" : "text-rose-400"}`}>{b.change}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <p className="mb-2 text-[10px] font-bold tracking-widest text-slate-500 uppercase">Key Drivers</p>
          <div className="space-y-1.5">
            {t.key_drivers.map((d, i) => (
              <div key={i} className="flex items-start gap-2">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-3.5 w-3.5 shrink-0 mt-0.5 text-emerald-400"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                <p className="text-xs text-slate-300">{d}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[16px] border border-violet-500/20 bg-violet-500/[0.04] p-4">
          <div className="flex items-start gap-2.5">
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5 shrink-0 mt-0.5 text-violet-400"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-violet-300 mb-1">AI Insight</p>
              <p className="text-xs leading-5 text-slate-300">{t.ai_insight}</p>
            </div>
          </div>
          <Link href={`/stories/${t.slug}`}
            className="mt-3 flex items-center justify-center gap-1.5 rounded-[12px] bg-gradient-to-r from-violet-600 to-sky-500 py-2 text-[11px] font-semibold text-white hover:opacity-90 transition">
            View Detailed Analysis →
          </Link>
        </div>
      </div>
    </div>
  );
}

// ── Themes tab ────────────────────────────────────────────────────────────────

function ThemesTab() {
  const [selected, setSelected] = useState<Theme>(THEMES[0]);
  const [category, setCategory] = useState("All");

  const filtered = THEMES.filter(t => themeMatchesCategory(t, category));
  const displaySelected = filtered.find(t => t.id === selected.id) ?? filtered[0] ?? THEMES[0];

  return (
    <div className="space-y-5">
      <div className="flex gap-1 overflow-x-auto pb-1 scrollbar-hide">
        {THEME_CATEGORIES.map(cat => (
          <button key={cat} onClick={() => setCategory(cat)}
            className={`flex-shrink-0 rounded-lg px-3.5 py-1.5 text-[12px] font-medium transition whitespace-nowrap ${
              category === cat ? "bg-sky-500/15 text-sky-300 border border-sky-500/30" : "text-slate-500 hover:text-slate-300 border border-transparent"
            }`}>
            {cat}
          </button>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <div className="space-y-3">
          {(filtered.length > 0 ? filtered : THEMES).map(t => {
            const sparkColor = t.badge === "Hot" ? "#f87171" : t.badge === "High" ? "#fbbf24" : "#38bdf8";
            const isSelected = displaySelected.id === t.id;
            return (
              <button key={t.id} onClick={() => setSelected(t)}
                className={`w-full text-left rounded-[20px] border p-4 transition ${isSelected ? "border-indigo-500/40 bg-indigo-500/[0.07] ring-1 ring-indigo-500/20" : "border-white/8 bg-white/[0.025] hover:border-white/15 hover:bg-white/[0.04]"}`}>
                <div className="flex gap-3">
                  <div className={`relative h-20 w-24 shrink-0 overflow-hidden rounded-[14px] bg-gradient-to-br ${t.gradient} flex items-center justify-center text-white/80`}>
                    {t.icon}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="truncate text-sm font-semibold text-white">{t.title}</span>
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${BADGE_COLOR[t.badge]}`}>
                        {t.badge === "Hot" ? <><Flame className="inline h-3 w-3 mr-0.5" />Hot</> : t.badge}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] leading-4 text-slate-400 line-clamp-2">{t.description}</p>
                    <div className="mt-2 flex gap-2 text-[10px] text-slate-500">
                      <span className="rounded-full bg-white/5 px-2 py-0.5">{t.companies} Companies</span>
                      <span className="rounded-full bg-white/5 px-2 py-0.5">{t.events} Events</span>
                      <span className="rounded-full bg-white/5 px-2 py-0.5">{t.news} News</span>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex items-end justify-between gap-3">
                  <div>
                    <p className="text-[10px] text-slate-500">Opportunity Score</p>
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-bold text-white">{t.opportunity_score}</span>
                      <span className="text-[10px] text-emerald-400">+{t.vs_yesterday} vs yesterday</span>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <div className="h-1 w-20 overflow-hidden rounded-full bg-white/5">
                        <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500" style={{ width: `${t.ai_confidence}%` }}/>
                      </div>
                      <span className="text-[10px] text-slate-500">AI {t.ai_confidence}%</span>
                    </div>
                  </div>
                  <div className="h-8 w-20">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={t.sparkline} margin={{ top: 1, right: 0, bottom: 1, left: 0 }}>
                        <defs>
                          <linearGradient id={`sg-${t.id}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={sparkColor} stopOpacity={0.3}/>
                            <stop offset="100%" stopColor={sparkColor} stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <Area type="monotone" dataKey="value" stroke={sparkColor} strokeWidth={1.5} fill={`url(#sg-${t.id})`} dot={false}/>
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="hidden xl:block">
          <ThemeDetail key={displaySelected.id} t={displaySelected}/>
        </div>
      </div>
    </div>
  );
}

// ── Stories tab ───────────────────────────────────────────────────────────────

function StoriesTab() {
  const [stories, setStories] = useState<StoryListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("All Stories");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<StoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const STORY_CATEGORIES = ["All Stories","Infrastructure","Technology","Energy","Manufacturing","Financial Services","Healthcare","Consumer","Defense","Agriculture"];

  useEffect(() => {
    fetch(`${API}/api/stories/`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        const raw: StoryListItem[] = Array.isArray(d) ? d : (d?.items ?? []);
        setStories(raw.length === 0 ? STATIC_STORIES : raw);
      })
      .catch(() => setStories(STATIC_STORIES))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (stories.length > 0 && selectedId === null) setSelectedId(stories[0].id);
  }, [stories, selectedId]);

  useEffect(() => {
    if (selectedId === null) return;
    setDetailLoading(true);
    setDetail(null);
    fetch(`${API}/api/stories/${selectedId}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setDetail(d); })
      .catch(() => {})
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  const filtered = useMemo(() => {
    let list = stories;
    if (category !== "All Stories") {
      list = list.filter(s => (s.sectors ?? []).some(sec => sec.toLowerCase().includes(category.toLowerCase()) || category.toLowerCase().includes(sec.toLowerCase())));
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(s => s.title.toLowerCase().includes(q) || (s.summary ?? s.description ?? "").toLowerCase().includes(q));
    }
    return list;
  }, [stories, category, search]);

  const selected = stories.find(s => s.id === selectedId) ?? null;
  const chartData = selected ? genChartData(Math.round(selected.opportunity_score ?? 0)) : [];

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_340px] items-start">
      <div className="min-w-0 space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-1 overflow-x-auto pb-1 scrollbar-hide">
            {STORY_CATEGORIES.map(cat => (
              <button key={cat} onClick={() => setCategory(cat)}
                className={`flex-shrink-0 rounded-lg px-3 py-1.5 text-[12px] font-medium transition whitespace-nowrap ${
                  category === cat ? "bg-sky-500/15 text-sky-300 border border-sky-500/30" : "text-slate-500 hover:text-slate-300 border border-transparent"
                }`}>
                {cat}
              </button>
            ))}
          </div>
          <div className="relative shrink-0">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search stories…"
              className="h-9 w-48 rounded-xl border border-white/10 bg-white/[0.03] pl-8 pr-3 text-[13px] text-slate-300 outline-none placeholder:text-slate-600"/>
          </div>
        </div>

        {loading ? (
          <div className="flex gap-3 overflow-x-auto pb-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex-shrink-0 w-64 h-52 animate-pulse rounded-[20px] border border-white/10 bg-white/[0.02]"/>
            ))}
          </div>
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-2">
            {(filtered.length > 0 ? filtered : STATIC_STORIES).map(s => {
              const score = Math.round(s.opportunity_score ?? 0);
              const grad = gradForSectors(s.sectors ?? []);
              return (
                <button key={s.id} onClick={() => setSelectedId(s.id)}
                  className={`group relative flex-shrink-0 w-64 rounded-[20px] overflow-hidden border transition text-left ${s.id === selectedId ? "border-sky-500/50 ring-1 ring-sky-500/30" : "border-white/10 hover:border-white/20"}`}>
                  <div className={`h-36 w-full bg-gradient-to-br ${grad} relative`}>
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent"/>
                    <div className="absolute top-3 left-3">
                      <span className="rounded-full border border-white/20 bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white">
                        {s.sectors?.[0] ?? s.theme ?? "General"}
                      </span>
                    </div>
                    <div className="absolute bottom-3 right-3">
                      <ScoreRing score={score}/>
                    </div>
                  </div>
                  <div className="bg-slate-900/80 p-3">
                    <h3 className="text-[12px] font-bold leading-snug text-white line-clamp-2 group-hover:text-sky-200 transition">{s.title}</h3>
                    <p className="mt-1 text-[11px] leading-4 text-slate-400 line-clamp-2">{s.summary ?? s.description ?? ""}</p>
                    <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-500">
                      <span>{s.company_count ?? 0} companies</span><span>·</span><span>{s.event_count ?? 0} events</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        <div>
          <h2 className="mb-3 text-[13px] font-semibold text-white">Theme Performance Overview</h2>
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] overflow-hidden">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-white/5 text-[10px] uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3 text-left">Story</th>
                  <th className="px-4 py-3 text-center">Score</th>
                  <th className="px-4 py-3 text-center">Trend</th>
                  <th className="px-4 py-3 text-left">Sector</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {(filtered.length > 0 ? filtered : STATIC_STORIES).slice(0, 8).map(row => (
                  <tr key={row.id} onClick={() => setSelectedId(row.id)}
                    className={`cursor-pointer transition hover:bg-white/[0.03] ${row.id === selectedId ? "bg-sky-500/5" : ""}`}>
                    <td className="px-4 py-3 text-[12px] font-medium text-slate-200">{row.title.length > 30 ? row.title.slice(0, 30) + "…" : row.title}</td>
                    <td className={`px-4 py-3 text-center font-bold ${scoreLabelColor(Math.round(row.opportunity_score ?? 0))}`}>{Math.round(row.opportunity_score ?? 0)}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={row.trend === "up" ? "text-emerald-400" : "text-rose-400"}>{row.trend === "up" ? "↑" : "↓"}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-400">{row.sectors?.[0] ?? row.theme ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <aside className="sticky top-[84px]">
        {detailLoading ? (
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 space-y-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className={`animate-pulse rounded bg-white/[0.05] ${i === 0 ? "h-6 w-3/4" : "h-4 w-full"}`}/>
            ))}
          </div>
        ) : selected ? (
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] overflow-hidden">
            <div className={`relative bg-gradient-to-br ${gradForSectors(selected.sectors ?? [])} p-5`}>
              <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent"/>
              <div className="relative flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <span className="inline-block rounded-full border border-white/20 bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white mb-2">
                    {selected.sectors?.[0] ?? selected.theme ?? "General"}
                  </span>
                  <h2 className="text-[16px] font-bold leading-snug text-white line-clamp-3">{selected.title}</h2>
                </div>
                <div className="flex-shrink-0"><ScoreRing score={Math.round(selected.opportunity_score ?? 0)}/></div>
              </div>
            </div>
            <div className="p-5 space-y-5">
              <p className="text-[12px] leading-5 text-slate-300">{detail?.ai_summary?.matters || selected.summary || selected.description || ""}</p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: "Companies", value: detail ? (detail.companies?.length ?? 0) : (selected.company_count ?? 0) },
                  { label: "Events", value: detail ? (detail.events?.length ?? 0) : (selected.event_count ?? 0) },
                  { label: "Time Horizon", value: fixMojibake(selected.time_horizon) || "3-5 Years" },
                  { label: "Risk Level", value: selected.risk_level || "Medium" },
                  { label: "AI Confidence", value: selected.confidence != null ? `${Math.round(selected.confidence <= 1 ? selected.confidence * 100 : selected.confidence)}%` : "—" },
                ].map(stat => (
                  <div key={stat.label} className="rounded-[12px] border border-white/5 bg-white/[0.02] p-3">
                    <p className="text-[9px] uppercase tracking-widest text-slate-500">{stat.label}</p>
                    <p className="mt-0.5 text-[13px] font-bold text-white">{stat.value}</p>
                  </div>
                ))}
              </div>
              {detail && (detail.companies?.length ?? 0) > 0 && (
                <div>
                  <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Key Beneficiaries</p>
                  <div className="flex flex-wrap gap-1.5">
                    {detail.companies.slice(0, 8).map(c => (
                      <Link key={c.symbol} href={`/companies/${c.symbol}`}
                        className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-0.5 text-[11px] font-medium text-slate-200 hover:border-sky-500/40 hover:text-sky-300 transition">
                        {c.symbol}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
              <div>
                <p className="mb-2 text-[11px] font-semibold text-white">Impact Over Time</p>
                <div className="h-[120px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 4, right: 4, left: -25, bottom: 0 }}>
                      <XAxis dataKey="year" tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false}/>
                      <YAxis domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false}/>
                      <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontSize: 11 }} itemStyle={{ color: "#22c55e" }} labelStyle={{ color: "#94a3b8" }}/>
                      <Line type="monotone" dataKey="value" stroke="#22c55e" strokeWidth={2} dot={{ fill: "#22c55e", r: 2 }} activeDot={{ r: 4 }}/>
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <MultiHorizonOutlookCard
                fetchContext={{
                  type:       "story",
                  title:      selected.title,
                  context:    detail?.ai_summary?.matters || selected.summary || selected.description || "",
                  sectors:    selected.sectors ?? [],
                  context_id: `story:${selected.id}`,
                }}
                compact
              />
              <Link href={`/stories/${selected.slug ?? selected.id}`}
                className="flex items-center justify-center gap-1.5 rounded-xl bg-sky-500/10 border border-sky-500/25 py-2.5 text-[13px] font-medium text-sky-300 hover:bg-sky-500/15 transition">
                View Detailed Analysis →
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
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type PageTab = "themes" | "stories";

export default function StoriesPage() {
  const [tab, setTab] = useState<PageTab>("themes");

  return (
    <main className="min-w-0 pb-10">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Stories</h1>
          <p className="mt-1 text-sm text-slate-400">AI-powered investment themes · Long-term market narratives</p>
        </div>
        <Link href="/ai-search?q=top investment themes India"
          className="flex items-center gap-2 rounded-[14px] bg-gradient-to-r from-violet-600 to-sky-500 px-4 py-2 text-sm font-semibold text-white hover:opacity-90 transition whitespace-nowrap">
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg> AI Theme Analysis
        </Link>
      </div>

      <div className="mb-6 flex gap-1 border-b border-white/8 pb-0">
        {([
          { id: "themes" as PageTab, label: "Themes", icon: <Flame className="h-3.5 w-3.5" /> },
          { id: "stories" as PageTab, label: "Opportunity Stories", icon: <BookOpen className="h-3.5 w-3.5" /> },
        ]).map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition ${
              tab === t.id ? "border-sky-500 text-white" : "border-transparent text-slate-500 hover:text-slate-300"
            }`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === "themes"  && <ThemesTab />}
      {tab === "stories" && <StoriesTab />}

      <div className="mt-8">
        <AIDisclaimer />
      </div>
    </main>
  );
}
