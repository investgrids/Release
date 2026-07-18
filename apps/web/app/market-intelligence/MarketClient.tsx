"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Sparkles, Zap, Target, BarChart2 } from "lucide-react";
import { CountdownTimer }            from "@/components/market/CountdownTimer";
import { MarketIntelligenceSidebar } from "@/components/market/MarketIntelligenceSidebar";
import { PreMarketTab }              from "@/components/market/tabs/PreMarketTab";
import { LiveMarketTab }             from "@/components/market/tabs/LiveMarketTab";
import { AfterMarketTab }            from "@/components/market/tabs/AfterMarketTab";
import { GlobalMarketsTab }          from "@/components/market/tabs/GlobalMarketsTab";
import { EconomicCalendarTab }       from "@/components/market/tabs/EconomicCalendarTab";
import { OverviewTab }               from "@/components/market/tabs/OverviewTab";
import { API_BASE_URL as API } from "@/lib/api";

type TabId = "overview" | "pre-market" | "live-market" | "after-market" | "global-markets" | "economic-calendar";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview",           label: "Overview"          },
  { id: "pre-market",         label: "Pre-Market"        },
  { id: "live-market",        label: "Live Market"       },
  { id: "after-market",       label: "After Market"      },
  { id: "global-markets",     label: "Global Markets"    },
  { id: "economic-calendar",  label: "Economic Calendar" },
];

const SESSION_COLORS: Record<string, string> = {
  pre_market:   "border-amber-500/20 bg-amber-500/10 text-amber-400",
  pre_open:     "border-amber-500/20 bg-amber-500/10 text-amber-400",
  open:         "border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
  after_market: "border-sky-500/20 bg-sky-500/10 text-sky-400",
  weekend:      "border-slate-500/20 bg-slate-500/10 text-slate-400",
  closed:       "border-rose-500/20 bg-rose-500/10 text-rose-400",
};
const SESSION_LABELS: Record<string, string> = {
  pre_market:   "Pre-Market", pre_open: "Pre-Open",
  open:         "Market Open", after_market: "After Market",
  weekend:      "Weekend",    closed: "Market Closed",
};
const COUNTDOWN_LABELS: Record<string, string> = {
  pre_market: "Market Opens In", pre_open: "Pre-Open Ends In",
  open:       "Market Closes In",
};

