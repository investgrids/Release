import type { Metadata } from "next";
import Link from "next/link";
import {
  Radio,
  Brain,
  Tag,
  Waves,
  GitFork,
  Building2,
  BookOpen,
  Radar,
  Search,
  Cpu,
  Database,
  Network,
  ArrowRight,
  ChevronRight,
  CheckCircle2,
} from "lucide-react";

export const metadata: Metadata = {
  title: "How MarketRipple Works — AI Market Intelligence Pipeline",
  description:
    "Discover the full pipeline behind MarketRipple — from breaking news ingestion through AI analysis, Ripple Engine processing, and Opportunity Radar scoring to surfacing investment opportunities in seconds.",
  openGraph: {
    title: "How MarketRipple Works — AI Market Intelligence Pipeline",
    description:
      "From breaking news to investment opportunity in seconds. See how MarketRipple's AI pipeline transforms raw market events into actionable intelligence for Indian investors.",
  },
};

// ── Data ──────────────────────────────────────────────────────────────────────

const STEPS = [
  {
    number: "01",
    icon: Radio,
    title: "Breaking News Ingestion",
    tagline: "500+ sources. Real-time. Always on.",
    description:
      "MarketRipple's data pipeline monitors over 500 sources across global and Indian financial media — including NSE/BSE corporate filings, RBI press releases, SEBI circulars, Ministry of Finance notifications, PIB announcements, Reuters, Bloomberg feeds, and premium Indian financial news services.",
    details: [
      "NSE/BSE corporate disclosures and exchange filings",
      "RBI press releases and MPC meeting minutes",
      "SEBI circulars and regulatory announcements",
      "Global macro feeds: Fed, ECB, commodity markets",
      "Indian financial news: ET, Mint, Business Standard",
    ],
    accent: "violet",
    time: "< 15 seconds",
    timeLabel: "Ingestion latency",
  },
  {
    number: "02",
    icon: Brain,
    title: "AI Analysis",
    tagline: "LLMs extract signal from noise.",
    description:
      "Large Language Models trained on Indian financial data analyse each ingested item. The AI extracts key entities (companies, sectors, commodities, currencies), assesses market relevance, generates a human-readable summary, and assigns a confidence score based on source credibility, event novelty, and impact precedent.",
    details: [
      "Named entity recognition for stocks, sectors, and commodities",
      "Impact magnitude estimation (High / Medium / Low / Negligible)",
      "Source credibility scoring and cross-reference verification",
      "Duplicate detection and event deduplication across sources",
      "Confidence score assignment with supporting evidence",
    ],
    accent: "sky",
    time: "< 8 seconds",
    timeLabel: "Analysis latency",
  },
  {
    number: "03",
    icon: Tag,
    title: "Market Event Classification",
    tagline: "Every event gets a structured identity.",
    description:
      "The raw news item is transformed into a structured Market Event with classification metadata. MarketRipple classifies events by type, tags affected sectors and companies, estimates impact duration, and assigns an initial impact score — making every event queryable and comparable.",
    details: [
      "Event type: Monetary / Fiscal / Geopolitical / Earnings / Regulatory / Corporate",
      "Sector tagging: primary and secondary sector effects",
      "Company tagging: direct and indirect company exposure",
      "Impact duration: Short-term (< 1 week) / Medium / Long-term (> 6 months)",
      "Geographic scope: India-specific / Global with India exposure",
    ],
    accent: "amber",
    time: "Structured",
    timeLabel: "Event format",
  },
  {
    number: "04",
    icon: Waves,
    title: "Ripple Engine Processing",
    tagline: "Cause-effect chains across 700+ relationship types.",
    description:
      "MarketRipple's proprietary Ripple Engine is the core differentiator. It traces cause-effect relationships from every market event across seven dependency types, mapping how one event creates cascading effects across the Indian market ecosystem — with confidence scores on every relationship edge.",
    details: [
      "Commodity chain dependencies (crude oil → paint, aviation, logistics)",
      "Currency effects (INR/USD movement → IT exports, import-heavy sectors)",
      "Sector contagion (banking stress → NBFC, real estate, consumer credit)",
      "Policy responses (rate hike → bond yields → insurance, pension funds)",
      "Corporate earnings impact (raw material price → margin compression)",
      "Global capital flows (FII risk-off → mid/small cap, emerging market premium)",
      "Market sentiment shifts (event narrative → sector rotation triggers)",
    ],
    accent: "violet",
    time: "700+",
    timeLabel: "Relationship types",
  },
  {
    number: "05",
    icon: GitFork,
    title: "Market Dependency Graph",
    tagline: "The invisible connections made visible.",
    description:
      "A force-directed knowledge graph visualises how one event creates cascading effects across markets, sectors, and companies. Each node is a market entity (sector, company, commodity, currency). Each edge is a typed dependency with direction, magnitude, and confidence score — forming a queryable intelligence graph.",
    details: [
      "Nodes: companies, sectors, commodities, currencies, policy instruments",
      "Edges: 7 dependency types with direction and magnitude",
      "Confidence scores on every graph relationship",
      "Historical validation against 3+ years of Indian market data",
      "Real-time updates as new events are processed",
    ],
    accent: "sky",
    time: "Live Graph",
    timeLabel: "Intelligence network",
  },
  {
    number: "06",
    icon: Building2,
    title: "Company Identification",
    tagline: "Specific stocks. Specific reasons.",
    description:
      "AI identifies specific BSE/NSE-listed companies affected by each event, categorised by exposure type. Direct exposure means a company's revenues or costs are immediately impacted. Indirect means sector spillover. Thematic means long-term structural change to the business model or competitive position.",
    details: [
      "Direct exposure: earnings, margins, revenue directly affected",
      "Indirect exposure: sector spillover, input cost changes, demand shifts",
      "Thematic exposure: long-term structural change to business model",
      "Promoter / institutional holding context for price reaction prediction",
      "F&O activity and derivative positioning as confirmation signals",
    ],
    accent: "emerald",
    time: "3 layers",
    timeLabel: "Exposure depth",
  },
  {
    number: "07",
    icon: BookOpen,
    title: "Story Synthesis",
    tagline: "Multi-event narratives become investment themes.",
    description:
      "The AI synthesises multiple related events into coherent investment narratives — Stories. A Story connects 5–15 related events into a chronological theme (e.g., India's EV transition, NBFC credit cycle, IT sector re-rating) with a timeline, affected companies, opportunity score, and risk assessment.",
    details: [
      "Automatic event clustering by theme and sector coherence",
      "Timeline construction with key milestone events",
      "Compound opportunity scoring across the event cluster",
      "Risk factors extracted from contrarian evidence in the cluster",
      "Time horizon estimation: Short / Medium / Long-term thesis",
    ],
    accent: "violet",
    time: "5–15 events",
    timeLabel: "Per story",
  },
  {
    number: "08",
    icon: Radar,
    title: "Opportunity Radar Scoring",
    tagline: "0–100. Evidence-based. Explained.",
    description:
      "The Opportunity Radar scoring algorithm evaluates the investment opportunity strength of every market event and story on a 0–100 scale. The score combines event impact magnitude, AI confidence, sector momentum, volume of corroborating events, and historical precedent from similar past events.",
    details: [
      "Event impact weight: primary contributor to raw score",
      "AI confidence multiplier: penalises uncertain or low-evidence events",
      "Sector momentum factor: aligned with or against sector trend",
      "Corroboration bonus: score increases with multiple confirming events",
      "Historical precedent: similar events' actual outcome backtesting",
    ],
    accent: "amber",
    time: "0–100",
    timeLabel: "Opportunity score",
  },
  {
    number: "09",
    icon: Search,
    title: "AI Search Interface",
    tagline: "Ask anything. Get sourced answers.",
    description:
      "Users can query the entire MarketRipple intelligence graph in natural language via the AI Search interface. Queries like &lsquo;Which IT companies are exposed to US recession risk?&rsquo; or &lsquo;What sectors benefit if crude oil falls to $70?&rsquo; return instant, sourced answers — grounded in MarketRipple&apos;s knowledge graph, not hallucination.",
    details: [
      "Natural language query over the full intelligence graph",
      "Company screening: 'Which stocks benefit from rupee depreciation?'",
      "Event analysis: 'How did markets react to last RBI rate hike?'",
      "Sector queries: 'What are the key risks to Indian IT sector in 2025?'",
      "All answers include source events and evidence citations",
    ],
    accent: "sky",
    time: "< 3 sec",
    timeLabel: "Query response",
  },
] as const;

