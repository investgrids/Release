"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface NewsArticle {
  id: string;
  headline: string;
  summary: string;
  source: string;
  published_at: string;
  companies: string[];
  impact_score: number;
  url?: string;
}

const COMPANY_TO_SYMBOL: Record<string, string> = {
  "Reliance Industries": "RELIANCE", "TCS": "TCS", "Tata Consultancy": "TCS",
  "HDFC Bank": "HDFCBANK", "Infosys": "INFY", "Wipro": "WIPRO",
  "ICICI Bank": "ICICIBANK", "Axis Bank": "AXISBANK", "Kotak Mahindra Bank": "KOTAKBANK",
  "SBI": "SBIN", "State Bank": "SBIN", "Tata Motors": "TATAMOTORS",
  "Tata Steel": "TATASTEEL", "Adani Group": "ADANI", "Adani Green": "ADANIGREEN",
  "Adani Ports": "ADANIPORTS", "Bharti Airtel": "AIRTEL", "Bharat Electronics": "BEL",
  "HAL": "HAL", "NTPC": "NTPC", "ONGC": "ONGC", "ITC": "ITC",
  "Bajaj Finance": "BAJFINANCE", "Bajaj Auto": "BAJAJ-AUTO", "Maruti Suzuki": "MARUTI",
  "Zomato": "ZOMATO", "Sun Pharma": "SUNPHARMA", "UltraTech Cement": "ULTRACEMCO",
};

const SOURCE_BG: Record<string, string> = {
  "Economic Times":    "bg-amber-500/20 text-amber-300",
  "Business Standard": "bg-sky-500/20 text-sky-300",
  "LiveMint":          "bg-emerald-500/20 text-emerald-300",
  "Reuters":           "bg-violet-500/20 text-violet-300",
  "Moneycontrol":      "bg-blue-500/20 text-blue-300",
  "Google News":       "bg-rose-500/20 text-rose-300",
  "Yahoo Finance":     "bg-purple-500/20 text-purple-300",
  "Mint":              "bg-teal-500/20 text-teal-300",
};

const SOURCE_ABBR: Record<string, string> = {
  "Economic Times":    "ET",
  "Business Standard": "BS",
  "LiveMint":          "LM",
  "Reuters":           "RT",
  "Moneycontrol":      "MC",
  "Google News":       "GN",
  "Yahoo Finance":     "YF",
  "Mint":              "MN",
};

const TABS = ["All", "Market", "Economy", "Corporate", "Policy", "Global"];

const CATEGORY_KEYWORDS: Record<string, string[]> = {
  "Market":    ["nifty","sensex","bse","nse","index","stock","equity","share","trade"],
  "Economy":   ["gdp","inflation","cpi","iip","rbi","rate","growth","fiscal","budget"],
  "Corporate": ["results","earnings","profit","revenue","q4","q3","merger","ipo","company"],
  "Policy":    ["sebi","rbi","government","policy","regulation","regu","reform","scheme"],
  "Global":    ["us","fed","dollar","crude","global","china","europe","world"],
};

function classifyArticle(headline: string, summary: string): string {
  const text = (headline + " " + summary).toLowerCase();
  for (const [cat, kws] of Object.entries(CATEGORY_KEYWORDS)) {
    if (kws.some(k => text.includes(k))) return cat;
  }
  return "Market";
}

function impactBadge(s: number) {
  if (s >= 9) return { label: "High Impact",   cls: "text-rose-300 bg-rose-500/10 border-rose-500/25"     };
  if (s >= 7) return { label: "Medium Impact", cls: "text-amber-300 bg-amber-500/10 border-amber-500/25"  };
  return        { label: "Low Impact",    cls: "text-slate-300 bg-slate-700/40 border-slate-500/25"  };
}

const THUMB_GRADS = [
  "from-violet-700/40 to-indigo-700/20",
  "from-sky-700/40 to-blue-700/20",
  "from-emerald-700/40 to-teal-700/20",
  "from-amber-700/40 to-orange-700/20",
  "from-rose-700/40 to-pink-700/20",
];

