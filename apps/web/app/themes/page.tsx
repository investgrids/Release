"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Shield, Train, Leaf, Zap, FlaskConical, Flame, BarChart2 } from "lucide-react";
import { useIntelligence } from "@/hooks/useIntelligence";
import { IntelligenceBlock } from "@/components/intelligence/IntelligenceBlock";
import { API_BASE_URL as API } from "@/lib/api";
import {
  LineChart, Line, AreaChart, Area,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";


/* ── Types ───────────────────────────────────────────────── */
interface Beneficiary {
  name: string; symbol: string;
  exposure: "Very High" | "High" | "Medium" | "Low";
  score: number; change: string; positive: boolean;
}
interface Milestone { date: string; event: string }
interface ChartPt   { label: string; value: number }
interface Theme {
  id: number; title: string; slug: string;
  badge: "Hot" | "High" | "Medium";
  description: string;
  opportunity_score: number; vs_yesterday: number;
  ai_confidence: number;
  market_impact: string; trend: string;
  companies: number; events: number; news: number;
  sectors: string[];
  gradient: string; icon: ReactNode;
  sparkline: ChartPt[];
  score_chart: ChartPt[];
  timeline: Milestone[];
  beneficiaries: Beneficiary[];
  key_drivers: string[];
  related: string[];
  ai_insight: string;
}

/* ── Fallback data ───────────────────────────────────────── */
const mkSpark = (base: number, n = 8) =>
  Array.from({ length: n }, (_, i) => ({
    label: `D${i}`,
    value: +(base * (1 + (Math.random() - 0.46) * 0.04 * (i + 1))).toFixed(1),
  }));

const mkScore = (end: number) =>
  ["Dec'24","Jan'25","Feb'25","Mar'25","Apr'25","May'25"].map((label, i) => ({
    label,
    value: Math.round(end - (5 - i) * ((end - 45) / 5) + (Math.random() - 0.5) * 4),
  }));

const THEMES: Theme[] = [
  {
    id: 1, title: "AI Infrastructure Boom", slug: "ai-infrastructure",
    badge: "Hot", description: "Surging investments in AI data centers, cloud infrastructure and associated power demand.",
    opportunity_score: 94, vs_yesterday: 8, ai_confidence: 91, market_impact: "Very High", trend: "Strong Uptrend",
    companies: 12, events: 8, news: 34,
    sectors: ["Technology","Power","Infrastructure"],
    gradient: "from-blue-950 via-indigo-900 to-slate-900", icon: <Bot className="h-10 w-10 text-blue-400" />,
    sparkline: mkSpark(90), score_chart: mkScore(94),
    timeline: [
      { date: "May 2024", event: "IndiaAI Mission Announced" },
      { date: "Aug 2024", event: "NVIDIA India Partnership" },
      { date: "Jan 2025", event: "Data Center Policy Released" },
      { date: "Mar 2025", event: "Major Data Center Projects Announced" },
      { date: "May 2025", event: "Power Demand Outlook Raised" },
    ],
    beneficiaries: [
      { name: "Tata Power",        symbol: "TATAPOWER",  exposure: "Very High", score: 95, change: "+12.4%", positive: true },
      { name: "Siemens India",     symbol: "SIEMENS",    exposure: "High",      score: 91, change: "+8.7%",  positive: true },
      { name: "ABB India",         symbol: "ABB",        exposure: "High",      score: 88, change: "+7.2%",  positive: true },
      { name: "Cummins India",     symbol: "CUMMINSIND", exposure: "Medium",    score: 85, change: "+6.1%",  positive: true },
      { name: "Schneider Electric",symbol: "SCHNEIDER",  exposure: "Medium",    score: 82, change: "+5.3%",  positive: true },
    ],
    key_drivers: ["Rising AI adoption globally","Massive data center investments","Government policy support","Power infrastructure expansion","Cloud & edge computing growth"],
    related: ["Power Demand","Data Centers","Semiconductors","Cloud Computing"],
    ai_insight: "The AI infrastructure theme is expected to remain strong over the next 6–12 months with sustained investments and policy tailwinds. Key focus on power availability and execution.",
  },
  {
    id: 2, title: "Defence Manufacturing Push", slug: "defence-manufacturing",
    badge: "Hot", description: "Record defence budget, local manufacturing push and export opportunities.",
    opportunity_score: 92, vs_yesterday: 6, ai_confidence: 90, market_impact: "Very High", trend: "Strong Uptrend",
    companies: 18, events: 11, news: 27,
    sectors: ["Defence","Aerospace","Engineering"],
    gradient: "from-stone-900 via-amber-950 to-slate-900", icon: <Shield className="h-10 w-10 text-amber-400" />,
    sparkline: mkSpark(88), score_chart: mkScore(92),
    timeline: [
      { date: "Feb 2024", event: "Defence Budget Hiked 13%" },
      { date: "Jun 2024", event: "HAL Gets ₹60,000 Cr Order" },
      { date: "Nov 2024", event: "iDEX Startups Scaling" },
      { date: "Feb 2025", event: "Record Budget Allocation" },
      { date: "May 2025", event: "Export Target ₹50,000 Cr" },
    ],
    beneficiaries: [
      { name: "HAL",         symbol: "HAL",       exposure: "Very High", score: 96, change: "+18.2%", positive: true },
      { name: "BEL",         symbol: "BEL",        exposure: "Very High", score: 93, change: "+14.5%", positive: true },
      { name: "MTAR Tech",   symbol: "MTAR",       exposure: "High",      score: 87, change: "+11.2%", positive: true },
      { name: "Cochin Shipyard",symbol:"COCHINSHIP",exposure:"High",       score: 84, change: "+9.8%",  positive: true },
      { name: "GRSE",        symbol: "GRSE",       exposure: "Medium",    score: 80, change: "+7.6%",  positive: true },
    ],
    key_drivers: ["Record defence budget","Atmanirbhar Bharat push","Rising geopolitical risk","Export opportunity window","Technology transfer deals"],
    related: ["Aerospace","Public Sector","Infrastructure","Geopolitics"],
    ai_insight: "Defence manufacturing has strong multi-year tailwinds from budget allocation and export ambitions. HAL and BEL remain the primary beneficiaries.",
  },
  {
    id: 3, title: "Railway Modernization", slug: "railway-modernization",
    badge: "High", description: "Higher capex, new projects, station redevelopment and freight corridor expansion.",
    opportunity_score: 88, vs_yesterday: 5, ai_confidence: 85, market_impact: "High", trend: "Uptrend",
    companies: 14, events: 9, news: 19,
    sectors: ["Infrastructure","Engineering","Logistics"],
    gradient: "from-slate-800 via-blue-900 to-slate-900", icon: <Train className="h-10 w-10 text-sky-400" />,
    sparkline: mkSpark(84), score_chart: mkScore(88),
    timeline: [
      { date: "Jan 2024", event: "Vande Bharat Expansion" },
      { date: "Apr 2024", event: "Dedicated Freight Corridor Milestone" },
      { date: "Sep 2024", event: "Station Redevelopment Contracts" },
      { date: "Jan 2025", event: "Budget Capex ₹2.65 Lakh Cr" },
      { date: "Apr 2025", event: "Kavach Rollout Accelerated" },
    ],
    beneficiaries: [
      { name: "RVNL",       symbol: "RVNL",    exposure: "Very High", score: 92, change: "+16.4%", positive: true },
      { name: "IRCON",      symbol: "IRCON",   exposure: "High",      score: 88, change: "+12.1%", positive: true },
      { name: "Texmaco Rail",symbol:"TEXRAIL",  exposure: "High",      score: 83, change: "+9.3%",  positive: true },
      { name: "BEML",       symbol: "BEML",    exposure: "Medium",    score: 79, change: "+7.8%",  positive: true },
      { name: "Titagarh Wagons",symbol:"TWL",  exposure: "Medium",    score: 76, change: "+6.2%",  positive: true },
    ],
    key_drivers: ["Record railway capex","Freight corridor completion","Vande Bharat expansion","Station redevelopment","Kavach safety rollout"],
    related: ["Infrastructure","Logistics","Urban Mobility","Public Sector"],
    ai_insight: "Railway modernisation offers a multi-year growth runway. RVNL and IRCON are best positioned given their order books and execution track record.",
  },
  {
    id: 4, title: "Renewable Energy Acceleration", slug: "renewable-energy",
    badge: "High", description: "Green energy transition, solar & wind capacity additions and storage solutions.",
    opportunity_score: 86, vs_yesterday: 4, ai_confidence: 84, market_impact: "High", trend: "Uptrend",
    companies: 16, events: 10, news: 23,
    sectors: ["Energy","Utilities","Manufacturing"],
    gradient: "from-emerald-950 via-green-900 to-slate-900", icon: <Leaf className="h-10 w-10 text-emerald-400" />,
    sparkline: mkSpark(82), score_chart: mkScore(86),
    timeline: [
      { date: "Mar 2024", event: "500 GW Target Reaffirmed" },
      { date: "Jul 2024", event: "PLI Solar Module Boost" },
      { date: "Nov 2024", event: "Green Hydrogen Mission Funded" },
      { date: "Feb 2025", event: "Grid Storage Policy Cleared" },
      { date: "May 2025", event: "Offshore Wind Auction Launched" },
    ],
    beneficiaries: [
      { name: "Adani Green",    symbol: "ADANIGREEN", exposure: "Very High", score: 91, change: "+11.8%", positive: true },
      { name: "Torrent Power",  symbol: "TORNTPOWER", exposure: "High",      score: 86, change: "+8.9%",  positive: true },
      { name: "SJVN",          symbol: "SJVN",        exposure: "High",      score: 82, change: "+7.4%",  positive: true },
      { name: "Waaree Energies",symbol: "WAAREEENER",  exposure: "Medium",    score: 78, change: "+6.3%",  positive: true },
      { name: "Inox Wind",     symbol: "INOXWIND",    exposure: "Medium",    score: 74, change: "+5.1%",  positive: true },
    ],
    key_drivers: ["500 GW renewable target","PLI scheme for solar","Green hydrogen policy","Battery storage incentives","Global ESG capital flows"],
    related: ["Green Hydrogen","Solar Manufacturing","Wind Energy","Power Grid"],
    ai_insight: "India's renewable push is accelerating with policy support and global capital interest. Storage and green hydrogen sub-themes are emerging catalysts.",
  },
  {
    id: 5, title: "Electric Vehicles Ecosystem", slug: "electric-vehicles",
    badge: "High", description: "EV adoption, battery manufacturing, charging infrastructure and policy support.",
    opportunity_score: 82, vs_yesterday: 3, ai_confidence: 80, market_impact: "High", trend: "Uptrend",
    companies: 20, events: 13, news: 31,
    sectors: ["Auto","Manufacturing","Technology"],
    gradient: "from-teal-950 via-cyan-900 to-slate-900", icon: <Zap className="h-10 w-10 text-teal-400" />,
    sparkline: mkSpark(78), score_chart: mkScore(82),
    timeline: [
      { date: "Apr 2024", event: "PM e-Drive Scheme ₹10,900 Cr" },
      { date: "Aug 2024", event: "Battery Gigafactory Investments" },
      { date: "Dec 2024", event: "Charging Network Expansion" },
      { date: "Feb 2025", event: "EV Import Duty Reduced" },
      { date: "May 2025", event: "Two-Wheeler EV Penetration 8%" },
    ],
    beneficiaries: [
      { name: "Tata Motors",  symbol: "TATAMOTORS", exposure: "Very High", score: 89, change: "+9.6%",  positive: true },
      { name: "Ola Electric",  symbol: "OLAELEC",   exposure: "Very High", score: 85, change: "+13.2%", positive: true },
      { name: "Exide Industries",symbol:"EXIDEIND",  exposure: "High",      score: 80, change: "+7.1%",  positive: true },
      { name: "Amara Raja",   symbol: "AMARAJABAT", exposure: "High",      score: 77, change: "+6.4%",  positive: true },
      { name: "Motherson Sumi",symbol:"MOTHERSON",   exposure: "Medium",    score: 73, change: "+4.8%",  positive: true },
    ],
    key_drivers: ["PM e-Drive scheme","Battery localisation","Charging infrastructure","Two-wheeler EV surge","Global OEM partnerships"],
    related: ["Battery Storage","Auto Ancillaries","Charging Infrastructure","Clean Mobility"],
    ai_insight: "EV adoption is inflecting with policy support and falling battery costs. Battery supply chain and charging infrastructure are the next high-conviction plays.",
  },
  {
    id: 6, title: "Semiconductor Mission", slug: "semiconductor-mission",
    badge: "Medium", description: "Government incentives, new fabs, OSAT units and component manufacturing.",
    opportunity_score: 76, vs_yesterday: 2, ai_confidence: 76, market_impact: "Medium", trend: "Uptrend",
    companies: 11, events: 6, news: 15,
    sectors: ["Technology","Electronics","Manufacturing"],
    gradient: "from-purple-950 via-violet-900 to-slate-900", icon: <FlaskConical className="h-10 w-10 text-violet-400" />,
    sparkline: mkSpark(72), score_chart: mkScore(76),
    timeline: [
      { date: "Jun 2023", event: "India Semiconductor Mission Launched" },
      { date: "Feb 2024", event: "Micron Fab Approved ₹22,500 Cr" },
      { date: "Aug 2024", event: "OSAT Units Greenlit" },
      { date: "Jan 2025", event: "Tata Semiconductor Plant Begins" },
      { date: "Apr 2025", event: "Design-Linked Incentive Expanded" },
    ],
    beneficiaries: [
      { name: "Dixon Technologies",symbol:"DIXON",      exposure: "Very High", score: 87, change: "+14.7%", positive: true },
      { name: "Kaynes Technology",  symbol:"KAYNES",     exposure: "High",      score: 82, change: "+10.3%", positive: true },
      { name: "Tata Elxsi",         symbol:"TATAELXSI",  exposure: "High",      score: 78, change: "+7.9%",  positive: true },
      { name: "Syrma SGS",          symbol:"SYRMA",      exposure: "Medium",    score: 74, change: "+6.5%",  positive: true },
      { name: "Redington",          symbol:"REDINGTON",  exposure: "Medium",    score: 70, change: "+4.2%",  positive: true },
    ],
    key_drivers: ["India Semiconductor Mission","Production-linked incentives","Global chip diversification","Design talent base","OSAT unit pipeline"],
    related: ["Electronics Manufacturing","PCB","Chip Design","Tech Hardware"],
    ai_insight: "India's semiconductor ambitions are early-stage but gaining credibility with Micron and Tata commitments. Focus on OSAT and design-linked companies for near-term plays.",
  },
];

/* ── Constants ───────────────────────────────────────────── */
const BADGE_COLOR: Record<string, string> = {
  Hot:    "bg-rose-500/15 text-rose-300 border border-rose-500/30",
  High:   "bg-amber-500/15 text-amber-300 border border-amber-500/30",
  Medium: "bg-sky-500/15  text-sky-300  border border-sky-500/30",
};
const EXPOSURE_COLOR: Record<string, string> = {
  "Very High": "text-emerald-400",
  High:        "text-sky-400",
  Medium:      "text-amber-400",
  Low:         "text-slate-400",
};
const IMPACT_COLOR: Record<string, string> = {
  "Very High": "text-emerald-400",
  High:        "text-sky-400",
  Medium:      "text-amber-400",
};
const TABS = ["Overview","Companies","Events","News","Analysis","Historical","Risks"] as const;
type Tab = typeof TABS[number];

/* ── Sub-components ──────────────────────────────────────── */
function Sparkline({ data, color }: { data: { label: string; value: number }[]; color: string }) {
  return (
    <div className="h-8 w-20">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 1, right: 0, bottom: 1, left: 0 }}>
          <defs>
            <linearGradient id={`sg-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5}
            fill={`url(#sg-${color})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ScoreChart({ data }: { data: ChartPt[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -20 }}>
        <XAxis dataKey="label" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 100]} tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: "#0f1117", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontSize: 11 }}
          labelStyle={{ color: "#94a3b8" }}
          itemStyle={{ color: "#a78bfa" }}
        />
        <Line type="monotone" dataKey="value" stroke="#818cf8" strokeWidth={2}
          dot={false} activeDot={{ r: 4, fill: "#818cf8" }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ── Left panel: Theme card ──────────────────────────────── */
function ThemeCard({ t, selected, onClick }: { t: Theme; selected: boolean; onClick: () => void }) {
  const sparkColor = t.badge === "Hot" ? "#f87171" : t.badge === "High" ? "#fbbf24" : "#38bdf8";
  return (
    <button onClick={onClick} className={`w-full text-left rounded-[20px] border p-4 transition ${
      selected
        ? "border-indigo-500/40 bg-indigo-500/[0.07] ring-1 ring-indigo-500/20"
        : "border-white/8 bg-white/[0.025] hover:border-white/15 hover:bg-white/[0.04]"
    }`}>
      <div className="flex gap-3">
        {/* Thumbnail */}
        <div className={`relative h-20 w-24 shrink-0 overflow-hidden rounded-[14px] bg-gradient-to-br ${t.gradient} flex items-center justify-center text-white/80`}>
          {t.icon}
        </div>

        {/* Info */}
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

      {/* Score row */}
      <div className="mt-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] text-slate-500">Opportunity Score</p>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-white">{t.opportunity_score}</span>
            <span className="text-[10px] text-emerald-400">+{t.vs_yesterday} (vs yesterday)</span>
          </div>
          {/* AI Confidence bar */}
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1 w-20 overflow-hidden rounded-full bg-white/5">
              <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
                style={{ width: `${t.ai_confidence}%` }} />
            </div>
            <span className="text-[10px] text-slate-500">AI {t.ai_confidence}%</span>
          </div>
          <p className={`mt-1 text-[10px] font-medium ${IMPACT_COLOR[t.market_impact] ?? "text-slate-400"}`}>
            Impact: {t.market_impact}
          </p>
        </div>
        <Sparkline data={t.sparkline} color={sparkColor} />
      </div>
    </button>
  );
}

/* ── Right panel: Detail ─────────────────────────────────── */
function ThemeDetail({ t, onBack }: { t: Theme; onBack: () => void }) {
  const [tab, setTab] = useState<Tab>("Overview");

  return (
    <div className="flex flex-col gap-0 rounded-[24px] border border-white/10 bg-[#080910]/80 overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-3 border-b border-white/8 px-5 py-3">
        <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          Back to Themes
        </button>
        <div className="flex items-center gap-2">
          <select className="rounded-[10px] border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] text-slate-300 outline-none">
            <option>Today</option>
            <option>1W</option>
            <option>1M</option>
          </select>
          <button className="flex h-7 w-7 items-center justify-center rounded-[10px] border border-white/10 bg-white/5 text-slate-400 hover:text-white transition">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
          </button>
        </div>
      </div>

      {/* Hero image */}
      <div className={`relative h-36 w-full bg-gradient-to-br ${t.gradient} flex items-center justify-center overflow-hidden`}>
        <span className="opacity-30 text-white [&_svg]:h-20 [&_svg]:w-20">{t.icon}</span>
        <div className="absolute inset-0 bg-gradient-to-t from-[#080910]/80 via-transparent to-transparent" />
      </div>

      {/* Title block */}
      <div className="flex items-start justify-between gap-3 px-5 pt-4 pb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${BADGE_COLOR[t.badge]}`}>
              {t.badge === "Hot" ? <><Flame className="inline h-3 w-3 mr-0.5" />Hot Theme</> : `${t.badge} Theme`}
            </span>
          </div>
          <h2 className="text-xl font-bold text-white leading-tight">{t.title}</h2>
          <p className="mt-1.5 text-[12px] leading-5 text-slate-400 max-w-sm">{t.description}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button className="flex items-center gap-1.5 rounded-[12px] border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/10 transition">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5"><path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13"/></svg>
            Share
          </button>
          <button className="flex items-center gap-1.5 rounded-[12px] border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/10 transition">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5"><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
            Watch
          </button>
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-4 gap-px border-t border-b border-white/8 bg-white/5 mx-5 rounded-[14px] overflow-hidden mb-3">
        {[
          { label: "Opportunity Score", value: `${t.opportunity_score}/100`, color: "text-violet-300", up: true },
          { label: "AI Confidence",     value: `${t.ai_confidence}%`,       color: "text-sky-300",    up: true },
          { label: "Market Impact",     value: t.market_impact,             color: IMPACT_COLOR[t.market_impact] ?? "text-slate-300", up: true },
          { label: "Trend",             value: t.trend,                     color: "text-emerald-400", up: true },
        ].map(m => (
          <div key={m.label} className="flex flex-col items-center py-3 px-2 bg-[#080910]/80">
            <p className="text-[10px] text-slate-500 mb-1">{m.label}</p>
            <div className="flex items-center gap-1">
              <span className={`text-sm font-bold ${m.color}`}>{m.value}</span>
              {m.up && <svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3 text-emerald-400"><path d="M7 14l5-5 5 5H7z"/></svg>}
            </div>
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
            <Link href={`/radar`} className="mt-2 text-xs text-indigo-400 hover:text-indigo-300 transition">
              Explore on Opportunity Radar →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

function OverviewTab({ t }: { t: Theme }) {
  return (
    <div className="space-y-5 p-5">
      {/* Timeline + Chart */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Timeline */}
        <div>
          <p className="mb-3 text-[10px] font-bold tracking-[0.18em] uppercase text-slate-500">Theme Timeline</p>
          <div className="space-y-0">
            {t.timeline.map((m, i) => (
              <div key={i} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div className={`h-2.5 w-2.5 shrink-0 rounded-full border-2 mt-0.5 ${
                    i === t.timeline.length - 1
                      ? "border-indigo-500 bg-indigo-500/30"
                      : "border-slate-600 bg-slate-800"
                  }`} />
                  {i < t.timeline.length - 1 && <div className="w-px flex-1 bg-white/8 my-1" />}
                </div>
                <div className="pb-3">
                  <p className="text-[10px] text-slate-500">{m.date}</p>
                  <p className="text-xs text-slate-300">{m.event}</p>
                </div>
              </div>
            ))}
          </div>
          <button className="mt-1 text-[11px] text-indigo-400 hover:text-indigo-300 transition">
            View Full Timeline →
          </button>
        </div>

        {/* Score chart */}
        <div>
          <p className="mb-3 text-[10px] font-bold tracking-[0.18em] uppercase text-slate-500">Opportunity Score Over Time</p>
          <div className="h-44">
            <ScoreChart data={t.score_chart} />
          </div>
        </div>
      </div>

      {/* Beneficiary companies */}
      <div>
        <p className="mb-3 text-[10px] font-bold tracking-[0.18em] uppercase text-slate-500">Top Beneficiary Companies</p>
        <div className="rounded-[14px] border border-white/8 overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/8 bg-white/[0.02]">
                <th className="px-3 py-2 text-left text-[10px] font-semibold text-slate-500">Company</th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold text-slate-500">Theme Exposure</th>
                <th className="px-3 py-2 text-right text-[10px] font-semibold text-slate-500">AI Score</th>
                <th className="px-3 py-2 text-right text-[10px] font-semibold text-slate-500">1M Change</th>
              </tr>
            </thead>
            <tbody>
              {t.beneficiaries.map((b, i) => (
                <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02] transition">
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="h-5 w-5 rounded-full bg-gradient-to-br from-indigo-500/30 to-violet-500/20 flex items-center justify-center text-[9px] font-bold text-white shrink-0">
                        {b.name[0]}
                      </div>
                      <span className="text-slate-200 truncate">{b.name}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`text-[11px] font-medium ${EXPOSURE_COLOR[b.exposure]}`}>{b.exposure}</span>
                  </td>
                  <td className="px-3 py-2.5 text-right font-semibold text-white">{b.score}</td>
                  <td className={`px-3 py-2.5 text-right font-medium ${b.positive ? "text-emerald-400" : "text-rose-400"}`}>
                    {b.positive ? "▲" : "▼"} {b.change}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button className="w-full py-2.5 text-[11px] text-indigo-400 hover:text-indigo-300 hover:bg-white/[0.02] transition border-t border-white/8">
            View All {t.companies} Companies →
          </button>
        </div>
      </div>

      {/* Key drivers + Related themes */}
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="mb-3 text-[10px] font-bold tracking-[0.18em] uppercase text-slate-500">Key Drivers</p>
          <div className="space-y-2">
            {t.key_drivers.map((d, i) => (
              <div key={i} className="flex items-start gap-2">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-3.5 w-3.5 shrink-0 mt-0.5 text-emerald-400">
                  <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <p className="text-xs text-slate-300">{d}</p>
              </div>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-3 text-[10px] font-bold tracking-[0.18em] uppercase text-slate-500">Related Themes</p>
          <div className="flex flex-wrap gap-2">
            {t.related.map(r => (
              <span key={r} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300 hover:bg-white/10 cursor-pointer transition">
                {r}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* AI Insight */}
      <div className="rounded-[16px] border border-violet-500/20 bg-violet-500/[0.04] p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <span className="text-violet-400 mt-0.5 shrink-0"><svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg></span>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-violet-300 mb-1.5">AI Insight</p>
              <p className="text-xs leading-5 text-slate-300">{t.ai_insight}</p>
            </div>
          </div>
          <Link href={`/ai-search?q=${encodeURIComponent(t.title)}`}
            className="shrink-0 rounded-[12px] bg-gradient-to-r from-violet-600 to-sky-500 px-3 py-1.5 text-[11px] font-semibold text-white hover:opacity-90 transition whitespace-nowrap">
            View Detailed Analysis →
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ── Stats bar ───────────────────────────────────────────── */
function StatsBar({ themes }: { themes: Theme[] }) {
  const avgScore = Math.round(themes.reduce((a, t) => a + t.opportunity_score, 0) / themes.length);
  const totalEvents = themes.reduce((a, t) => a + t.events, 0);
  const avgConf = Math.round(themes.reduce((a, t) => a + t.ai_confidence, 0) / themes.length);

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
      {[
        { label: "Active Themes",       value: themes.length, sub: "+3 new today",        color: "text-white" },
        { label: "Avg. Opportunity Score", value: avgScore,   sub: "High ↑",             color: "text-emerald-400" },
        { label: "Total Events",        value: totalEvents,   sub: "+28 today",           color: "text-white" },
        { label: "AI Confidence",       value: `${avgConf}%`, sub: "Very High",           color: "text-violet-300" },
        { label: "Market Impact",       value: "High",        sub: "Broad Based",        color: "text-sky-300" },
      ].map(s => (
        <div key={s.label} className="rounded-[18px] border border-white/8 bg-white/[0.025] px-4 py-3">
          <p className="text-[10px] text-slate-500 mb-1">{s.label}</p>
          <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">{s.sub}</p>
        </div>
      ))}
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────── */
export default function ThemesPage() {
  const [themes, setThemes] = useState<Theme[]>(THEMES);
  const [selected, setSelected] = useState<Theme>(THEMES[0]);

  const { data: intelligence } = useIntelligence("theme", selected?.slug);

  useEffect(() => {
    fetch(`${API}/api/radar/`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.items?.length) {
          // Map backend items onto our rich fallback shapes (keep fallback fields for UI)
          const merged = THEMES.map((fb, i) => {
            const be = d.items[i];
            if (!be) return fb;
            return {
              ...fb,
              title: be.title ?? fb.title,
              description: be.summary ?? fb.description,
              opportunity_score: Math.round(be.opportunity_score ?? fb.opportunity_score),
              ai_confidence: Math.round((be.confidence ?? fb.ai_confidence / 100) * 100),
              sectors: be.sectors ?? fb.sectors,
            };
          });
          setThemes(merged);
          setSelected(merged[0]);
        }
      })
      .catch(() => {});
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
      <StatsBar themes={themes} />

      {/* Two-panel layout */}
      <div className="grid gap-4 xl:grid-cols-[1fr_440px]">
        {/* Left: theme list */}
        <div className="space-y-3">
          {themes.map(t => (
            <ThemeCard key={t.id} t={t} selected={selected.id === t.id} onClick={() => setSelected(t)} />
          ))}
          <button className="w-full rounded-[16px] border border-white/8 py-3 text-sm font-medium text-indigo-400 hover:bg-white/[0.02] hover:text-indigo-300 transition">
            View All Themes →
          </button>
        </div>

        {/* Right: detail */}
        <div className="hidden xl:block space-y-4">
          {intelligence && (
            <IntelligenceBlock data={intelligence} label={`${selected.title} Intelligence`} compact={false} />
          )}
          <ThemeDetail key={selected.id} t={selected} onBack={() => {}} />
        </div>
      </div>
    </main>
  );
}
