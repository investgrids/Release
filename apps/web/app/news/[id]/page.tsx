"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import type { ReactNode } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { TrackPageVisit } from "@/components/TrackPageVisit";
import {
  Landmark, TrendingUp, Scale, Shield, Plane, Zap, ShoppingCart, BarChart2,
  TrendingDown, Globe, DollarSign, Handshake, HardHat, Pill, Car,
  Building2, Monitor, Repeat2, Settings, Radio, Flag, Pin,
  ClipboardList, Globe2, Target, Newspaper,
} from "lucide-react";
import { useIntelligence } from "@/hooks/useIntelligence";
import { IntelligenceBlock } from "@/components/intelligence/IntelligenceBlock";
import { API_BASE_URL as API } from "@/lib/api";

const PALETTE = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#06b6d4", "#f43f5e"];

// ── Types ─────────────────────────────────────────────────────────────────────
interface NewsArticle {
  id: string; headline: string; summary: string; source: string;
  published_at: string; companies: string[]; impact_score: number;
  url?: string; sectors: string[];
}
interface StockInfo { price: string; pct_change: number; sector?: string; }
interface Event {
  id: string; title: string; summary: string; impact_score: number;
  sectors: string[]; companies: (string | { symbol: string; name: string })[];
  category: string; date: string; source?: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────
const TABS = ["Overview", "Market Impact", "Companies", "Related Events", "AI Analysis"] as const;
type Tab = (typeof TABS)[number];

const SOURCE_COLORS: Record<string, string> = {
  "Economic Times":   "text-amber-300 bg-amber-500/10 border-amber-500/20",
  "Business Standard":"text-sky-300 bg-sky-500/10 border-sky-500/20",
  "LiveMint":         "text-emerald-300 bg-emerald-500/10 border-emerald-500/20",
  "Reuters":          "text-violet-300 bg-violet-500/10 border-violet-500/20",
  "Moneycontrol":     "text-blue-300 bg-blue-500/10 border-blue-500/20",
  "Google News":      "text-rose-300 bg-rose-500/10 border-rose-500/20",
  "Yahoo Finance":    "text-purple-300 bg-purple-500/10 border-purple-500/20",
  "Mint":             "text-teal-300 bg-teal-500/10 border-teal-500/20",
};

const SECTOR_ICONS: Record<string, ReactNode> = {
  Banking:              <Landmark className="h-4 w-4" />,
  "Monetary Policy":    <Landmark className="h-4 w-4" />,
  "Capital Markets":    <TrendingUp className="h-4 w-4" />,
  Regulation:           <Scale className="h-4 w-4" />,
  Defence:              <Shield className="h-4 w-4" />,
  Aerospace:            <Plane className="h-4 w-4" />,
  Energy:               <Zap className="h-4 w-4" />,
  FMCG:                 <ShoppingCart className="h-4 w-4" />,
  Equity:               <BarChart2 className="h-4 w-4" />,
  Index:                <TrendingDown className="h-4 w-4" />,
  Macro:                <Globe className="h-4 w-4" />,
  Government:           <Building2 className="h-4 w-4" />,
  "Corporate Earnings": <DollarSign className="h-4 w-4" />,
  "Corporate Action":   <Handshake className="h-4 w-4" />,
  Infrastructure:       <HardHat className="h-4 w-4" />,
  Pharmaceuticals:      <Pill className="h-4 w-4" />,
  Automotive:           <Car className="h-4 w-4" />,
  "Real Estate":        <Building2 className="h-4 w-4" />,
  Technology:           <Monitor className="h-4 w-4" />,
  Currency:             <Repeat2 className="h-4 w-4" />,
  "Institutional Flow": <Landmark className="h-4 w-4" />,
  Metals:               <Settings className="h-4 w-4" />,
  Telecommunications:   <Radio className="h-4 w-4" />,
  "Indian Markets":     <Flag className="h-4 w-4" />,
};

const INDEX_FOR_SECTOR: Record<string, string[]> = {
  Banking: ["BANKNIFTY", "NIFTY 50"], "Monetary Policy": ["BANKNIFTY", "NIFTY 50"],
  Technology: ["NIFTY IT", "NIFTY 50"], Pharmaceuticals: ["NIFTY PHARMA", "NIFTY 50"],
  Automotive: ["NIFTY AUTO", "NIFTY 50"], FMCG: ["NIFTY FMCG", "NIFTY 50"],
  Energy: ["NIFTY ENERGY", "NIFTY 50"], Infrastructure: ["NIFTY INFRA", "NIFTY 50"],
  Metals: ["NIFTY METAL", "NIFTY 50"], "Real Estate": ["NIFTY REALTY", "NIFTY 50"],
};

const COMPANY_TO_SYMBOL: Record<string, string> = {
  "Reliance Industries": "RELIANCE", "TCS": "TCS", "HDFC Bank": "HDFCBANK",
  "Infosys": "INFY", "ICICI Bank": "ICICIBANK", "Wipro": "WIPRO",
  "Tata Motors": "TATAMOTORS", "Tata Steel": "TATASTEEL", "NTPC": "NTPC",
  "ONGC": "ONGC", "HCL Technologies": "HCLTECH", "Axis Bank": "AXISBANK",
  "Kotak Bank": "KOTAKBANK", "Kotak Mahindra Bank": "KOTAKBANK",
  "Maruti Suzuki": "MARUTI", "Sun Pharma": "SUNPHARMA",
  "Bajaj Finance": "BAJFINANCE", "SBI": "SBIN", "LT": "LT", "ITC": "ITC",
  "Hindustan Unilever": "HINDUNILVR", "Adani Green": "ADANIGREEN",
  "Adani Enterprises": "ADANIENT", "Adani Ports": "ADANIPORTS",
  "Adani Group": "ADANIPORTS", "Coal India": "COALINDIA",
  "Bharat Electronics": "BEL", "HAL": "HAL", "Power Grid": "POWERGRID",
  "HDFC Life": "HDFCLIFE", "Bajaj Auto": "BAJAJ-AUTO",
  "Tech Mahindra": "TECHM", "Tata Power": "TATAPOWER",
  "Larsen & Toubro": "LT", "Bharti Airtel": "BHARTIARTL",
};

// Client-side fallback: derive companies from article text when backend extraction missed them
const COMPANY_ALIASES: [string, string][] = [
  ["reliance", "Reliance Industries"], ["tata consultancy", "TCS"], [" tcs ", "TCS"],
  ["hdfc bank", "HDFC Bank"], ["hdfc", "HDFC Bank"],
  ["infosys", "Infosys"], [" infy", "Infosys"], ["wipro", "Wipro"],
  ["icici bank", "ICICI Bank"], ["icici", "ICICI Bank"],
  ["tata motors", "Tata Motors"], ["tata steel", "Tata Steel"],
  ["adani ports", "Adani Ports"], ["vizhinjam", "Adani Ports"],
  ["adani green", "Adani Green"], ["adani enterprises", "Adani Enterprises"],
  ["adani", "Adani Ports"],
  ["airtel", "Bharti Airtel"], ["bharti", "Bharti Airtel"],
  ["axis bank", "Axis Bank"], ["kotak", "Kotak Mahindra Bank"],
  [" sbi", "SBI"], ["state bank", "SBI"],
  ["ntpc", "NTPC"], ["ongc", "ONGC"], [" itc ", "ITC"],
  ["bajaj finance", "Bajaj Finance"], ["bajaj auto", "Bajaj Auto"],
  ["maruti", "Maruti Suzuki"], ["sun pharma", "Sun Pharma"],
  ["ultratech", "UltraTech Cement"], ["zomato", "Zomato"],
  ["coal india", "Coal India"], [" hal ", "HAL"],
  ["bharat electronics", "Bharat Electronics"], [" bel ", "Bharat Electronics"],
  ["hcl tech", "HCL Technologies"], ["hcltech", "HCL Technologies"],
  ["tech mahindra", "Tech Mahindra"], ["tata power", "Tata Power"],
  ["power grid", "Power Grid"], ["l&t", "Larsen & Toubro"], ["larsen", "Larsen & Toubro"],
];

function deriveCompaniesFromText(headline: string, summary: string): string[] {
  const text = " " + (headline + " " + summary).toLowerCase() + " ";
  const found: string[] = [];
  for (const [kw, name] of COMPANY_ALIASES) {
    if (text.includes(kw) && !found.includes(name)) found.push(name);
    if (found.length >= 4) break;
  }
  return found;
}

const BULLISH_WORDS = ["profit", "growth", "record", "surge", "gain", "rise", "strong",
  "beat", "expand", "award", "order", "win", "outperform", "positive", "upgrade",
  "increase", "revenue", "deal", "launch", "invest", "milestone", "highest"];

const BEARISH_WORDS = ["loss", "fall", "decline", "concern", "worry", "weak", "miss",
  "cut", "slowdown", "risk", "warning", "drop", "slump", "crisis", "trouble",
  "downgrade", "below", "penalty", "suspend", "cancel", "reduce"];

const SECTOR_RISKS: Record<string, string[]> = {
  Banking: ["Interest rate sensitivity may compress NIMs", "Asset quality concerns in stress segments", "Regulatory capital requirements tightening"],
  Technology: ["Global tech spending slowdown risk", "Currency headwinds from rupee appreciation", "Talent retention and wage inflation pressure"],
  Energy: ["Crude oil price volatility impacting margins", "Regulatory policy changes on pricing", "Capex execution risk in renewable expansion"],
  Defence: ["Geopolitical uncertainty affecting order timelines", "Supply chain dependencies on imports", "Execution risk in large government contracts"],
  Pharmaceuticals: ["USFDA compliance and approval risks", "Generic price erosion in US market", "Input cost volatility for APIs"],
  "Corporate Earnings": ["Revenue miss risk if demand softens", "Margin compression from input costs", "Guidance uncertainty in volatile macro"],
  Infrastructure: ["Project execution and delay risks", "Land acquisition and clearance bottlenecks", "Commodity cost overruns"],
  FMCG: ["Rural demand recovery slower than expected", "Input commodity inflation pressuring margins", "Competitive intensity from regional players"],
  Automotive: ["EV transition disruption risk for ICE volumes", "Commodity cost headwinds", "Export market uncertainty"],
  "Indian Markets": ["Global risk-off sentiment impact", "Rupee depreciation pressure", "FII outflows in rate-sensitive environment"],
};

// ── Pure helpers ──────────────────────────────────────────────────────────────
function impactLabel(s: number) {
  if (s >= 85) return { label: "Very High Impact", color: "text-rose-300 bg-rose-500/10 border-rose-500/20",   ring: "stroke-rose-500",    bar: "from-rose-500 to-rose-400"    };
  if (s >= 70) return { label: "High Impact",      color: "text-amber-300 bg-amber-500/10 border-amber-500/20", ring: "stroke-amber-500",   bar: "from-amber-500 to-yellow-400"  };
  if (s >= 50) return { label: "Medium Impact",    color: "text-sky-300 bg-sky-500/10 border-sky-500/20",       ring: "stroke-sky-500",     bar: "from-sky-500 to-cyan-400"     };
  return              { label: "Low Impact",        color: "text-slate-400 bg-slate-500/10 border-slate-500/20", ring: "stroke-slate-500",   bar: "from-slate-500 to-slate-400"  };
}

function deriveSentiment(article: NewsArticle): "Bullish" | "Neutral" | "Bearish" {
  const text = ((article.headline ?? "") + " " + (article.summary ?? "")).toLowerCase();
  const bs = BULLISH_WORDS.filter(w => text.includes(w)).length;
  const br = BEARISH_WORDS.filter(w => text.includes(w)).length;
  if (article.impact_score >= 75 && bs > br) return "Bullish";
  if (br > bs + 1) return "Bearish";
  return "Neutral";
}

function deriveAIInsights(article: NewsArticle) {
  const sentiment = deriveSentiment(article);
  const sectors = article.sectors ?? [];
  const primarySector = sectors[0] ?? "Indian Markets";
  const score = article.impact_score;

  const shortTerm = sentiment === "Bullish"
    ? `Positive near-term momentum expected in ${primarySector} as market digests ${score >= 80 ? "this high-impact" : "this"} development.`
    : sentiment === "Bearish"
    ? `Near-term pressure anticipated in ${primarySector}. Caution advised as market reassesses risk.`
    : `Moderate near-term volatility expected while markets assess implications for ${primarySector}.`;

  const longTerm = sectors.includes("Infrastructure") || sectors.includes("Defence")
    ? `Long-term outlook remains positive — government capex and policy push create multi-year tailwinds.`
    : sectors.includes("Technology") || sectors.includes("Pharmaceuticals")
    ? `Structural growth story intact. Monitor quarterly execution; long-term fundamentals supportive.`
    : score >= 80
    ? `Sustained impact likely if policy/trend confirmed. Structural re-rating possible over 12–24 months.`
    : `Long-term outlook depends on macro stability and sector-specific execution over next few quarters.`;

  const themes = sectors.slice(0, 3).map(s =>
    s === "Corporate Earnings" ? "Earnings Growth" :
    s === "Monetary Policy"    ? "Rate Cycle" :
    s === "Institutional Flow" ? "FII Activity" : s
  );

  const risks = (SECTOR_RISKS[primarySector] ?? SECTOR_RISKS["Indian Markets"]).slice(0, 3);
  const bullishFactors = BULLISH_WORDS.filter(w =>
    ((article.headline ?? "") + " " + (article.summary ?? "")).toLowerCase().includes(w)
  ).slice(0, 3).map(w =>
    w === "profit"   ? "Strong profitability growth reported" :
    w === "record"   ? "Record performance metrics achieved" :
    w === "order"    ? "New order win signals business momentum" :
    w === "revenue"  ? "Revenue expansion driving top-line growth" :
    w === "invest"   ? "Capital investment signals long-term confidence" :
    w === "deal"     ? "Strategic deal creating shareholder value" :
    `${w.charAt(0).toUpperCase() + w.slice(1)} signal detected in article`
  );

  return { sentiment, shortTerm, longTerm, themes, risks, bullishFactors };
}

function highlights(summary: string): string[] {
  return summary.split(/\.\s+/).filter(s => s.trim().length > 20).slice(0, 3);
}

function companySymbol(name: string): string {
  return COMPANY_TO_SYMBOL[name] ?? name.replace(/[^A-Z0-9]/gi, "").toUpperCase().slice(0, 10);
}

// ── Micro-components ──────────────────────────────────────────────────────────
function Spinner() {
  return (
    <div className="flex h-40 items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/10 border-t-sky-400" />
    </div>
  );
}

function ScoreRing({ score, size = 96 }: { score: number; size?: number }) {
  const imp = impactLabel(score);
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const [dash, setDash] = useState(0);
  useEffect(() => { const t = setTimeout(() => setDash((score / 100) * circ), 120); return () => clearTimeout(t); }, [score, circ]);
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,0.06)" strokeWidth={6} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} className={imp.ring} strokeWidth={6} fill="none"
          strokeLinecap="round" strokeDasharray={`${dash} ${circ}`} style={{ transition: "stroke-dasharray 1s ease" }} />
      </svg>
      <div className="absolute text-center">
        <div className="text-2xl font-black text-white leading-none">{Math.round(score)}</div>
        <div className="text-[9px] text-slate-500 mt-0.5">/ 100</div>
      </div>
    </div>
  );
}

