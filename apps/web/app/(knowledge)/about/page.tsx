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
  Check,
  X,
  Radio,
  Scale,
  ShieldCheck,
  FileCheck,
  Gauge,
  Eye,
  MessageSquare,
  Landmark,
  History,
  Sparkles,
  GraduationCap,
  LineChart,
  Microscope,
  HelpCircle,
} from "lucide-react";
import { safeJsonLd } from "@/lib/text";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "About MarketRipple — AI-Powered Market Intelligence Platform",
  description:
    "MarketRipple is an AI-powered Indian stock market intelligence platform — understand not just what happened, but why, and what opportunities exist.",
  alternates: { canonical: `${SITE_URL}/about` },
  openGraph: {
    title: "About MarketRipple — AI-Powered Market Intelligence Platform",
    description:
      "MarketRipple connects market events to companies to investment opportunities using explainable AI built specifically for Indian markets.",
    url: `${SITE_URL}/about`,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

// ── Data ──────────────────────────────────────────────────────────────────────
// Every array on this page is either reused verbatim from an existing real
// page (PROBLEMS/FEATURES/PHILOSOPHY were already here; COMPARISON/FAQ are
// pulled from why-marketripple/page.tsx and faq/page.tsx respectively, not
// re-authored) or grounded in real, verified backend facts — the same 512
// tracked companies / 7 relationship types / 24 historical events (2008–2024)
// figures reconciled across every knowledge page this session. Nothing here
// is a new, unverified claim.

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

// Condensed from why-marketripple/page.tsx's real TRADITIONAL/
// MARKETRIPPLE_FEATURES comparison (same claims, not re-invented) — full
// version lives there; this page links out to it rather than duplicating
// every row.
const COMPARISON_ROWS = [
  { traditional: "Shows headlines — no context or analysis", ripple: "Explains news with AI impact analysis and sector tagging" },
  { traditional: "Displays price changes — no causal explanation", ripple: "Traces why prices moved and what's next via real events" },
  { traditional: "Lists data points in isolation", ripple: "Connects events, sectors, and companies through the Ripple Engine" },
  { traditional: "Passive consumption — you find the signal", ripple: "Surfaces investment opportunities via Opportunity Radar" },
  { traditional: "Black-box or no reasoning shown", ripple: "Explainable AI — reasoning and evidence shown for every output" },
  { traditional: "Generic global templates applied to India", ripple: "Built ground-up for BSE, NSE, RBI, SEBI, and Indian macro" },
];

// Section 4 — the six-stage pipeline, in plain language. Same real
// mechanisms detailed on /how-it-works and /ai-methodology, condensed to
// one line each for this page.
const HOW_IT_WORKS_STEPS = [
  {
    icon: Radio,
    title: "Detect",
    description: "Real-time ingestion from NSE, BSE, RSS news wires, RBI, SEBI, and PIB — filtered down to what actually moves markets, not every filing.",
  },
  {
    icon: Brain,
    title: "Understand",
    description: "AI classifies each event's impact using real per-company price moves as grounding data, not just headline text.",
  },
  {
    icon: GitBranch,
    title: "Connect",
    description: "The Ripple Engine traces cause-effect chains across seven relationship types — benefits, hurts, supplies, depends_on, competes_with, influences, triggered_by.",
  },
  {
    icon: Scale,
    title: "Compare",
    description: "Head-to-head company comparisons are broken into real dimensions — business model, growth drivers, risk profile, valuation — each independently scored.",
  },
  {
    icon: Radar,
    title: "Evaluate",
    description: "Opportunity Radar scores investment opportunities 0–100 using event impact, AI confidence, sector momentum, and historical precedent.",
  },
  {
    icon: FileCheck,
    title: "Explain",
    description: "Every output ships with its own Evidence — real Fact separated from AI Interpretation, sources cited, confidence scored — never a bare conclusion.",
  },
];

// Section 5 — question-driven, AEO-style. Real questions investors ask,
// each answered by a real, already-shipped mechanism.
const UNDERSTAND_QUESTIONS = [
  { q: "Why did a stock move today?", a: "Real events are matched to real price moves — you see the specific catalyst, not just the percentage change.", href: "/events" },
  { q: "Which sectors benefit from a policy change?", a: "The Ripple Engine maps a single policy event across every sector and company it touches, not just the headline industry.", href: "/ripple" },
  { q: "Is this part of a bigger pattern?", a: "Market Stories connect individual events into a persistent, evolving investment narrative.", href: "/newsroom/themes" },
  { q: "How does my portfolio look today?", a: "The Portfolio Intelligence Brief turns your real holdings into a daily briefing — no login, no storage.", href: "/tools/portfolio-confidence" },
  { q: "What happened last time this occurred?", a: "24 verified historical market events (2008–2024) give a real base rate, not a guess.", href: "/historical" },
];

const FEATURES = [
  {
    icon: Globe2,
    title: "Market Intelligence",
    description: "Real-time pre-market, live, and after-market dashboards with Gift Nifty, India VIX, US Futures, Asian & European indices, FII/DII flows, and AI opening predictions.",
    href: "/market-intelligence",
  },
  {
    icon: Calendar,
    title: "Events Engine",
    description: "Classified events by type (Monetary, Fiscal, Regulatory, Earnings, Global) with AI-generated impact analysis, sector mapping, timeline tracking, and historical comparison.",
    href: "/events",
  },
  {
    icon: Layers,
    title: "Ripple Intelligence",
    description: "Proprietary cause-effect engine that traces how one event cascades across sectors, companies, and market segments — visualised as an interactive knowledge graph.",
    href: "/ripple",
  },
  {
    icon: Radar,
    title: "Opportunity Radar",
    description: "Algorithmic scoring of investment opportunities 0–100 using event impact, AI confidence, sector momentum, and historical precedent across the 512 companies MarketRipple actively tracks.",
    href: "/opportunity-radar",
  },
  {
    icon: Search,
    title: "AI Search",
    description: "Natural language queries across the entire MarketRipple intelligence graph — sourced, explainable answers with multi-horizon outlook in seconds.",
    href: "/ai-search",
  },
  {
    icon: Building2,
    title: "Company Intelligence",
    description: "Deep company profiles with event exposure mapping, financial data, AI investment thesis, scenario analysis, and sector dependency charts.",
    href: "/companies",
  },
  {
    icon: BookMarked,
    title: "Market Stories",
    description: "AI-curated thematic narratives that connect multiple events, sectors, and companies into a coherent market story — updated as the situation evolves.",
    href: "/newsroom/themes",
  },
  {
    icon: Newspaper,
    title: "AI Newsroom",
    description: "AI-written market articles built on real per-company price data, each with an Evidence section split into verified Fact and labelled AI Interpretation, plus an AI Investment Verdict derived from real company and sector data.",
    href: "/newsroom",
  },
  {
    icon: Activity,
    title: "Sector & Index Tracker",
    description: "Live Nifty sector indices, heatmaps, and individual stock movers with AI-annotated context for every price movement that matters.",
    href: "/sectors",
  },
  {
    icon: Zap,
    title: "Expected Horizons",
    description: "AI-powered multi-horizon investment outlook across 5 time frames — Immediate, Short Term, Medium Term, Long Term, and Structural — with catalysts, risks, and confidence scores.",
    href: undefined,
  },
  {
    icon: Clock,
    title: "Economic Calendar",
    description: "Forward-looking calendar of scheduled market events — RBI meetings, earnings dates, policy announcements — with expected impact and sector exposure.",
    href: "/calendar",
  },
  {
    icon: Brain,
    title: "AI Transparency System",
    description: "Every AI output shows its reasoning, evidence sources, confidence score, and limitations — so you always know how MarketRipple arrived at its analysis.",
    href: "/ai-methodology",
  },
];

// Section 7 — real coverage, not aspirational. 512/7/24 figures verified
// against app.api.companies._NSE_UNIVERSE, app.db.models.intelligence_graph
// IGEdge.edge_type, and app.services.historical_memory_service respectively.
const COVERAGE = [
  { icon: LineChart, label: "Markets", detail: "NSE & BSE — Nifty 50, Sensex, Bank Nifty, sector indices, India VIX", href: "/market-intelligence" },
  { icon: Building2, label: "Companies", detail: "512 companies actively tracked in depth across the NSE-listed universe", href: "/companies" },
  { icon: Layers, label: "Sectors", detail: "13 canonical sectors — Banking, IT, Pharma, Energy, Auto, FMCG, Metals, and more", href: "/sectors" },
  { icon: Landmark, label: "Policies", detail: "RBI, SEBI, and PIB — regulatory and government announcements as they're released", href: "/calendar" },
  { icon: Calendar, label: "Events", detail: "Real-time NSE/BSE filings plus Economic Times, Moneycontrol, Business Standard, and more", href: "/events" },
  { icon: Globe2, label: "Macro", detail: "Nifty, Bank Nifty, USD/INR, Brent Crude, India VIX — monitored on live thresholds", href: "/market-intelligence" },
  { icon: History, label: "Historical Patterns", detail: "24 verified market events spanning 2008–2024 with real, measured outcomes", href: "/historical" },
];

// Section 8 — five trust pillars, each a real, shipped mechanism (not a
// marketing promise) — see /ai-methodology for the full technical detail.
const AI_TRUST = [
  { icon: FileCheck, title: "Evidence", description: "Every article's Evidence panel separates real Fact — sources, historical outcomes — from AI Interpretation. The two are never blended." },
  { icon: Gauge, title: "Confidence", description: "Every AI output carries a real, calculated confidence score — never a fabricated certainty, and never hidden." },
  { icon: BookOpen, title: "Sources", description: "Every claim is attributed to where it actually came from — NSE, RBI, a named news outlet — not a generic 'market sources.'" },
  { icon: Eye, title: "Transparency", description: "The AI Transparency System and a dedicated AI & Methodology page show exactly how MarketRipple reaches its conclusions." },
  { icon: MessageSquare, title: "Human-Readable Reasoning", description: "Plain language, not just numbers — you get the why behind a score, not just the score itself." },
];

// Section 9 — four real usage patterns, not invented personas; each maps
// to real, existing product surfaces.
const AUDIENCES = [
  { icon: GraduationCap, title: "New Investors", description: "Learn market mechanics in plain language via the Glossary and Learning Center — no jargon, no assumed knowledge.", href: "/learn" },
  { icon: Zap, title: "Active Investors", description: "Real-time events, breaking alerts, and Opportunity Radar for day-to-day decision-making.", href: "/opportunity-radar" },
  { icon: Microscope, title: "Experienced Investors", description: "Deep company and sector analysis, head-to-head comparisons, and full Ripple Engine cascade tracing.", href: "/compare" },
  { icon: Sparkles, title: "Researchers & Analysts", description: "Full methodology transparency, verified historical pattern matching, and structured AI Search for research queries.", href: "/ai-methodology" },
];

// Section 10 — 10 of the 23 real Q&A pairs from faq/page.tsx, reused
// verbatim (not re-authored) so this page never states a claim the full
// FAQ doesn't already back — see that page for the complete set.
const ABOUT_FAQ = [
  {
    id: "what-is",
    q: "What is MarketRipple?",
    a: "MarketRipple is an AI-powered market intelligence platform focused on Indian equity markets. It continuously monitors market-moving events — from government policy announcements and RBI decisions to global macro developments — and uses artificial intelligence to analyse their impact on sectors, companies, and broader market themes.",
  },
  {
    id: "who-for",
    q: "Who is MarketRipple designed for?",
    a: "MarketRipple serves a wide range of market participants: retail investors who want to understand how news events affect their holdings; research analysts who need rapid sector-level impact assessments; portfolio managers looking for early signals; and traders who monitor high-impact catalysts.",
  },
  {
    id: "free",
    q: "Is MarketRipple free to use?",
    a: "Yes — the current version of MarketRipple is completely free to use. All core features including the Events Engine, AI Search, Opportunity Radar, Stories, and the Portfolio Intelligence Brief are available at no cost. Premium plans are planned for a future release.",
  },
  {
    id: "login",
    q: "Does MarketRipple require login or account creation?",
    a: "No — MarketRipple currently requires no login or account creation. You can access all features immediately without registering. This is intentional: we want to remove all friction between you and the intelligence you need.",
  },
  {
    id: "markets-covered",
    q: "What markets does MarketRipple cover?",
    a: "MarketRipple's primary focus is Indian equity markets — stocks listed on the BSE and NSE. The platform also tracks global market context that influences Indian markets: US equity futures, Gift Nifty, Asian market performance, crude oil, gold, and major central bank decisions.",
  },
  {
    id: "advisor",
    q: "Does MarketRipple replace a financial advisor?",
    a: "No. MarketRipple is a market research and intelligence tool — it does not replace the personalised advice of a SEBI-registered investment advisor, who takes into account your individual financial situation, risk tolerance, and long-term goals.",
  },
  {
    id: "confidence-reliable",
    q: "How reliable are the confidence scores?",
    a: "Confidence scores are probability estimates, not guarantees. Markets are inherently uncertain and subject to events no model can anticipate. Scores should be used as one input among many in your research process — see the AI & Methodology page for the full explanation.",
  },
  {
    id: "tech",
    q: "What technology powers MarketRipple?",
    a: "The frontend is built with Next.js and TypeScript; the backend uses Python with FastAPI. Market data is sourced via yfinance and specialised financial data APIs. AI analysis is powered by models accessed through a multi-provider fallback chain.",
  },
  {
    id: "privacy",
    q: "Does MarketRipple store my personal data?",
    a: "No. Because MarketRipple currently requires no login or account creation, we do not collect any personally identifiable information. Usage analytics are collected in anonymous, aggregated form only.",
  },
  {
    id: "portfolio-brief",
    q: "What is the Portfolio Intelligence Brief?",
    a: "A free tool that turns your holdings into a daily intelligence briefing. Paste in your holdings — no login, no broker connection, nothing stored — and MarketRipple generates a brief covering real events, price signals, and shared themes across your holdings.",
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

const FAQ_JSONLD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: ABOUT_FAQ.map((item) => ({
    "@type": "Question",
    name: item.q,
    acceptedAnswer: { "@type": "Answer", text: item.a },
  })),
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AboutPage() {
  return (
    <main className="min-w-0 space-y-16 pb-20">
      <script
        type="application/ld+json"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: static JSON-LD
        dangerouslySetInnerHTML={{
          __html: safeJsonLd({
            "@context": "https://schema.org",
            "@type": "AboutPage",
            name: "About MarketRipple",
            url: `${SITE_URL}/about`,
            description:
              "MarketRipple is an AI-powered Indian stock market intelligence platform that helps investors understand not just what happened in markets, but why it happened and what opportunities exist.",
            mainEntity: {
              "@type": "Organization",
              name: "MarketRipple",
              url: SITE_URL,
            },
          }),
        }}
      />
      <script
        type="application/ld+json"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: static JSON-LD
        dangerouslySetInnerHTML={{ __html: safeJsonLd(FAQ_JSONLD) }}
      />

      {/* ── Hero ── */}
      <section className="rounded-2xl border border-surface-border/8 bg-gradient-to-br from-violet-500/[0.06] to-surface-bg p-8 md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-400">
          About MarketRipple
        </p>
        <h1 className="mt-4 text-[28px] font-black leading-tight text-text-primary md:text-[42px]">
          AI-Powered Market Intelligence for Indian Investors
        </h1>
        <p className="mt-3 text-lg font-semibold text-text-secondary md:text-xl">
          Understanding Markets. Not Just Watching Them.
        </p>
        <p className="mt-5 max-w-2xl text-base leading-7 text-text-secondary md:text-lg">
          MarketRipple is an AI-powered market intelligence platform built specifically for
          Indian investors. We transform breaking news and market events into structured
          intelligence — connecting events to sectors, sectors to companies, and companies
          to opportunities — in real time.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          {[
            { label: "12 Intelligence Features", color: "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-300" },
            { label: "Real-time AI Analysis", color: "border-sky-500/30 bg-sky-500/10 text-sky-600 dark:text-sky-300" },
            { label: "Built for Indian Markets", color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300" },
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

      {/* ── 1. What is MarketRipple? ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          The Direct Answer
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          What Is MarketRipple?
        </h2>
        <p className="mt-4 max-w-3xl text-[15px] leading-7 text-text-secondary">
          MarketRipple is an AI-powered market intelligence platform focused on Indian equity
          markets. It continuously monitors market-moving events — from government policy
          announcements and RBI decisions to global macro developments — and uses artificial
          intelligence to analyse their impact on sectors, companies, and broader market
          themes. The platform synthesises raw information into structured intelligence:
          impact scores, confidence ratings, ripple-effect cascades, investment opportunity
          rankings, and AI-curated narratives — compressing hours of research into minutes.
        </p>
      </section>

      {/* ── 2. What problem are we solving? ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          The Problem
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          What Problem Are We Solving?
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
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
              <h3 className="mt-4 text-base font-bold text-text-primary">{p.title}</h3>
              <p className="mt-2 text-sm leading-6 text-text-secondary">{p.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── 3. How is MarketRipple different? ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          The Difference
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          How Is MarketRipple Different?
        </h2>
        <div className="mt-8 overflow-x-auto rounded-xl border border-surface-border/8">
          <table className="w-full min-w-[560px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-surface-border/8 bg-text-primary/[0.03]">
                <th className="px-5 py-3 text-left text-[11px] font-bold uppercase tracking-wide text-text-muted">Traditional Platforms</th>
                <th className="px-5 py-3 text-left text-[11px] font-bold uppercase tracking-wide text-violet-400">MarketRipple</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON_ROWS.map((row, i) => (
                <tr key={i} className={i < COMPARISON_ROWS.length - 1 ? "border-b border-surface-border/6" : ""}>
                  <td className="px-5 py-3.5 align-top text-text-muted">
                    <div className="flex items-start gap-2">
                      <X className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" aria-hidden="true" />
                      {row.traditional}
                    </div>
                  </td>
                  <td className="px-5 py-3.5 align-top text-text-primary">
                    <div className="flex items-start gap-2">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden="true" />
                      {row.ripple}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Link href="/why-marketripple" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-violet-400 hover:text-violet-300">
          See the full comparison <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── 4. How MarketRipple works ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          The Pipeline
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          How MarketRipple Works
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {HOW_IT_WORKS_STEPS.map((s, i) => (
            <article key={s.title} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-text-primary/[0.04] border border-surface-border/6">
                  <s.icon className="h-4 w-4 text-violet-400" aria-hidden="true" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted">
                  Step {i + 1} of {HOW_IT_WORKS_STEPS.length}
                </span>
              </div>
              <h3 className="mt-3 text-base font-bold text-text-primary">{s.title}</h3>
              <p className="mt-1.5 text-sm leading-6 text-text-muted">{s.description}</p>
            </article>
          ))}
        </div>
        <Link href="/how-it-works" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-violet-400 hover:text-violet-300">
          See the full pipeline <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── 5. What can MarketRipple help investors understand? ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Real Questions
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          What Can MarketRipple Help Investors Understand?
        </h2>
        <div className="mt-8 space-y-3">
          {UNDERSTAND_QUESTIONS.map((item) => (
            <Link
              key={item.q}
              href={item.href}
              className="flex items-center justify-between gap-4 rounded-xl border border-surface-border/8 bg-surface-card p-5 transition hover:border-surface-border/15 hover:bg-text-primary/[0.02]"
            >
              <div>
                <p className="text-[15px] font-bold text-text-primary">{item.q}</p>
                <p className="mt-1 text-sm leading-6 text-text-secondary">{item.a}</p>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
            </Link>
          ))}
        </div>
      </section>

      {/* ── 6. 12 Intelligence Features ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Core Features
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          What&apos;s Inside MarketRipple?
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
          Twelve interconnected features that work together to give you a complete picture
          of the Indian market — from pre-market signals to long-term structural trends.
        </p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <article
              key={f.title}
              className="group rounded-xl border border-surface-border/8 bg-surface-card p-5 transition hover:border-surface-border/15 hover:bg-text-primary/[0.02]"
              aria-label={f.title}
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-text-primary/[0.04] border border-surface-border/6">
                  <f.icon className="h-4 w-4 text-violet-400" aria-hidden="true" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted">
                  Feature {String(i + 1).padStart(2, "0")}
                </span>
              </div>
              <h3 className="mt-3 text-sm font-bold text-text-primary">
                {f.href ? (
                  <Link href={f.href} className="underline-offset-4 hover:text-violet-400 hover:underline">
                    {f.title}
                  </Link>
                ) : (
                  f.title
                )}
              </h3>
              <p className="mt-1.5 text-sm leading-5 text-text-muted">{f.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── 7. MarketRipple's intelligence coverage ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Coverage
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          MarketRipple&apos;s Intelligence Coverage
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {COVERAGE.map((c) => (
            <Link
              key={c.label}
              href={c.href}
              className="rounded-xl border border-surface-border/8 bg-surface-card p-5 transition hover:border-surface-border/15 hover:bg-text-primary/[0.02]"
            >
              <c.icon className="h-6 w-6 text-sky-400" aria-hidden="true" />
              <h3 className="mt-3 text-sm font-bold text-text-primary">{c.label}</h3>
              <p className="mt-1.5 text-sm leading-5 text-text-muted">{c.detail}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* ── 8. Why our AI is different ── */}
      <section className="rounded-2xl border border-surface-border/8 bg-surface-card p-8 md:p-10">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Trust
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          Why Our AI Is Different
        </h2>
        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {AI_TRUST.map((t) => (
            <div key={t.title} className="flex gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-surface-border/8 bg-text-primary/[0.03]">
                <t.icon className="h-5 w-5 text-emerald-400" aria-hidden="true" />
              </div>
              <div>
                <h3 className="text-base font-bold text-text-primary">{t.title}</h3>
                <p className="mt-1.5 text-sm leading-6 text-text-secondary">{t.description}</p>
              </div>
            </div>
          ))}
        </div>
        <Link href="/ai-methodology" className="mt-6 inline-flex items-center gap-1 text-sm font-semibold text-violet-400 hover:text-violet-300">
          Read the full AI methodology <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── 9. Who is MarketRipple for? ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Who It&apos;s For
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          Who Is MarketRipple For?
        </h2>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {AUDIENCES.map((a) => (
            <Link
              key={a.title}
              href={a.href}
              className="rounded-xl border border-surface-border/8 bg-surface-card p-5 transition hover:border-surface-border/15 hover:bg-text-primary/[0.02]"
            >
              <a.icon className="h-6 w-6 text-amber-400" aria-hidden="true" />
              <h3 className="mt-3 text-sm font-bold text-text-primary">{a.title}</h3>
              <p className="mt-1.5 text-sm leading-5 text-text-muted">{a.description}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* ── 10. FAQ ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Questions
        </p>
        <h2 className="mt-3 flex items-center gap-2 text-[24px] font-black text-text-primary md:text-[30px]">
          <HelpCircle className="h-6 w-6 text-violet-400" aria-hidden="true" />
          Frequently Asked Questions
        </h2>
        <div className="mt-8 space-y-2">
          {ABOUT_FAQ.map((item) => (
            <details
              key={item.id}
              id={item.id}
              className="group scroll-mt-24 rounded-xl border border-surface-border/7 bg-text-primary/[0.02] px-5 py-4 open:bg-text-primary/[0.035]"
            >
              <summary className="cursor-pointer list-none text-[14px] font-semibold text-text-primary marker:content-none">
                {item.q}
              </summary>
              <p className="mt-2 text-sm leading-6 text-text-secondary">{item.a}</p>
            </details>
          ))}
        </div>
        <Link href="/faq" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-violet-400 hover:text-violet-300">
          See all questions <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── 11. Product Philosophy ── */}
      <section className="rounded-2xl border border-surface-border/8 bg-surface-card p-8 md:p-10">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Product Philosophy
        </p>
        <h2 className="mt-3 text-[24px] font-black text-text-primary md:text-[30px]">
          Principles We Build By
        </h2>
        <div className="mt-8 space-y-6">
          {PHILOSOPHY.map((p, i) => (
            <div key={p.title} className="flex gap-5">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-surface-border/8 bg-text-primary/[0.03]">
                <p.icon className="h-5 w-5 text-sky-400" aria-hidden="true" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted">
                    Principle {i + 1}
                  </span>
                </div>
                <h3 className="mt-0.5 text-base font-bold text-text-primary">{p.title}</h3>
                <p className="mt-1.5 text-sm leading-6 text-text-secondary">{p.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── 12. CTA ── */}
      <section className="rounded-2xl border border-surface-border/8 bg-gradient-to-br from-violet-500/[0.06] to-surface-bg p-8 text-center md:p-12">
        <TrendingUp className="mx-auto h-10 w-10 text-violet-400" aria-hidden="true" />
        <h2 className="mt-4 text-[22px] font-black text-text-primary md:text-[28px]">
          Ready to Understand Your Markets?
        </h2>
        <p className="mt-3 text-sm leading-6 text-text-secondary">
          Explore MarketRipple&apos;s intelligence modules and see how we make sense of
          the Indian market for you.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-6 py-2.5 text-sm font-semibold text-text-primary transition hover:opacity-90"
            aria-label="Start exploring MarketRipple"
          >
            Start Exploring
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
          <Link
            href="/how-it-works"
            className="flex items-center gap-2 rounded-xl border border-surface-border/[0.12] bg-text-primary/[0.04] px-6 py-2.5 text-sm font-semibold text-text-primary transition hover:bg-text-primary/[0.07]"
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
