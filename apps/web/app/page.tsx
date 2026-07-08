import { Suspense, cache } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { Bot, Shield, Train, Leaf, FlaskConical, Zap, Flame, Sparkles, Waves } from "lucide-react";
import { AITransparencyPanel }  from "@/components/ai/AITransparencyPanel";
import { AIDisclaimer }         from "@/components/ai/AIDisclaimer";
import { InvestmentThesisCard } from "@/components/intelligence";
import { SmartHero }            from "@/components/dashboard/SmartHero";
import { TodaysMarketRipple }  from "@/components/dashboard/TodaysMarketRipple";
import { DashboardMarketTabs }  from "@/components/DashboardMarketTabs";
import { MarketOverviewSection } from "@/components/MarketOverviewSection";
import { SectorPerformanceCard } from "@/components/SectorPerformanceCard";
import { TopEventsSection }     from "@/components/TopEventsSection";
import { AIOpportunitySection } from "@/components/AIOpportunitySection";
import { TopMoversGrid }        from "@/components/TopMoversSection";
import { DashboardBottomRow }   from "@/components/DashboardBottomRow";
import { DashboardRightSidebar } from "@/components/DashboardRightSidebar";
import { FloatingAISearch }     from "@/components/FloatingAISearch";
import { EconomicCalendar }     from "@/components/EconomicCalendar";
import { LatestNews }           from "@/components/LatestNews";
import { calendarData, opportunityRadarData } from "@/app/lib/mock";
import {
  MarketSkeleton, AIWrapSkeleton,
  EventsOppSkeleton, MoversSkeleton, RightSidebarSkeleton, TickerSkeleton,
} from "@/components/ui/Skeletons";

export const dynamic = "force-dynamic";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Fetch helpers ─────────────────────────────────────────────────────────────
// fetchLive: real-time data — never cached (market prices, top movers, premarket)
// fetchStable: slow-changing data — ISR revalidated every N seconds
async function fetchLive<T = any>(url: string, ms = 7000): Promise<T | null> {
  const ac = new AbortController();
  const t  = setTimeout(() => ac.abort(), ms);
  try {
    const r = await fetch(url, { cache: "no-store", signal: ac.signal });
    clearTimeout(t);
    return r.ok ? r.json() : null;
  } catch {
    clearTimeout(t);
    return null;
  }
}

async function fetchStable<T = any>(url: string, revalidate = 60, ms = 7000): Promise<T | null> {
  const ac = new AbortController();
  const t  = setTimeout(() => ac.abort(), ms);
  try {
    const r = await fetch(url, { next: { revalidate }, signal: ac.signal });
    clearTimeout(t);
    return r.ok ? r.json() : null;
  } catch {
    clearTimeout(t);
    return null;
  }
}

// cache() deduplicates identical calls within one render pass
const getDashboard = cache(() => fetchLive(`${API}/api/dashboard/`));
const getCalendar  = cache(() => fetchStable(`${API}/api/calendar/`,  3600)); // calendar entries change rarely
const getNews      = cache(() => fetchLive<any[]>(`${API}/api/news/`));
const getSectors   = cache(() => fetchStable<any[]>(`${API}/api/sectors/`, 60));
const getPremarket = cache(() => fetchLive(`${API}/api/market/premarket`));
const getRadar     = cache(() => fetchStable(`${API}/api/radar/?page=1&page_size=8`, 120));
const getIndices   = cache(() => fetchLive<any[]>(`${API}/api/indices/`, 5000));