function SentimentBadge({ sentiment }: { sentiment: "Bullish" | "Neutral" | "Bearish" }) {
  const cfg = {
    Bullish: { color: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30", icon: "↑" },
    Neutral: { color: "text-amber-300 bg-amber-500/15 border-amber-500/30",       icon: "→" },
    Bearish: { color: "text-rose-300 bg-rose-500/15 border-rose-500/30",           icon: "↓" },
  }[sentiment];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold ${cfg.color}`}>
      <span className="text-base">{cfg.icon}</span>{sentiment}
    </span>
  );
}

function Card({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm ${className}`}>
      {title && <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{title}</h3>}
      {children}
    </div>
  );
}

function SectorBar({ label, icon, pct, color }: { label: string; icon: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-lg w-6 shrink-0">{icon}</span>
      <span className="min-w-[120px] text-[13px] font-medium text-slate-200">{label}</span>
      <div className="flex-1 h-2 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%`, transition: "width 0.8s ease" }} />
      </div>
      <span className="w-8 text-right text-[11px] font-semibold text-white">{Math.round(pct)}</span>
    </div>
  );
}

function EmptyState({ icon, title, sub }: { icon: ReactNode; title: string; sub: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.02] py-16 text-center">
      <span className="text-slate-500 mb-1">{icon}</span>
      <p className="mt-3 text-sm font-semibold text-white">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{sub}</p>
    </div>
  );
}

