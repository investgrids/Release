import type { Metadata } from "next";
import Link from "next/link";
import {
  AlertCircle,
  FileQuestion,
  Unlink,
  Newspaper,
  GitBranch,
  Target,
  Brain,
  Calendar,
  Radar,
  Search,
  Building2,
  BarChart3,
  BookOpen,
  Lightbulb,
  ArrowRight,
  Layers,
  TrendingUp,
  Globe2,
  BookMarked,
  Zap,
  Clock,
  Activity,
} from "lucide-react";

export const metadata: Metadata = {
  title: "About MarketRipple — AI-Powered Market Intelligence Platform",
  description:
    "MarketRipple is an AI-powered Indian stock market intelligence platform that helps investors understand not just what happened in markets, but why it happened and what opportunities exist.",
  openGraph: {
    title: "About MarketRipple — AI-Powered Market Intelligence Platform",
    description:
      "MarketRipple connects market events to companies to investment opportunities using explainable AI built specifically for Indian markets.",
  },
};

// ── Data ──────────────────────────────────────────────────────────────────────

const PROBLEMS = [
  {
    icon: AlertCircle,
    title: "Information Overload",
    description:
      "Indian investors face 500+ news articles daily across BSE, NSE, RBI, SEBI, and global markets. With no signal-to-noise filter, important events get buried under market noise.",
    color: "text-rose-400",
    bg: "bg-rose-500/10 border-rose-500/20",
  },
  {
    icon: FileQuestion,
    title: "No Context",
    description:
      "Traditional platforms show you that RBI raised rates by 50 bps — but not which banks face NIM compression, which NBFCs face funding pressure, or which sectors benefit from rupee stability.",
    color: "text-amber-400",
    bg: "bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: Unlink,
    title: "No Connections",
    description:
      "Events don't happen in isolation. A US Federal Reserve decision affects FII flows, which affects the Nifty, which affects derivative premiums — yet platforms show these as separate, unrelated data points.",
    color: "text-sky-400",
    bg: "bg-sky-500/10 border-sky-500/20",
  },
];

const SOLUTIONS = [
  {
    icon: Newspaper,
    title: "We Explain News",
    description:
      "Every market event on MarketRipple comes with AI-generated analysis: why it matters, which sectors are affected, the confidence level, and the expected impact duration — in plain language.",
    color: "text-violet-400",
  },
  {
    icon: GitBranch,
    title: "We Connect Events",
    description:
      "Our Ripple Engine traces cause-effect chains across 700+ market relationship types — commodity dependencies, currency effects, policy responses, sector contagion, and FII/DII flows.",
    color: "text-sky-400",
  },
  {
    icon: Target,
    title: "We Surface Opportunities",
    description:
      "The Opportunity Radar scores investment opportunities 0–100 using event impact, AI confidence, sector momentum, and historical precedent across BSE and NSE listed companies.",
    color: "text-emerald-400",
  },
];