// ── Fallbacks ─────────────────────────────────────────────────────────────────
const FB_GAINERS = [
  { company: "Bharat Electronics",  ticker: "BEL",      value: "+6.32%", subtitle: "₹282.75",   positive: true },
  { company: "Rail Vikas Nigam",    ticker: "RVNL",     value: "+5.21%", subtitle: "₹475.80",   positive: true },
  { company: "Larsen & Toubro",     ticker: "LT",       value: "+4.18%", subtitle: "₹3,512.20", positive: true },
  { company: "NTPC Ltd",            ticker: "NTPC",     value: "+3.56%", subtitle: "₹345.60",   positive: true },
];
const FB_LOSERS = [
  { company: "Tech Mahindra",    ticker: "TECHM",   value: "-2.35%", subtitle: "₹1,342.80", positive: false },
  { company: "Wipro Limited",    ticker: "WIPRO",   value: "-2.01%", subtitle: "₹465.75",   positive: false },
  { company: "Tata Consultancy", ticker: "TCS",     value: "-1.78%", subtitle: "₹3,721.90", positive: false },
  { company: "HCL Technologies", ticker: "HCLTECH", value: "-1.32%", subtitle: "₹1,294.50", positive: false },
];
const FB_ACTIVE = [
  { company: "Reliance Industries", ticker: "RELIANCE",  value: "₹8,932 Cr", subtitle: "Volume", positive: true },
  { company: "HDFC Bank",           ticker: "HDFCBANK",  value: "₹6,812 Cr", subtitle: "Volume", positive: true },
  { company: "Tata Steel",          ticker: "TATASTEEL", value: "₹5,421 Cr", subtitle: "Volume", positive: true },
  { company: "Infosys Limited",     ticker: "INFY",      value: "₹4,876 Cr", subtitle: "Volume", positive: true },
];
const FB_INDICES = [
  { title: "NIFTY 50",   value: "24,565.35", change: "+0.62% (+150.85)", positive: true,  high: "24,612.00", low: "24,380.10" },
  { title: "SENSEX",     value: "80,796.15", change: "+0.61% (+490.05)", positive: true,  high: "80,901.20", low: "80,235.45" },
  { title: "NIFTY BANK", value: "54,125.25", change: "+0.78% (+420.35)", positive: true,  high: "54,290.10", low: "53,840.25" },
  { title: "NIFTY IT",   value: "37,145.80", change: "+0.34% (+125.60)", positive: true,  high: "37,280.00", low: "36,920.40" },
];
const FB_SECTORS = [
  { id: "infra",  name: "Nifty Infrastructure", value: "+1.48", positive: true  },
  { id: "bank",   name: "Nifty Bank",            value: "+1.32", positive: true  },
  { id: "auto",   name: "Nifty Auto",            value: "+0.85", positive: true  },
  { id: "it",     name: "Nifty IT",              value: "+0.62", positive: true  },
  { id: "fmcg",   name: "Nifty FMCG",           value: "+0.21", positive: true  },
  { id: "pharma", name: "Nifty Pharma",          value: "-0.12", positive: false },
  { id: "metal",  name: "Nifty Metal",           value: "-0.34", positive: false },
  { id: "realty", name: "Nifty Realty",          value: "+0.55", positive: true  },
];
const FB_GLOBAL_INDICES = [
  { name: "Dow Jones",  value: "41,860.44", change: "+0.32%", positive: true  },
  { name: "S&P 500",   value: "5,842.01",  change: "+0.41%", positive: true  },
  { name: "Nasdaq",    value: "18,872.64", change: "+0.67%", positive: true  },
  { name: "FTSE 100",  value: "8,402.57",  change: "+0.28%", positive: true  },
  { name: "Nikkei 225",value: "38,529.48", change: "+0.20%", positive: true  },
  { name: "Hang Seng", value: "19,544.31", change: "+0.91%", positive: true  },
];
const FB_GLOBAL_COMM = [
  { name: "Crude Oil",   value: "$78.63", change: "-0.24%", positive: false },
  { name: "Gold",        value: "$2,340", change: "+0.18%", positive: true  },
  { name: "Silver",      value: "$27.45", change: "+0.35%", positive: true  },
  { name: "Natural Gas", value: "$2.12",  change: "-1.20%", positive: false },
];
const FB_GLOBAL_CURR = [
  { name: "USD/INR", value: "83.42",  change: "+0.04%", positive: false },
  { name: "EUR/INR", value: "90.18",  change: "-0.12%", positive: false },
  { name: "GBP/INR", value: "106.32", change: "+0.08%", positive: true  },
  { name: "JPY/INR", value: "0.554",  change: "-0.22%", positive: false },
];
const FALLBACK_HERO_STATS = {
  sentimentScore: 72, sentimentLabel: "Bullish" as const, sentimentChange: "8 pts",
  eventsToday: 48, eventsTodayVs: "14",
  highImpactEvents: 12, highImpactVs: "3",
  opportunityScore: 82, opportunityVs: "6 pts",
  aiConfidence: 92, aiConfidenceLabel: "High", aiConfidenceVs: "4%",
};

