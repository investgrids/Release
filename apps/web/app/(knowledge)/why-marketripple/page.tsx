import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import {
  Check,
  Database,
  Lightbulb,
  FlaskConical,
  Landmark,
  TrendingUp,
  Users,
  CalendarDays,
  ArrowRight,
  Building2,
  ArrowDown,
  ChevronRight,
  HelpCircle,
  Layers,
  Link2,
  Radar,
  Search,
  ShieldCheck,
} from "lucide-react";
import { safeJsonLd } from "@/lib/text";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Why MarketRipple Is Different | AI Market Intelligence for India",
  description:
    "See how MarketRipple connects market events, sectors, companies and historical patterns to deliver explainable AI market intelligence for Indian investors.",
  alternates: { canonical: `${SITE_URL}/why-marketripple` },
  openGraph: {
    title: "Why MarketRipple Is Different | AI Market Intelligence for India",
    description:
      "MarketRipple connects market events to sectors, companies, historical patterns and opportunities — with the evidence behind every conclusion.",
    url: `${SITE_URL}/why-marketripple`,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

// ── Data ──────────────────────────────────────────────────────────────────────
// Verified against the real backend, 2026-08-11. Corrections from the
// previous version: "all within seconds of the announcement" removed (real
// cadence is a 5–15 minute scheduled cycle, not literal real-time — same
// finding as /how-it-works and /ai-methodology). "F&O expiry dynamics,"
// "promoter pledge data," "mutual fund mandate changes," "insider trading
// disclosures," and "CRR/SLR changes" as tracked signal categories were
// removed — none exist as real, implemented signals anywhere in the
// codebase (CRR appears once, inside a single historical narrative string,
// not as a tracked category). The RBI rate-hike ripple example is now
// explicitly labelled an illustrative example, not live data — it wasn't
// labelled at all in the previous version.

const WORKFLOW = ["Event", "Impact", "Sector", "Company", "Historical Pattern", "Opportunity / Risk", "Evidence"];

const DIFFERENTIATORS = [
  { icon: Layers, title: "Context Instead of Isolated Data", description: "An event is shown with what it affects, not just what happened." },
  { icon: Link2, title: "Connections Instead of Disconnected Information", description: "Events, sectors, and companies are linked through a real relationship graph." },
  { icon: ShieldCheck, title: "Evidence Instead of Black-Box AI", description: "Every conclusion carries the fact and reasoning behind it, clearly separated." },
];

const COMPARISON_ROWS = [
  { traditional: "Market data", ripple: "Market intelligence" },
  { traditional: "Headlines", ripple: "Event context" },
  { traditional: "Price movement", ripple: "Impact explanation" },
  { traditional: "Isolated information", ripple: "Connected relationships" },
  { traditional: "Manual signal discovery", ripple: "Intelligence-driven discovery" },
  { traditional: "Generic analysis", ripple: "Indian-market context" },
  { traditional: "Limited reasoning", ripple: "Explainable analysis" },
  { traditional: "Data consumption", ripple: "Research workflow" },
];

const PHILOSOPHY = [
  {
    icon: Database,
    title: "From Data to Intelligence",
    description:
      "Data tells you what happened. Market intelligence explains why it happened, what it affects, which sectors are exposed, which companies may be affected, and what historical patterns show.",
    accent: "violet",
  },
  {
    icon: Lightbulb,
    title: "From Events to Opportunities",
    description:
      "MarketRipple evaluates events for potential company and sector implications and surfaces opportunities or risks when the available evidence supports them — not every event automatically becomes an opportunity.",
    accent: "sky",
  },
  {
    icon: FlaskConical,
    title: "From AI to Explainable AI",
    description:
      "Every conclusion distinguishes Fact (what the data shows), AI Interpretation (the model's read of it), Historical Evidence (verified precedent), and Prediction (a probabilistic outlook, never certainty).",
    accent: "emerald",
  },
];

const INDIA_REASONS = [
  {
    icon: Building2,
    label: "Indian Exchanges",
    description:
      "The Indian market has 5,000+ listed companies across BSE/NSE — MarketRipple actively tracks 512 of them in depth, with real filings, index behaviour, and market microstructure specific to Indian exchanges.",
    href: "/companies",
  },
  {
    icon: Landmark,
    label: "RBI & Monetary Policy",
    description:
      "MPC decisions, repo rate changes, and other RBI announcements are ingested as real events and connected to banking, NBFC, and rate-sensitive companies through the Ripple Engine.",
    href: "/calendar",
  },
  {
    icon: ShieldCheck,
    label: "SEBI & Regulation",
    description:
      "SEBI circulars and regulatory announcements are ingested as real events and classified for market-wide or sector-specific relevance.",
    href: undefined,
  },
  {
    icon: Users,
    label: "FII/DII Flows",
    description:
      "Institutional flow data is tracked as part of MarketRipple's real-time market intelligence, giving sector-level context alongside events.",
    href: "/market-intelligence",
  },
  {
    icon: CalendarDays,
    label: "Union & State Budgets",
    description:
      "India's Union Budget, interim budgets, and state budgets create real, dated events on the Economic Calendar, each analysed for sector-specific impact.",
    href: "/calendar",
  },
  {
    icon: TrendingUp,
    label: "Indian Sector Dynamics",
    description:
      "Events are classified against real Indian sector categories — Banking, IT, Pharma, Energy, and more — not a generic global sector taxonomy.",
    href: "/sectors",
  },
];

const RIPPLE_CHAIN = [
  { sector: "Banking", impact: "Negative", detail: "NIM compression as deposit repricing outpaces lending rate hikes in the near term", companies: ["HDFC Bank", "ICICI Bank", "SBI"] },
  { sector: "Real Estate & Housing Finance", impact: "Negative", detail: "Home loan EMIs may rise, potentially dampening affordability and new loan demand", companies: ["DLF", "LIC Housing Finance"] },
  { sector: "NBFCs", impact: "Negative", detail: "Funding costs may rise as commercial paper rates track the repo rate", companies: ["Bajaj Finance", "Cholamandalam"] },
  { sector: "IT Services", impact: "Mixed", detail: "A weaker rupee on rate-differential narrowing can be positive for dollar-revenue companies", companies: ["Infosys", "TCS"] },
];

const IMPACT_STYLE: Record<string, string> = {
  Negative: "bg-rose-500/10 text-rose-600 dark:text-rose-300 border-rose-500/20",
  Positive: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 border-emerald-500/20",
  Mixed: "bg-amber-500/10 text-amber-600 dark:text-amber-300 border-amber-500/20",
};

const PHILOSOPHY_ACCENT: Record<string, { bg: string; border: string; icon: string }> = {
  violet: { bg: "bg-violet-500/[0.06]", border: "border-violet-500/20", icon: "text-violet-400" },
  sky: { bg: "bg-sky-500/[0.06]", border: "border-sky-500/20", icon: "text-sky-400" },
  emerald: { bg: "bg-emerald-500/[0.06]", border: "border-emerald-500/20", icon: "text-emerald-400" },
};

const DOES: string[] = ["Organize market information", "Connect events and companies", "Explain potential impact", "Surface historical context", "Show evidence", "Provide confidence indicators", "Identify potential opportunities and risks"];
const DOES_NOT: string[] = ["Guarantee returns", "Predict markets with certainty", "Replace investor judgment", "Provide guaranteed buy/sell outcomes"];

const FAQS = [
  { id: "what-is", q: "What is MarketRipple?", a: "MarketRipple is an AI-powered market intelligence platform for Indian investors. It connects market events to sectors, companies, historical patterns and potential opportunities or risks, while showing the evidence and reasoning behind its analysis." },
  { id: "different", q: "How is MarketRipple different from traditional financial platforms?", a: "Traditional platforms show market data — prices, headlines, charts. MarketRipple connects that data into intelligence: why an event matters, which sectors and companies it may affect, what history suggests, and the evidence behind the conclusion." },
  { id: "analyze", q: "How does MarketRipple analyze market events?", a: "Each event is classified by type, sector, and company exposure. AI extracts the relevant entities and assesses relevance, then the Ripple Engine connects the event to potentially affected sectors and companies through real relationship types." },
  { id: "identify-companies", q: "How does MarketRipple identify affected companies?", a: "Companies are identified through direct exposure (named in the event), indirect exposure (sector or supply-chain spillover), or thematic exposure (longer-term structural change), combined with available market data for context." },
  { id: "ripple", q: "What is Ripple Intelligence?", a: "Ripple Intelligence traces how a market event may affect other companies and sectors beyond the obvious one, through 7 defined relationship types, each carrying a confidence indicator — not a guarantee that every traced effect will materialise." },
  { id: "radar", q: "What is Opportunity Radar?", a: "Opportunity Radar organizes potential opportunity signals from a transparent, count-based formula — how many corroborating events, companies, and sectors are involved in a developing situation. It's an intelligence signal, not a guaranteed return." },
  { id: "historical", q: "How does MarketRipple use historical patterns?", a: "Current events are compared against a library of 24 verified historical market events (2008–2024) where a genuinely similar precedent exists, adding real context. Historical patterns provide context, not a guarantee of future returns." },
  { id: "explain-ai", q: "How does MarketRipple explain AI decisions?", a: "Every conclusion separates Fact (what the data shows) from AI Interpretation (the model's read), with a confidence score attached. See the AI & Methodology page for the full scoring breakdown." },
  { id: "advisory", q: "Is MarketRipple an investment advisory platform?", a: "No. MarketRipple is a market research and intelligence tool. It does not replace the personalised advice of a SEBI-registered investment advisor, and all investment decisions remain the user's responsibility." },
  { id: "recommendations", q: "Does MarketRipple provide buy or sell recommendations?", a: "No. MarketRipple surfaces potential opportunities and risks with the evidence behind them — it does not issue buy or sell recommendations or guarantee any outcome." },
  { id: "updates", q: "How often is MarketRipple intelligence updated?", a: "News and exchange sources are polled every 15 minutes, regulatory sources hourly, with article generation running on a 5-minute cycle — a scheduled cadence, not continuous real-time streaming." },
];

const FAQ_JSONLD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQS.map((item) => ({ "@type": "Question", name: item.q, acceptedAnswer: { "@type": "Answer", text: item.a } })),
};

