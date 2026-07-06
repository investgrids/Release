import type { Metadata } from "next";
import Link from "next/link";
import {
  Check,
  X,
  Database,
  Lightbulb,
  FlaskConical,
  Globe,
  Landmark,
  TrendingUp,
  Users,
  CalendarDays,
  ArrowRight,
  Building2,
  ArrowDown,
  ChevronRight,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Why MarketRipple — Beyond Traditional Market Platforms",
  description:
    "Discover why MarketRipple is different from traditional market data platforms. We explain news, connect events, and surface opportunities — built specifically for Indian markets.",
  openGraph: {
    title: "Why MarketRipple — Beyond Traditional Market Platforms",
    description:
      "MarketRipple goes beyond data aggregation to deliver structured market intelligence with explainable AI, built for India's unique equity ecosystem.",
  },
};

// ── Data ──────────────────────────────────────────────────────────────────────

const TRADITIONAL = [
  "Shows headlines — no context or analysis",
  "Displays price changes — no causal explanation",
  "Renders standard OHLCV charts",
  "Lists data points in isolation",
  "Passive consumption — you find the signal",
  "Generic global templates applied to India",
];

const MARKETRIPPLE_FEATURES = [
  "Explains news with AI impact analysis and sector tagging",
  "Connects events — traces why prices moved and what's next",
  "Visualises Ripple Effects across sectors and companies",
  "Discovers relationships between events, sectors, and stocks",
  "Surfaces investment opportunities via Opportunity Radar",
  "Uses Explainable AI — reasoning shown for every output",
  "Built ground-up for BSE, NSE, RBI, SEBI, and Indian macro",
];

const PHILOSOPHY = [
  {
    icon: Database,
    title: "From Data to Intelligence",
    description:
      "Data is raw numbers and headlines. Intelligence is understanding why RBI's rate decision compresses NBFC margins, which specific companies are exposed, and what the historical precedent suggests. MarketRipple bridges that gap — taking market data and transforming it into structured, actionable intelligence.",
    accent: "violet",
  },
  {
    icon: Lightbulb,
    title: "From Events to Opportunities",
    description:
      "Every market event creates winners and losers. A Union Budget announcement on infrastructure capex benefits RVNL, NCC, and KNR Constructions — while hurting competing capital allocation. MarketRipple's Opportunity Radar algorithmically identifies which companies stand to gain or lose from every classified event.",
    accent: "sky",
  },
  {
    icon: FlaskConical,
    title: "From AI to Explainable AI",
    description:
      "Black-box AI is dangerous for investment decisions. MarketRipple shows its work — every ripple relationship comes with a dependency type (commodity chain, sector contagion, currency effect), confidence score, and supporting evidence. You always know why the AI reached its conclusion.",
    accent: "emerald",
  },
];

const INDIA_REASONS = [
  {
    icon: Building2,
    label: "BSE & NSE Ecosystem",
    description:
      "Deep knowledge of 5,000+ listed companies, sector-specific index behaviour, circuit breaker mechanics, F&O expiry dynamics, and NSE/BSE-specific market microstructure.",
  },
  {
    icon: Landmark,
    label: "SEBI Regulations",
    description:
      "Real-time tracking of SEBI circulars, insider trading disclosures, promoter pledge data, mutual fund mandate changes, and regulatory actions that move specific stocks.",
  },
  {
    icon: Globe,
    label: "RBI Monetary Policy",
    description:
      "Structured analysis of MPC decisions, repo rate impacts, CRR/SLR changes, liquidity operations, and their sector-specific effects on banking, NBFC, and rate-sensitive companies.",
  },
  {
    icon: Users,
    label: "FII & DII Flows",
    description:
      "Daily institutional flow intelligence — connecting FII selling in financials to specific derivative positions, or DII buying in pharma to sector rotation signals with historical context.",
  },
  {
    icon: CalendarDays,
    label: "Budget & Policy Cycles",
    description:
      "India's unique annual Union Budget, interim budgets, state budgets, and quarterly policy reviews create predictable event cycles. MarketRipple tracks and analyses each with sector-specific impact mapping.",
  },
  {
    icon: TrendingUp,
    label: "Sector-Specific Knowledge",
    description:
      "From PLI scheme beneficiaries to agrochemical monsoon sensitivity, from IT sector US-recession exposure to power sector renewable capacity additions — MarketRipple speaks Indian market.",
  },
];

// ── RBI Example Chain ─────────────────────────────────────────────────────────