const FEATURES = [
  {
    icon: Globe2,
    title: "Market Intelligence",
    description: "Real-time pre-market, live, and after-market dashboards with Gift Nifty, India VIX, US Futures, Asian & European indices, FII/DII flows, and AI opening predictions.",
  },
  {
    icon: Calendar,
    title: "Events Engine",
    description: "Classified events by type (Monetary, Fiscal, Regulatory, Earnings, Global) with AI-generated impact analysis, sector mapping, timeline tracking, and historical comparison.",
  },
  {
    icon: Layers,
    title: "Ripple Intelligence",
    description: "Proprietary cause-effect engine that traces how one event cascades across sectors, companies, and market segments — visualised as an interactive knowledge graph.",
  },
  {
    icon: Radar,
    title: "Opportunity Radar",
    description: "Algorithmic scoring of investment opportunities 0–100 using event impact, AI confidence, sector momentum, and historical precedent across BSE and NSE listed companies.",
  },
  {
    icon: Search,
    title: "AI Search",
    description: "Natural language queries across the entire MarketRipple intelligence graph — sourced, explainable answers with multi-horizon outlook in seconds.",
  },
  {
    icon: Building2,
    title: "Company Intelligence",
    description: "Deep company profiles with event exposure mapping, financial data, AI investment thesis, scenario analysis, and sector dependency charts.",
  },
  {
    icon: BookMarked,
    title: "Market Stories",
    description: "AI-curated thematic narratives that connect multiple events, sectors, and companies into a coherent market story — updated as the situation evolves.",
  },
  {
    icon: Newspaper,
    title: "News Intelligence",
    description: "Real-time news with AI-generated impact scores, sentiment analysis, affected sectors, and direct links to related market events and companies.",
  },
  {
    icon: Activity,
    title: "Sector & Index Tracker",
    description: "Live Nifty sector indices, heatmaps, and individual stock movers with AI-annotated context for every price movement that matters.",
  },
  {
    icon: Zap,
    title: "Expected Horizons",
    description: "AI-powered multi-horizon investment outlook across 5 time frames — Immediate, Short Term, Medium Term, Long Term, and Structural — with catalysts, risks, and confidence scores.",
  },
  {
    icon: Clock,
    title: "Economic Calendar",
    description: "Forward-looking calendar of scheduled market events — RBI meetings, earnings dates, policy announcements — with expected impact and sector exposure.",
  },
  {
    icon: Brain,
    title: "AI Transparency System",
    description: "Every AI output shows its reasoning, evidence sources, confidence score, and limitations — so you always know how MarketRipple arrived at its analysis.",
  },
];

