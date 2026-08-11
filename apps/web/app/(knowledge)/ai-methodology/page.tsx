import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import {
  Search,
  Network,
  Target,
  BookOpen,
  ShieldAlert,
  UserCheck,
  Brain,
  GitMerge,
  Filter,
  TrendingUp,
  Clock,
  BarChart2,
  Layers,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Database,
  Zap,
  Sigma,
  ShieldCheck,
  Copy,
  Scale,
  History,
  Activity,
  HelpCircle,
  Landmark,
  Newspaper,
  Waves,
} from "lucide-react";
import { safeJsonLd } from "@/lib/text";

const SITE_URL = "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "How MarketRipple AI Works | Intelligence, Evidence & Scoring",
  description:
    "How MarketRipple's AI Search, Ripple Engine, and scoring actually work — real methodology, evidence, and honest limitations.",
  alternates: { canonical: `${SITE_URL}/ai-methodology` },
  openGraph: {
    title: "How MarketRipple AI Works | Intelligence, Evidence & Scoring",
    description:
      "How MarketRipple's AI Search, Ripple Engine, Opportunity Radar and confidence scoring actually work — with real methodology and honest limitations.",
    url: `${SITE_URL}/ai-methodology`,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

// ── Section wrapper ─────────────────────────────────────────────────────────
function Section({
  id,
  badge,
  badgeColor = "text-text-muted",
  title,
  subtitle,
  children,
}: {
  id: string;
  badge: string;
  badgeColor?: string;
  title: string;
  subtitle: ReactNode;
  children: ReactNode;
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

function StatTile({ label, value, sub, color = "text-text-primary" }: { label: string; value: string; sub: string; color?: string }) {
  return (
    <div className="rounded-xl border border-surface-border/8 bg-surface-card px-4 py-3">
      <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">{label}</p>
      <p className={`mt-1 text-2xl font-black ${color}`}>{value}</p>
      <p className="mt-0.5 text-[11px] text-text-muted">{sub}</p>
    </div>
  );
}

// ── Data ──────────────────────────────────────────────────────────────────────
// Every claim below was checked against the real backend on 2026-08-11.
// Three corrections from the previous version of this page, all confirmed
// by tracing the actual code path (not just grepping for a plausible name):
//   - AI Search: the previous page claimed the query is "embedded into
//     vector space" and matched by "semantic similarity." No embedding or
//     vector-search code exists anywhere in app/services/ai_search/ — real
//     retrieval (_search_events/_search_news/_search_policies) is
//     entity/keyword matching against the knowledge graph. Corrected.
//   - Ripple Engine confidence: the previous page claimed "Bayesian
//     inference combining Source Reliability × Historical Accuracy ×
//     Analyst Consensus × Recency Weight." No Bayesian inference exists.
//     The real mechanism (intelligence_graph_service.py) is a stored
//     per-edge confidence value (default 0.8) multiplicatively attenuated
//     as it propagates through the graph — simpler, but real, and it's
//     what the "Cascade Simulation" step already correctly described.
//   - Opportunity Radar: the previous "Event Impact / AI Confidence /
//     Sector Momentum / Historical Precedent / Time Sensitivity" formula
//     does not match the real, live-called scoring function
//     (app.pipeline.opportunity_generator._score_opportunity) — a
//     transparent heuristic built from real signal counts (corroborating
//     events, company breadth, sector breadth), not a multi-factor
//     AI-weighted model. Corrected to describe the real formula, matching
//     the same correction made on /how-it-works for consistency.
// Kept unchanged because independently verified accurate: the 8-factor
// confidence score (confidence_service.py), the fact-grounding validators
// (fact_grounding.py, shipped this session), the 4-level ripple cascade
// depth (ripple_graph.py's max_depth=4), and the 512/24/7 headline stats.

const METHODOLOGY_TABLE = [
  { system: "AI Search", input: "User query + market data", processing: "Entity/intent matching → knowledge graph retrieval → AI synthesis", output: "Sourced answer" },
  { system: "Ripple Engine", input: "Events + relationship graph", processing: "Multi-level dependency propagation, confidence attenuated per hop", output: "Impact cascade" },
  { system: "Opportunity Radar", input: "Events + companies + sectors", processing: "Signal-density scoring engine", output: "Opportunity score (0–99)" },
  { system: "Confidence Engine", input: "Evidence signals (sources, market/sector confirmation, precedent)", processing: "8-factor point-based scoring", output: "Confidence score (0–100)" },
  { system: "AI Newsroom", input: "Events + companies + real price data", processing: "Generation + deterministic fact-grounding validation", output: "Published article" },
];

const AI_SEARCH_STEPS = [
  {
    step: "1",
    icon: <Search className="h-4 w-4" />,
    title: "Intent Understanding",
    detail: "Entities (companies, sectors, events, time periods) and query intent (comparison, trend, causal) are extracted from the question.",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/25",
  },
  {
    step: "2",
    icon: <Database className="h-4 w-4" />,
    title: "Intelligence Retrieval",
    detail: (
      <>
        Extracted entities are matched against MarketRipple&apos;s{" "}
        <Link href="/ripple" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">
          knowledge graph
        </Link>{" "}
        of real event-company-sector relationships to find relevant events, companies, and sectors.
      </>
    ),
    color: "text-sky-400 bg-sky-500/10 border-sky-500/25",
  },
  {
    step: "3",
    icon: <Filter className="h-4 w-4" />,
    title: "Evidence Assembly",
    detail: "Supporting evidence is gathered from the matched events, sources, and any relevant historical precedent.",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/25",
  },
  {
    step: "4",
    icon: <BookOpen className="h-4 w-4" />,
    title: "AI Synthesis",
    detail: "The retrieved evidence is synthesised into an answer grounded in that real data — not a generic model response.",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/25",
  },
];

const RIPPLE_STEPS = [
  {
    number: "01",
    icon: <Network className="h-5 w-5" />,
    title: "Graph Construction",
    description: "MarketRipple maintains a knowledge graph with nodes for events, companies, sectors, commodities, and currencies. Edges represent 7 real relationship types, each carrying a stored confidence value.",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    number: "02",
    icon: <Layers className="h-5 w-5" />,
    title: "Relationship Detection",
    description: (
      <>
        New events are matched against real, verified{" "}
        <Link href="/historical" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">
          historical market events (2008–2024)
        </Link>{" "}
        and existing graph structure to identify which relationships are economically meaningful.
      </>
    ),
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    number: "03",
    icon: <Waves className="h-5 w-5" />,
    title: "Cascade Propagation",
    description: "Effects propagate through the dependency graph up to 4 levels deep. Each hop's confidence is attenuated by that edge's own confidence value, so distant, indirect effects are shown with visibly lower confidence than direct ones.",
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  },
  {
    number: "04",
    icon: <Zap className="h-5 w-5" />,
    title: "Graph Updates",
    description: "New events trigger graph re-evaluation on MarketRipple's regular processing cycle — not instantaneously, but on the same schedule described below in \"How frequently is intelligence updated?\"",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
];

const OPPORTUNITY_FACTORS = [
  { factor: "Event Impact", icon: <Zap className="h-4 w-4" />, description: "The number of real, corroborating events feeding into a developing situation — more independently confirming events raise the score.", color: "text-violet-400" },
  { factor: "Company Breadth", icon: <Target className="h-4 w-4" />, description: "How many real companies are identified as exposed to the situation.", color: "text-sky-400" },
  { factor: "Sector Breadth", icon: <TrendingUp className="h-4 w-4" />, description: "How many sectors the situation spans — a multi-sector theme scores higher than a single, narrow one.", color: "text-emerald-400" },
];

const CONFIDENCE_FACTORS = [
  { icon: <CheckCircle2 className="h-5 w-5" />, factor: "Source Count", points: "0–15 pts", detail: "Distinct trusted sources behind the claim. More independent sources confirming the same fact raises confidence.", color: "text-violet-400 bg-violet-500/10 border-violet-500/20" },
  {
    icon: <BarChart2 className="h-5 w-5" />, factor: "Historical Precedent", points: "0–25 pts — the single largest factor",
    detail: (<>How many similar events exist in MarketRipple&apos;s library of <Link href="/historical" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">24 verified historical events (2008–2024)</Link>, and how accurate past reads of those events turned out to be.</>),
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  { icon: <TrendingUp className="h-5 w-5" />, factor: "Market Confirmation", points: "0–20 pts", detail: "Whether sectors or indices are already moving in the expected direction — real-time confirmation from the market itself.", color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
  { icon: <Layers className="h-5 w-5" />, factor: "Sector Confirmation", points: "0–15 pts", detail: "Whether sector peers are independently confirming the same trend, beyond the specific company or event analysed.", color: "text-sky-400 bg-sky-500/10 border-sky-500/20" },
  { icon: <Target className="h-5 w-5" />, factor: "Macro Alignment", points: "0–15 pts", detail: "Whether the read is consistent with the prevailing macro regime — rates, inflation, growth — rather than fighting it.", color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20" },
  { icon: <Zap className="h-5 w-5" />, factor: "Company Sensitivity", points: "0–10 pts", detail: "How directly and predictably this company's fundamentals respond to this event type.", color: "text-rose-400 bg-rose-500/10 border-rose-500/20" },
  { icon: <Brain className="h-5 w-5" />, factor: "AI Self-Certainty", points: "0–10 pts", detail: "The model's own calibrated certainty rating — one signal among many, never allowed to dominate the score alone.", color: "text-violet-400 bg-violet-500/10 border-violet-500/20" },
  { icon: <AlertTriangle className="h-5 w-5" />, factor: "Volatility Adjustment", points: "−10 to +5 pts", detail: "A penalty in turbulent markets, a small bonus in calm ones — the same evidence supports a firmer conclusion when conditions are stable.", color: "text-amber-400 bg-amber-500/10 border-amber-500/20" },
];

const FACT_GROUNDING_CHECKS = [
  { icon: <Copy className="h-5 w-5" />, title: "Shared-Reason Detection", description: "Flags the same boilerplate causal reason reused near word-for-word (≥90% text match) across two different companies in the same article.", color: "text-violet-400 bg-violet-500/10 border-violet-500/20" },
  { icon: <Scale className="h-5 w-5" />, title: "Sentiment/Magnitude Consistency", description: "Checks each company's stated impact tag against its real fetched price move. A ±2% or larger move tagged \"neutral,\" or a move opposite the stated tag, is flagged.", color: "text-rose-400 bg-rose-500/10 border-rose-500/20" },
  { icon: <History className="h-5 w-5" />, title: "Status-Tense Consistency", description: "Compares the article's language against the source event's own language to catch a draft regulation described as finalized, or vice versa.", color: "text-sky-400 bg-sky-500/10 border-sky-500/20" },
];

const DATA_SOURCE_GROUPS = [
  { icon: Landmark, title: "Market Data", items: "Live equity prices, index levels", href: "/market-intelligence" },
  { icon: ShieldCheck, title: "Events & Filings", items: "NSE/BSE filings, RBI, SEBI, PIB", href: "/events" },
  { icon: Newspaper, title: "News", items: "Economic Times, Moneycontrol, Business Standard, Livemint, NDTV Profit", href: "/newsroom" },
  { icon: History, title: "Historical Data", items: "24 verified events, 2008–2024", href: "/historical" },
  { icon: Brain, title: "AI / Reasoning", items: "Multi-provider LLM fallback chain", href: "/how-it-works" },
  { icon: Network, title: "Derived Intelligence", items: "The Ripple graph, opportunity and confidence scores", href: "/ripple" },
];

const LIMITATIONS = [
  { icon: <AlertTriangle className="h-5 w-5" />, title: "No Certainty in Market Prediction", description: "MarketRipple analyses probabilities and historical patterns. It cannot predict market movements with certainty. Treat high-confidence signals as strong hypotheses, not facts.", severity: "high" },
  { icon: <Database className="h-5 w-5" />, title: "Public Information Only", description: "Analysis is based exclusively on publicly available information — filings, market data, news, and official announcements. MarketRipple has no access to private or insider information.", severity: "medium" },
  { icon: <BarChart2 className="h-5 w-5" />, title: "Novel Situations Lack Precedent", description: "Historical patterns are the foundation of confidence scoring. In genuinely unprecedented events, confidence scores will be lower — as they should be.", severity: "medium" },
  { icon: <Sigma className="h-5 w-5" />, title: "Confidence Scores Are Estimates", description: "Confidence percentages are calibrated uncertainty, not statistical guarantees. A 75% confidence signal will be wrong roughly 25% of the time.", severity: "high" },
  { icon: <Clock className="h-5 w-5" />, title: "Not Instantaneous", description: "News and exchange sources are polled on a fixed schedule, not streamed live. For intraday trading decisions, always verify against primary sources.", severity: "medium" },
];

const FAQS = [
  { id: "search", q: "How does MarketRipple's AI search work?", a: "A natural-language question is matched against MarketRipple's own event, company, and sector data through entity and intent matching — not vector embeddings — and an AI model synthesises a sourced answer from what's retrieved. Answers cite the underlying events." },
  { id: "connect", q: "How does MarketRipple connect events to companies?", a: "Events are matched to companies either directly (the company is named in the event) or through the Ripple Engine's relationship graph, which connects an event's sector or commodity to a company through one of 7 defined relationship types." },
  { id: "ripple-calc", q: "How does the Ripple Engine calculate relationships?", a: "Each relationship (edge) in the graph carries a stored confidence value. When an event's effects propagate through the graph — up to 4 levels deep — that confidence is multiplicatively attenuated at each hop, so distant effects are shown with visibly lower confidence than direct ones." },
  { id: "opportunity-calc", q: "How is an Opportunity Radar score calculated?", a: "From a transparent, count-based formula: a base score plus credit for the number of corroborating events, the breadth of companies involved, and the breadth of sectors involved, capped at 99. It's a real signal-density measure, not a guaranteed return." },
  { id: "confidence-calc", q: "How is MarketRipple's confidence score calculated?", a: "A point-based sum across 8 real evidence signals — source count, historical precedent (the largest factor), market confirmation, sector confirmation, macro alignment, company sensitivity, AI self-certainty, and a volatility adjustment — capped at 100." },
  { id: "historical", q: "Does MarketRipple use historical market data?", a: "Yes — MarketRipple compares current events against a set of 24 verified historical market events (2008–2024) where a genuinely similar precedent exists. This is the single largest factor in the confidence score, but it provides context, not a guarantee of future returns." },
  { id: "hallucinations", q: "How does MarketRipple prevent AI hallucinations?", a: "Company-impact analysis is grounded in real fetched price data before generation, and deterministic (non-AI) validators check every draft afterward for shared boilerplate reasons, sentiment tags that contradict the real price move, and status mismatches — before anything publishes." },
  { id: "advice", q: "Is MarketRipple's analysis financial advice?", a: "No. MarketRipple is a market research and intelligence tool. It does not replace the personalised advice of a SEBI-registered investment advisor, and all investment decisions remain the user's responsibility." },
  { id: "frequency", q: "How frequently is MarketRipple intelligence updated?", a: "News and exchange sources are polled every 15 minutes, and regulatory sources hourly. Article generation runs on a 5-minute cycle over newly classified events. This is a scheduled cadence, not literal real-time streaming." },
  { id: "explained", q: "How are MarketRipple's AI outputs explained?", a: "Every AI Newsroom article carries an Evidence section split into Fact — what happened, sources, historical outcomes — and AI Interpretation — the model's own read, clearly labelled as such." },
];

const FAQ_JSONLD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQS.map((item) => ({ "@type": "Question", name: item.q, acceptedAnswer: { "@type": "Answer", text: item.a } })),
};

const WEBPAGE_JSONLD = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "How MarketRipple AI Works",
  url: `${SITE_URL}/ai-methodology`,
  description: "How MarketRipple's AI Search, Ripple Engine, Opportunity Radar and confidence scoring actually work — with real methodology, evidence, and honest limitations.",
  about: { "@type": "Organization", name: "MarketRipple", url: SITE_URL },
};

// ── Page ───────────────────────────────────────────────────────────────────────
export default function AIMethodologyPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(WEBPAGE_JSONLD) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(FAQ_JSONLD) }} />
      <main className="min-w-0 space-y-14 pb-16" aria-label="AI Methodology">

        {/* ── HERO + DIRECT ANSWER ── */}
        <section aria-labelledby="hero-heading">
          <div className="rounded-2xl border border-surface-border/8 bg-gradient-to-br from-sky-500/[0.06] to-surface-bg px-8 py-10 md:px-12 md:py-14">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-sky-400">AI &amp; Methodology</p>
            <h1 id="hero-heading" className="mt-3 text-[26px] font-black leading-tight text-text-primary md:text-[36px]">
              How MarketRipple AI Works: Market Intelligence, Evidence &amp; Scoring
            </h1>
            <p className="mt-4 max-w-2xl text-[15px] leading-7 text-slate-700 dark:text-white">
              MarketRipple is an AI-powered market intelligence platform for Indian investors. It
              connects market events to sectors, companies, historical patterns, and opportunities
              using real market data, evidence, and structured intelligence.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="Companies Tracked" value="512" sub="Curated NSE-listed universe" color="text-violet-400" />
              <StatTile label="Historical Events" value="24" sub="Verified events, 2008–2024" color="text-sky-400" />
              <StatTile label="Relationship Types" value="7" sub="Causal edge categories" color="text-emerald-400" />
              <StatTile label="Cascade Depth" value="4 levels" sub="Upstream to downstream" color="text-amber-400" />
            </div>
          </div>
        </section>

        {/* ── INTELLIGENCE WORKFLOW ── */}
        <section>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">The Workflow</p>
          <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">MarketRipple&apos;s Intelligence Workflow</h2>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            {["Event", "Impact", "Sector", "Company", "Historical Pattern", "Opportunity", "Evidence"].map((step, i, arr) => (
              <span key={step} className="flex items-center gap-2">
                <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary">{step}</span>
                {i < arr.length - 1 && <ArrowRight className="h-3 w-3 shrink-0 text-text-muted" aria-hidden="true" />}
              </span>
            ))}
          </div>
        </section>

        {/* ── METHODOLOGY TABLE ── */}
        <section>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">At a Glance</p>
          <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">MarketRipple&apos;s Intelligence Systems</h2>
          <div className="mt-6 overflow-x-auto rounded-xl border border-surface-border/8">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-surface-border/8 bg-text-primary/[0.03]">
                  {["System", "Input", "Processing", "Output"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-wide text-text-muted">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {METHODOLOGY_TABLE.map((row, i) => (
                  <tr key={row.system} className={i < METHODOLOGY_TABLE.length - 1 ? "border-b border-surface-border/6" : ""}>
                    <td className="px-4 py-3 align-top text-[13px] font-bold text-text-primary">{row.system}</td>
                    <td className="px-4 py-3 align-top text-[12.5px] text-text-secondary">{row.input}</td>
                    <td className="px-4 py-3 align-top text-[12.5px] text-text-secondary">{row.processing}</td>
                    <td className="px-4 py-3 align-top text-[12.5px] text-text-secondary">{row.output}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── AI SEARCH ── */}
        <Section
          id="ai-search-heading" badge="AI Search" badgeColor="text-violet-400"
          title="How does MarketRipple's AI search work?"
          subtitle="A natural-language question is matched against MarketRipple's own real event, company, and sector data — through entity and intent matching, not keyword search or a generic language-model response — and an AI model synthesises a sourced answer from what's retrieved."
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {AI_SEARCH_STEPS.map((s) => (
              <div key={s.step} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <div className="mb-3 flex items-center gap-2.5">
                  <div className={`flex h-8 w-8 items-center justify-center rounded-lg border ${s.color}`} aria-hidden="true">{s.icon}</div>
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">Step {s.step}</span>
                </div>
                <h3 className="text-[14px] font-bold text-text-primary">{s.title}</h3>
                <p className="mt-2 text-[12px] leading-5 text-text-secondary">{s.detail}</p>
              </div>
            ))}
          </div>
          <Link href="/ai-search" className="inline-flex items-center gap-1 text-sm font-semibold text-violet-400 hover:text-violet-300">
            Try AI Search <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </Section>

        {/* ── RIPPLE ENGINE ── */}
        <Section
          id="ripple-heading" badge="Ripple Engine" badgeColor="text-sky-400"
          title="How does the Ripple Engine calculate relationships?"
          subtitle="Each relationship in MarketRipple's knowledge graph carries a stored confidence value. When an event's effects propagate through the graph, that confidence is attenuated at each hop — so a distant, indirect effect is shown with visibly lower confidence than a direct one."
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {RIPPLE_STEPS.map((step) => (
              <div key={step.number} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <div className="mb-3 flex items-center justify-between">
                  <div className={`flex h-9 w-9 items-center justify-center rounded-xl border ${step.color}`} aria-hidden="true">{step.icon}</div>
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">{step.number}</span>
                </div>
                <h3 className="text-[14px] font-bold text-text-primary">{step.title}</h3>
                <p className="mt-2 text-[12px] leading-5 text-text-secondary">{step.description}</p>
              </div>
            ))}
          </div>
          <Link href="/ripple" className="inline-flex items-center gap-1 text-sm font-semibold text-sky-400 hover:text-sky-300">
            Explore Ripple Intelligence <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </Section>

        {/* ── OPPORTUNITY RADAR ── */}
        <Section
          id="radar-heading" badge="Opportunity Radar" badgeColor="text-emerald-400"
          title="How is an Opportunity Radar score calculated?"
          subtitle="From a transparent, count-based formula — a base score plus credit for the number of corroborating events, and the breadth of companies and sectors involved in a developing situation, capped at 99. It's a real signal-density measure, not a fabricated number, and not a guaranteed return."
        >
          <div className="rounded-xl border border-surface-border/8 bg-surface-card p-5 md:p-7">
            <div className="grid gap-4 sm:grid-cols-3">
              {OPPORTUNITY_FACTORS.map((f) => (
                <div key={f.factor}>
                  <div className={`mb-2 flex h-9 w-9 items-center justify-center rounded-lg border border-surface-border/8 bg-text-primary/[0.04] ${f.color}`} aria-hidden="true">{f.icon}</div>
                  <p className="text-[13px] font-bold text-text-primary">{f.factor}</p>
                  <p className="mt-1 text-[12px] leading-5 text-text-secondary">{f.description}</p>
                </div>
              ))}
            </div>
            <p className="mt-5 text-[11px] italic text-text-muted">
              Weights are versioned and retuned as the formula improves — see the factors above for
              what consistently matters, not a fixed public percentage split.
            </p>
          </div>
          <p className="rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 text-sm font-medium text-amber-700 dark:text-amber-300">
            An opportunity score is an intelligence signal, not a guaranteed return or investment recommendation.
          </p>
          <Link href="/opportunity-radar" className="inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
            Explore Opportunity Radar <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </Section>

        {/* ── CONFIDENCE SCORE ── */}
        <Section
          id="confidence-heading" badge="Confidence Engine" badgeColor="text-indigo-400"
          title="How is MarketRipple's confidence score calculated?"
          subtitle="A point-based sum across 8 real evidence signals — source count, historical precedent, market and sector confirmation, macro alignment, company sensitivity, AI self-certainty, and a volatility adjustment — capped at 100. It is computed, not an AI self-rating alone."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {CONFIDENCE_FACTORS.map((item) => (
              <div key={item.factor} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <div className="mb-3 flex items-center gap-2.5">
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${item.color}`} aria-hidden="true">{item.icon}</div>
                  <div>
                    <p className="text-[14px] font-bold text-text-primary">{item.factor}</p>
                    <p className="text-[10px] text-text-muted">{item.points}</p>
                  </div>
                </div>
                <p className="text-[12px] leading-5 text-text-secondary">{item.detail}</p>
              </div>
            ))}
          </div>
          <p className="text-[11px] italic text-text-muted">
            Points across all eight signals are summed and capped at 100 — a genuinely
            well-corroborated read comfortably clears the top of the range.
          </p>
        </Section>

        {/* ── AI TRUST / VALIDATION ── */}
        <Section
          id="validation-heading" badge="Validation" badgeColor="text-rose-400"
          title="How does MarketRipple validate AI-generated analysis?"
          subtitle="Before generating a company-impact analysis, real per-company price-move data is fetched and fed directly into the generation prompt. Three deterministic checks — no LLM involved — then run against the output before it can publish."
        >
          <div className="flex flex-wrap items-center gap-2">
            {["Real market price grounding", "Shared-reason detection", "Sentiment/magnitude consistency", "Status-tense consistency", "Publication"].map((step, i, arr) => (
              <span key={step} className="flex items-center gap-2">
                <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary">{step}</span>
                {i < arr.length - 1 && <ArrowRight className="h-3 w-3 shrink-0 text-text-muted" aria-hidden="true" />}
              </span>
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {FACT_GROUNDING_CHECKS.map((check) => (
              <div key={check.title} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl border ${check.color}`} aria-hidden="true">{check.icon}</div>
                <h3 className="text-[14px] font-bold text-text-primary">{check.title}</h3>
                <p className="mt-2 text-[12px] leading-5 text-text-secondary">{check.description}</p>
              </div>
            ))}
          </div>
          <div className="flex items-start gap-3 rounded-xl border border-amber-500/20 bg-amber-500/[0.05] p-4">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden="true" />
            <p className="text-[12px] leading-5 text-text-secondary">
              <span className="font-semibold text-amber-600 dark:text-amber-300">Currently in shadow mode:</span>{" "}
              violations are logged for review, not yet blocking publication, while MarketRipple
              observes real-world violation rates before turning this into a hard publish gate.
            </p>
          </div>
          <div className="rounded-xl border border-surface-border/8 bg-surface-card p-6">
            <h3 className="text-sm font-bold text-text-primary">Fact vs. AI Interpretation vs. Prediction</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <div className="rounded-lg border border-emerald-500/15 bg-emerald-500/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-wide text-emerald-500">Fact</p>
                <p className="mt-1.5 text-[12.5px] leading-6 text-text-secondary">What the source or data indicates — a real price move, a real filing, a real historical outcome.</p>
              </div>
              <div className="rounded-lg border border-violet-500/15 bg-violet-500/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-wide text-violet-500">AI Interpretation</p>
                <p className="mt-1.5 text-[12.5px] leading-6 text-text-secondary">MarketRipple&apos;s model-generated read of what the evidence means, clearly labelled as such.</p>
              </div>
              <div className="rounded-lg border border-amber-500/15 bg-amber-500/[0.03] p-4">
                <p className="text-[10px] font-black uppercase tracking-wide text-amber-500">Prediction / Outlook</p>
                <p className="mt-1.5 text-[12.5px] leading-6 text-text-secondary">A forward-looking view — always probabilistic, never presented as certain or guaranteed.</p>
              </div>
            </div>
          </div>
        </Section>

        {/* ── DATA SOURCES ── */}
        <Section
          id="data-heading" badge="Data" badgeColor="text-sky-400"
          title="What data does MarketRipple use?"
          subtitle="Only real, verifiable sources — never a source claimed without a real connection behind it."
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {DATA_SOURCE_GROUPS.map((g) => (
              <Link key={g.title} href={g.href} className="rounded-xl border border-surface-border/8 bg-surface-card p-5 transition hover:border-surface-border/15 hover:bg-text-primary/[0.02]">
                <g.icon className="h-6 w-6 text-sky-400" aria-hidden="true" />
                <h3 className="mt-3 text-[13px] font-bold text-text-primary">{g.title}</h3>
                <p className="mt-1.5 text-[12px] leading-5 text-text-muted">{g.items}</p>
              </Link>
            ))}
          </div>
        </Section>

        {/* ── AI LIMITATIONS ── */}
        <Section
          id="limitations-heading" badge="Honest Disclosure" badgeColor="text-rose-400"
          title="What are MarketRipple's AI limitations?"
          subtitle="Transparency requires honesty about what AI can and cannot do. These are the genuine limitations of MarketRipple's analytical systems."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {LIMITATIONS.map((lim) => {
              const severityColor = lim.severity === "high" ? "border-rose-500/20 bg-rose-500/[0.04]" : "border-amber-500/20 bg-amber-500/[0.04]";
              const iconColor = lim.severity === "high" ? "text-rose-400 bg-rose-500/10 border-rose-500/25" : "text-amber-400 bg-amber-500/10 border-amber-500/25";
              return (
                <div key={lim.title} className={`rounded-xl border p-5 ${severityColor}`}>
                  <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-xl border ${iconColor}`} aria-hidden="true">{lim.icon}</div>
                  <h3 className="text-[14px] font-bold text-text-primary">{lim.title}</h3>
                  <p className="mt-2 text-[12px] leading-5 text-text-secondary">{lim.description}</p>
                </div>
              );
            })}
          </div>
        </Section>

        {/* ── WHAT MARKETRIPPLE DOES AND DOESN'T DO ── */}
        <section className="rounded-2xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
          <h2 className="text-[20px] font-black text-text-primary md:text-[24px]">What MarketRipple Does — and Doesn&apos;t Do</h2>
          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <div>
              <p className="text-[10px] font-black uppercase tracking-wide text-emerald-500">Does</p>
              <ul className="mt-3 space-y-2">
                {["Organizes market information", "Connects events, sectors, and companies", "Explains potential impact with evidence", "Surfaces historical context", "Shows confidence indicators", "Identifies potential opportunities and risks"].map((d) => (
                  <li key={d} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" aria-hidden="true" />{d}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-wide text-rose-500">Does Not</p>
              <ul className="mt-3 space-y-2">
                {["Guarantee returns", "Predict markets with certainty", "Replace investor judgment", "Provide guaranteed buy/sell outcomes"].map((d) => (
                  <li key={d} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-500" aria-hidden="true" />{d}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ── HUMAN JUDGMENT ── */}
        <section aria-labelledby="human-judgment-heading">
          <div className="rounded-xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-sky-500/25 bg-sky-500/10 text-sky-400" aria-hidden="true">
                <UserCheck className="h-6 w-6" />
              </div>
              <div>
                <h2 id="human-judgment-heading" className="text-xl font-black text-text-primary">Does MarketRipple provide investment advice?</h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary">
                  No. MarketRipple is designed to augment human investment judgment, not replace it.
                  We recommend using MarketRipple to generate and stress-test hypotheses, then
                  verifying conclusions against primary sources (BSE/NSE filings, RBI releases,
                  company annual reports) before making any investment decision.
                </p>
                <div className="mt-5 flex items-center gap-2 rounded-xl border border-sky-500/20 bg-sky-500/[0.06] p-3">
                  <ShieldAlert className="h-4 w-4 shrink-0 text-sky-400" aria-hidden="true" />
                  <p className="text-[12px] text-sky-600 dark:text-sky-300">
                    MarketRipple does not provide personalised investment advice. All analysis is for
                    informational purposes only. Past patterns do not guarantee future outcomes.
                  </p>
                </div>
              </div>
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
          <Link href="/faq" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-sky-400 hover:text-sky-300">
            See all questions <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </section>

        {/* ── CTA ── */}
        <section aria-label="Related pages" className="rounded-xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Continue Exploring</p>
          <h2 className="mt-2 text-xl font-black text-text-primary">See the system in action</h2>
          <p className="mt-2 text-sm text-text-secondary">
            Explore how MarketRipple reasons through real market events — and see the pipeline behind it.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/how-marketripple-thinks" className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-5 py-2.5 text-sm font-semibold text-text-primary transition hover:opacity-90">
              <Brain className="h-4 w-4" />How MarketRipple Thinks<ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link href="/how-it-works" className="flex items-center gap-2 rounded-xl border border-surface-border/15 bg-text-primary/[0.04] px-5 py-2.5 text-sm font-semibold text-text-secondary transition hover:border-surface-border/25 hover:text-text-primary">
              <GitMerge className="h-4 w-4" />How It Works<ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}
