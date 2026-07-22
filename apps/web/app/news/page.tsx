"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { MarketContextStrip } from "@/components/MarketContextStrip";
import { NextSteps } from "@/components/NextSteps";
import { API_BASE_URL as API } from "@/lib/api";
import { compareScoresDesc } from "@/lib/scoring";


interface NewsArticle {
  id: string;
  headline: string;
  summary: string;
  source: string;
  published_at: string;
  companies: string[];
  impact_score: number | null;
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

// Same 0–100 scale used everywhere else in the app (Events, Ripple, etc.) —
// impact_score from the API is 0–100, not 0–10.
function impactBadge(s: number | null | undefined) {
  if (s === null || s === undefined) return { label: "Unscored", cls: "text-slate-500 bg-slate-800/20 border-slate-700/30" };
  if (s >= 90) return { label: "High Impact",   cls: "text-rose-300 bg-rose-500/10 border-rose-500/25"     };
  if (s >= 75) return { label: "Medium Impact", cls: "text-amber-300 bg-amber-500/10 border-amber-500/25"  };
  return        { label: "Low Impact",    cls: "text-slate-300 bg-slate-700/40 border-slate-500/25"  };
}


export default function NewsPage() {
  const router = useRouter();
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading]   = useState(true);
  const [activeTab, setActiveTab] = useState("All");