const PHILOSOPHY = [
  {
    icon: Brain,
    title: "Explainability over Black Boxes",
    description:
      "Every AI output on MarketRipple comes with its reasoning. We show you the evidence behind the analysis — sources, confidence scores, dependency chains — so you can judge for yourself.",
  },
  {
    icon: BarChart3,
    title: "Evidence over Opinion",
    description:
      "We don't publish analyst opinions or price targets. We surface structured intelligence: event data, market relationships, sector flows, and company exposure — the raw material for your decisions.",
  },
  {
    icon: BookOpen,
    title: "Education over Advice",
    description:
      "MarketRipple is designed to make you a more informed investor — not to replace your judgment. We explain market mechanics so you understand why events move markets, not just that they do.",
  },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AboutPage() {
  return (
    <main className="min-w-0 space-y-16 pb-20">
      {/* ── Hero ── */}
      <section className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#0d1028] to-[#080c14] p-8 md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-400">
          About MarketRipple
        </p>
        <h1 className="mt-4 text-[28px] font-black leading-tight text-white md:text-[42px]">
          Understanding Markets.
          <br />
          <span className="bg-gradient-to-r from-violet-400 to-sky-400 bg-clip-text text-transparent">
            Not Just Watching Them.
          </span>
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300 md:text-lg">
          MarketRipple is an AI-powered market intelligence platform built specifically for
          Indian investors. We transform breaking news and market events into structured
          intelligence — connecting events to sectors, sectors to companies, and companies
          to opportunities — in real time.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          {[
            { label: "12 Intelligence Features", color: "border-violet-500/30 bg-violet-500/10 text-violet-300" },
            { label: "Real-time AI Analysis", color: "border-sky-500/30 bg-sky-500/10 text-sky-300" },
            { label: "Built for Indian Markets", color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" },
          ].map((pill) => (
            <span
              key={pill.label}
              className={`rounded-full border px-4 py-1.5 text-sm font-medium ${pill.color}`}
            >
              {pill.label}
            </span>
          ))}
        </div>
      </section>

      {/* ── The Problem ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          The Problem
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          Why Traditional Platforms Fail Investors
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          The Indian market generates enormous amounts of information daily. Traditional
          platforms aggregate it — but aggregation is not intelligence.
        </p>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {PROBLEMS.map((p) => (
            <article
              key={p.title}
              className={`rounded-xl border p-6 ${p.bg}`}
              aria-label={p.title}
            >
              <p.icon className={`h-7 w-7 ${p.color}`} aria-hidden="true" />
              <h3 className="mt-4 text-base font-bold text-white">{p.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{p.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── Our Mission ── */}
      <section className="rounded-2xl border border-violet-500/20 bg-gradient-to-br from-violet-950/40 to-[#080c14] p-8 md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-400">
          Our Mission
        </p>
        <blockquote className="mt-6 border-l-2 border-violet-500 pl-6">
          <p className="text-xl font-semibold leading-8 text-white md:text-2xl md:leading-9">
            &ldquo;Our mission is to help every investor understand not just{" "}
            <em className="not-italic text-violet-300">what happened</em>, but{" "}
            <em className="not-italic text-sky-300">why it happened</em>, which companies
            are affected, and{" "}
            <em className="not-italic text-emerald-300">what opportunities exist</em>.&rdquo;
          </p>
        </blockquote>
        <p className="mt-6 max-w-2xl text-sm leading-6 text-slate-400">
          We believe that access to institutional-quality market intelligence should not be
          limited to hedge funds and proprietary trading desks. MarketRipple democratises
          contextual market understanding for every Indian investor — from seasoned
          portfolio managers to first-time equity investors.
        </p>
      </section>

      {/* ── Our Solution ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Our Solution
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          Three Things We Do That Others Don&apos;t
        </h2>
        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {SOLUTIONS.map((s) => (
            <article
              key={s.title}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6"
              aria-label={s.title}
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-white/[0.04] border border-white/[0.08]">
                <s.icon className={`h-5 w-5 ${s.color}`} aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-bold text-white">{s.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{s.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── Core Features ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Core Features
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          Everything Inside MarketRipple
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          Twelve interconnected features that work together to give you a complete picture
          of the Indian market — from pre-market signals to long-term structural trends.
        </p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <article
              key={f.title}
              className="group rounded-xl border border-white/[0.08] bg-[#080c14] p-5 transition hover:border-white/[0.15] hover:bg-white/[0.02]"
              aria-label={f.title}
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] border border-white/[0.06]">
                  <f.icon className="h-4 w-4 text-violet-400" aria-hidden="true" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-600">
                  Feature {String(i + 1).padStart(2, "0")}
                </span>
              </div>
              <h3 className="mt-3 text-sm font-bold text-white">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-5 text-slate-500">{f.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── Product Philosophy ── */}
      <section className="rounded-2xl border border-white/[0.08] bg-[#080c14] p-8 md:p-10">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Product Philosophy
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          Principles We Build By
        </h2>
        <div className="mt-8 space-y-6">
          {PHILOSOPHY.map((p, i) => (
            <div key={p.title} className="flex gap-5">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03]">
                <p.icon className="h-5 w-5 text-sky-400" aria-hidden="true" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-600">
                    Principle {i + 1}
                  </span>
                </div>
                <h3 className="mt-0.5 text-base font-bold text-white">{p.title}</h3>
                <p className="mt-1.5 text-sm leading-6 text-slate-400">{p.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#0d1028] to-[#080c14] p-8 text-center md:p-12">
        <TrendingUp className="mx-auto h-10 w-10 text-violet-400" aria-hidden="true" />
        <h2 className="mt-4 text-[22px] font-black text-white md:text-[28px]">
          Ready to Understand Your Markets?
        </h2>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          Explore MarketRipple&apos;s intelligence modules and see how we make sense of
          the Indian market for you.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-6 py-2.5 text-sm font-semibold text-white transition hover:opacity-90"
            aria-label="Start exploring MarketRipple"
          >
            Start Exploring
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
          <Link
            href="/how-it-works"
            className="flex items-center gap-2 rounded-xl border border-white/[0.12] bg-white/[0.04] px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[0.07]"
            aria-label="Learn how MarketRipple works"
          >
            <Lightbulb className="h-4 w-4 text-amber-400" aria-hidden="true" />
            Learn How It Works
          </Link>
        </div>
      </section>
    </main>
  );
}