const TECH_CARDS = [
  {
    icon: Cpu,
    title: "AI Models",
    description:
      "Domain-adapted Large Language Models fine-tuned on Indian financial data — SEBI filings, RBI reports, earnings transcripts, and 3+ years of BSE/NSE market events. Combined with retrieval-augmented generation (RAG) to ground every output in real market data.",
    stat: "15-min",
    statLabel: "Intelligence refresh cycle",
    accent: "violet",
  },
  {
    icon: Database,
    title: "Data Pipeline",
    description:
      "Real-time ingestion from 500+ financial data sources with deduplication, entity normalisation, and quality scoring. The pipeline handles structured data (exchange filings, regulatory databases) and unstructured text (news, press releases, social signals) in a unified processing architecture.",
    stat: "500+",
    statLabel: "Sources monitored",
    accent: "sky",
  },
  {
    icon: Network,
    title: "Graph Engine",
    description:
      "A dynamic market knowledge graph with 700+ typed relationship edges covering Indian market dependencies. The graph is updated in real-time as events are processed, enabling fast graph traversal queries for ripple analysis, sector contagion mapping, and company exposure scoring.",
    stat: "700+",
    statLabel: "Market relationship types",
    accent: "emerald",
  },
];

const ACCENT: Record<string, { bg: string; border: string; icon: string; pill: string; number: string }> = {
  violet: {
    bg: "bg-violet-500/[0.05]",
    border: "border-violet-500/25",
    icon: "text-violet-400",
    pill: "bg-violet-500/15 text-violet-300 border-violet-500/25",
    number: "text-violet-500",
  },
  sky: {
    bg: "bg-sky-500/[0.05]",
    border: "border-sky-500/25",
    icon: "text-sky-400",
    pill: "bg-sky-500/15 text-sky-300 border-sky-500/25",
    number: "text-sky-500",
  },
  amber: {
    bg: "bg-amber-500/[0.05]",
    border: "border-amber-500/25",
    icon: "text-amber-400",
    pill: "bg-amber-500/15 text-amber-300 border-amber-500/25",
    number: "text-amber-500",
  },
  emerald: {
    bg: "bg-emerald-500/[0.05]",
    border: "border-emerald-500/25",
    icon: "text-emerald-400",
    pill: "bg-emerald-500/15 text-emerald-300 border-emerald-500/25",
    number: "text-emerald-500",
  },
};