export default function NewsPage() {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("All");

  useEffect(() => {
    fetch(`${API}/api/news`)
      .then(r => r.ok ? r.json() : [])
      .then(d => setArticles(Array.isArray(d) ? d : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const tabbed = activeTab === "All"
    ? articles
    : articles.filter(a => classifyArticle(a.headline, a.summary) === activeTab);

  /* Computed sidebar data */
  const categoryCounts = TABS.slice(1).map(cat => ({
    cat,
    count: articles.filter(a => classifyArticle(a.headline, a.summary) === cat).length,
  }));

  const sourceCounts = Object.entries(
    articles.reduce<Record<string, number>>((acc, a) => {
      acc[a.source] = (acc[a.source] ?? 0) + 1;
      return acc;
    }, {})
  )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  const popular = [...articles].sort((a, b) => b.impact_score - a.impact_score).slice(0, 5);

  return (
    <main className="min-w-0 pb-10">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Market News</h1>
          <p className="mt-1 text-sm text-slate-400">Real-time news and market updates</p>
        </div>
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.04] px-3 py-2">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"/>
          <span className="text-[10px] text-emerald-300">Live · refreshes every 15 min</span>
        </div>
      </div>

      {/* 3-col layout */}
      <div className="grid grid-cols-[196px_1fr_220px] gap-5 items-start">

        {/* ── LEFT: Popular Stories ─────────────────────── */}
        <aside className="sticky top-[84px] rounded-[20px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
          <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Popular Stories</h3>
          <div className="space-y-3">
            {loading
              ? Array.from({length:5}).map((_,i) => (
                  <div key={i} className="h-12 animate-pulse rounded-xl bg-white/[0.03]"/>
                ))
              : popular.map((a, i) => {
                  const imp = impactBadge(a.impact_score);
                  return (
                    <Link key={a.id} href={`/news/${a.id}`}
                      className="group flex items-start gap-2.5 rounded-xl p-1.5 hover:bg-white/[0.03] transition">
                      <span className="mt-0.5 shrink-0 text-[11px] font-bold text-slate-600 w-5">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[12px] font-medium text-white line-clamp-2 leading-4 group-hover:text-sky-300 transition">
                          {a.headline}
                        </p>
                        <p className="mt-1 text-[10px] text-slate-500">
                          {a.source} · {a.published_at}
                        </p>
                      </div>
                    </Link>
                  );
                })
            }
          </div>
        </aside>

        {/* ── CENTER: Tab feed ──────────────────────────── */}
        <div className="min-w-0 space-y-4">
          {/* Tab row */}
          <div className="flex gap-1 rounded-xl border border-white/10 bg-white/[0.02] p-1">
            {TABS.map(t => (
              <button key={t} onClick={() => setActiveTab(t)}
                className={`flex-1 rounded-lg py-1.5 text-[12px] font-medium transition ${
                  activeTab === t
                    ? "bg-white/10 text-white"
                    : "text-slate-500 hover:text-slate-300"
                }`}>
                {t}
              </button>
            ))}
          </div>

          {/* Article cards */}
          {loading
            ? Array.from({length:4}).map((_,i) => (
                <div key={i} className="h-28 animate-pulse rounded-[18px] border border-white/8 bg-white/[0.02]"/>
              ))
            : tabbed.length === 0
            ? (
              <div className="flex items-center justify-center rounded-[18px] border border-white/10 bg-white/[0.03] py-16 text-sm text-slate-500">
                {articles.length === 0 ? "Start the backend to load news." : "No articles in this category."}
              </div>
            )
            : tabbed.map((a, i) => {
                const imp = impactBadge(a.impact_score);
                const srcBg = SOURCE_BG[a.source] ?? "bg-slate-700/40 text-slate-300";
                return (
                  <Link key={a.id} href={`/news/${a.id}`}
                    className="group flex gap-3 rounded-[18px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl hover:border-white/20 hover:-translate-y-0.5 transition">
                    {/* Thumbnail */}
                    <div className={`h-16 w-16 shrink-0 rounded-xl bg-gradient-to-br ${THUMB_GRADS[i % THUMB_GRADS.length]} border border-white/8`}/>
                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${imp.cls}`}>
                          {imp.label}
                        </span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${srcBg}`}>
                          {a.source}
                        </span>
                        <span className="text-[10px] text-slate-600">{a.published_at}</span>
                      </div>
                      <h3 className="text-[13px] font-semibold leading-snug text-white line-clamp-2 group-hover:text-sky-200 transition">
                        {a.headline}
                      </h3>
                      {a.companies?.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {a.companies.slice(0, 4).map((c: string) => {
                            const sym = COMPANY_TO_SYMBOL[c];
                            return sym
                              ? <Link key={c} href={`/stocks/${sym}`} className="rounded-full border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-sky-400 hover:text-sky-300 transition">{c}</Link>
                              : <span key={c} className="rounded-full border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-slate-500">{c}</span>;
                          })}
                        </div>
                      )}
                    </div>
                    {/* Score */}
                    <div className="shrink-0 text-right">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/[0.06] text-[11px] font-bold text-white">
                        {Math.round(a.impact_score * 10)}
                      </div>
                    </div>
                  </Link>
                );
              })
          }
        </div>

        {/* ── RIGHT: Categories + Sources ─────────────────── */}
        <aside className="sticky top-[84px] space-y-4">
          {/* News Categories */}
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
            <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">News Categories</h3>
            <div className="space-y-2.5">
              {categoryCounts.map(({ cat, count }) => {
                const maxCount = Math.max(...categoryCounts.map(c => c.count), 1);
                return (
                  <button key={cat} onClick={() => setActiveTab(cat)}
                    className={`w-full transition ${activeTab === cat ? "opacity-100" : "opacity-70 hover:opacity-90"}`}>
                    <div className="mb-1 flex justify-between">
                      <span className={`text-[12px] font-medium ${activeTab === cat ? "text-sky-300" : "text-slate-300"}`}>{cat}</span>
                      <span className="text-[12px] font-bold text-white">{count}</span>
                    </div>
                    <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                      <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-blue-400"
                        style={{ width: `${Math.round(count / maxCount * 100)}%` }}/>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Top Sources */}
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
            <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Top Sources</h3>
            <div className="space-y-2">
              {sourceCounts.map(([src, cnt]) => {
                const srcBg = SOURCE_BG[src] ?? "bg-slate-700/40 text-slate-300";
                const abbr = SOURCE_ABBR[src] ?? src.slice(0, 2).toUpperCase();
                return (
                  <div key={src} className="flex items-center gap-2.5">
                    <span className={`flex h-7 w-7 items-center justify-center rounded-lg text-[9px] font-bold ${srcBg}`}>
                      {abbr}
                    </span>
                    <span className="flex-1 text-[12px] text-slate-300 truncate">{src}</span>
                    <span className="text-[11px] font-semibold text-slate-500">{cnt}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>

      </div>
    </main>
  );
}