export function MarketClient({
  initialSession,
  initialOverview,
  initialEvents,
  initialNews,
  initialOpportunities,
  initialCalendar,
  initialInsights,
  initialMovers,
}: {
  initialSession:       any;
  initialOverview:      any;
  initialEvents:        any[];
  initialNews:          any[];
  initialOpportunities: any[];
  initialCalendar:      any[];
  initialInsights:      any;
  initialMovers:        any;
}) {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab") as TabId | null;
  const [activeTab, setActiveTab] = useState<TabId>(
    tabParam ?? (initialSession?.active_tab as TabId) ?? "overview"
  );
  const [session,  setSession]  = useState<any>(initialSession);
  const [overview, setOverview] = useState<any>(initialOverview);
  const [overviewLoading, setOverviewLoading] = useState(true);


  // Fetch overview client-side — it's slow (24 yfinance calls) so we don't block SSR with it
  useEffect(() => {
    fetch(`${API}/api/market/overview`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setOverview(d); })
      .catch(() => {})
      .finally(() => setOverviewLoading(false));
  }, []);

  // Re-sync session state every 60s (market status changes)
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const s = await fetch(`${API}/api/market/session`).then(r => r.ok ? r.json() : null);
        if (s) setSession(s);
      } catch {}
    }, 60_000);
    return () => clearInterval(id);
  }, []);

  const sess       = session?.session       ?? "closed";
  const countdown  = session?.countdown_seconds ?? null;
  const timeIST    = session?.time_ist ?? "";

  const sessColor  = SESSION_COLORS[sess]  ?? SESSION_COLORS.closed;
  const sessLabel  = SESSION_LABELS[sess]  ?? "—";
  const cntLabel   = COUNTDOWN_LABELS[sess] ?? "";

  return (
    <>
      {/* ── MAIN CONTENT ──────────────────────────────────────────────── */}
      <div className="min-w-0 space-y-5 pb-8">

        {/* Hero header card */}
        <div className="rounded-xl border border-white/[0.08] bg-[#080c14] px-5 py-4">

          <div className="flex items-start justify-between gap-4">
            {/* Left: title + greeting + summary */}
            <div className="flex-1 min-w-0">
              <div className="mb-2 flex items-center gap-2.5">
                <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${sessColor}`}>
                  ● {sessLabel}
                </span>
                <span className="text-[10px] text-slate-600">{session?.date} · {timeIST} IST</span>
              </div>
              <h1 className="text-[20px] font-black text-white leading-tight mb-1.5">
                Market Intelligence
                <span className="ml-2.5 text-[13px] text-slate-500 font-normal">Command Center</span>
              </h1>
              <p className="text-[12px] text-slate-400 leading-5 max-w-lg">
                Real-time market insights, AI analysis &amp; actionable intelligence across all sessions.
              </p>
              {/* Quick actions */}
              <div className="mt-3 flex gap-2 flex-wrap">
                {([
                  { icon: <Sparkles className="h-3.5 w-3.5" />, label: "Ask AI",            href: "#",                 color: "flex items-center gap-1.5 bg-gradient-to-r from-violet-600/80 to-sky-600/60 hover:from-violet-600 hover:to-sky-600 text-white" },
                  { icon: <Zap className="h-3.5 w-3.5" />,      label: "Explore Events",    href: "/events",           color: "flex items-center gap-1.5 border border-white/10 bg-white/[0.04] hover:bg-white/[0.07] text-slate-300" },
                  { icon: <Target className="h-3.5 w-3.5" />,   label: "Opportunity Radar", href: "/opportunity-radar",color: "flex items-center gap-1.5 border border-white/10 bg-white/[0.04] hover:bg-white/[0.07] text-slate-300" },
                  { icon: <BarChart2 className="h-3.5 w-3.5" />,label: "Market Wrap",       href: "#after-market",     color: "flex items-center gap-1.5 border border-white/10 bg-white/[0.04] hover:bg-white/[0.07] text-slate-300" },
                ] as { icon: ReactNode; label: string; href: string; color: string }[]).map(b => (
                  <Link key={b.label} href={b.href}
                    className={`rounded-xl px-4 py-2 text-[12px] font-semibold transition ${b.color}`}
                    onClick={b.href === "#after-market" ? (e) => { e.preventDefault(); setActiveTab("after-market"); } : undefined}>
                    {b.icon}{b.label}
                  </Link>
                ))}
              </div>
            </div>

            {/* Center: Countdown */}
            {countdown !== null && cntLabel && (
              <div className="shrink-0 flex flex-col items-center">
                <CountdownTimer
                  initialSeconds={countdown}
                  label={cntLabel}
                />
              </div>
            )}

            {/* Right: KPI mini cards */}
            <div className="shrink-0 grid grid-cols-2 gap-1.5">
              {[
                { label: "AI Confidence", value: initialInsights?.confidence != null ? `${initialInsights.confidence}%` : "—", color: "text-violet-400" },
                { label: "Fear & Greed",  value: String(initialInsights?.fear_greed ?? 72),   color: "text-amber-400"  },
                { label: "Events Today",  value: String(initialEvents?.length ?? 0),          color: "text-sky-400"    },
                { label: "Opportunities", value: String(initialOpportunities?.length ?? 0),   color: "text-emerald-400"},
              ].map(k => (
                <div key={k.label} className="rounded-lg border border-white/[0.06] bg-[#0d1120] px-2.5 py-2 min-w-[78px]">
                  <p className={`text-[15px] font-black leading-none tabular-nums ${k.color}`}>{k.value}</p>
                  <p className="text-[9px] text-slate-600 mt-0.5 uppercase tracking-wider">{k.label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Session Tabs */}
        <div className="flex gap-0.5 overflow-x-auto rounded-xl border border-white/[0.07] bg-[#080c14] p-1 scrollbar-hide">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 min-w-[120px] rounded-xl px-4 py-2.5 text-[12px] font-semibold whitespace-nowrap transition ${
                activeTab === tab.id
                  ? "bg-gradient-to-r from-sky-600/25 to-violet-600/20 text-white border border-sky-500/20"
                  : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]"
              }`}
            >
              {tab.label}
              {tab.id === "live-market" && sess === "open" && (
                <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"/>
              )}
              {tab.id === "pre-market" && (sess === "pre_market" || sess === "pre_open") && (
                <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse"/>
              )}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div>
          {activeTab === "overview"          && <OverviewTab data={overview} loading={overviewLoading} events={initialEvents} news={initialNews} opportunities={initialOpportunities} calendarEvents={initialCalendar}/>}
          {activeTab === "pre-market"        && <PreMarketTab/>}
          {activeTab === "live-market"       && <LiveMarketTab initialData={overview}/>}
          {activeTab === "after-market"      && <AfterMarketTab initialData={overview}/>}
          {activeTab === "global-markets"    && <GlobalMarketsTab/>}
          {activeTab === "economic-calendar" && <EconomicCalendarTab initialEvents={initialCalendar}/>}
        </div>
      </div>

      {/* ── RIGHT SIDEBAR ──────────────────────────────────────────────── */}
      <aside className="hidden xl:flex xl:flex-col gap-0 min-w-0 sticky top-[88px] self-start max-h-[calc(100vh-100px)] overflow-y-auto scrollbar-hide pb-16">
        <MarketIntelligenceSidebar
          session={sess}
          countdown={countdown}
          insights={initialInsights}
          movers={initialMovers}
          calendarEvents={initialCalendar}
          news={initialNews}
        />
      </aside>
    </>
  );
}