const TECH_ACCENT: Record<string, { border: string; icon: string; stat: string }> = {
  violet: { border: "border-violet-500/20", icon: "text-violet-400", stat: "text-violet-300" },
  sky:    { border: "border-sky-500/20",    icon: "text-sky-400",    stat: "text-sky-300"    },
  emerald:{ border: "border-emerald-500/20",icon: "text-emerald-400",stat: "text-emerald-300"},
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function HowItWorksPage() {
  return (
    <main className="min-w-0 space-y-16 pb-20">
      {/* ── Hero ── */}
      <section className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#0d1028] to-[#080c14] p-8 md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-400">
          How It Works
        </p>
        <h1 className="mt-4 text-[28px] font-black leading-tight text-white md:text-[42px]">
          From Breaking News to
          <br />
          <span className="bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">
            Investment Opportunity
          </span>
          <br />
          in Seconds
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300 md:text-lg">
          MarketRipple operates a multi-stage AI intelligence pipeline — continuously ingesting
          market events, running them through analysis and classification, tracing ripple
          effects across the market graph, and surfacing scored opportunities — all within
          seconds of any market-moving event in India or globally.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          {[
            { label: "9-Stage Pipeline", color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" },
            { label: "Real-time Processing", color: "border-sky-500/30 bg-sky-500/10 text-sky-300" },
            { label: "Explainable AI", color: "border-violet-500/30 bg-violet-500/10 text-violet-300" },
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

      {/* ── Pipeline ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          The Intelligence Pipeline
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          9 Steps from News to Opportunity
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          Every market event flows through each stage of the pipeline — producing
          richer, more structured intelligence at each step.
        </p>

        <div className="mt-10 space-y-0">
          {STEPS.map((step, index) => {
            const a = ACCENT[step.accent];
            const isLast = index === STEPS.length - 1;
            return (
              <div key={step.number} className="relative">
                {/* Connector line */}
                {!isLast && (
                  <div
                    className="absolute left-6 top-[72px] z-0 h-[calc(100%-16px)] w-px bg-gradient-to-b from-white/10 to-transparent md:left-8"
                    aria-hidden="true"
                  />
                )}

                <article
                  className={`relative z-10 mb-4 rounded-xl border p-5 md:p-6 ${a.bg} ${a.border}`}
                  aria-label={`Step ${step.number}: ${step.title}`}
                >
                  <div className="flex gap-4 md:gap-5">
                    {/* Step icon column */}
                    <div className="flex flex-col items-center gap-2 shrink-0">
                      <div className={`flex h-12 w-12 items-center justify-center rounded-xl border ${a.border} bg-[#080c14]`}>
                        <step.icon className={`h-5 w-5 ${a.icon}`} aria-hidden="true" />
                      </div>
                    </div>

                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`text-[10px] font-black tracking-[0.18em] ${a.number}`}>
                          STEP {step.number}
                        </span>
                        <span
                          className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${a.pill}`}
                        >
                          {step.time}
                        </span>
                        <span className="text-[10px] text-slate-600">{step.timeLabel}</span>
                      </div>
                      <h3 className="mt-1.5 text-base font-black text-white md:text-lg">
                        {step.title}
                      </h3>
                      <p className={`text-xs font-semibold ${a.icon} mt-0.5`}>
                        {step.tagline}
                      </p>
                      <p className="mt-3 text-sm leading-6 text-slate-400">
                        {step.description}
                      </p>
                      <ul
                        className="mt-4 grid gap-1.5 sm:grid-cols-2"
                        aria-label={`${step.title} details`}
                      >
                        {step.details.map((detail) => (
                          <li key={detail} className="flex items-start gap-2">
                            <CheckCircle2
                              className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${a.icon} opacity-70`}
                              aria-hidden="true"
                            />
                            <span className="text-xs leading-5 text-slate-500">{detail}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </article>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Technology ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Technology
        </p>
        <h2 className="mt-3 text-[24px] font-black text-white md:text-[30px]">
          What Powers the Pipeline
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
          Three technology layers working together to deliver real-time market intelligence
          at institutional quality.
        </p>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {TECH_CARDS.map((card) => {
            const ta = TECH_ACCENT[card.accent];
            return (
              <article
                key={card.title}
                className={`rounded-xl border bg-[#080c14] p-6 ${ta.border}`}
                aria-label={card.title}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03]">
                    <card.icon className={`h-5 w-5 ${ta.icon}`} aria-hidden="true" />
                  </div>
                  <div className="text-right">
                    <p className={`text-xl font-black ${ta.stat}`}>{card.stat}</p>
                    <p className="text-[10px] text-slate-600">{card.statLabel}</p>
                  </div>
                </div>
                <h3 className="mt-4 text-base font-bold text-white">{card.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">{card.description}</p>
              </article>
            );
          })}
        </div>
      </section>

      {/* ── Pipeline Summary ── */}
      <section className="rounded-2xl border border-white/[0.08] bg-[#080c14] p-6 md:p-8">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Pipeline Summary
        </p>
        <h2 className="mt-3 text-lg font-black text-white">
          From Raw News to Structured Opportunity
        </h2>
        <div className="mt-6 flex flex-wrap items-center gap-2 text-sm">
          {[
            { label: "News", color: "bg-slate-700 text-slate-300" },
            { label: "AI Analysis", color: "bg-violet-500/20 text-violet-300" },
            { label: "Classification", color: "bg-sky-500/20 text-sky-300" },
            { label: "Ripple Engine", color: "bg-violet-500/20 text-violet-300" },
            { label: "Graph Build", color: "bg-sky-500/20 text-sky-300" },
            { label: "Company Tagging", color: "bg-emerald-500/20 text-emerald-300" },
            { label: "Story Synthesis", color: "bg-violet-500/20 text-violet-300" },
            { label: "Opportunity Score", color: "bg-amber-500/20 text-amber-300" },
            { label: "AI Search Ready", color: "bg-emerald-500/20 text-emerald-300" },
          ].map((stage, i, arr) => (
            <div key={stage.label} className="flex items-center gap-2">
              <span className={`rounded-lg px-3 py-1 text-xs font-semibold ${stage.color}`}>
                {stage.label}
              </span>
              {i < arr.length - 1 && (
                <ArrowRight
                  className="h-3 w-3 shrink-0 text-slate-700"
                  aria-hidden="true"
                />
              )}
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-slate-600">
          Total pipeline latency: under 60 seconds from source publication to fully enriched,
          scored, and searchable intelligence.
        </p>
      </section>

      {/* ── CTA ── */}
      <section className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#0a0d1a] to-[#080c14] p-8 text-center md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-400">
          Go Deeper
        </p>
        <h2 className="mt-3 text-[22px] font-black text-white md:text-[28px]">
          Understand How MarketRipple Thinks
        </h2>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          Explore the AI reasoning models, evidence standards, and confidence calibration
          that power every output on MarketRipple.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-4">
          <Link
            href="/how-marketripple-thinks"
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-sky-600 px-6 py-2.5 text-sm font-semibold text-white transition hover:opacity-90"
            aria-label="Learn how MarketRipple thinks and reasons"
          >
            How MarketRipple Thinks
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
          <Link
            href="/events"
            className="flex items-center gap-2 rounded-xl border border-white/[0.12] bg-white/[0.04] px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[0.07]"
            aria-label="See live market events"
          >
            See Live Events
            <ChevronRight className="h-4 w-4 text-slate-400" aria-hidden="true" />
          </Link>
        </div>
      </section>
    </main>
  );
}
