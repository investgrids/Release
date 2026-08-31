import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import {
  Landmark,
  Scale,
  Activity,
  Brain,
  ShieldCheck,
  ShieldAlert,
  Gauge,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  HelpCircle,
  Clock,
} from "lucide-react";
import { safeJsonLd } from "@/lib/text";

const SITE_URL = "https://www.marketripple.in";
const PAGE_URL = `${SITE_URL}/methodology/marketripple-score`;

export const metadata: Metadata = {
  title: "MarketRipple Score Methodology | Banking V1",
  description:
    "What the MarketRipple Score means, how the four pillars are weighted, what Banking V1 evaluates, and MarketRipple's real evidence-quality and publication requirements.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "MarketRipple Score Methodology | Banking V1",
    description:
      "How the MarketRipple Score is built: four weighted pillars, real verified evidence, and honest publication requirements — Banking V1, the first live methodology.",
    url: PAGE_URL,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

// ── Section wrapper (matches /ai-methodology's own Section component) ──────────
function Section({
  id, badge, badgeColor = "text-text-muted", title, subtitle, children,
}: {
  id: string; badge: string; badgeColor?: string; title: string; subtitle: ReactNode; children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-6">
      <div>
        <p className={`text-[10px] font-bold uppercase tracking-[0.18em] ${badgeColor}`}>{badge}</p>
        <h2 id={id} className="mt-2 text-[20px] font-black text-text-primary md:text-[24px]">{title}</h2>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

// ── Data ─────────────────────────────────────────────────────────────────────
// Every number on this page was checked directly against the real backend
// code on 2026-08-29 (app/services/marketripple_score/): pillar weights
// from engine.py's CANDIDATE_WEIGHTS, rating boundaries from engine.py's
// _label_for() (test-covered, tests/services/test_marketripple_score.py:80-91),
// the 7 real Banking V1 metrics and known-unavailable list from
// financial_strength.py, and the publication policy from eligibility.py's
// BANKING_V1_P1. Nothing here is aspirational or rounded for effect.

const PILLARS = [
  { name: "Financial Strength",   weight: "40%", desc: "Sector-specific financial health and operating performance, built from real, verified regulatory and market data.", icon: <Landmark className="h-5 w-5" />, color: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" },
  { name: "Valuation",            weight: "20%", desc: "Valuation relative to the eligible peer universe for that sector, plus the company's own historical valuation range.", icon: <Scale className="h-5 w-5" />, color: "border-sky-500/25 bg-sky-500/10 text-sky-400" },
  { name: "Market Behaviour",     weight: "15%", desc: "Real, current price behaviour and relative performance.", icon: <Activity className="h-5 w-5" />, color: "border-amber-500/25 bg-amber-500/10 text-amber-400" },
  { name: "Current Intelligence", weight: "25%", desc: "Current evidence from MarketRipple's event and company-intelligence system — published analysis and tracked opportunity signals.", icon: <Brain className="h-5 w-5" />, color: "border-violet-500/25 bg-violet-500/10 text-violet-400" },
];

const BANKING_V1_METRICS = [
  { name: "Gross NPA %", source: "NSE regulatory filing" },
  { name: "Net NPA %", source: "NSE regulatory filing" },
  { name: "CET1 Ratio", source: "NSE regulatory filing" },
  { name: "ROA", source: "NSE regulatory filing" },
  { name: "ROE", source: "Market data" },
  { name: "NII Growth", source: "Market data" },
  { name: "Profit Growth", source: "Market data" },
];

const BANKING_V1_UNAVAILABLE = [
  "CASA Ratio", "Provision Coverage Ratio", "Total CAR", "Deposit Growth", "Advances Growth",
];

const RATINGS = [
  { label: "Strong",   range: "75 – 100", color: "text-emerald-500" },
  { label: "Positive", range: "60 – 74",  color: "text-sky-500" },
  { label: "Neutral",  range: "45 – 59",  color: "text-amber-500" },
  { label: "Cautious", range: "0 – 44",   color: "text-rose-500" },
];

const FAQS = [
  {
    id: "faq-why-not-every-company",
    q: "Why doesn't every company have a MarketRipple Score?",
    a: "MarketRipple Score currently uses Banking V1, the first sector-specific methodology. Companies outside Banking don't have an approved methodology yet, so no unified score is published for them — their real evidence still appears on their Company page under Current Intelligence, just not under the MarketRipple Score name.",
  },
  {
    id: "faq-no-score-shown",
    q: "Why does a bank sometimes show \"MarketRipple Score unavailable\"?",
    a: "A score is only published once a company clears MarketRipple's minimum evidence requirements (see Publication Requirements above). If verified financial data is insufficient, or overall evidence coverage is too thin, MarketRipple does not publish a score for that company rather than publishing one built on weak evidence.",
  },
  {
    id: "faq-coverage-vs-confidence",
    q: "Is evidence coverage the same as confidence?",
    a: "No. Evidence coverage measures how much of the evidence the methodology expects was actually available and eligible when the score was calculated. It says nothing about how certain MarketRipple is in its interpretation — those are two different questions, and MarketRipple doesn't collapse them into one number.",
  },
];

const WEBPAGE_JSONLD = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "MarketRipple Score Methodology",
  url: PAGE_URL,
  description: "How the MarketRipple Score is built: four weighted pillars, real verified evidence, and honest publication requirements — Banking V1, the first live methodology.",
  about: { "@type": "Organization", name: "MarketRipple", url: SITE_URL },
};

const FAQ_JSONLD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQS.map((item) => ({ "@type": "Question", name: item.q, acceptedAnswer: { "@type": "Answer", text: item.a } })),
};

// ── Page ─────────────────────────────────────────────────────────────────────
export default function MarketRippleScoreMethodologyPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(WEBPAGE_JSONLD) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(FAQ_JSONLD) }} />
      <main className="min-w-0 space-y-14 pb-16" aria-label="MarketRipple Score Methodology">

        {/* ── HERO ── */}
        <section aria-labelledby="hero-heading">
          <div className="rounded-2xl border border-surface-border/8 bg-gradient-to-br from-emerald-500/[0.06] to-surface-bg px-8 py-10 md:px-12 md:py-14">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-400">Methodology</p>
            <h1 id="hero-heading" className="mt-3 text-[26px] font-black leading-tight text-text-primary md:text-[36px]">
              What Is the MarketRipple Score?
            </h1>
            <p className="mt-4 max-w-2xl text-[15px] leading-7 text-slate-700 dark:text-white">
              MarketRipple Score is a 0–100 company intelligence score that combines financial strength,
              valuation, market behaviour and current intelligence into a single assessment. MarketRipple
              uses sector-specific financial methodologies and verified market and intelligence data — a
              score is published only once minimum evidence requirements are satisfied.
            </p>
            <div className="mt-6 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] p-4">
              <p className="text-[13px] leading-6 text-text-secondary">
                <span className="font-semibold text-amber-700 dark:text-amber-300">A higher score represents stronger conditions across the factors MarketRipple evaluates.</span>{" "}
                It is not a prediction of future share-price returns and not a buy/sell recommendation.
              </p>
            </div>
          </div>
        </section>

        {/* ── FOUR PILLARS ── */}
        <Section
          id="pillars-heading" badge="The Four Pillars" badgeColor="text-emerald-400"
          title="What makes up the score?"
          subtitle="Every MarketRipple Score is a weighted combination of the same four pillars, whatever the sector — only the Financial Strength pillar's own inputs change between sector methodologies."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {PILLARS.map((p) => (
              <div key={p.name} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <div className="flex items-center justify-between">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-xl border ${p.color}`} aria-hidden="true">{p.icon}</div>
                  <span className="text-[20px] font-black text-text-primary">{p.weight}</span>
                </div>
                <h3 className="mt-3 text-[14px] font-bold text-text-primary">{p.name}</h3>
                <p className="mt-1.5 text-[12.5px] leading-5 text-text-secondary">{p.desc}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* ── BANKING V1 ── */}
        <Section
          id="banking-v1-heading" badge="Currently Available Methodology" badgeColor="text-sky-400"
          title="Banking V1"
          subtitle="MarketRipple Score is live for one sector methodology today: Banking. Other sectors will get their own Financial Strength methodology over time, evaluated on inputs appropriate to that sector — a real estate company is never scored on Net NPA, the same way a bank is never scored on inventory turnover — while keeping the same four-pillar MarketRipple Score framework."
        >
          <div className="grid gap-6 md:grid-cols-2">
            <div className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">7 real inputs, this quarter's latest filing</p>
              <ul className="mt-3 space-y-2">
                {BANKING_V1_METRICS.map((m) => (
                  <li key={m.name} className="flex items-center justify-between text-[13px] text-text-secondary">
                    <span className="font-medium text-text-primary">{m.name}</span>
                    <span className="text-[11px] text-text-muted">{m.source}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">Known gaps, disclosed rather than hidden</p>
              <p className="mt-2 text-[12.5px] leading-5 text-text-secondary">
                Five real, originally-proposed Banking metrics are not yet part of the score — either the
                source doesn&apos;t carry them at all, or there isn&apos;t enough real history yet to compute a
                genuine growth rate:
              </p>
              <ul className="mt-3 flex flex-wrap gap-2">
                {BANKING_V1_UNAVAILABLE.map((m) => (
                  <li key={m} className="rounded-md border border-surface-border/10 bg-text-primary/[0.05] px-2.5 py-1 text-[11px] text-text-muted">{m}</li>
                ))}
              </ul>
            </div>
          </div>
        </Section>

        {/* ── EVIDENCE QUALITY ── */}
        <Section
          id="evidence-quality-heading" badge="Evidence Quality" badgeColor="text-rose-400"
          title="How does MarketRipple validate the data it scores?"
          subtitle="MarketRipple validates source financial data before it becomes eligible for scoring."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl border border-rose-500/25 bg-rose-500/10 text-rose-400" aria-hidden="true"><ShieldAlert className="h-4.5 w-4.5" /></div>
              <h3 className="text-[14px] font-bold text-text-primary">Excluded, never corrected</h3>
              <p className="mt-2 text-[12.5px] leading-5 text-text-secondary">
                A value that fails a quality check is excluded from that score entirely — MarketRipple never
                estimates, corrects, or silently replaces a value it doesn&apos;t trust.
              </p>
            </div>
            <div className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-500/25 bg-emerald-500/10 text-emerald-400" aria-hidden="true"><ShieldCheck className="h-4.5 w-4.5" /></div>
              <h3 className="text-[14px] font-bold text-text-primary">Insufficient evidence, no score</h3>
              <p className="mt-2 text-[12.5px] leading-5 text-text-secondary">
                If too much evidence is excluded, MarketRipple may choose not to publish a score for that
                company at all, rather than publish one built on weak evidence.
              </p>
            </div>
          </div>
        </Section>

        {/* ── EVIDENCE COVERAGE ── */}
        <Section
          id="evidence-coverage-heading" badge="Evidence Coverage" badgeColor="text-indigo-400"
          title={'What does "Evidence coverage" mean?'}
          subtitle=""
        >
          <div className="flex items-start gap-4 rounded-xl border border-indigo-500/20 bg-indigo-500/[0.05] p-6">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-indigo-500/25 bg-indigo-500/10 text-indigo-400" aria-hidden="true"><Gauge className="h-5 w-5" /></div>
            <div>
              <p className="text-[14px] font-bold text-text-primary">Evidence coverage is not a confidence score.</p>
              <p className="mt-2 text-[13px] leading-6 text-text-secondary">
                It indicates how much of the evidence expected by the methodology was available and eligible
                when the score was calculated — not how sure MarketRipple is about its interpretation. A
                company can have high coverage and a low score, or lower coverage and a strong score; the two
                numbers answer different questions.
              </p>
            </div>
          </div>
        </Section>

        {/* ── PUBLICATION REQUIREMENTS ── */}
        <Section
          id="publication-heading" badge="Publication Requirements" badgeColor="text-emerald-400"
          title="When does MarketRipple publish a score?"
          subtitle="For Banking V1, a score is published only once a company clears all of the following."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              { title: "At least 5 of 7 Financial Strength metrics", desc: "A real, verified value for at least five of the seven Banking V1 inputs above." },
              { title: "At least 65% overall evidence coverage", desc: "Enough real evidence across all four pillars combined, not just Financial Strength." },
              { title: "A real, eligible financial reporting period", desc: "At least one recent, verified financial period free of quality issues." },
              { title: "Financial Strength always required", desc: "Every other pillar can tolerate some missing evidence — Financial Strength cannot be absent." },
            ].map((r) => (
              <div key={r.title} className="flex items-start gap-3 rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" />
                <div>
                  <p className="text-[13px] font-bold text-text-primary">{r.title}</p>
                  <p className="mt-1 text-[12px] leading-5 text-text-secondary">{r.desc}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 text-[12.5px] leading-5 text-text-secondary">
            A company that doesn&apos;t clear these requirements shows <span className="font-semibold text-text-primary">&quot;MarketRipple Score unavailable&quot;</span> with
            a plain-language reason — never a score built on evidence MarketRipple doesn&apos;t trust.
          </p>
        </Section>

        {/* ── RATINGS ── */}
        <Section
          id="ratings-heading" badge="Ratings" badgeColor="text-sky-400"
          title="What do the rating labels mean?"
          subtitle="Every published score also carries one of four labels, based on the same 0–100 score."
        >
          <div className="overflow-x-auto rounded-xl border border-surface-border/8">
            <table className="w-full min-w-[420px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-surface-border/8 bg-text-primary/[0.03]">
                  <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-wide text-text-muted">Rating</th>
                  <th className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-wide text-text-muted">Score range</th>
                </tr>
              </thead>
              <tbody>
                {RATINGS.map((r, i) => (
                  <tr key={r.label} className={i < RATINGS.length - 1 ? "border-b border-surface-border/6" : ""}>
                    <td className={`px-4 py-3 align-top text-[13px] font-bold ${r.color}`}>{r.label}</td>
                    <td className="px-4 py-3 align-top text-[13px] text-text-secondary">{r.range}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        {/* ── UPDATE FREQUENCY ── */}
        <section aria-labelledby="frequency-heading">
          <div className="rounded-xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-sky-500/25 bg-sky-500/10 text-sky-400" aria-hidden="true">
                <Clock className="h-6 w-6" />
              </div>
              <div>
                <h2 id="frequency-heading" className="text-xl font-black text-text-primary">How often does the score update?</h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary">
                  Scores are recalculated as underlying MarketRipple data is refreshed. Different components
                  update at different frequencies — Financial Strength changes around financial reporting
                  cycles, Market Behaviour can change much more frequently, and Current Intelligence evolves
                  as new evidence enters MarketRipple.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── DOES / DOES NOT ── */}
        <section className="rounded-2xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
          <h2 className="text-[20px] font-black text-text-primary md:text-[24px]">What the MarketRipple Score Does — and Doesn&apos;t Do</h2>
          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <div>
              <p className="text-[10px] font-black uppercase tracking-wide text-emerald-500">Does</p>
              <ul className="mt-3 space-y-2">
                {["Combine real financial, valuation, market and intelligence evidence into one score", "Disclose how much real evidence went into each score", "Exclude data it can't verify, rather than estimate it", "Withhold publication when evidence is insufficient"].map((d) => (
                  <li key={d} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" aria-hidden="true" />{d}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-wide text-rose-500">Does Not</p>
              <ul className="mt-3 space-y-2">
                {["Predict future share-price returns", "Provide a buy/sell recommendation", "Estimate missing data to complete a score", "Cover every sector yet"].map((d) => (
                  <li key={d} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-500" aria-hidden="true" />{d}
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
            <HelpCircle className="h-5 w-5 text-sky-400" aria-hidden="true" />
            Frequently Asked Questions
          </h2>
          <div className="mt-6 space-y-2">
            {FAQS.map((item) => (
              <details key={item.id} id={item.id} className="group scroll-mt-24 rounded-xl border border-surface-border/7 bg-text-primary/[0.02] px-5 py-4 open:bg-text-primary/[0.035]">
                <summary className="cursor-pointer list-none text-[14px] font-semibold text-text-primary marker:content-none">{item.q}</summary>
                <p className="mt-2 text-sm leading-6 text-text-secondary">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* ── CTA ── */}
        <section aria-label="Related pages" className="rounded-xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Continue Exploring</p>
          <h2 className="mt-2 text-xl font-black text-text-primary">See real MarketRipple Scores</h2>
          <p className="mt-2 text-sm text-text-secondary">
            Browse companies to see a real, published MarketRipple Score and its evidence.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/companies" className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-sky-500 px-5 py-2.5 text-sm font-semibold text-text-primary transition hover:opacity-90">
              <Landmark className="h-4 w-4" />Browse Companies<ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link href="/ai-methodology" className="flex items-center gap-2 rounded-xl border border-surface-border/15 bg-text-primary/[0.04] px-5 py-2.5 text-sm font-semibold text-text-secondary transition hover:border-surface-border/25 hover:text-text-primary">
              <Brain className="h-4 w-4" />How MarketRipple AI Works<ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}