const RIPPLE_CHAIN = [
  {
    sector: "Banking",
    impact: "Negative",
    detail: "NIM compression as deposit repricing outpaces lending rate hikes in near term",
    companies: ["HDFC Bank", "ICICI Bank", "SBI"],
    score: 8.4,
  },
  {
    sector: "Real Estate & Housing Finance",
    impact: "Negative",
    detail: "Home loan EMIs rise 8–12% — dampening affordability and new loan demand",
    companies: ["DLF", "LIC Housing Finance", "Can Fin Homes"],
    score: 7.9,
  },
  {
    sector: "NBFCs",
    impact: "Negative",
    detail: "Funding costs rise as commercial paper rates track repo; spread compression",
    companies: ["Bajaj Finance", "Cholamandalam", "Shriram Finance"],
    score: 7.2,
  },
  {
    sector: "IT Services",
    impact: "Mixed",
    detail: "INR weakens vs USD on rate differential narrowing — positive for dollar revenue companies",
    companies: ["Infosys", "TCS", "Wipro"],
    score: 5.1,
  },
];

const IMPACT_STYLE: Record<string, { pill: string; dot: string }> = {
  Negative: { pill: "bg-rose-500/10 text-rose-300 border-rose-500/20", dot: "bg-rose-400" },
  Positive: { pill: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20", dot: "bg-emerald-400" },
  Mixed: { pill: "bg-amber-500/10 text-amber-300 border-amber-500/20", dot: "bg-amber-400" },
};

const PHILOSOPHY_ACCENT: Record<string, { bg: string; border: string; icon: string }> = {
  violet: { bg: "bg-violet-500/[0.06]", border: "border-violet-500/20", icon: "text-violet-400" },
  sky:    { bg: "bg-sky-500/[0.06]",    border: "border-sky-500/20",    icon: "text-sky-400"    },
  emerald:{ bg: "bg-emerald-500/[0.06]",border: "border-emerald-500/20",icon: "text-emerald-400"},
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function WhyMarketRipplePage() {
  return (
    <main className="min-w-0 space-y-16 pb-20">
      {/* ── Hero ── */}
      <section className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#0d1028] to-[#080c14] p-8 md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-sky-400">
          Why MarketRipple
        </p>
        <h1 className="mt-4 text-[28px] font-black leading-tight text-white md:text-[42px]">
          The Market Intelligence Platform
          <br />
          <span className="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">
            Built Different
          </span>
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300 md:text-lg">
          Traditional platforms give you data. MarketRipple gives you intelligence. There&apos;s a
          fundamental difference between seeing that markets fell 2% and understanding
          that RBI&apos;s surprise rate action compressed NBFC spreads, triggered FII outflows
          from financials, and created a specific dip-buying opportunity in quality NBFCs
          — all within seconds of the announcement.
        </p>
      </section>

      {/* ── Comparison Table ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          The Difference
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          Traditional Platforms vs MarketRipple
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {/* Traditional */}
          <div className="rounded-xl border border-white/[0.06] bg-[#080c14] overflow-hidden">
            <div className="border-b border-white/[0.06] bg-white/[0.02] px-6 py-4">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                Traditional Platforms
              </p>
              <p className="mt-1 text-lg font-bold text-slate-400">Data Aggregators</p>
            </div>
            <ul className="divide-y divide-white/[0.04] px-6" aria-label="Traditional platform features">
              {TRADITIONAL.map((item) => (
                <li key={item} className="flex items-start gap-3 py-4">
                  <X
                    className="mt-0.5 h-4 w-4 shrink-0 text-slate-600"
                    aria-hidden="true"
                  />
                  <span className="text-sm leading-5 text-slate-500">{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* MarketRipple */}
          <div className="rounded-xl border border-violet-500/30 bg-[#080c14] overflow-hidden">
            <div className="border-b border-violet-500/20 bg-gradient-to-r from-violet-600/20 to-sky-600/20 px-6 py-4">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-400">
                MarketRipple
              </p>
              <p className="mt-1 text-lg font-bold text-white">Market Intelligence</p>
            </div>
            <ul className="divide-y divide-white/[0.04] px-6" aria-label="MarketRipple features">
              {MARKETRIPPLE_FEATURES.map((item) => (
                <li key={item} className="flex items-start gap-3 py-4">
                  <Check
                    className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400"
                    aria-hidden="true"
                  />
                  <span className="text-sm leading-5 text-slate-300">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── Philosophy Gap ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          The Philosophy Gap
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          Three Shifts That Change Everything
        </h2>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {PHILOSOPHY.map((p) => {
            const a = PHILOSOPHY_ACCENT[p.accent];
            return (
              <article
                key={p.title}
                className={`rounded-xl border p-6 ${a.bg} ${a.border}`}
                aria-label={p.title}
              >
                <p.icon className={`h-6 w-6 ${a.icon}`} aria-hidden="true" />
                <h3 className="mt-4 text-base font-bold text-white">{p.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">{p.description}</p>
              </article>
            );
          })}
        </div>
      </section>

      {/* ── Real Example ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Real Example
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          See the Difference in Action
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          The same event. Two completely different levels of understanding.
        </p>

        <div className="mt-8 rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-5 md:p-6">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-400">
            The Event
          </p>
          <p className="mt-2 text-xl font-black text-white">
            RBI raises interest rates by 50 bps — Emergency MPC Meeting
          </p>
          <p className="mt-1 text-sm text-slate-400">Surprise off-cycle monetary policy action</p>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {/* Traditional */}
          <div className="rounded-xl border border-white/[0.06] bg-[#080c14] p-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
              Traditional Platform
            </p>
            <div className="mt-4 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <p className="text-sm font-semibold text-slate-300">
                &ldquo;RBI Hikes Rates 50 bps — Markets React&rdquo;
              </p>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                The Reserve Bank of India raised the repo rate by 50 basis points in an
                emergency meeting. Nifty fell 1.2%. Bank Nifty declined 2.1%.
              </p>
            </div>
            <div className="mt-4 space-y-2">
              {[
                "No sector breakdown",
                "No company-level impact",
                "No cause-effect chain",
                "No opportunity identification",
              ].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <X className="h-3.5 w-3.5 shrink-0 text-slate-600" aria-hidden="true" />
                  <span className="text-xs text-slate-500">{item}</span>
                </div>
              ))}
            </div>
          </div>

          {/* MarketRipple */}
          <div className="rounded-xl border border-violet-500/20 bg-[#080c14] p-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-400">
              MarketRipple Intelligence
            </p>
            <div className="mt-4 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Ripple Engine — Impact Chain
              </p>
              {RIPPLE_CHAIN.map((item, i) => {
                const s = IMPACT_STYLE[item.impact];
                return (
                  <div key={item.sector}>
                    {i > 0 && (
                      <div className="flex justify-center py-0.5">
                        <ArrowDown
                          className="h-3.5 w-3.5 text-slate-700"
                          aria-hidden="true"
                        />
                      </div>
                    )}
                    <article
                      className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3"
                      aria-label={`${item.sector} impact`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-white">
                          {item.sector}
                        </span>
                        <div className="flex items-center gap-2">
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${s.pill}`}
                          >
                            {item.impact}
                          </span>
                          <span className="text-[10px] font-bold text-slate-500">
                            {item.score}
                          </span>
                        </div>
                      </div>
                      <p className="mt-1 text-[11px] leading-4 text-slate-500">
                        {item.detail}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {item.companies.map((c) => (
                          <span
                            key={c}
                            className="rounded border border-white/[0.06] bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-400"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </article>
                  </div>
                );
              })}
              <div className="mt-2 rounded-lg border border-emerald-500/20 bg-emerald-500/[0.05] p-3">
                <div className="flex items-center gap-2">
                  <div
                    className="h-1.5 w-1.5 rounded-full bg-emerald-400"
                    aria-hidden="true"
                  />
                  <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-300">
                    Opportunity Identified
                  </span>
                </div>
                <p className="mt-1.5 text-[11px] leading-4 text-slate-300">
                  Quality NBFCs with diversified funding (SBI Cards, Muthoot Finance) — limited
                  CP exposure, premium valuation compression creates entry opportunity.
                  Opportunity Score: 74/100
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Why India ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Built for India
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          Why MarketRipple Is Designed for Indian Markets
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          Indian equity markets have unique dynamics that generic global platforms
          fundamentally misunderstand. MarketRipple is built from the ground up for India&apos;s
          market structure, regulatory environment, and capital flow patterns.
        </p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {INDIA_REASONS.map((r) => (
            <article
              key={r.label}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5 transition hover:border-white/[0.14]"
              aria-label={r.label}
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03]">
                <r.icon className="h-4 w-4 text-sky-400" aria-hidden="true" />
              </div>
              <h3 className="mt-3 text-sm font-bold text-white">{r.label}</h3>
              <p className="mt-1.5 text-sm leading-5 text-slate-500">{r.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#0a0d1a] to-[#080c14] p-8 text-center md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-sky-400">
          Next Step
        </p>
        <h2 className="mt-3 text-[22px] font-black text-white md:text-[28px]">
          See How the Intelligence Is Built
        </h2>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          Understand the technology pipeline behind MarketRipple — from breaking news to
          investment opportunity in seconds.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-4">
          <Link
            href="/how-it-works"
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-violet-600 px-6 py-2.5 text-sm font-semibold text-white transition hover:opacity-90"
            aria-label="See how MarketRipple works"
          >
            How It Works
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
          <Link
            href="/how-marketripple-thinks"
            className="flex items-center gap-2 rounded-xl border border-white/[0.12] bg-white/[0.04] px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[0.07]"
            aria-label="Learn how MarketRipple thinks"
          >
            How MarketRipple Thinks
            <ChevronRight className="h-4 w-4 text-slate-400" aria-hidden="true" />
          </Link>
        </div>
      </section>
    </main>
  );
}
