import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import {
  TrendingUp,
  Building2,
  Landmark,
  Newspaper,
  ArrowDownToLine,
  CheckCircle2,
  Sparkles,
  Database,
  Globe,
  BarChart2,
  ShieldAlert,
  ArrowRight,
  Brain,
  Activity,
  Banknote,
  Clock,
  FileText,
  Users,
  Scale,
  Zap,
  Package,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Data Sources — Where MarketRipple Gets Its Intelligence",
  description:
    "Full transparency on every data source MarketRipple uses: market prices, corporate filings, economic data, news, and how each source feeds into AI analysis.",
  openGraph: {
    title: "Data Sources — Where MarketRipple Gets Its Intelligence",
    description:
      "Every data source behind MarketRipple's market intelligence — equities, derivatives, commodities, corporate filings, economic releases, and news — with refresh frequencies and data philosophy.",
  },
};

// ── Section heading ──────────────────────────────────────────────────────────
function SectionHeading({
  id,
  badge,
  badgeColor = "text-slate-500",
  title,
  subtitle,
}: {
  id: string;
  badge: string;
  badgeColor?: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div>
      <p className={`text-[10px] font-bold uppercase tracking-[0.18em] ${badgeColor}`}>
        {badge}
      </p>
      <h2 id={id} className="mt-2 text-[22px] font-black text-white md:text-[28px]">
        {title}
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{subtitle}</p>
    </div>
  );
}

