"use client";

import { useEffect, useState } from "react";
import { AreaChart, Area, ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import { ClipboardList } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";


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

type MainTab = "dashboard" | "upcoming" | "ongoing" | "listed" | "calendar";
type DetailTab = "overview" | "financials" | "objects" | "risks" | "peers";
type Filter = "all" | "upcoming" | "ongoing" | "listed";

const STATUS_BADGE: Record<string, string> = {
  Upcoming: "bg-sky-500/10 text-sky-300 border border-sky-500/20",
  Ongoing:  "bg-amber-500/10 text-amber-300 border border-amber-500/20",
  Listed:   "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20",
};
const RATING_COLOR: Record<string, string> = {
  Bullish: "text-emerald-400", Neutral: "text-amber-400", Bearish: "text-rose-400",
};

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
        <Area type="monotone" dataKey="value" stroke="#34d399" strokeWidth={1.5}
          fill="url(#gmp-grad)" dot={false} />
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
              <path key={i}
                d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2} Z`}
                fill={seg.color} opacity={0.7}
              />
            );
          })}
          {/* Needle */}
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

function IPORow({ ipo, selected, onClick }: { ipo: IPO; selected: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`w-full text-left px-3 py-3 rounded-[14px] transition hover:bg-white/[0.04] border ${selected ? "border-violet-500/30 bg-violet-500/[0.05]" : "border-transparent"}`}>
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-white/[0.06] text-base font-bold text-white">
          {ipo.name.charAt(0)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <p className="text-xs font-semibold text-white truncate">{ipo.name}</p>
            <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${ipo.type === "SME" ? "bg-amber-500/15 text-amber-300" : "bg-indigo-500/15 text-indigo-300"}`}>
              {ipo.type}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-0.5">
            <p className="text-[10px] text-slate-500">{ipo.sector}</p>
            <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${STATUS_BADGE[ipo.status]}`}>
              {ipo.status}
            </span>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-xs font-semibold text-white">₹{ipo.priceMin}–{ipo.priceMax}</p>
          <p className="text-[10px] text-emerald-400">
            ₹{ipo.gmp} ({ipo.gmpPct > 0 ? "+" : ""}{ipo.gmpPct.toFixed(2)}%)
          </p>
        </div>
      </div>
    </button>
  );
}

function DetailPanel({ ipo }: { ipo: IPO }) {
  const [tab, setTab] = useState<DetailTab>("overview");
  const TABS: { id: DetailTab; label: string }[] = [
    { id: "overview",   label: "Company Overview" },
    { id: "financials", label: "Financials" },
    { id: "objects",    label: "Objects of Issue" },
    { id: "risks",      label: "Risk Factors" },
    { id: "peers",      label: "Peers Comparison" },
  ];

  return (
    <div className="rounded-[24px] border border-white/10 bg-white/[0.02] flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-white/8">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-[14px] bg-gradient-to-br from-violet-500/20 to-sky-500/20 text-xl font-bold text-white border border-white/10">
              {ipo.name.charAt(0)}
            </div>
            <div>
              <p className="text-sm font-bold text-white">{ipo.name}</p>
              <p className="text-xs text-slate-400">{ipo.sector}</p>
              <div className="flex items-center gap-1.5 mt-1">
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[ipo.status]}`}>
                  {ipo.status} IPO
                </span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${ipo.type === "SME" ? "bg-amber-500/15 text-amber-300" : "bg-indigo-500/15 text-indigo-300"}`}>
                  {ipo.type}
                </span>
              </div>
            </div>
          </div>
          <div className="text-right shrink-0">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider">Price Band</p>
            <p className="text-lg font-bold text-white">₹{ipo.priceMin} – ₹{ipo.priceMax}</p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 mt-3">
          <button className="flex items-center gap-1.5 rounded-[10px] border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/10 transition">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Download DRHP
          </button>
          <button className="flex items-center gap-1.5 rounded-[10px] border border-violet-500/20 bg-violet-500/10 px-3 py-1.5 text-[11px] text-violet-300 hover:bg-violet-500/15 transition">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/></svg>
            Add to Watchlist
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
          {[
            ["Issue Size", ipo.issueSize], ["Fresh Issue", ipo.freshIssue],
            ["Offer for Sale", ipo.offerForSale], ["Lot Size", `${ipo.lotSize} Shares`],
            ["Listing On", ipo.listingOn],
          ].map(([label, val]) => (
            <div key={label} className="rounded-[12px] border border-white/8 bg-white/[0.02] p-2.5">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</p>
              <p className="text-xs font-semibold text-white mt-0.5">{val}</p>
            </div>
          ))}
        </div>

        {/* Dates + GMP */}
        <div className="grid sm:grid-cols-2 gap-3">
          {/* Important Dates */}
          <div>
            <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-2">Important Dates</p>
            <div className="space-y-1.5">
              {[
                ["IPO Open Date", ipo.openDate], ["IPO Close Date", ipo.closeDate],
                ["Basis of Allotment", ipo.allotmentDate], ["Initiation of Refunds", ipo.refundDate],
                ["Credit of Shares", ipo.creditDate], ["Listing Date", ipo.listingDate],
              ].map(([label, val]) => (
                <div key={label} className="flex items-center justify-between gap-2">
                  <span className="text-[10px] text-slate-500">{label}</span>
                  <span className="text-[10px] font-medium text-white">{val}</span>
                </div>
              ))}
            </div>
          </div>

          {/* GMP */}
          <div>
            <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-2">GMP & Market Sentiment</p>
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="text-2xl font-bold text-white">₹{ipo.gmp}</p>
                <p className="text-[10px] text-slate-500">GMP (Grey Market Premium)</p>
              </div>
              <div className="text-right">
                <p className="text-xl font-bold text-emerald-400">{ipo.gmpPct.toFixed(2)}%</p>
                <p className="text-[10px] text-slate-500">Premium %</p>
              </div>
            </div>
            <p className="text-[10px] text-slate-500 mb-1">GMP Trend (Last 7 Days)</p>
            <div className="h-16">
              <GmpChart data={ipo.gmpTrend} />
            </div>
          </div>
        </div>

        {/* Detail tabs */}
        <div>
          <div className="flex gap-0.5 overflow-x-auto pb-1 -mx-1 px-1">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`shrink-0 rounded-[10px] px-3 py-1.5 text-[11px] font-medium transition ${
                  tab === t.id
                    ? "bg-white/10 text-white"
                    : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
                }`}>
                {t.label}
              </button>
            ))}
          </div>

          <div className="mt-3">
            {tab === "overview" && (
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-2">About the Company</p>
                  <p className="text-xs text-slate-300 leading-relaxed">{ipo.description}</p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {[["Founded", ipo.founded], ["Headquarters", ipo.headquarters],
                      ["Promoters", ipo.promoters], ["Website", ipo.website]].map(([k, v]) => (
                      <div key={k}>
                        <p className="text-[10px] text-slate-500">{k}</p>
                        <p className="text-[11px] font-medium text-white mt-0.5">{v}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-2">Key Highlights</p>
                  <ul className="space-y-1.5">
                    {ipo.highlights.map((h, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="mt-0.5 h-3.5 w-3.5 shrink-0 flex items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400 text-[8px]">✓</span>
                        <span className="text-[11px] text-slate-300">{h}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
            {tab === "financials" && (
              <div className="text-xs text-slate-400 text-center py-6">
                Detailed financials available in the DRHP. Download above for full analysis.
              </div>
            )}
            {tab === "objects" && (
              <div className="text-xs text-slate-300 space-y-2">
                <p>• Expansion of manufacturing capacity</p>
                <p>• Repayment of outstanding borrowings</p>
                <p>• Working capital requirements</p>
                <p>• General corporate purposes</p>
              </div>
            )}
            {tab === "risks" && (
              <div className="space-y-2">
                {["Revenue concentration in few clients", "Raw material price volatility", "Regulatory and compliance risks", "Competition from global players"].map((r, i) => (
                  <div key={i} className="flex items-start gap-2 text-[11px] text-slate-400">
                    <span className="text-rose-400 shrink-0">⚠</span> {r}
                  </div>
                ))}
              </div>
            )}
            {tab === "peers" && (
              <div className="text-xs text-slate-400 text-center py-6">
                Peer comparison data will be available after listing.
              </div>
            )}
          </div>
        </div>

        {/* AI IPO Summary */}
        <div className="rounded-[16px] border border-violet-500/15 bg-violet-500/[0.04] p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-violet-300"><svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg></span>
              <p className="text-[10px] font-bold tracking-widest text-violet-300 uppercase">AI IPO Summary</p>
            </div>
            <div className="flex items-center gap-1.5">
              <p className="text-[10px] text-slate-500">IPO Rating</p>
              <span className={`text-[11px] font-bold ${RATING_COLOR[ipo.aiRating] ?? "text-white"}`}>{ipo.aiRating}</span>
            </div>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">{ipo.aiSummary}</p>
          <button className="mt-2 text-[11px] text-violet-400 hover:text-violet-300 transition">
            View Full Analysis →
          </button>
        </div>

        {/* Subscription */}
        {ipo.subscriptionRetail !== null && (
          <div>
            <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-2">Subscription Status</p>
            <div className="grid grid-cols-3 gap-2">
              {[["Retail", ipo.subscriptionRetail], ["HNI / NII", ipo.subscriptionHNI], ["QIB", ipo.subscriptionQIB]].map(([label, val]) => (
                <div key={label as string} className="rounded-[12px] border border-white/8 bg-white/[0.02] p-2.5 text-center">
                  <p className="text-[10px] text-slate-500">{label as string}</p>
                  <p className={`text-sm font-bold mt-0.5 ${(val as number) >= 1 ? "text-emerald-400" : "text-white"}`}>
                    {(val as number).toFixed(2)}x
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function IPOHubPage() {
  const [data, setData] = useState<IPOData | null>(null);
  const [mainTab, setMainTab] = useState<MainTab>("dashboard");
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<IPO | null>(null);

  useEffect(() => {
    fetch(`${API}/api/ipo/`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) {
          setData(d);
          setSelected(d.ipos[0] ?? null);
        }
      })
      .catch(() => {});
  }, []);

  const ipos = data?.ipos ?? [];
  const stats = data?.stats ?? { upcoming: 0, ongoing: 0, listed: 0, avg_listing_gain: 0 };
  const sectorTrends = data?.sector_trends ?? [];
  const sentiment = data?.sentiment ?? { score: 78, label: "Bullish", retail: "High", hni: "High", volatility: "Moderate", overall: "Bullish" };

  const filtered = filter === "all" ? ipos : ipos.filter(i => i.status.toLowerCase() === filter);
  const displayed = mainTab === "upcoming" ? ipos.filter(i => i.status === "Upcoming")
    : mainTab === "ongoing" ? ipos.filter(i => i.status === "Ongoing")
    : mainTab === "listed"  ? ipos.filter(i => i.status === "Listed")
    : filtered;

  const MAIN_TABS: { id: MainTab; label: string }[] = [
    { id: "dashboard", label: "IPO Dashboard" },
    { id: "upcoming",  label: "Upcoming IPOs" },
    { id: "ongoing",   label: "Ongoing IPOs" },
    { id: "listed",    label: "Listed IPOs" },
    { id: "calendar",  label: "IPO Calendar" },
  ];

  return (
    <main className="min-w-0 space-y-5 pb-10">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="flex h-9 w-9 items-center justify-center rounded-[12px] bg-gradient-to-br from-violet-500/20 to-sky-500/20 border border-white/10 text-violet-300">
              <ClipboardList className="h-5 w-5" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white">IPO HUB</h1>
          </div>
          <p className="text-sm text-slate-400">Live IPO updates, insights & analysis</p>
        </div>
        <div className="rounded-[16px] border border-violet-500/20 bg-violet-500/[0.06] p-4 max-w-xs">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-violet-300"><svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg></span>
            <p className="text-[10px] font-bold tracking-widest text-violet-300 uppercase">AI Daily Insight</p>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">{data?.ai_insight ?? "Loading IPO insights…"}</p>
          <button className="mt-2 text-[11px] text-violet-400 hover:text-violet-300 transition">
            View Insight →
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Upcoming IPOs", value: stats.upcoming, sub: "+3 this week",       color: "text-sky-400",     dot: "bg-sky-400" },
          { label: "Ongoing IPOs",  value: stats.ongoing,  sub: "2 closing soon",     color: "text-amber-400",   dot: "bg-amber-400" },
          { label: "Listed This Month", value: stats.listed, sub: `Avg. Gain ${stats.avg_listing_gain}%`, color: "text-emerald-400", dot: "bg-emerald-400" },
        ].map(s => (
          <div key={s.label} className="rounded-[18px] border border-white/10 bg-white/[0.02] p-4">
            <div className="flex items-center gap-2">
              <span className={`text-2xl font-bold text-white`}>{s.value}</span>
              <span className={`h-2 w-2 rounded-full ${s.dot} animate-pulse`} />
            </div>
            <p className="text-xs font-semibold text-white mt-0.5">{s.label}</p>
            <p className={`text-[11px] mt-0.5 ${s.color}`}>▲ {s.sub}</p>
          </div>
        ))}
      </div>

      {/* Tab navigation */}
      <div className="flex gap-0.5 overflow-x-auto">
        {MAIN_TABS.map(t => (
          <button key={t.id} onClick={() => setMainTab(t.id)}
            className={`shrink-0 rounded-[12px] px-4 py-2 text-sm font-medium transition ${
              mainTab === t.id
                ? "bg-white/10 text-white"
                : "text-slate-400 hover:bg-white/[0.04] hover:text-white"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Main content: list + detail */}
      {mainTab === "calendar" ? (
        <div className="rounded-[24px] border border-white/10 bg-white/[0.02] p-5">
          <p className="text-sm font-semibold text-white mb-4">Upcoming IPO Calendar — May 2025</p>
          <div className="space-y-2">
            {ipos.filter(i => i.status !== "Listed").map(ipo => (
              <div key={ipo.id} className="flex items-center justify-between gap-4 rounded-[12px] border border-white/8 bg-white/[0.02] px-4 py-3">
                <div>
                  <p className="text-xs font-semibold text-white">{ipo.name}</p>
                  <p className="text-[10px] text-slate-500">{ipo.sector} • {ipo.type}</p>
                </div>
                <div className="text-center hidden sm:block">
                  <p className="text-[10px] text-slate-500">Open</p>
                  <p className="text-[11px] text-white font-medium">{ipo.openDate}</p>
                </div>
                <div className="text-center hidden sm:block">
                  <p className="text-[10px] text-slate-500">Close</p>
                  <p className="text-[11px] text-white font-medium">{ipo.closeDate}</p>
                </div>
                <div className="text-center">
                  <p className="text-[10px] text-slate-500">Listing</p>
                  <p className="text-[11px] text-white font-medium">{ipo.listingDate}</p>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[ipo.status]}`}>
                  {ipo.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1fr_420px] 2xl:grid-cols-[1fr_480px]">
          {/* IPO List */}
          <div className="rounded-[24px] border border-white/10 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-white">IPO Overview</p>
              <p className="text-xs text-slate-500">Track all live, upcoming and recently listed IPOs</p>
            </div>

            {/* Filter tabs */}
            <div className="flex gap-1 mb-3">
              {(["all", "upcoming", "ongoing", "listed"] as Filter[]).map(f => (
                <button key={f} onClick={() => setFilter(f)}
                  className={`rounded-[10px] px-3 py-1.5 text-[11px] font-medium capitalize transition ${
                    filter === f
                      ? "bg-white/10 text-white"
                      : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
                  }`}>
                  {f === "all" ? `All (${ipos.length})` : `${f.charAt(0).toUpperCase() + f.slice(1)} (${ipos.filter(i => i.status.toLowerCase() === f).length})`}
                </button>
              ))}
            </div>

            <div className="space-y-0.5 max-h-[520px] overflow-y-auto pr-1">
              {displayed.length === 0 ? (
                <p className="text-center text-sm text-slate-500 py-8">No IPOs in this category</p>
              ) : (
                displayed.map(ipo => (
                  <IPORow key={ipo.id} ipo={ipo} selected={selected?.id === ipo.id} onClick={() => setSelected(ipo)} />
                ))
              )}
            </div>

            <button className="mt-3 w-full rounded-[14px] border border-violet-500/20 bg-violet-500/[0.06] py-2.5 text-xs font-semibold text-violet-300 hover:bg-violet-500/10 transition">
              View All Upcoming IPOs →
            </button>
          </div>

          {/* Detail panel */}
          <div className="min-h-[520px]">
            {selected ? (
              <DetailPanel ipo={selected} />
            ) : (
              <div className="flex h-full items-center justify-center rounded-[24px] border border-white/10 bg-white/[0.02]">
                <p className="text-sm text-slate-500">Select an IPO to view details</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Bottom: Sentiment + Sector Trends */}
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="rounded-[24px] border border-white/10 bg-white/[0.02] p-5">
          <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-4">IPO Market Sentiment</p>
          <p className="text-[11px] text-slate-500 mb-3">Overall market sentiment for upcoming IPOs</p>
          <div className="flex items-start gap-6">
            <SentimentGauge score={sentiment.score} label={sentiment.label} />
            <div className="space-y-2 flex-1">
              {[
                ["Retail Interest",       sentiment.retail,     "text-emerald-400"],
                ["Institutional Interest", sentiment.hni,        "text-emerald-400"],
                ["Market Volatility",      sentiment.volatility, "text-amber-400"],
                ["Overall Sentiment",      sentiment.overall,    "text-emerald-400"],
              ].map(([label, val, color]) => (
                <div key={label as string} className="flex items-center justify-between">
                  <span className="text-[11px] text-slate-400">{label as string}</span>
                  <span className={`text-[11px] font-semibold ${color as string}`}>{val as string}</span>
                </div>
              ))}
            </div>
          </div>
          <p className="mt-3 text-[10px] text-slate-500">
            AI Insight: Strong retail participation expected in solar, EV and tech IPOs.
          </p>
        </div>

        <div className="rounded-[24px] border border-white/10 bg-white/[0.02] p-5">
          <p className="text-[10px] font-bold tracking-widest text-slate-400 uppercase mb-1">IPO Sector Trends</p>
          <p className="text-[11px] text-slate-500 mb-3">Number of upcoming IPOs by sector</p>
          <div className="flex items-center gap-4">
            <div className="h-36 w-36 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sectorTrends} dataKey="count" cx="50%" cy="50%"
                    innerRadius={40} outerRadius={65} paddingAngle={2}>
                    {sectorTrends.map((s, i) => <Cell key={i} fill={s.color} />)}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "#020617", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }}
                    formatter={(v: number, n: string) => [`${v} IPOs`, n]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-1.5">
              {sectorTrends.map(s => (
                <div key={s.name} className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ background: s.color }} />
                    <span className="text-[11px] text-slate-400">{s.name}</span>
                  </div>
                  <span className="text-[11px] font-medium text-white">{s.count} ({s.pct}%)</span>
                </div>
              ))}
            </div>
          </div>
          <p className="mt-3 text-[10px] text-slate-500">
            Manufacturing and Tech sectors lead the IPO pipeline.
          </p>
        </div>
      </div>
    </main>
  );
}