// ── Top Themes preview data ────────────────────────────────────────────────────
const TOP_THEMES_PREVIEW: { title: string; badge: string; score: number; sectors: string; gradient: string; icon: ReactNode }[] = [
  { title: "AI Infrastructure Boom",     badge: "Hot",    score: 94, sectors: "Technology · Power",         gradient: "from-blue-950 via-indigo-900 to-slate-900",    icon: <Bot className="h-9 w-9" /> },
  { title: "Defence Manufacturing Push", badge: "Hot",    score: 92, sectors: "Defence · Aerospace",        gradient: "from-stone-900 via-amber-950 to-slate-900",    icon: <Shield className="h-9 w-9" /> },
  { title: "Railway Modernization",      badge: "High",   score: 88, sectors: "Infrastructure · Logistics", gradient: "from-slate-800 via-blue-900 to-slate-900",     icon: <Train className="h-9 w-9" /> },
  { title: "Renewable Energy",           badge: "High",   score: 86, sectors: "Energy · Utilities",         gradient: "from-emerald-950 via-green-900 to-slate-900",  icon: <Leaf className="h-9 w-9" /> },
  { title: "Semiconductor Mission",      badge: "Medium", score: 76, sectors: "Technology · Electronics",   gradient: "from-purple-950 via-violet-900 to-slate-900",  icon: <FlaskConical className="h-9 w-9" /> },
  { title: "Electric Vehicles",          badge: "High",   score: 82, sectors: "Auto · Manufacturing",       gradient: "from-teal-950 via-cyan-900 to-slate-900",      icon: <Zap className="h-9 w-9" /> },
];

// ── Pure time helpers (no async) ───────────────────────────────────────────────
function getTimeData() {
  const nowUtc  = new Date();
  const istMs   = nowUtc.getTime() + (5 * 60 + 30) * 60_000;
  const ist     = new Date(istMs);
  const hour    = ist.getUTCHours();
  const istMins = hour * 60 + ist.getUTCMinutes();
  const dow     = ist.getUTCDay();
  const isWeekday    = dow >= 1 && dow <= 5;
  const isMarketTime = istMins >= 9 * 60 + 15 && istMins < 15 * 60 + 30;
  return {
    timeIST:      ist.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" }),
    heroDate:     ist.toLocaleDateString("en-IN",  { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }),
    marketStatus: (isWeekday && isMarketTime ? "Market Open" : "Market Closed") as "Market Open" | "Market Closed",
    greeting:     hour < 12 ? "Good Morning" : hour < 17 ? "Good Afternoon" : "Good Evening",
  };
}

// ── Async streaming sections ───────────────────────────────────────────────────

async function MarketBelowHero() {
  const [extIndices, sectorRows] = await Promise.all([getIndices(), getSectors()]);
  const rawIndices = extIndices?.length ? extIndices : [];
  const indexCards = rawIndices.length
    ? rawIndices.map((q: any) => ({
        title: q.title ?? q.name, value: q.value, change: q.change, positive: q.positive,
        high: q.high ?? q.value, low: q.low ?? q.value,
      }))
    : FB_INDICES;
  const sectors: any[] = sectorRows?.length ? sectorRows : FB_SECTORS;
  return (
    <div className="grid grid-cols-[1fr_280px] gap-5 items-start">
      <MarketOverviewSection indices={indexCards} />
      <SectorPerformanceCard sectors={sectors} />
    </div>
  );
}

