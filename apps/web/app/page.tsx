import { AIMarketWrapCard } from "@/components/AIMarketWrapCard";
import { DashboardHero } from "@/components/DashboardHero";
import { EconomicCalendar } from "@/components/EconomicCalendar";
import { FloatingAISearch } from "@/components/FloatingAISearch";
import { LatestNews } from "@/components/LatestNews";
import { MarketIndexCard } from "@/components/MarketOverviewCards";
import { OpportunityRadar } from "@/components/OpportunityRadar";
import { SectorHeatmap } from "@/components/SectorHeatmap";
import { TrendingEvents } from "@/components/TrendingEvents";
import { TopMoversGrid } from "@/components/TopMoversSection";
import { calendarData, newsData, sectorHeatmapData, opportunityRadarData } from "@/app/lib/mock";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getDashboard() {
  const res = await fetch(`${API}/api/dashboard/`, { cache: "no-store" });
  if (!res.ok) throw new Error("dashboard fetch failed");
  return res.json();
}

async function getCalendar() {
  try {
    const res = await fetch(`${API}/api/calendar/`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function getNews() {
  try {
    const res = await fetch(`${API}/api/news/`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function getSectors() {
  try {
    const res = await fetch(`${API}/api/sectors/`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function getRadar() {
  try {
    const res = await fetch(`${API}/api/radar/?page=1&page_size=4`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// Static fallback top-movers (used only when API is unavailable)
const _FALLBACK_GAINERS = [
  { company: "Bharat Electronics",  ticker: "BEL",      value: "+6.32%", subtitle: "₹282.75",   positive: true  },
  { company: "Rail Vikas Nigam",    ticker: "RVNL",     value: "+5.21%", subtitle: "₹475.80",   positive: true  },
  { company: "Larsen & Toubro",     ticker: "L&T",      value: "+4.18%", subtitle: "₹3,512.20", positive: true  },
  { company: "NTPC Ltd",            ticker: "NTPC",     value: "+3.56%", subtitle: "₹345.60",   positive: true  },
];
const _FALLBACK_LOSERS = [
  { company: "Tech Mahindra",    ticker: "TECHM",   value: "-2.35%", subtitle: "₹1,342.80", positive: false },
  { company: "Wipro Limited",    ticker: "WIPRO",   value: "-2.01%", subtitle: "₹465.75",   positive: false },
  { company: "Tata Consultancy", ticker: "TCS",     value: "-1.78%", subtitle: "₹3,721.90", positive: false },
  { company: "HCL Technologies", ticker: "HCLTECH", value: "-1.32%", subtitle: "₹1,294.50", positive: false },
];
const _FALLBACK_ACTIVE = [
  { company: "Reliance Industries", ticker: "RELIANCE",  value: "₹8,932 Cr", subtitle: "Vol.", positive: true, isVolume: true },
  { company: "HDFC Bank",           ticker: "HDFCBANK",  value: "₹6,812 Cr", subtitle: "Vol.", positive: true, isVolume: true },
  { company: "Tata Steel",          ticker: "TATASTEEL", value: "₹5,421 Cr", subtitle: "Vol.", positive: true, isVolume: true },
  { company: "Infosys Limited",     ticker: "INFY",      value: "₹4,876 Cr", subtitle: "Vol.", positive: true, isVolume: true },
];

export default async function HomePage() {
  // Fetch real data; fall back to stubs on error
  let dashboard: any = null;
  try { dashboard = await getDashboard(); } catch { dashboard = null; }

  const [calendarRows, newsRows, sectorRows, radarRows] = await Promise.all([
    getCalendar(),
    getNews(),
    getSectors(),
    getRadar(),
  ]);

  // ── Index cards ───────────────────────────────────────────────────────────
  const FALLBACK_INDICES = [
    {
      title: "NIFTY 50",  value: "22,530.70", change: "+241.30 (1.08%)", positive: true,
      high: "22,568.40",  low: "22,210.35",
      chartData: [{ label: "Mon", value: 22.1 }, { label: "Tue", value: 22.3 }, { label: "Wed", value: 22.45 }, { label: "Thu", value: 22.48 }, { label: "Fri", value: 22.53 }]
    },
    {
      title: "SENSEX",    value: "74,125.28", change: "+820.97 (1.12%)", positive: true,
      high: "74,233.31",  low: "72,893.48",
      chartData: [{ label: "Mon", value: 73.2 }, { label: "Tue", value: 73.6 }, { label: "Wed", value: 73.9 }, { label: "Thu", value: 74.0 }, { label: "Fri", value: 74.12 }]
    },
    {
      title: "BANKNIFTY", value: "48,734.15", change: "+568.95 (1.18%)", positive: true,
      high: "48,901.20",  low: "47,821.15",
      chartData: [{ label: "Mon", value: 47.2 }, { label: "Tue", value: 47.6 }, { label: "Wed", value: 48.0 }, { label: "Thu", value: 48.3 }, { label: "Fri", value: 48.73 }]
    }
  ];

  const indexCards = (dashboard?.index_quotes?.length ? dashboard.index_quotes : FALLBACK_INDICES).map(
    (q: any) => ({
      title:     q.title,
      value:     q.value,
      change:    q.change,
      positive:  q.positive,
      high:      q.high ?? q.value,
      low:       q.low  ?? q.value,
      chartData: q.chartData ?? [],
    })
  );

  // ── Trending events ───────────────────────────────────────────────────────
  const trendingEvents = (dashboard?.trending_events ?? []).map((e: any) => ({
    id:    e.id,
    score: Math.round(e.impact_score ?? 0),   // already 0-100, no * 10
    title: e.title,
    tags:  [e.category ?? "Macro", ...(e.sectors ?? []).slice(0, 1)],
    time:  e.category ?? "Macro",
  }));

  // ── AI summary ────────────────────────────────────────────────────────────
  const aiSummary = dashboard?.aiSummary
    ?? "Markets tracking mixed global cues. Domestic macro data stable; RBI policy on hold. Defence and energy sectors outperforming.";

  // ── Sidebar data ──────────────────────────────────────────────────────────
  const calEvents = calendarRows ?? calendarData;
  const newsItems = newsRows
    ? newsRows.map((n: any) => ({ id: n.id, headline: n.headline, source: n.source, published_at: n.published_at, score: Math.round(n.impact_score ?? 0) }))
    : newsData;
  const sectors = sectorRows ?? sectorHeatmapData;

  // ── Opportunity radar ─────────────────────────────────────────────────────
  const radarItems = (radarRows?.items ?? []).slice(0, 4).map((r: any) => ({
    id:       String(r.slug ?? r.id),
    score:    Math.round(r.opportunity_score ?? 0),
    theme:    r.title ?? "Opportunity",
    reason:   r.summary ?? "",
    category: (r.sectors ?? [])[0] ?? r.risk_level ?? "General",
  }));

  // ── Hero: live date + NSE market hours (IST = UTC+5:30) ─────────────────
  const nowUtc  = new Date();
  const istMs   = nowUtc.getTime() + (5 * 60 + 30) * 60_000;
  const ist     = new Date(istMs);
  const heroDate = ist.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  const hour    = ist.getUTCHours();
  const minute  = ist.getUTCMinutes();
  const dow     = ist.getUTCDay(); // 0=Sun,6=Sat
  const istMins = hour * 60 + minute;
  const isWeekday    = dow >= 1 && dow <= 5;
  const isMarketTime = istMins >= 9 * 60 + 15 && istMins < 15 * 60 + 30;
  const marketStatus = (isWeekday && isMarketTime ? "Market Open" : "Market Closed") as "Market Open" | "Market Closed";
  const greeting = hour < 12 ? "Good Morning" : hour < 17 ? "Good Afternoon" : "Good Evening";

  // ── Ticker bar values ─────────────────────────────────────────────────────
  const tickerIndices = indexCards.length
    ? indexCards.map((c: any) => ({ label: c.title, value: c.value, change: c.change.split(" ")[1]?.replace(/[()]/g, "") ?? c.change, positive: c.positive }))
    : [
        { label: "NIFTY 50",  value: "22,530.70", change: "+1.08%", positive: true },
        { label: "SENSEX",    value: "74,125.28", change: "+1.12%", positive: true },
        { label: "BANKNIFTY", value: "48,734.15", change: "+1.18%", positive: true },
      ];

  return (
    <>
      {/*
       * Col 2 of outer grid (layout.tsx: [240px | 1fr | 260px])
       * min-w-0 prevents overflow from nested grids.
       * pb-36 clears the fixed ticker bar + floating AI search.
       */}
      <div className="min-w-0 space-y-6 pb-36">

        {/* Hero */}
        <DashboardHero date={heroDate} status={marketStatus} greeting={greeting} />

        {/* Row 1 — AI Market Wrap + combined index card */}
        <div className="grid grid-cols-2 gap-6 items-stretch">
          <AIMarketWrapCard title="AI Market Intelligence" description={aiSummary} />
          <MarketIndexCard indices={indexCards} />
        </div>

        {/* Row 2 — Top movers */}
        <TopMoversGrid
          gainers={dashboard?.top_movers?.gainers?.length ? dashboard.top_movers.gainers : _FALLBACK_GAINERS}
          losers={dashboard?.top_movers?.losers?.length  ? dashboard.top_movers.losers  : _FALLBACK_LOSERS}
          active={dashboard?.top_movers?.active?.length  ? dashboard.top_movers.active  : _FALLBACK_ACTIVE}
        />

        {/* Row 3 — Trending Events / Sector Heatmap / Opportunity Radar */}
        <div className="grid grid-cols-3 gap-6 items-stretch">
          <TrendingEvents events={trendingEvents} />
          <SectorHeatmap sectors={sectors} />
          <OpportunityRadar items={radarItems.length ? radarItems : opportunityRadarData} />
        </div>

      </div>

      {/* Col 3 of outer grid (260px) — sticky right sidebar */}
      <aside className="hidden xl:flex xl:flex-col gap-6 min-w-0 sticky top-[92px] self-start max-h-[calc(100vh-92px)] overflow-y-auto">
        <EconomicCalendar events={calEvents} />
        <LatestNews items={newsItems} />
      </aside>

      {/* Ticker bar */}
      <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-white/10 bg-[#02040a]/95 px-6 py-3 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1600px] items-center gap-8 text-sm">
          {tickerIndices.map((idx: any) => (
            <div key={idx.label} className="flex items-center gap-3">
              <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-slate-500">{idx.label}</span>
              <span className="font-semibold text-white">{idx.value}</span>
              <span className={`text-xs ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.change}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Floating AI search — sits above ticker bar */}
      <FloatingAISearch className="bottom-14" />
    </>
  );
}