const WEBPAGE_JSONLD = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "Why MarketRipple Is Different",
  url: `${SITE_URL}/why-marketripple`,
  description: "How MarketRipple connects market events, sectors, companies and historical patterns to deliver explainable AI market intelligence for Indian investors.",
  about: { "@type": "Organization", name: "MarketRipple", url: SITE_URL },
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function WhyMarketRipplePage() {
  return (
    <main className="min-w-0 space-y-14 pb-20">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(WEBPAGE_JSONLD) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(FAQ_JSONLD) }} />

      {/* ── Hero ── */}
      <section className="rounded-2xl border border-surface-border/8 bg-gradient-to-br from-violet-500/[0.06] to-surface-bg p-8 md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-sky-400">Why MarketRipple</p>
        <h1 className="mt-4 text-[26px] font-black leading-tight text-text-primary md:text-[38px]">
          Why MarketRipple Is Different: AI Market Intelligence for Indian Investors
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-text-secondary">
          MarketRipple is an AI-powered market intelligence platform for Indian investors. It
          connects market events to sectors, companies, historical patterns and potential
          opportunities or risks, while showing the evidence and reasoning behind its analysis.
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-2">
          {WORKFLOW.map((step, i, arr) => (
            <span key={step} className="flex items-center gap-2">
              <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary">{step}</span>
              {i < arr.length - 1 && <ArrowRight className="h-3 w-3 shrink-0 text-text-muted" aria-hidden="true" />}
            </span>
          ))}
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          {DIFFERENTIATORS.map((d) => (
            <div key={d.title} className="rounded-xl border border-surface-border/8 bg-surface-card p-4">
              <d.icon className="h-5 w-5 text-violet-400" aria-hidden="true" />
              <p className="mt-2 text-[13px] font-bold text-text-primary">{d.title}</p>
              <p className="mt-1 text-xs leading-5 text-text-muted">{d.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── What Is MarketRipple? ── */}
      <section>
        <h2 className="text-[20px] font-black text-text-primary md:text-[24px]">What Is MarketRipple?</h2>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
          MarketRipple is an AI-powered market intelligence platform focused on Indian equity
          markets. It monitors market-moving events, analyses their potential impact, connects
          them to affected sectors and companies, and adds historical context and evidence —
          turning raw events into structured, explainable intelligence.
        </p>
      </section>

      {/* ── Comparison ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">The Difference</p>
        <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">
          How Is MarketRipple Different From Traditional Stock-Market Platforms?
        </h2>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
          Generic financial platforms may not fully reflect the structure, regulatory
          environment, and market-specific relationships of Indian equities. MarketRipple was
          built around them from the start.
        </p>
        <div className="mt-7 overflow-x-auto rounded-xl border border-surface-border/8">
          <table className="w-full min-w-[520px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-surface-border/8 bg-text-primary/[0.03]">
                <th className="px-5 py-3 text-left text-[11px] font-bold uppercase tracking-wide text-text-muted">Traditional Financial Platforms</th>
                <th className="px-5 py-3 text-left text-[11px] font-bold uppercase tracking-wide text-violet-400">MarketRipple</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON_ROWS.map((row, i) => (
                <tr key={row.traditional} className={i < COMPARISON_ROWS.length - 1 ? "border-b border-surface-border/6" : ""}>
                  <td className="px-5 py-3 align-top text-text-muted">{row.traditional}</td>
                  <td className="px-5 py-3 align-top text-text-primary">
                    <div className="flex items-start gap-2">
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" aria-hidden="true" />
                      {row.ripple}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Three Shifts ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">How MarketRipple Turns Events Into Intelligence</p>
        <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">Three Shifts That Change Everything</h2>
        <div className="mt-7 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {PHILOSOPHY.map((p) => {
            const a = PHILOSOPHY_ACCENT[p.accent];
            return (
              <article key={p.title} className={`rounded-xl border p-6 ${a.bg} ${a.border}`}>
                <p.icon className={`h-6 w-6 ${a.icon}`} aria-hidden="true" />
                <h3 className="mt-4 text-base font-bold text-text-primary">{p.title}</h3>
                <p className="mt-2 text-sm leading-6 text-text-secondary">{p.description}</p>
              </article>
            );
          })}
        </div>
        <p className="max-w-2xl text-sm leading-6 text-text-secondary">
          The chain is: Event → Classification → Impact → Sector → Company → Historical Context →
          Opportunity/Risk → Evidence. Explore the full mechanism on{" "}
          <Link href="/how-it-works" className="underline decoration-dotted underline-offset-2 hover:text-violet-400">how it works</Link>.
        </p>
      </section>

      {/* ── Opportunity Radar ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Opportunities &amp; Risks</p>
        <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">How Does MarketRipple Identify Opportunities and Risks?</h2>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
          Opportunity Radar organizes potential opportunity signals by combining available event
          impact, corroborating events, and the breadth of companies and sectors involved in a
          developing situation. It is an intelligence signal, not a guaranteed return or
          investment recommendation.
        </p>
        <Link href="/opportunity-radar" className="inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
          <Radar className="h-4 w-4" aria-hidden="true" /> Explore Opportunity Radar <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Historical Patterns ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Historical Context</p>
        <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">How Does MarketRipple Use Historical Patterns?</h2>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
          Current events are compared against a library of 24 verified historical market events
          (2008–2024) where a genuinely similar precedent exists. Historical patterns provide
          context, not a guarantee of future returns.
        </p>
        <Link href="/historical" className="inline-flex items-center gap-1 text-sm font-semibold text-sky-400 hover:text-sky-300">
          View historical patterns <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Explainable AI ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Trust</p>
        <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">How Does MarketRipple Make AI Explainable?</h2>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
          Every conclusion is shown with its evidence — Fact, AI Interpretation, and, where
          relevant, historical precedent — never a bare, unexplained claim. Company-impact
          analysis is grounded in real fetched price data before generation, and deterministic
          validators check every draft afterward.
        </p>
        <Link href="/ai-methodology" className="inline-flex items-center gap-1 text-sm font-semibold text-violet-400 hover:text-violet-300">
          <Search className="h-4 w-4" aria-hidden="true" /> Read the AI &amp; Methodology page <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Illustrative Example ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">What Does the Difference Look Like in Practice?</p>
        <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">The Same Event, Two Levels of Understanding</h2>
        <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/[0.06] px-3 py-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-hidden="true" />
          <p className="text-[11px] font-bold uppercase tracking-wide text-amber-700 dark:text-amber-300">Illustrative Example — Not Live Data</p>
        </div>

        <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-5 md:p-6">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-400">The Event (Hypothetical)</p>
          <p className="mt-2 text-xl font-black text-text-primary">RBI raises interest rates by 50 bps — emergency MPC meeting</p>
          <p className="mt-1 text-sm text-text-secondary">A worked example to show how MarketRipple's reasoning differs from a headline alone.</p>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-surface-border/6 bg-surface-card p-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Traditional Platform</p>
            <div className="mt-4 rounded-lg border border-surface-border/6 bg-text-primary/[0.02] p-4">
              <p className="text-sm font-semibold text-text-secondary">&ldquo;RBI Hikes Rates 50 bps — Markets React&rdquo;</p>
              <p className="mt-2 text-xs leading-5 text-text-muted">The Reserve Bank of India raised the repo rate by 50 basis points. Nifty fell 1.2%. Bank Nifty declined 2.1%.</p>
            </div>
          </div>

          <div className="rounded-xl border border-violet-500/20 bg-surface-card p-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-400">MarketRipple-Style Analysis</p>
            <div className="mt-4 space-y-3">
              {RIPPLE_CHAIN.map((item, i) => (
                <div key={item.sector}>
                  {i > 0 && <div className="flex justify-center py-0.5"><ArrowDown className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" /></div>}
                  <article className="rounded-lg border border-surface-border/6 bg-text-primary/[0.02] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-text-primary">{item.sector}</span>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${IMPACT_STYLE[item.impact]}`}>{item.impact}</span>
                    </div>
                    <p className="mt-1 text-[11px] leading-4 text-text-muted">{item.detail}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {item.companies.map((c) => (
                        <span key={c} className="rounded border border-surface-border/6 bg-text-primary/[0.03] px-2 py-0.5 text-[10px] text-text-secondary">{c}</span>
                      ))}
                    </div>
                  </article>
                </div>
              ))}
            </div>
          </div>
        </div>
        <p className="mt-3 max-w-2xl text-xs leading-5 text-text-muted">
          This example illustrates MarketRipple&apos;s reasoning pattern, not a real, live analysis
          of a specific past event. For real intelligence, see{" "}
          <Link href="/events" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">live events</Link>.
        </p>
      </section>

      {/* ── Why India ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Built for India</p>
        <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">Why Is MarketRipple Built for Indian Markets?</h2>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
          Indian equity markets have their own structure, regulatory environment, and
          market-specific relationships. MarketRipple is built around the real sources and
          categories that reflect that.
        </p>
        <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {INDIA_REASONS.map((r) => (
            <article key={r.label} className="rounded-xl border border-surface-border/8 bg-surface-card p-5 transition hover:border-surface-border/[0.14]">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-surface-border/8 bg-text-primary/[0.03]">
                <r.icon className="h-4 w-4 text-sky-400" aria-hidden="true" />
              </div>
              <h3 className="mt-3 text-sm font-bold text-text-primary">
                {r.href ? <Link href={r.href} className="underline decoration-dotted underline-offset-2 hover:text-violet-400">{r.label}</Link> : r.label}
              </h3>
              <p className="mt-1.5 text-sm leading-5 text-text-muted">{r.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── Does / Doesn't ── */}
      <section className="rounded-2xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
        <h2 className="text-[20px] font-black text-text-primary md:text-[24px]">What MarketRipple Does — and Doesn&apos;t Do</h2>
        <div className="mt-6 grid gap-5 sm:grid-cols-2">
          <div>
            <p className="text-[10px] font-black uppercase tracking-wide text-emerald-500">Does</p>
            <ul className="mt-3 space-y-2">
              {DOES.map((d) => (
                <li key={d} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
                  <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" aria-hidden="true" />{d}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-[10px] font-black uppercase tracking-wide text-rose-500">Does Not</p>
            <ul className="mt-3 space-y-2">
              {DOES_NOT.map((d) => (
                <li key={d} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" aria-hidden="true" />{d}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Questions</p>
        <h2 className="mt-3 flex items-center gap-2 text-[20px] font-black text-text-primary md:text-[24px]">
          <HelpCircle className="h-5 w-5 text-violet-400" aria-hidden="true" /> Frequently Asked Questions
        </h2>
        <div className="mt-7 space-y-2">
          {FAQS.map((item) => (
            <details key={item.id} id={item.id} className="group scroll-mt-24 rounded-xl border border-surface-border/7 bg-text-primary/[0.02] px-5 py-4 open:bg-text-primary/[0.035]">
              <summary className="cursor-pointer list-none text-[14px] font-semibold text-text-primary marker:content-none">{item.q}</summary>
              <p className="mt-2 text-sm leading-6 text-text-secondary">{item.a}</p>
            </details>
          ))}
        </div>
        <Link href="/faq" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-violet-400 hover:text-violet-300">
          See all questions <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── CTA ── */}
      <section className="rounded-2xl border border-surface-border/8 bg-gradient-to-br from-surface-card to-surface-bg p-8 text-center md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-sky-400">Next Step</p>
        <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">Explore MarketRipple Intelligence</h2>
        <p className="mt-3 max-w-xl mx-auto text-sm leading-6 text-text-secondary">
          See the intelligence pipeline in action across live events, Ripple Intelligence, and Opportunity Radar.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Link href="/ai-search" className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-violet-600 px-5 py-2.5 text-sm font-semibold text-text-primary transition hover:opacity-90">
            <Search className="h-4 w-4" />AI Search<ArrowRight className="h-3.5 w-3.5" />
          </Link>
          <Link href="/events" className="flex items-center gap-2 rounded-xl border border-surface-border/[0.12] bg-text-primary/[0.04] px-5 py-2.5 text-sm font-semibold text-text-primary transition hover:bg-text-primary/[0.07]">
            Events<ChevronRight className="h-3.5 w-3.5 text-text-secondary" />
          </Link>
          <Link href="/ripple" className="flex items-center gap-2 rounded-xl border border-surface-border/[0.12] bg-text-primary/[0.04] px-5 py-2.5 text-sm font-semibold text-text-primary transition hover:bg-text-primary/[0.07]">
            Ripple Intelligence<ChevronRight className="h-3.5 w-3.5 text-text-secondary" />
          </Link>
          <Link href="/opportunity-radar" className="flex items-center gap-2 rounded-xl border border-surface-border/[0.12] bg-text-primary/[0.04] px-5 py-2.5 text-sm font-semibold text-text-primary transition hover:bg-text-primary/[0.07]">
            Opportunity Radar<ChevronRight className="h-3.5 w-3.5 text-text-secondary" />
          </Link>
        </div>
      </section>
    </main>
  );
}