// ── Source Card ───────────────────────────────────────────────────────────────
function SourceCard({
  icon,
  name,
  description,
  tags,
  note,
  color,
}: {
  icon: ReactNode;
  name: string;
  description: string;
  tags?: string[];
  note?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#080c14] p-4">
      <div className="mb-3 flex items-start gap-3">
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${color}`}
          aria-hidden="true"
        >
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-[13px] font-bold text-white">{name}</h3>
          <p className="mt-1 text-[12px] leading-5 text-slate-400">{description}</p>
        </div>
      </div>
      {tags && tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-400"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      {note && (
        <p className="mt-2 text-[11px] italic text-slate-500">{note}</p>
      )}
    </div>
  );
}

// ── Market Data Sources ───────────────────────────────────────────────────────
const marketDataSources = [
  {
    icon: <TrendingUp className="h-4 w-4" />,
    name: "Equity Prices — BSE & NSE",
    description:
      "OHLCV data for all listed equities on Bombay Stock Exchange and National Stock Exchange. Free tier provides 15-minute delayed prices; real-time feed available via exchange-licensed data providers.",
    tags: ["BSE", "NSE", "OHLCV", "15-min delay (free)", "Real-time (licensed)"],
    note: "Coverage: ~5,400 BSE-listed companies · ~2,200 NSE-listed securities",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: <BarChart2 className="h-4 w-4" />,
    name: "Indian Indices — Full Suite",
    description:
      "All NSE and BSE indices tracked: Nifty50, Nifty500, Nifty Next 50, Bank Nifty, Nifty IT, Nifty Pharma, Nifty Auto, Nifty FMCG, Nifty Realty, Nifty Metal, Nifty Energy, and 30+ sectoral/thematic indices.",
    tags: ["Nifty50", "Bank Nifty", "Nifty IT", "Nifty Pharma", "30+ indices"],
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    icon: <Activity className="h-4 w-4" />,
    name: "Derivatives — F&O Data",
    description:
      "Futures and options data for key indices (Nifty, Bank Nifty, Fin Nifty) and single-stock F&O. Includes open interest, implied volatility, PCR, and derivatives expiry schedules.",
    tags: ["Nifty Options", "Bank Nifty Futures", "OI", "Implied Volatility", "PCR"],
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  },
  {
    icon: <Banknote className="h-4 w-4" />,
    name: "Commodity Prices — MCX, COMEX, NYMEX",
    description:
      "Gold (MCX/COMEX), Silver (MCX/COMEX), Crude Oil (NYMEX WTI, ICE Brent), Natural Gas, Copper, Aluminium, Zinc via yfinance and direct exchange feeds.",
    tags: ["Gold", "Silver", "Crude WTI", "Brent", "Natural Gas", "MCX", "COMEX"],
    note: "Commodity data is critical for India's energy and metal sector ripple analysis",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: <Globe className="h-4 w-4" />,
    name: "Currency Rates — INR & Majors",
    description:
      "RBI reference rates for INR/USD, INR/EUR, INR/GBP, INR/JPY. Supplemented by real-time forex market data. Cross-currency pairs relevant to India's trade partners tracked daily.",
    tags: ["INR/USD", "INR/EUR", "RBI Reference Rate", "Forex Market"],
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: <TrendingUp className="h-4 w-4" />,
    name: "Global Indices",
    description:
      "US markets: S&P 500, Nasdaq Composite, Dow Jones. Asian markets: Nikkei 225, Hang Seng, KOSPI, Straits Times, Shanghai Composite. European: FTSE 100, DAX, CAC 40. Tracked for FII flow correlation and global risk sentiment.",
    tags: ["S&P 500", "Nasdaq", "Nikkei", "Hang Seng", "FTSE 100", "DAX"],
    note: "Global index moves are a leading indicator for Indian market opening sentiment",
    color: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  },
];

// ── Corporate Data Sources ─────────────────────────────────────────────────
const corporateDataSources = [
  {
    icon: <FileText className="h-4 w-4" />,
    name: "Quarterly Results",
    description:
      "Company filings submitted to BSE and NSE under LODR (Listing Obligations and Disclosure Requirements). Includes standalone and consolidated P&L, balance sheet, cash flows, and key ratios. Earnings call transcripts scraped and indexed.",
    tags: ["BSE Filings", "NSE Filings", "LODR", "Earnings Transcripts"],
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: <Building2 className="h-4 w-4" />,
    name: "Annual Reports & MDA",
    description:
      "Management Discussion & Analysis sections from annual reports, sourced from company websites and regulatory filing portals. Analysed for forward-looking guidance, risk disclosures, and strategic updates.",
    tags: ["Annual Reports", "MDA", "Forward Guidance", "Strategic Updates"],
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    icon: <Zap className="h-4 w-4" />,
    name: "Corporate Actions",
    description:
      "Dividends (interim and final), buyback announcements, rights issues, bonus issues, stock splits, mergers and acquisitions, rights entitlements — all sourced from BSE/NSE corporate action calendars.",
    tags: ["Dividends", "Buybacks", "Bonus", "Splits", "M&A"],
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: <Users className="h-4 w-4" />,
    name: "Shareholding Patterns",
    description:
      "Quarterly shareholding disclosures per SEBI requirements. FII/FPI holdings, DII (domestic institutional) holdings, promoter holdings, public float — tracked quarter-over-quarter for meaningful changes.",
    tags: ["FII/FPI Holdings", "DII", "Promoter %", "SEBI Disclosures"],
    note: "FII selling is a leading indicator for market-wide liquidity conditions",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: <Newspaper className="h-4 w-4" />,
    name: "Board Announcements",
    description:
      "Material corporate developments disclosed under SEBI regulations: board meeting outcomes, appointment and resignation of key management personnel, regulatory actions, litigation disclosures, and unstructured event announcements.",
    tags: ["Board Meetings", "KMP Changes", "Regulatory Actions", "Material Events"],
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  },
];

// ── Economic Data Sources ──────────────────────────────────────────────────
const economicDataSources = [
  {
    icon: <Landmark className="h-4 w-4" />,
    name: "Reserve Bank of India (RBI)",
    description:
      "Monetary Policy Committee decisions (repo rate, reverse repo, CRR, SLR), credit policy statements, inflation data (CPI and WPI), banking system liquidity data, forex reserves, and governor speeches.",
    tags: ["Repo Rate", "CPI", "WPI", "Forex Reserves", "MPC Minutes"],
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: <Scale className="h-4 w-4" />,
    name: "Ministry of Finance",
    description:
      "Union Budget documents, revised estimates, fiscal deficit data, direct and indirect tax collection data, government borrowing calendar, disinvestment target updates, and Treasury management disclosures.",
    tags: ["Union Budget", "Fiscal Deficit", "Tax Collections", "Disinvestment"],
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    icon: <Package className="h-4 w-4" />,
    name: "Ministry of Commerce & Industry",
    description:
      "Monthly trade data (merchandise exports and imports), balance of trade, trade deficit, country-wise export-import breakdown, sector-level trade statistics relevant to listed companies.",
    tags: ["Trade Data", "Exports", "Imports", "Trade Deficit"],
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: <ShieldAlert className="h-4 w-4" />,
    name: "SEBI — Securities & Exchange Board of India",
    description:
      "Regulatory circulars affecting market microstructure (F&O margin rules, insider trading regulations), market surveillance reports, FPI registration data, and enforcement actions against listed entities.",
    tags: ["Regulatory Circulars", "F&O Rules", "FPI Data", "Enforcement"],
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: <BarChart2 className="h-4 w-4" />,
    name: "NSO — National Statistical Office",
    description:
      "Quarterly and annual GDP estimates (advance and final), Index of Industrial Production (IIP), National Accounts Statistics, and periodic surveys on income, consumption, and employment.",
    tags: ["GDP", "IIP", "National Accounts", "Advance Estimates"],
    color: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  },
];

// ── Refresh Frequency Table ────────────────────────────────────────────────
const refreshFrequencies = [
  {
    dataType: "Equity Prices",
    frequency: "Every 15 minutes",
    during: "Market hours (9:15 AM – 3:30 PM IST)",
    latency: "~15 min (free tier) / Near real-time (licensed)",
    status: "live",
  },
  {
    dataType: "News & Events",
    frequency: "Near real-time",
    during: "24×7",
    latency: "< 5 min target from source publication",
    status: "live",
  },
  {
    dataType: "Economic Indicators",
    frequency: "On release",
    during: "Event-driven",
    latency: "Typically within 10 minutes of official release",
    status: "event",
  },
  {
    dataType: "AI Ripple Analysis",
    frequency: "Triggered by new events",
    during: "Continuous",
    latency: "5–15 min from event detection to full cascade",
    status: "event",
  },
  {
    dataType: "Corporate Filings",
    frequency: "On submission",
    during: "Event-driven",
    latency: "Within 30 minutes of BSE/NSE filing timestamp",
    status: "event",
  },
  {
    dataType: "Company Profiles",
    frequency: "Daily refresh",
    during: "Post-market close (after 4:30 PM IST)",
    latency: "Updated by midnight IST each trading day",
    status: "daily",
  },
  {
    dataType: "Shareholding Patterns",
    frequency: "Quarterly",
    during: "Within 21 days of quarter end",
    latency: "Indexed within 24 hours of SEBI filing",
    status: "batch",
  },
  {
    dataType: "Historical Data",
    frequency: "Monthly batch",
    during: "First Sunday of each month",
    latency: "Back-adjusted prices, splits, dividends corrected",
    status: "batch",
  },
];

// ── Pipeline Steps ─────────────────────────────────────────────────────────
const pipelineSteps = [
  {
    icon: <ArrowDownToLine className="h-5 w-5" />,
    label: "Ingest",
    description:
      "Raw data pulled from 40+ feeds: exchange APIs, RBI/SEBI RSS, news aggregators, web scraping of official publications. All ingestion is idempotent — no duplicate records.",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: <CheckCircle2 className="h-5 w-5" />,
    label: "Clean & Validate",
    description:
      "Schema validation, null handling, outlier detection, duplicate elimination, and source credibility scoring. Malformed records are quarantined and flagged for review.",
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    icon: <Brain className="h-5 w-5" />,
    label: "Analyse & Enrich",
    description:
      "NLP entity extraction, event classification, sector tagging, company linkage, confidence scoring, and Ripple Engine cascade computation. Human-readable summaries generated.",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: <Sparkles className="h-5 w-5" />,
    label: "Publish to MarketRipple Graph",
    description:
      "Enriched data committed to the knowledge graph. UI updated, alerts triggered for relevant subscribers, and stale analyses invalidated where underlying data has changed.",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
];

// ── News Sources ───────────────────────────────────────────────────────────
const newsSources = [
  {
    category: "Financial News",
    sources: [
      "Economic Times (Markets & Corporate)",
      "Business Standard",
      "Mint",
      "Moneycontrol",
      "Financial Express",
      "Bloomberg Quint / BQ Prime",
      "Reuters India",
    ],
    icon: <Newspaper className="h-4 w-4" />,
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    category: "Official & Government",
    sources: [
      "RBI Press Releases & Circulars",
      "SEBI Circulars & Regulatory Updates",
      "Press Information Bureau (PIB)",
      "Ministry of Finance press releases",
      "NSE/BSE official announcements",
      "IRDAI (insurance sector)",
      "TRAI (telecom sector)",
    ],
    icon: <Landmark className="h-4 w-4" />,
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    category: "Global & Macro",
    sources: [
      "Reuters (global wire)",
      "Bloomberg (macro data)",
      "Federal Reserve press releases",
      "US Bureau of Labor Statistics (CPI, NFP)",
      "IMF & World Bank publications",
    ],
    icon: <Globe className="h-4 w-4" />,
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
];

// ── Page ───────────────────────────────────────────────────────────────────────
export default function DataSourcesPage() {
  return (
    <main className="min-w-0 space-y-16 pb-16" aria-label="Data Sources">

      {/* ── HERO ──────────────────────────────────────────────────────── */}
      <section aria-labelledby="hero-heading">
        <div className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-emerald-950/60 via-[#080c14] to-sky-950/40 px-8 py-12 md:px-12 md:py-16">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-400">
            Data Philosophy
          </p>
          <h1
            id="hero-heading"
            className="mt-3 text-[28px] font-black leading-tight text-white md:text-[40px]"
          >
            Intelligence Is Only as Good
            <br />
            as Its Sources
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300 md:text-lg">
            MarketRipple aggregates data from 40+ verified sources across Indian and global
            markets. We prioritise official primary sources, apply multi-layer
            verification, and are transparent about the origin and latency of every
            data point.
          </p>
          <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-white/[0.08] bg-[#080c14] px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">Data Sources</p>
              <p className="mt-1 text-2xl font-black text-emerald-400">40+</p>
              <p className="mt-0.5 text-[11px] text-slate-500">Verified feeds</p>
            </div>
            <div className="rounded-xl border border-white/[0.08] bg-[#080c14] px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">News Latency</p>
              <p className="mt-1 text-2xl font-black text-sky-400">&lt;5 min</p>
              <p className="mt-0.5 text-[11px] text-slate-500">Target from source</p>
            </div>
            <div className="rounded-xl border border-white/[0.08] bg-[#080c14] px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">Companies Covered</p>
              <p className="mt-1 text-2xl font-black text-violet-400">5,400+</p>
              <p className="mt-0.5 text-[11px] text-slate-500">BSE-listed securities</p>
            </div>
            <div className="rounded-xl border border-white/[0.08] bg-[#080c14] px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">History</p>
              <p className="mt-1 text-2xl font-black text-amber-400">14 yrs</p>
              <p className="mt-0.5 text-[11px] text-slate-500">2010–2024 backtested</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── MARKET DATA ───────────────────────────────────────────────── */}
      <section aria-labelledby="market-data-heading" className="space-y-6">
        <SectionHeading
          id="market-data-heading"
          badge="Category 1"
          badgeColor="text-violet-400"
          title="Market Data"
          subtitle="Real-time and historical price data across equities, derivatives, commodities, currencies, and global indices."
        />
        <div className="grid gap-4 sm:grid-cols-2">
          {marketDataSources.map((s) => (
            <SourceCard key={s.name} {...s} />
          ))}
        </div>
      </section>

      {/* ── CORPORATE DATA ────────────────────────────────────────────── */}
      <section aria-labelledby="corporate-data-heading" className="space-y-6">
        <SectionHeading
          id="corporate-data-heading"
          badge="Category 2"
          badgeColor="text-sky-400"
          title="Corporate Data"
          subtitle="Quarterly and annual filings, board announcements, corporate actions, and shareholding disclosures from listed Indian companies."
        />
        <div className="grid gap-4 sm:grid-cols-2">
          {corporateDataSources.map((s) => (
            <SourceCard key={s.name} {...s} />
          ))}
        </div>
      </section>

      {/* ── ECONOMIC & GOVERNMENT DATA ────────────────────────────────── */}
      <section aria-labelledby="economic-data-heading" className="space-y-6">
        <SectionHeading
          id="economic-data-heading"
          badge="Category 3"
          badgeColor="text-emerald-400"
          title="Economic & Government Data"
          subtitle="Official macroeconomic indicators from RBI, Ministry of Finance, SEBI, NSO, and other government bodies."
        />
        <div className="grid gap-4 sm:grid-cols-2">
          {economicDataSources.map((s) => (
            <SourceCard key={s.name} {...s} />
          ))}
        </div>
      </section>

      {/* ── NEWS & MEDIA ──────────────────────────────────────────────── */}
      <section aria-labelledby="news-data-heading" className="space-y-6">
        <SectionHeading
          id="news-data-heading"
          badge="Category 4"
          badgeColor="text-amber-400"
          title="News & Media"
          subtitle="Financial news aggregation from India's leading publications, official government channels, and global wires — with AI-powered relevance filtering."
        />
        <div className="grid gap-4 sm:grid-cols-3">
          {newsSources.map((cat) => (
            <div
              key={cat.category}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5"
            >
              <div className="mb-3 flex items-center gap-2.5">
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-xl border ${cat.color}`}
                  aria-hidden="true"
                >
                  {cat.icon}
                </div>
                <h3 className="text-[13px] font-bold text-white">{cat.category}</h3>
              </div>
              <ul className="space-y-1.5" aria-label={`${cat.category} sources`}>
                {cat.sources.map((source) => (
                  <li key={source} className="flex items-start gap-2 text-[12px] text-slate-400">
                    <CheckCircle2
                      className="mt-0.5 h-3 w-3 shrink-0 text-emerald-500"
                      aria-hidden="true"
                    />
                    {source}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-4">
          <div className="flex items-start gap-3">
            <Sparkles className="h-4 w-4 shrink-0 mt-0.5 text-amber-400" aria-hidden="true" />
            <div>
              <p className="text-[12px] font-bold text-amber-300">
                AI-Powered Relevance Filtering
              </p>
              <p className="mt-1 text-[12px] leading-5 text-slate-400">
                MarketRipple processes hundreds of news items daily. An NLP relevance classifier filters out
                opinion pieces, sponsored content, and low-signal articles — surfacing only events with
                genuine market implications. The classifier is trained on 3 years of annotated financial
                news with precision &gt;90% on held-out test sets.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── REFRESH FREQUENCY ─────────────────────────────────────────── */}
      <section aria-labelledby="refresh-heading" className="space-y-6">
        <SectionHeading
          id="refresh-heading"
          badge="Data Freshness"
          badgeColor="text-indigo-400"
          title="Refresh Frequency"
          subtitle="How often each data type is updated — so you always know how current your analysis is."
        />
        <div className="rounded-xl border border-white/[0.08] bg-[#080c14] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]" aria-label="Data refresh frequency table">
              <thead>
                <tr className="border-b border-white/[0.08] bg-white/[0.02]">
                  <th className="px-5 py-3.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">
                    Data Type
                  </th>
                  <th className="px-5 py-3.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">
                    Frequency
                  </th>
                  <th className="px-5 py-3.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500 hidden sm:table-cell">
                    Window
                  </th>
                  <th className="px-5 py-3.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500 hidden md:table-cell">
                    Latency / Notes
                  </th>
                  <th className="px-5 py-3.5 text-center text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">
                    Type
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {refreshFrequencies.map((row) => {
                  const statusBadge =
                    row.status === "live"
                      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/25"
                      : row.status === "event"
                      ? "bg-sky-500/15 text-sky-300 border-sky-500/25"
                      : row.status === "daily"
                      ? "bg-violet-500/15 text-violet-300 border-violet-500/25"
                      : "bg-slate-700/30 text-slate-400 border-slate-600/30";
                  const statusLabel =
                    row.status === "live"
                      ? "Live"
                      : row.status === "event"
                      ? "Event-driven"
                      : row.status === "daily"
                      ? "Daily"
                      : "Batch";
                  return (
                    <tr
                      key={row.dataType}
                      className="hover:bg-white/[0.02] transition"
                    >
                      <td className="px-5 py-3.5 font-semibold text-slate-200">
                        {row.dataType}
                      </td>
                      <td className="px-5 py-3.5 text-slate-300">{row.frequency}</td>
                      <td className="px-5 py-3.5 text-slate-500 hidden sm:table-cell">
                        {row.during}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500 hidden md:table-cell">
                        {row.latency}
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <span
                          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusBadge}`}
                        >
                          {statusLabel}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── DATA PROCESSING PIPELINE ──────────────────────────────────── */}
      <section aria-labelledby="pipeline-heading" className="space-y-6">
        <SectionHeading
          id="pipeline-heading"
          badge="Infrastructure"
          badgeColor="text-rose-400"
          title="Data Processing Pipeline"
          subtitle="How raw data becomes structured market intelligence — the four-stage pipeline from ingestion to the MarketRipple knowledge graph."
        />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {pipelineSteps.map((step, i) => (
            <div key={step.label} className="relative">
              <div className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5 h-full">
                <div className="mb-4 flex items-center justify-between">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-xl border ${step.color}`}
                    aria-hidden="true"
                  >
                    {step.icon}
                  </div>
                  <span className="text-[32px] font-black text-white/[0.05] select-none leading-none">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </div>
                <h3 className="text-[15px] font-bold text-white">{step.label}</h3>
                <p className="mt-2 text-[12px] leading-5 text-slate-400">{step.description}</p>
              </div>
              {i < pipelineSteps.length - 1 && (
                <div
                  className="absolute -right-2 top-1/2 hidden -translate-y-1/2 xl:block"
                  aria-hidden="true"
                >
                  <ArrowRight className="h-4 w-4 text-slate-700" />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── IMPORTANT DISCLAIMER ──────────────────────────────────────── */}
      <section aria-labelledby="disclaimer-heading">
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/[0.04] p-6 md:p-8">
          <div className="flex items-start gap-4">
            <ShieldAlert
              className="h-6 w-6 shrink-0 text-rose-400 mt-0.5"
              aria-hidden="true"
            />
            <div>
              <h2
                id="disclaimer-heading"
                className="text-[16px] font-black text-white"
              >
                Important Disclaimer
              </h2>
              <p className="mt-3 text-[13px] leading-6 text-slate-300">
                MarketRipple aggregates, analyses, and explains publicly available information.
                It does not replace official disclosures. Always verify information against
                primary sources before making investment decisions:
              </p>
              <div className="mt-4 grid gap-2 sm:grid-cols-2 md:grid-cols-3">
                {[
                  { name: "BSE India", url: "https://www.bseindia.com", desc: "BSE filings & corporate actions" },
                  { name: "NSE India", url: "https://www.nseindia.com", desc: "NSE data & derivatives" },
                  { name: "SEBI", url: "https://www.sebi.gov.in", desc: "Regulatory circulars" },
                  { name: "Reserve Bank of India", url: "https://www.rbi.org.in", desc: "Monetary policy & data" },
                  { name: "Ministry of Finance", url: "https://www.finmin.nic.in", desc: "Budget & fiscal data" },
                  { name: "Company Websites", url: "#", desc: "Investor relations portals" },
                ].map((source) => (
                  <div
                    key={source.name}
                    className="flex items-start gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3"
                  >
                    <Database className="h-3.5 w-3.5 shrink-0 mt-0.5 text-slate-500" aria-hidden="true" />
                    <div>
                      <p className="text-[12px] font-semibold text-slate-200">{source.name}</p>
                      <p className="text-[11px] text-slate-500">{source.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-[12px] leading-5 text-slate-400">
                MarketRipple is not a licensed investment adviser, stockbroker, or research analyst under
                SEBI regulations. All analysis is provided for informational and educational purposes
                only. Past market patterns do not guarantee future performance.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────────────── */}
      <section aria-label="Related pages" className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6 md:p-8">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Continue Exploring
        </p>
        <h2 className="mt-2 text-xl font-black text-white">
          Understand how the data becomes intelligence
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          Learn how MarketRipple processes this data into market insights, ripple chains,
          and opportunity scores.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            href="/how-marketripple-thinks"
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:opacity-90"
            aria-label="See How MarketRipple Thinks"
          >
            <Brain className="h-4 w-4" />
            How MarketRipple Thinks
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
          <Link
            href="/ai-methodology"
            className="flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] px-5 py-2.5 text-sm font-semibold text-slate-300 transition hover:border-white/25 hover:text-white"
            aria-label="Read AI Methodology"
          >
            <Activity className="h-4 w-4" />
            AI Methodology
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </section>
    </main>
  );
}