  useEffect(() => {
    fetch(`${API}/api/news`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (Array.isArray(d)) setArticles(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const tabbed = useMemo(
    () => activeTab === "All"
      ? articles
      : articles.filter(a => classifyArticle(a.headline, a.summary) === activeTab),
    [articles, activeTab]
  );

  /* Computed sidebar data — memoised so they don't recalculate on every render */
  const categoryCounts = useMemo(
    () => TABS.slice(1).map(cat => ({
      cat,
      count: articles.filter(a => classifyArticle(a.headline, a.summary) === cat).length,
    })),
    [articles]
  );

  const sourceCounts = useMemo(
    () => Object.entries(
      articles.reduce<Record<string, number>>((acc, a) => {
        acc[a.source] = (acc[a.source] ?? 0) + 1;
        return acc;
      }, {})
    ).sort((a, b) => b[1] - a[1]).slice(0, 6),
    [articles]
  );

  const popular = useMemo(
    () => [...articles].sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score)).slice(0, 5),
    [articles]
  );

  return (
    <main className="min-w-0 pb-10">
      <MarketContextStrip />

      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Market News</h1>
          <p className="mt-1 text-sm text-slate-400">
            Sorted by market impact. High-impact stories appear first — these are the ones that can move your portfolio.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.04] px-3 py-2">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"/>
          <span className="text-[10px] text-emerald-300">Live · refreshes every 15 min</span>
        </div>
      </div>

      {/* 3-col layout */}
      <div className="grid grid-cols-[196px_1fr_220px] gap-5 items-start">

        {/* ── LEFT: Popular Stories ─────────────────────── */}
        <aside className="sticky top-[84px] rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
          <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Popular Stories</h3>
          <div className="space-y-3">
            {popular.map((a, i) => {
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
            })}
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
            ? (
              <div className="space-y-4">
                {[1,2,3,4].map(i => <div key={i} className="h-28 animate-pulse rounded-[18px] border border-white/[0.06] bg-white/[0.02]" />)}
              </div>
            )
            : tabbed.length === 0
            ? (
              <div className="flex items-center justify-center rounded-[18px] border border-white/10 bg-white/[0.03] py-16 text-sm text-slate-500">
                No articles in this category.
              </div>
            )
            : tabbed.map((a) => {
                const imp = impactBadge(a.impact_score);
                const srcBg = SOURCE_BG[a.source] ?? "bg-slate-700/40 text-slate-300";
                const whyLine = a.summary
                  ? a.summary.split(/(?<=[.!?])\s+/)[0]?.trim() ?? ""
                  : "";
                return (
                  <Link key={a.id} href={`/news/${a.id}`}
                    className="group flex gap-3 rounded-[18px] border border-white/10 bg-white/[0.03] p-4 hover:border-white/20 hover:-translate-y-0.5 transition">
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
                      {whyLine && (
                        <p className="mt-1.5 text-[11px] leading-4 text-slate-500 line-clamp-2">
                          <span className="font-semibold text-slate-400">Why this matters: </span>{whyLine}
                        </p>
                      )}
                      {a.companies?.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {a.companies.slice(0, 4).map((c: string) => {
                            const sym = COMPANY_TO_SYMBOL[c];
                            return sym
                              ? <button key={c} onClick={(e) => { e.preventDefault(); e.stopPropagation(); router.push(`/stocks/${sym}`); }}
                                  className="rounded-full border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-sky-400 hover:text-sky-300 transition">{c}</button>
                              : <span key={c} className="rounded-full border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-slate-500">{c}</span>;
                          })}
                        </div>
                      )}
                      <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); router.push(`/ai-search?q=${encodeURIComponent(a.headline)}`); }}
                        className="mt-1.5 text-[10px] font-medium text-violet-400 hover:text-violet-300 transition">
                        Ask AI →
                      </button>
                    </div>
                    {/* Impact indicator */}
                    <div className="shrink-0 text-right">
                      <div className={`flex h-8 w-8 items-center justify-center rounded-full text-[9px] font-black border ${imp.cls}`}>
                        {a.impact_score === null || a.impact_score === undefined ? "—" : a.impact_score >= 90 ? "HI" : a.impact_score >= 75 ? "MID" : "LO"}
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
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
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
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
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

      {/* Intelligent guidance — derived from top article */}
      <div className="mt-6">
      {(() => {
        const top     = popular[0];
        if (!top) return null;
        const topComp = top?.companies?.[0];
        const topSym  = topComp ? COMPANY_TO_SYMBOL[topComp] : null;
        const q       = (s: string) => encodeURIComponent(s);
        const whyLine = top.summary?.split(/(?<=[.!?])\s+/)[0] || top.headline;
        return (
          <NextSteps config={{
            takeaway: whyLine.length > 130 ? whyLine.slice(0, 127) + "…" : whyLine,
            primary: topSym && topComp ? {
              label: `Research ${topComp}`,
              why:   `Because they're the most mentioned company in today's top stories — this news changes the near-term investment narrative around them.`,
              href:  `/companies/${topSym}`,
            } : {
              label: `Ask AI: What do today's top stories mean for investors?`,
              why:   `Because news alone doesn't tell you if the market has already priced this in — AI can contextualize the real impact.`,
              href:  `/ai-search?q=${q(`What do today's top market news stories mean for Indian equity investors? Which sectors and companies are most affected?`)}`,
            },
            groups: [
              {
                label: "Understand More",
                actions: [
                  topComp ? {
                    label: `Ask AI: Does this news change ${topComp}'s investment outlook?`,
                    why:   `Because market reactions to news are often temporary — you need to know if the fundamentals actually changed.`,
                    href:  `/ai-search?q=${q(`Does "${top.headline}" change the investment thesis for ${topComp}? Is the market reaction justified or an overreaction?`)}`,
                  } : {
                    label: "Ask AI: Is the market reaction to this news justified?",
                    why:   "Because news creates noise — AI helps separate genuine signal from short-term overreaction.",
                    href:  `/ai-search?q=${q(`Is the market reaction to "${top.headline}" justified or is it an overreaction?`)}`,
                  },
                  {
                    label: "View the related market event",
                    why:   "Because news is often a symptom of a deeper market event — the event page shows the full timeline and affected companies.",
                    href:  `/events`,
                  },
                ],
              },
              {
                label: "Explore Further",
                actions: [
                  {
                    label: "Trace how this story ripples through the market",
                    why:   "Because a news story that moves one company often triggers second-order effects across suppliers, competitors, and the sector.",
                    href:  `/ripple`,
                  },
                ],
              },
            ],
            path: ["News", topComp || "Market", "Events", "Investment Impact"],
          }} />
        );
      })()}
      </div>
    </main>
  );
}