async function DashboardMainContent() {
  const [dashboard, radarData] = await Promise.all([getDashboard(), getRadar()]);

  const aiSummary: string = dashboard?.aiSummary
    ?? "Indian markets likely to open higher tracking positive Asian cues and strong FII inflows. Infrastructure and banking sectors may see early strength.";

  const trending: any[] = (dashboard?.trending_events ?? []).map((e: any, i: number) => ({
    id:        String(e.id),
    score:     Math.round(e.impact_score ?? 0),
    title:     e.title,
    tags:      [e.category ?? "Macro", ...(e.sectors ?? []).slice(0, 1)],
    companies: (e.companies ?? []).map((c: any) => {
      const s = typeof c === "string" ? c : (c?.symbol ?? c?.name ?? "");
      return s.slice(0, 4).toUpperCase();
    }).filter(Boolean),
    sector: (e.sectors ?? ["Market"])[0] ?? "Market",
    time:   e.published_at ? (e.published_at.match(/T(\d{2}:\d{2})/) ?? [])[1] ?? "" : `${8 + i}:30`,
    trend:  ((e.impact_score ?? 50) >= 70 ? "up" : "stable") as "up" | "stable",
  }));

  const radarItems: any[] = ((radarData?.items ?? []) as any[]).slice(0, 6).map((r: any) => ({
    id:       String(r.slug ?? r.id),
    score:    Math.round(r.opportunity_score ?? 0),
    theme:    r.title ?? "Opportunity",
    reason:   r.summary ?? "",
    category: (r.sectors ?? [])[0] ?? r.risk_level ?? "General",
    trend:    ((r.opportunity_score ?? 50) >= 70 ? "up" : "stable") as "up" | "stable",
  }));

  const fallbackRadar = opportunityRadarData.map((r: any) => ({ ...r, trend: "up" as const }));

  const gainers = dashboard?.top_movers?.gainers?.length ? dashboard.top_movers.gainers : FB_GAINERS;
  const losers  = dashboard?.top_movers?.losers?.length  ? dashboard.top_movers.losers  : FB_LOSERS;
  const active  = dashboard?.top_movers?.active?.length  ? dashboard.top_movers.active  : FB_ACTIVE;

  return (
    <>
      {/* AI Market Wrap */}
      <div className="relative overflow-hidden rounded-[28px] border border-sky-500/15 bg-gradient-to-br from-sky-500/[0.06] via-transparent to-violet-500/[0.04] p-5">
        <div className="pointer-events-none absolute -top-10 left-20 h-40 w-40 rounded-full bg-sky-600/10 blur-3xl"/>
        <div className="pointer-events-none absolute bottom-0 right-10 h-32 w-32 rounded-full bg-violet-600/8 blur-3xl"/>
        <div className="relative flex items-start gap-6">
          <div className="flex-1 min-w-0">
            <div className="mb-3 flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-sky-500/20 text-sky-400"><Sparkles className="h-4 w-4" /></span>
              <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sky-400">AI Market Wrap</span>
            </div>
            <h3 className="text-[16px] font-bold text-white mb-2 leading-snug">
              Markets tracking positive global cues with FII inflows supporting domestic rally
            </h3>
            <p className="text-[13px] leading-6 text-slate-400 line-clamp-2">{aiSummary}</p>
          </div>
          <div className="grid grid-cols-3 gap-3 shrink-0">
            {[
              { label: "Positive Factors", items: ["Strong FII flows", "Stable crude oil", "Robust corporate earnings"], color: "emerald" },
              { label: "Negative Factors", items: ["Global rate uncertainty", "INR weakness", "Mixed global cues"],       color: "rose"    },
              { label: "Watch Today",      items: ["RBI rate decision", "Q4 results season", "FOMC minutes"],            color: "amber"   },
            ].map(f => (
              <div key={f.label} className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 min-w-[140px]">
                <p className={`mb-2 text-[9px] font-bold uppercase tracking-wider ${f.color === "emerald" ? "text-emerald-400" : f.color === "rose" ? "text-rose-400" : "text-amber-400"}`}>{f.label}</p>
                <ul className="space-y-1">
                  {f.items.map(it => (
                    <li key={it} className="flex items-start gap-1 text-[10px] text-slate-400">
                      <span className={`mt-0.5 shrink-0 ${f.color === "emerald" ? "text-emerald-400" : f.color === "rose" ? "text-rose-400" : "text-amber-400"}`}>•</span>
                      {it}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <AITransparencyPanel
          confidence={75}
          reasoning="AI-generated market wrap based on top events, market movers, and sector data from today's session."
        />
        <AIDisclaimer />
        <InvestmentThesisCard
          thesis={aiSummary}
          whyItMatters="India's structural bull phase is supported by strong domestic institutional flows, government capital expenditure at multi-decade highs, and corporate earnings outperforming expectations."
          keyDrivers={[
            "Robust FII and DII institutional inflows",
            "Government infrastructure capex cycle",
            "Corporate earnings growth above historical averages",
            "Resilient domestic consumption story",
          ]}
          riskFactors={[
            "Global rate tightening pressure on emerging market valuations",
            "INR vulnerability to external commodity shocks",
            "Mid/small-cap segment elevated valuations",
          ]}
          confidence={72}
          timeHorizon="Medium-term (6–18 months)"
        />
        <Link href="/ai-wrap" className="mt-4 flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-[12px] font-medium text-white hover:bg-white/[0.08] transition">
          Read Full Analysis →
        </Link>
      </div>

      {/* Top Events + Opportunity Radar */}
      <div className="grid grid-cols-[1fr_280px] gap-5 items-start">
        <TopEventsSection events={trending} />
        <AIOpportunitySection items={radarItems.length ? radarItems : fallbackRadar} />
      </div>

      {/* Top Movers */}
      <TopMoversGrid gainers={gainers} losers={losers} active={active} />
    </>
  );
}

function HowItWorksSection() {
  const steps = [
    {
      num: "01", title: "Event Happens",
      desc: "RBI decisions, earnings, policy changes — we track every market-moving event in real time.",
      border: "border-sky-500/20", glow: "from-sky-500/10 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5 text-sky-400">
          <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
        </svg>
      ),
    },
    {
      num: "02", title: "AI Analyzes Impact",
      desc: "Our AI explains what happened, why it matters, and how markets are likely to react.",
      border: "border-violet-500/20", glow: "from-violet-500/10 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5 text-violet-400">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
        </svg>
      ),
    },
    {
      num: "03", title: "Companies Identified",
      desc: "We pinpoint exactly which companies gain or lose — scored by confidence and impact level.",
      border: "border-emerald-500/20", glow: "from-emerald-500/10 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5 text-emerald-400">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
      ),
    },
    {
      num: "04", title: "Opportunities Scored",
      desc: "The Opportunity Radar ranks the best investments that emerge from each market event.",
      border: "border-amber-500/20", glow: "from-amber-500/10 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5 text-amber-400">
          <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
        </svg>
      ),
    },
    {
      num: "05", title: "Better Decisions",
      desc: "Ask Market AI any question — get reasoned answers with full AI transparency, not guesswork.",
      border: "border-teal-500/20", glow: "from-teal-500/10 to-transparent",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5 text-teal-400">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
      ),
    },
  ];

  return (
    <div className="py-1">
      <div className="mb-4 flex items-end justify-between">
        <div>
          <h2 className="text-[15px] font-bold text-white">How MarketRipple Works</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">From market event to investment decision — in 5 steps</p>
        </div>
        <Link href="/ai-search" className="text-[11px] font-medium text-sky-400 hover:text-sky-300 transition">
          Try it now →
        </Link>
      </div>
      <div className="grid grid-cols-5 gap-3">
        {steps.map((step, i) => (
          <div key={i} className="relative flex flex-col">
            {/* Arrow connector */}
            {i < steps.length - 1 && (
              <div className="pointer-events-none absolute -right-2 top-[22px] z-10 text-slate-700">›</div>
            )}
            <div className={`flex-1 rounded-[18px] border ${step.border} bg-gradient-to-br ${step.glow} p-4`}>
              <div className="mb-3 flex items-center justify-between">
                <span className="text-[10px] font-black tracking-widest text-slate-600">{step.num}</span>
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/[0.05]">
                  {step.icon}
                </div>
              </div>
              <p className="text-[12px] font-bold text-white mb-1.5">{step.title}</p>
              <p className="text-[10px] leading-[1.55] text-slate-500">{step.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopThemesSection() {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-[16px] font-bold text-white">Top Investment Themes</h2>
          <p className="text-[11px] text-slate-500">AI-scored long-term market narratives</p>
        </div>
        <Link href="/stories" className="text-[11px] font-medium text-sky-400 hover:text-sky-300 transition">
          View All Themes →
        </Link>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {TOP_THEMES_PREVIEW.map(t => (
          <Link key={t.title} href="/stories"
            className="group relative overflow-hidden rounded-[20px] border border-white/10 bg-white/[0.025] hover:border-white/20 transition">
            <div className={`relative h-20 bg-gradient-to-br ${t.gradient} flex items-center justify-between px-4 overflow-hidden`}>
              <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent"/>
              <div className="relative">
                <span className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-bold ${t.badge === "Hot" ? "bg-rose-500/20 text-rose-300" : t.badge === "High" ? "bg-amber-500/20 text-amber-300" : "bg-sky-500/20 text-sky-300"}`}>
                  {t.badge === "Hot" && <Flame className="h-2.5 w-2.5" />}{t.badge}
                </span>
              </div>
              <div className="relative flex items-center gap-1 text-white/80">
                {t.icon}
              </div>
            </div>
            <div className="p-3">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-[12px] font-semibold text-white leading-snug group-hover:text-sky-200 transition">{t.title}</h3>
                <div className="shrink-0 text-right">
                  <div className="text-lg font-black text-white">{t.score}</div>
                  <div className="text-[8px] text-slate-500">score</div>
                </div>
              </div>
              <p className="mt-1 text-[10px] text-slate-500">{t.sectors}</p>
              <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-white/5">
                <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all" style={{ width: `${t.score}%` }}/>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

async function RipplePreviewSection() {
  const data = await fetchStable(`${API}/api/ripple/?page=1&page_size=6`, 120);
  const items: any[] = data?.items ?? data ?? [];

  const STATIC_RIPPLE = [
    { id: "rbi-rate-ripple", title: "RBI Rate Decision Impact", summary: "Cascading effects across banking, NBFC, and real estate sectors.", impact_score: 9.2, affected_sectors: ["Banking","NBFC","Realty"] },
    { id: "oil-price-ripple", title: "Crude Oil Price Surge", summary: "Rising crude impacts paint, chemicals, aviation and auto margins.", impact_score: 8.7, affected_sectors: ["Energy","Chemicals","Aviation"] },
    { id: "dollar-strengthening", title: "USD Strengthening Ripple", summary: "Strong dollar pressure on IT export margins and import costs.", impact_score: 8.4, affected_sectors: ["IT","Pharma","Textiles"] },
  ];

  const rippleItems = items.length > 0 ? items.slice(0, 3) : STATIC_RIPPLE;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-[16px] font-bold text-white">Ripple Intelligence</h2>
          <p className="text-[11px] text-slate-500">AI-mapped cross-sector dependency chains</p>
        </div>
        <Link href="/ripple" className="text-[11px] font-medium text-sky-400 hover:text-sky-300 transition">
          View All →
        </Link>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {rippleItems.map((r: any, i: number) => {
          const score = typeof r.impact_score === "number" ? (r.impact_score <= 10 ? r.impact_score * 10 : r.impact_score) : 80;
          const sectors: string[] = r.affected_sectors ?? r.sectors ?? [];
          return (
            <Link key={r.id ?? i} href={`/ripple/${r.id ?? i}`}
              className="group rounded-[20px] border border-white/10 bg-white/[0.025] p-4 hover:border-indigo-500/30 hover:bg-indigo-500/[0.03] transition">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400"><Waves className="h-4 w-4" /></div>
                <div className="text-right">
                  <div className="text-lg font-black text-white">{Math.round(score)}</div>
                  <div className="text-[8px] text-indigo-400">impact</div>
                </div>
              </div>
              <h3 className="text-[12px] font-semibold text-white leading-snug group-hover:text-indigo-200 transition line-clamp-2">
                {r.title ?? r.name}
              </h3>
              <p className="mt-1.5 text-[10px] leading-4 text-slate-500 line-clamp-2">{r.summary ?? ""}</p>
              {sectors.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {sectors.slice(0, 3).map((s: string) => (
                    <span key={s} className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-1.5 py-0.5 text-[9px] text-indigo-300">{s}</span>
                  ))}
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

async function RightSidebarSection() {
  const [dashboard, premarketData, calendarRows, newsRows] = await Promise.all([
    getDashboard(), getPremarket(), getCalendar(), getNews(),
  ]);

  const mapQ = (q: any) => ({ name: q.name, value: q.value, change: q.change_str ?? q.pct, positive: q.positive });
  const globalIndices: any[]     = (premarketData?.us ?? []).map(mapQ);
  const globalCommodities: any[] = (premarketData?.commodities ?? []).map(mapQ);
  const globalAsian: any[]       = (premarketData?.asian ?? []).map(mapQ);
  const globalCurrencies: any[]  = (premarketData?.currencies ?? []).map(mapQ);
  const allGlobalIndices = [...globalIndices, ...globalAsian].filter(
    (r, i, arr) => arr.findIndex((x: any) => x.name === r.name) === i
  );

  const gainers = dashboard?.top_movers?.gainers?.length ? dashboard.top_movers.gainers : FB_GAINERS;
  const losers  = dashboard?.top_movers?.losers?.length  ? dashboard.top_movers.losers  : FB_LOSERS;
  const active  = dashboard?.top_movers?.active?.length  ? dashboard.top_movers.active  : FB_ACTIVE;
  const aiSummary = dashboard?.aiSummary ?? "Indian markets likely to open higher tracking positive Asian cues.";

  const calEvents = calendarRows ?? calendarData;
  const newsItems = newsRows
    ? (newsRows as any[]).map((n: any) => ({
        id: n.id, headline: n.headline, source: n.source,
        published_at: n.published_at, score: Math.round(n.impact_score ?? 0),
      }))
    : [];

  return (
    <aside className="hidden xl:flex xl:flex-col gap-4 min-w-0 sticky top-[88px] self-start max-h-[calc(100vh-100px)] overflow-y-auto scrollbar-hide pb-16">
      <DashboardRightSidebar
        gainers={gainers} losers={losers} active={active}
        globalIndices={allGlobalIndices.length ? allGlobalIndices : FB_GLOBAL_INDICES}
        globalCommodities={globalCommodities.length ? globalCommodities : FB_GLOBAL_COMM}
        globalCurrencies={globalCurrencies.length ? globalCurrencies : FB_GLOBAL_CURR}
        aiInsight={aiSummary}
      />
      <EconomicCalendar events={calEvents} />
      {newsItems.length > 0 && <LatestNews items={newsItems} />}
    </aside>
  );
}

async function TickerBarSection() {
  const [extIndices, dashboard] = await Promise.all([getIndices(), getDashboard()]);
  const rawIndices = extIndices?.length ? extIndices : dashboard?.index_quotes ?? [];
  const tickerIndices = rawIndices.length
    ? rawIndices.map((q: any) => ({
        label:    q.title ?? q.name,
        value:    q.value,
        change:   q.change?.split(" ")[1]?.replace(/[()]/g, "") ?? q.change,
        positive: q.positive,
      }))
    : FB_INDICES.map(c => ({ label: c.title, value: c.value, change: c.change, positive: c.positive }));
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 glass-bar">
      <div className="mx-auto flex max-w-[1600px] items-center gap-8 overflow-x-auto px-6 py-2.5 scrollbar-hide">
        {tickerIndices.map((idx: any, i: number) => (
          <div key={`${idx.label ?? i}-${i}`} className="flex shrink-0 items-center gap-2.5">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-600">{idx.label}</span>
            <span className="num text-[12px] font-bold text-white">{idx.value}</span>
            <span className={`num text-[11px] font-semibold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.change}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Today's Market Ripple hero — streams in from dashboard + radar ────────────
async function TodaysMarketRippleSection() {
  const [dashboard, radarData] = await Promise.all([getDashboard(), getRadar()]);
  const { heroDate, marketStatus } = getTimeData();
  return (
    <TodaysMarketRipple
      aiSummary={
        dashboard?.aiSummary
          ?? "Indian markets navigating global macro cues with domestic fundamentals remaining robust. Institutional flows and sector rotation are the key themes driving today's session."
      }
      trendingEvents={dashboard?.trending_events ?? []}
      topMovers={dashboard?.top_movers ?? {}}
      radarItems={radarData?.items ?? []}
      heroDate={heroDate}
      marketStatus={marketStatus}
    />
  );
}

// ── Page shell (synchronous — renders immediately) ────────────────────────────
export default function HomePage() {
  const { timeIST, heroDate, marketStatus, greeting } = getTimeData();

  return (
    <>
      {/* ── MAIN CONTENT ───────────────────────────────────────────────────── */}
      <div className="min-w-0 space-y-5 pb-36">

        {/* Today's Market Ripple — streams in alongside dashboard + radar */}
        <Suspense fallback={
          <div className="h-[480px] animate-pulse rounded-[28px] border border-indigo-500/10 bg-indigo-500/[0.03]" />
        }>
          <TodaysMarketRippleSection />
        </Suspense>

        {/* Hero — SmartHero detects first vs returning visit via localStorage */}
        <SmartHero
          greeting={greeting}
          date={heroDate}
          status={marketStatus}
          timeIST={timeIST}
          stats={FALLBACK_HERO_STATS}
        />

        {/* How MarketRipple Works — shown to help first-time visitors understand the product */}
        <HowItWorksSection />

        {/* Market Session Tabs — client component, fetches own data */}
        <DashboardMarketTabs />

        {/* Market Overview + Sectors — streams in ~5s (indices timeout bound) */}
        <Suspense fallback={<MarketSkeleton />}>
          <MarketBelowHero />
        </Suspense>

        {/* AI Wrap + Top Events + Opportunities + Top Movers — streams in ~3-5s */}
        <Suspense fallback={
          <div className="space-y-5">
            <AIWrapSkeleton />
            <EventsOppSkeleton />
            <MoversSkeleton />
          </div>
        }>
          <DashboardMainContent />
        </Suspense>

        {/* Top Investment Themes — static, renders immediately */}
        <TopThemesSection />

        {/* Ripple Intelligence Preview — streams in ~2-4s */}
        <Suspense fallback={
          <div className="grid gap-3 sm:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-36 animate-pulse rounded-[20px] border border-white/10 bg-white/[0.02]"/>
            ))}
          </div>
        }>
          <RipplePreviewSection />
        </Suspense>

        {/* Bottom Row — no API, renders immediately */}
        <DashboardBottomRow />
      </div>

      {/* ── RIGHT SIDEBAR — streams in ~3-5s ──────────────────────────────── */}
      <Suspense fallback={<RightSidebarSkeleton />}>
        <RightSidebarSection />
      </Suspense>

      {/* ── TICKER BAR — streams in ~5s ───────────────────────────────────── */}
      <Suspense fallback={<TickerSkeleton />}>
        <TickerBarSection />
      </Suspense>

      {/* Floating AI Search */}
      <FloatingAISearch className="bottom-14" />
    </>
  );
}