function CompanyCard({ name, stockInfo, idx, sentiment }: { name: string; stockInfo?: StockInfo; idx: number; sentiment: "Bullish" | "Neutral" | "Bearish" }) {
  const sym = companySymbol(name);
  const isPos = (stockInfo?.pct_change ?? 0) >= 0;
  const impact = sentiment === "Bullish" ? "Positive" : sentiment === "Bearish" ? "Negative" : "Neutral";
  const impactColor = impact === "Positive" ? "text-emerald-400" : impact === "Negative" ? "text-rose-400" : "text-amber-400";
  return (
    <div className="flex flex-col rounded-[18px] border border-white/10 bg-white/[0.03] p-4 hover:border-white/20 hover:-translate-y-0.5 transition">
      <div className="flex items-center gap-3 mb-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white"
          style={{ background: `${PALETTE[idx % PALETTE.length]}20`, border: `1px solid ${PALETTE[idx % PALETTE.length]}30` }}>
          {sym.slice(0, 2)}
        </div>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold text-white">{sym}</p>
          <p className="truncate text-[11px] text-slate-500">{name}</p>
        </div>
      </div>
      {!stockInfo ? (
        <div className="space-y-1.5">
          <div className="h-4 w-24 animate-pulse rounded bg-white/[0.06]" />
          <div className="h-3 w-14 animate-pulse rounded bg-white/[0.04]" />
        </div>
      ) : (
        <div className="mb-2">
          <p className="text-base font-bold text-white">₹{stockInfo.price}</p>
          <p className={`text-xs font-medium ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
            {isPos ? "+" : ""}{(stockInfo.pct_change ?? 0).toFixed(2)}%
          </p>
        </div>
      )}
      <div className="mt-auto flex items-center justify-between pt-2 border-t border-white/[0.05]">
        <span className={`text-[10px] font-medium ${impactColor}`}>{impact} impact</span>
        <Link href={`/companies/${sym}`} className="text-[11px] text-sky-400 hover:text-sky-300 transition">
          View Stock →
        </Link>
      </div>
    </div>
  );
}

function RelatedEventCard({ ev }: { ev: Event }) {
  const ICONS: Record<string, ReactNode> = { Government: <Building2 className="h-4 w-4" />, Policy: <ClipboardList className="h-4 w-4" />, Corporate: <Building2 className="h-4 w-4" />, RBI: <Landmark className="h-4 w-4" />, Macro: <Globe className="h-4 w-4" />, Global: <Globe2 className="h-4 w-4" />, Results: <BarChart2 className="h-4 w-4" /> };
  const score = Math.round(ev.impact_score ?? 0);
  const scoreColor = score >= 85 ? "border-rose-500 bg-rose-500/10 text-rose-400" : score >= 70 ? "border-amber-400 bg-amber-500/10 text-amber-400" : "border-sky-400 bg-sky-500/10 text-sky-400";
  return (
    <div className="flex gap-3 rounded-[16px] border border-white/8 bg-white/[0.02] p-3 hover:border-white/15 hover:bg-white/[0.035] transition">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/5 text-slate-400">
        {ICONS[ev.category] ?? <Pin className="h-4 w-4" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[12px] font-semibold leading-snug text-white line-clamp-2">{ev.title}</p>
        <div className="mt-1.5 flex items-center gap-2">
          <span className="text-[10px] text-slate-500">{ev.date}</span>
          <span className="text-[10px] text-slate-600">•</span>
          <Link href={`/events/${ev.id}`} className="text-[10px] text-sky-400 hover:text-sky-300 transition">View Details →</Link>
        </div>
      </div>
      <div className={`flex h-9 w-9 shrink-0 flex-col items-center justify-center rounded-full border ${scoreColor}`}>
        <span className="text-[12px] font-black leading-none">{score}</span>
      </div>
    </div>
  );
}

function RelatedArticleCard({ article }: { article: NewsArticle }) {
  const imp = impactLabel(article.impact_score);
  const srcCls = SOURCE_COLORS[article.source] ?? "text-slate-400 bg-white/5 border-white/10";
  return (
    <Link href={`/news/${article.id}`}
      className="group rounded-[16px] border border-white/8 bg-white/[0.02] p-4 hover:border-white/15 hover:bg-white/[0.035] hover:-translate-y-0.5 transition block">
      <div className="flex flex-wrap items-center gap-1.5 mb-2">
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${imp.color}`}>{imp.label}</span>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${srcCls}`}>{article.source}</span>
        <span className="text-[10px] text-slate-600 ml-auto">{article.published_at}</span>
      </div>
      <p className="text-[13px] font-semibold leading-snug text-white group-hover:text-sky-300 transition line-clamp-2">{article.headline}</p>
    </Link>
  );
}

// ── Tab content ───────────────────────────────────────────────────────────────
function OverviewTab({ article, relatedEvents }: { article: NewsArticle; relatedEvents: Event[] }) {
  const ins = deriveAIInsights(article);
  const bullets = highlights(article.summary);
  const top3Events = relatedEvents.slice(0, 3);

  return (
    <div className="grid grid-cols-[1fr_284px] gap-5 items-start">
      {/* LEFT */}
      <div className="space-y-4">
        <Card title="Article Summary">
          <p className="text-[14px] leading-7 text-slate-200">{article.summary}</p>
          {bullets.length > 0 && (
            <div className="mt-5 space-y-2 border-t border-white/[0.05] pt-4">
              <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-3">Key Highlights</p>
              {bullets.map((b, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-500" />
                  <p className="text-[13px] leading-5 text-slate-300">{b.trim()}.</p>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Publication Details">
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Source",       value: article.source },
              { label: "Published",    value: article.published_at },
              { label: "Impact Score", value: `${Math.round(article.impact_score)} / 100` },
              { label: "Category",     value: (article.sectors ?? [])[0] ?? "Indian Markets" },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <p className="text-[10px] text-slate-500">{label}</p>
                <p className="mt-1 text-[13px] font-semibold text-white">{value}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* RIGHT sticky sidebar */}
      <div className="sticky top-[84px] space-y-4">
        <Card title="AI Summary">
          <SentimentBadge sentiment={ins.sentiment} />
          <p className="mt-3 text-[12px] leading-5 text-slate-400">{ins.shortTerm}</p>
          <div className="mt-3 space-y-1.5 border-t border-white/[0.05] pt-3">
            <p className="text-[10px] uppercase tracking-widest text-slate-500">What this means</p>
            {ins.themes.map(t => (
              <div key={t} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-violet-400 shrink-0" />
                <span className="text-[12px] text-slate-300">{t}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Related Events">
          {top3Events.length === 0 ? (
            <p className="text-[12px] text-slate-500">No linked events found.</p>
          ) : (
            <div className="space-y-2.5">
              {top3Events.map(ev => (
                <div key={ev.id} className="flex items-start gap-2">
                  <div className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
                  <div className="min-w-0">
                    <p className="text-[12px] text-slate-300 leading-4 line-clamp-1">{ev.title}</p>
                    <p className="mt-0.5 text-[10px] text-slate-600">{ev.date}</p>
                  </div>
                </div>
              ))}
              <Link href="/events" className="mt-2 flex items-center gap-1 text-[11px] text-sky-400 hover:text-sky-300 transition">
                View All Events →
              </Link>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

interface MarketIndex { name: string; ticker: string; value: string; pct_change: number; positive: boolean; change_str: string; }
interface MarketStatus { is_open: boolean; status: string; time_ist: string; date: string; }
interface SectorDetail {
  sector: string; icon: string; indexName: string; indexTicker: string;
  value: string; pct_change: number; positive: boolean; change_str: string;
  impactLevel: "High" | "Medium" | "Low";
}
interface MarketData { marketStatus: MarketStatus; marketIndices: MarketIndex[]; sectors: string[]; sectorDetails: SectorDetail[]; }

function MarketImpactTab({ article }: { article: NewsArticle }) {
  const [mktData, setMktData] = useState<MarketData | null>(null);
  const [loadingMkt, setLoadingMkt] = useState(true);

  useEffect(() => {
    setLoadingMkt(true);
    fetch(`${API}/api/news/${article.id}/market-data`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setMktData(d); })
      .catch(() => {})
      .finally(() => setLoadingMkt(false));
  }, [article.id]);

  const sentiment = deriveSentiment(article);
  const score = article.impact_score;

  const fiiNote = sentiment === "Bullish"
    ? "FII inflows likely to accelerate as sentiment improves"
    : sentiment === "Bearish"
    ? "FII caution expected; possible short-term outflows"
    : "FII activity neutral; sector-specific positioning likely";

  const breadth = score >= 80
    ? "Broad market impact expected — affects multiple sectors and indices"
    : score >= 60
    ? "Moderate impact — primarily sector-specific, limited index-level effect"
    : "Narrow impact — company/sector specific, broader market unaffected";

  const status = mktData?.marketStatus;
  const statusLabel = status?.status === "open" ? "Market Open"
    : status?.status === "pre_open" ? "Pre-open"
    : status?.status === "pre_market" ? "Pre-market"
    : status?.status === "weekend" ? "Weekend"
    : "Market Closed";
  const statusColor = status?.is_open
    ? "text-emerald-300 bg-emerald-500/10 border-emerald-500/25"
    : "text-rose-300 bg-rose-500/10 border-rose-500/25";

  return (
    <div className="space-y-4">
      {/* Market status header */}
      {!loadingMkt && status && (
        <div className="flex items-center justify-between rounded-[16px] border border-white/[0.06] bg-white/[0.02] px-4 py-3">
          <div className="flex items-center gap-3">
            <div className={`h-2 w-2 rounded-full ${status.is_open ? "bg-emerald-400 animate-pulse" : "bg-slate-500"}`} />
            <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${statusColor}`}>{statusLabel}</span>
            <span className="text-[12px] text-slate-400">NSE · {status.time_ist} IST</span>
          </div>
          <span className="text-[11px] text-slate-500">{status.date}</span>
        </div>
      )}

      {/* Live index quotes */}
      <Card title="Live Index Performance">
        {loadingMkt ? (
          <div className="space-y-2">
            {[1,2,3].map(i => <div key={i} className="h-12 animate-pulse rounded-xl bg-white/[0.04]" />)}
          </div>
        ) : (mktData?.marketIndices?.length ?? 0) > 0 ? (
          <div className="space-y-2">
            {mktData!.marketIndices.map(idx => {
              // Normalise pct_change to bar width: ±5% → 0–100%
              const absPct = Math.abs(idx.pct_change);
              const barW = Math.min(100, (absPct / 5) * 100);
              const barColor = idx.positive ? "bg-gradient-to-r from-emerald-500 to-teal-400" : "bg-gradient-to-r from-rose-500 to-rose-400";
              return (
                <div key={idx.ticker} className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                  <div className="min-w-[130px]">
                    <p className="text-[13px] font-semibold text-white">{idx.name}</p>
                    <p className="text-[10px] text-slate-500">{idx.ticker}</p>
                  </div>
                  <div className="flex-1">
                    <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                      <div className={`h-full rounded-full ${barColor}`}
                        style={{ width: `${barW}%`, transition: "width 0.8s ease" }} />
                    </div>
                  </div>
                  <div className="text-right shrink-0 w-24">
                    <p className="text-[13px] font-bold text-white">{idx.value}</p>
                    <p className={`text-[11px] font-semibold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>
                      {idx.change_str}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-[12px] text-slate-500">Index data unavailable — backend may be starting up.</p>
        )}
      </Card>

      {/* Sectors affected */}
      <div>
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          Sectors Affected by This Article
        </p>
        {loadingMkt ? (
          <div className="grid grid-cols-2 gap-3">
            {[1,2,3,4].map(i => <div key={i} className="h-28 animate-pulse rounded-[18px] bg-white/[0.04]" />)}
          </div>
        ) : (mktData?.sectorDetails?.length ?? 0) > 0 ? (
          <div className="grid grid-cols-2 gap-3">
            {mktData!.sectorDetails.map(sd => {
              const barW = Math.min(100, (Math.abs(sd.pct_change) / 3) * 100);
              const impactColors: Record<string, string> = {
                High:   "text-rose-300 bg-rose-500/10 border-rose-500/25",
                Medium: "text-amber-300 bg-amber-500/10 border-amber-500/25",
                Low:    "text-slate-400 bg-white/[0.04] border-white/10",
              };
              const barGrad = sd.positive
                ? "from-emerald-500 to-teal-400"
                : "from-rose-500 to-rose-400";
              const changeColor = sd.positive ? "text-emerald-400" : "text-rose-400";
              const arrow = sd.positive ? "↑" : "↓";
              return (
                <div key={sd.sector}
                  className="flex flex-col gap-2.5 rounded-[18px] border border-white/[0.07] bg-white/[0.03] p-4 backdrop-blur-sm">
                  {/* Header */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xl leading-none">{sd.icon}</span>
                      <span className="text-[13px] font-semibold text-white leading-tight">{sd.sector}</span>
                    </div>
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${impactColors[sd.impactLevel]}`}>
                      {sd.impactLevel}
                    </span>
                  </div>

                  {/* Index chip + value */}
                  <div className="flex items-center justify-between">
                    <span className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-400">
                      {sd.indexName}
                    </span>
                    <span className="text-[12px] font-bold text-slate-200">{sd.value}</span>
                  </div>

                  {/* Bar + change */}
                  <div className="space-y-1.5">
                    <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                      <div
                        className={`h-full rounded-full bg-gradient-to-r ${barGrad}`}
                        style={{ width: `${barW}%`, transition: "width 0.9s ease" }}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-slate-600">{sd.indexTicker}</span>
                      <span className={`text-[12px] font-bold ${changeColor}`}>
                        {arrow} {sd.change_str}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* Fallback: derive from article.sectors when API data missing */
          <div className="grid grid-cols-2 gap-3">
            {(article.sectors ?? []).map(sector => (
              <div key={sector}
                className="flex items-center gap-3 rounded-[18px] border border-white/[0.07] bg-white/[0.03] p-4">
                <span className="text-slate-400">{SECTOR_ICONS[sector] ?? <Pin className="h-4 w-4" />}</span>
                <div>
                  <p className="text-[13px] font-semibold text-white">{sector}</p>
                  <p className="text-[10px] text-slate-500">No live data</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Flow implication */}
      <div className="grid grid-cols-2 gap-4">
        <Card title="Flow Implication">
          <div className="space-y-3">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
              <p className="text-[10px] text-slate-500 mb-1">FII / DII Activity</p>
              <p className="text-[12px] text-slate-300">{fiiNote}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
              <p className="text-[10px] text-slate-500 mb-1">Market Breadth</p>
              <p className="text-[12px] text-slate-300">{breadth}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
              <p className="text-[10px] text-slate-500 mb-1">Impact Duration</p>
              <p className="text-[12px] text-slate-300">
                {score >= 85 ? "Multi-day sustained impact likely" : score >= 65 ? "1–2 session immediate reaction" : "Intraday effect, normalises quickly"}
              </p>
            </div>
          </div>
        </Card>

        <Card title="Market Context">
          <div className="space-y-3">
            {loadingMkt ? (
              <div className="h-32 animate-pulse rounded-xl bg-white/[0.04]" />
            ) : (
              <>
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <p className="text-[10px] text-slate-500 mb-1">Trading Session</p>
                  <p className="text-[12px] text-slate-300">{statusLabel} · {status?.time_ist} IST</p>
                </div>
                {mktData?.marketIndices?.[0] && (
                  <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                    <p className="text-[10px] text-slate-500 mb-1">Primary Index</p>
                    <p className="text-[13px] font-bold text-white">{mktData.marketIndices[0].name}</p>
                    <p className={`text-[12px] font-semibold ${mktData.marketIndices[0].positive ? "text-emerald-400" : "text-rose-400"}`}>
                      {mktData.marketIndices[0].value} ({mktData.marketIndices[0].change_str})
                    </p>
                  </div>
                )}
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <p className="text-[10px] text-slate-500 mb-1">Sectors Monitored</p>
                  <p className="text-[12px] text-slate-300">{(mktData?.sectors ?? article.sectors ?? []).join(", ") || "Indian Markets"}</p>
                </div>
              </>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function CompaniesTab({ article, stockData }: { article: NewsArticle; stockData: Record<string, StockInfo> }) {
  const sentiment = deriveSentiment(article);
  // Use backend companies if available, else derive from text client-side
  const companies = (article.companies ?? []).length > 0
    ? article.companies
    : deriveCompaniesFromText(article.headline ?? "", article.summary ?? "");

  if (companies.length === 0) {
    return <EmptyState icon={<Building2 className="h-8 w-8" />} title="No specific companies linked" sub="This article discusses broad market or macro themes without specific company mentions." />;
  }
  return (
    <div className="space-y-3">
      {(article.companies ?? []).length === 0 && (
        <p className="text-[11px] text-slate-500 italic">Companies detected from article content</p>
      )}
      <div className="grid grid-cols-2 gap-4">
        {companies.slice(0, 6).map((name, idx) => (
          <CompanyCard key={name} name={name} stockInfo={stockData[name]} idx={idx} sentiment={sentiment} />
        ))}
      </div>
    </div>
  );
}

function RelatedEventsTab({ events, article }: { events: Event[]; article: NewsArticle }) {
  const { related, isFallback } = useMemo(() => {
    // Use backend companies, or fall back to client-derived companies from text
    const artComps = (article.companies ?? []).length > 0
      ? article.companies
      : deriveCompaniesFromText(article.headline ?? "", article.summary ?? "");
    const artSects = article.sectors ?? [];

    const matched = events.filter(ev => {
      const evComps = (ev.companies ?? []).map(c => typeof c === "string" ? c : c.symbol);
      const compMatch = artComps.some(ac =>
        evComps.some(ec => ec.toLowerCase().includes(ac.toLowerCase().split(" ")[0]))
      );
      const sectMatch = artSects.some(s =>
        (ev.sectors ?? []).some(es => es.toLowerCase().includes(s.toLowerCase().split(" ")[0]))
      );
      return compMatch || sectMatch;
    }).sort((a, b) => b.impact_score - a.impact_score).slice(0, 8);

    if (matched.length > 0) return { related: matched, isFallback: false };

    // Fallback: show top events by impact score so tab is never empty
    const fallback = [...events].sort((a, b) => b.impact_score - a.impact_score).slice(0, 5);
    return { related: fallback, isFallback: true };
  }, [events, article]);

  if (related.length === 0) {
    return <EmptyState icon={<ClipboardList className="h-8 w-8" />} title="No events found" sub="No market events are currently available." />;
  }
  return (
    <div className="space-y-3">
      {isFallback && (
        <p className="text-[11px] text-slate-500 italic">Showing top market events — no exact matches for this article</p>
      )}
      {related.map(ev => <RelatedEventCard key={ev.id} ev={ev} />)}
    </div>
  );
}

function AIAnalysisTab({ article }: { article: NewsArticle }) {
  const ins = deriveAIInsights(article);
  const score = article.impact_score;

  // Sentiment breakdown
  const bullPct = ins.sentiment === "Bullish" ? Math.round(score * 0.7) : ins.sentiment === "Bearish" ? Math.round(score * 0.15) : Math.round(score * 0.35);
  const bearPct = ins.sentiment === "Bearish" ? Math.round(score * 0.65) : Math.round(score * 0.15);
  const neutPct = Math.max(0, 100 - bullPct - bearPct);

  const action = score >= 80 ? "Research" : score >= 60 ? "Watch" : "Monitor";
  const actionColor = action === "Research" ? "text-emerald-300 bg-emerald-500/15 border-emerald-500/30"
                    : action === "Watch"    ? "text-amber-300 bg-amber-500/15 border-amber-500/30"
                    : "text-sky-300 bg-sky-500/15 border-sky-500/30";

  return (
    <div className="grid grid-cols-[1fr_260px] gap-5 items-start">
      {/* LEFT */}
      <div className="space-y-4">
        <Card title="Sentiment Analysis">
          <div className="flex items-center gap-4 mb-4">
            <SentimentBadge sentiment={ins.sentiment} />
            <div className="flex-1">
              <div className="flex justify-between text-[10px] text-slate-500 mb-1">
                <span>Confidence</span><span>{Math.round(score)}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-sky-400"
                  style={{ width: `${score}%`, transition: "width 0.8s ease" }} />
              </div>
            </div>
          </div>
          <div className="space-y-2">
            {[
              { label: "Bullish", pct: bullPct, color: "bg-emerald-500" },
              { label: "Neutral", pct: neutPct, color: "bg-amber-500" },
              { label: "Bearish", pct: bearPct, color: "bg-rose-500" },
            ].map(s => (
              <div key={s.label} className="flex items-center gap-2">
                <span className="w-12 text-[11px] text-slate-400">{s.label}</span>
                <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                  <div className={`h-full rounded-full ${s.color}`} style={{ width: `${s.pct}%`, transition: "width 0.8s ease" }} />
                </div>
                <span className="w-7 text-right text-[11px] font-semibold text-white">{s.pct}%</span>
              </div>
            ))}
          </div>
        </Card>

        {ins.bullishFactors.length > 0 && (
          <Card title="Bullish Factors">
            <div className="space-y-2">
              {ins.bullishFactors.map((f, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="mt-1 text-emerald-400 text-xs">✓</span>
                  <p className="text-[13px] text-slate-300">{f}</p>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card title="Risk Factors">
          <div className="space-y-2">
            {ins.risks.map((r, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="mt-1 text-rose-400 text-xs">!</span>
                <p className="text-[13px] text-slate-300">{r}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* RIGHT sticky */}
      <div className="sticky top-[84px] space-y-4">
        <Card title="Market Outlook">
          <div className="space-y-3">
            {[
              { period: "Short-term (0–3M)", text: ins.shortTerm },
              { period: "Medium-term (3–12M)", text: "Monitor sector execution and policy follow-through. Sector rotation likely if macro environment shifts." },
              { period: "Long-term (1Y+)", text: ins.longTerm },
            ].map(({ period, text }) => (
              <div key={period} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                <p className="text-[10px] text-slate-500 mb-1">{period}</p>
                <p className="text-[12px] text-slate-300 leading-5">{text}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Investment Signal">
          <div className="flex items-center justify-between mb-4">
            <p className="text-[12px] text-slate-400">Recommended action</p>
            <span className={`rounded-full border px-3 py-1 text-xs font-bold ${actionColor}`}>{action}</span>
          </div>
          <div className="space-y-2">
            <p className="text-[10px] text-slate-500 mb-2">Sectors to watch</p>
            <div className="flex flex-wrap gap-1.5">
              {(article.sectors ?? []).map(s => (
                <span key={s} className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2 py-0.5 text-[10px] text-violet-300">{s}</span>
              ))}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function NewsDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [article, setArticle] = useState<NewsArticle | null>(null);
  const [allNews, setAllNews]  = useState<NewsArticle[]>([]);
  const [events, setEvents]    = useState<Event[]>([]);
  const [stockData, setStockData] = useState<Record<string, StockInfo>>({});
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [loading, setLoading]  = useState(true);
  const [notFound, setNotFound] = useState(false);

  const { data: intelligence } = useIntelligence("news", id || undefined);

  // Fetch article + news + events in parallel
  useEffect(() => {
    if (!id) return;
    setLoading(true); setNotFound(false);
    Promise.all([
      fetch(`${API}/api/news/${id}`).then(r => r.ok ? r.json() : null),
      fetch(`${API}/api/news/`).then(r => r.ok ? r.json() : []),
      fetch(`${API}/api/events/?limit=30`).then(r => r.ok ? r.json() : []),
    ]).then(([art, news, evts]) => {
      if (!art) { setNotFound(true); return; }
      setArticle(art);
      setAllNews(Array.isArray(news) ? news : []);
      setEvents(Array.isArray(evts) ? evts : []);
    }).catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [id]);

  // Fetch live stock prices for companies (backend list or client-derived fallback)
  useEffect(() => {
    if (!article) return;
    const companies = (article.companies ?? []).length > 0
      ? article.companies
      : deriveCompaniesFromText(article.headline ?? "", article.summary ?? "");
    if (!companies.length) return;
    companies.slice(0, 6).forEach(name => {
      const sym = companySymbol(name);
      fetch(`${API}/api/stocks/${sym}`)
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d) setStockData(prev => ({ ...prev, [name]: d })); })
        .catch(() => {});
    });
  }, [article]);

  const related = useMemo(() =>
    allNews.filter(a => a.id !== id).slice(0, 4),
    [allNews, id]
  );

  const relatedEvents = useMemo(() => {
    if (!article) return [];
    const artComps = (article.companies ?? []).length > 0
      ? article.companies
      : deriveCompaniesFromText(article.headline ?? "", article.summary ?? "");
    const artSects = article.sectors ?? [];
    return events.filter(ev => {
      const evComps = (ev.companies ?? []).map((c: any) => typeof c === "string" ? c : c.symbol);
      const compMatch = artComps.some(ac =>
        evComps.some(ec => ec.toLowerCase().includes(ac.toLowerCase().split(" ")[0]))
      );
      const sectMatch = artSects.some(s =>
        (ev.sectors ?? []).some((es: string) => es.toLowerCase().includes(s.toLowerCase().split(" ")[0]))
      );
      return compMatch || sectMatch;
    }).sort((a, b) => b.impact_score - a.impact_score).slice(0, 8);
  }, [events, article]);

  // ── Render states ──
  if (loading) {
    return (
      <main className="min-w-0 pb-10">
        <div className="mb-5 h-4 w-32 animate-pulse rounded bg-white/[0.06]" />
        <div className="grid grid-cols-[1fr_284px] gap-5">
          <div className="h-56 animate-pulse rounded-[24px] bg-white/[0.03]" />
          <div className="h-56 animate-pulse rounded-[20px] bg-white/[0.03]" />
        </div>
        <Spinner />
      </main>
    );
  }

  if (notFound || !article) {
    return (
      <main className="min-w-0 flex flex-col items-center justify-center gap-4 py-24 text-center">
        <Newspaper className="h-12 w-12 text-slate-500" />
        <h1 className="text-2xl font-semibold text-white">Article not found</h1>
        <p className="text-slate-400">This article may have expired from the live feed.</p>
        <Link href="/news" className="mt-2 rounded-full bg-sky-500/15 px-5 py-2 text-sm text-sky-300 hover:bg-sky-500/25 transition">
          ← Back to News
        </Link>
      </main>
    );
  }

  const imp = impactLabel(article.impact_score);
  const sentiment = deriveSentiment(article);
  const srcCls = SOURCE_COLORS[article.source] ?? "text-slate-400 bg-white/5 border-white/10";

  return (
    <main className="min-w-0 space-y-5 pb-10">
      <TrackPageVisit type="news" id={article.id} title={article.headline} subtitle={article.source} href={`/news/${article.id}`} />
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-[13px] text-slate-500">
        <Link href="/news" className="hover:text-slate-300 transition">← News</Link>
        <span>/</span>
        <span className="truncate text-slate-400 max-w-[320px]">{article.headline.slice(0, 60)}{article.headline.length > 60 ? "…" : ""}</span>
      </nav>

      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-[1fr_284px] gap-5 items-start">
        {/* Article header */}
        <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6 backdrop-blur-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-3 py-0.5 text-[11px] font-medium ${imp.color}`}>{imp.label}</span>
            <span className={`rounded-full border px-3 py-0.5 text-[11px] font-medium ${srcCls}`}>{article.source}</span>
            <span className="text-[12px] text-slate-500">{article.published_at}</span>
          </div>
          <h1 className="mt-4 text-2xl font-bold leading-snug text-white sm:text-[26px]">{article.headline}</h1>
          {(article.sectors ?? []).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {(article.sectors ?? []).map(s => (
                <span key={s} className="flex items-center gap-1 rounded-full border border-violet-500/20 bg-violet-500/10 px-2.5 py-0.5 text-[11px] text-violet-300">
                  {SECTOR_ICONS[s] ?? <Pin className="h-3 w-3" />} {s}
                </span>
              ))}
            </div>
          )}
          <div className="mt-5 flex items-center gap-2">
            {article.url && (
              <a href={article.url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-xl bg-sky-500/15 px-4 py-2 text-[13px] font-semibold text-sky-300 hover:bg-sky-500/25 transition">
                Read original ↗
              </a>
            )}
            <button className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-slate-400 hover:text-white transition">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
            </button>
            <button className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-slate-400 hover:text-white transition">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13"/></svg>
            </button>
          </div>
        </div>

        {/* Impact card */}
        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm flex flex-col items-center text-center gap-3">
          <p className="text-[10px] uppercase tracking-widest text-slate-500">Impact Score</p>
          <ScoreRing score={article.impact_score} size={96} />
          <span className={`rounded-full border px-3 py-0.5 text-[11px] font-medium ${imp.color}`}>{imp.label}</span>
          <div className="w-full border-t border-white/[0.05] pt-3">
            <p className="text-[10px] text-slate-500 mb-2">Market Sentiment</p>
            <SentimentBadge sentiment={sentiment} />
          </div>
          {(article.sectors ?? []).length > 0 && (
            <div className="w-full border-t border-white/[0.05] pt-3 text-left">
              <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Primary Sectors</p>
              <div className="flex flex-wrap gap-1">
                {(article.sectors ?? []).slice(0, 3).map(s => (
                  <span key={s} className="rounded-full bg-white/[0.05] px-2 py-0.5 text-[10px] text-slate-400">{s}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Intelligence Block ────────────────────────────────────────────── */}
      {intelligence && (
        <IntelligenceBlock data={intelligence} label="News Intelligence" compact={true} />
      )}

      {/* ── Tabs ──────────────────────────────────────────────────────────── */}
      <div className="flex gap-1 border-b border-white/[0.06] pb-px">
        {TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-[13px] font-medium transition border-b-2 -mb-px ${
              activeTab === tab
                ? "border-violet-500 text-white"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}>
            {tab}
          </button>
        ))}
      </div>

      {/* ── Tab panels ────────────────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        <motion.div key={activeTab}
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.18 }}>
          {activeTab === "Overview"       && <OverviewTab article={article} relatedEvents={relatedEvents} />}
          {activeTab === "Market Impact"  && <MarketImpactTab article={article} />}
          {activeTab === "Companies"      && <CompaniesTab article={article} stockData={stockData} />}
          {activeTab === "Related Events" && <RelatedEventsTab events={events} article={article} />}
          {activeTab === "AI Analysis"    && <AIAnalysisTab article={article} />}
        </motion.div>
      </AnimatePresence>

      {/* ── Related articles ──────────────────────────────────────────────── */}
      {related.length > 0 && (
        <div>
          <p className="mb-3 text-[10px] uppercase tracking-widest text-slate-500">More Market News</p>
          <div className="grid gap-3 xl:grid-cols-2">
            {related.map(a => <RelatedArticleCard key={a.id} article={a} />)}
          </div>
        </div>
      )}
    </main>
  );
}
