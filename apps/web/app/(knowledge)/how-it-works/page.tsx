import type { Metadata } from "next";
import Link from "next/link";
import {
  Radio,
  Brain,
  Layers,
  Waves,
  GitFork,
  Scale,
  Radar,
  FileCheck,
  Building2,
  BookOpen,
  Search,
  Cpu,
  Database,
  Network,
  ArrowRight,
  ChevronRight,
  ShieldCheck,
  Landmark,
  Newspaper,
  HelpCircle,
} from "lucide-react";
import { safeJsonLd } from "@/lib/text";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "How MarketRipple Works | AI Market Intelligence",
  description:
    "How MarketRipple turns market events into structured intelligence — connecting events, sectors, companies, historical context, and opportunities.",
  alternates: { canonical: `${SITE_URL}/how-it-works` },
  openGraph: {
    title: "How MarketRipple Works | AI Market Intelligence",
    description:
      "How MarketRipple turns market events into structured intelligence — connecting events to sectors, companies, historical context, and opportunities.",
    url: `${SITE_URL}/how-it-works`,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

// ── Data ──────────────────────────────────────────────────────────────────────
// Every number and capability claim on this page was checked against the
// real backend before being written (2026-08-11 audit). Two corrections
// worth flagging explicitly, since they replace the previous version's
// claims:
//   - Ingestion/analysis latency: news ingestion polls every 15 minutes
//     (app.core.config.ingest_news_interval_sec=900) and policy sources
//     every hour (ingest_policy_interval_sec=3600); the AIPE article
//     generation cycle runs every 5 minutes (scheduler.py's
//     run_aipe_cycle, IntervalTrigger(seconds=300)). The previous page
//     claimed "< 15 seconds" / "< 8 seconds" / "under 60 seconds" —
//     none of which match the real scheduled-job cadence. Corrected here.
//   - Opportunity Radar scoring: the real, live-called formula
//     (app.pipeline.opportunity_generator._score_opportunity) is a
//     transparent count-based heuristic — a 60-point base plus credit for
//     corroborating event count, company breadth, and sector breadth,
//     capped at 99 — not the "AI confidence multiplier / sector momentum
//     factor / historical precedent backtesting" the previous page
//     described (that richer formula, scoring_engine.score_opportunity,
//     exists in the codebase but has no confirmed live caller). Corrected
//     to describe the real formula. "F&O activity" and "promoter holding"
//     as company-exposure signals were removed entirely — neither is a
//     real implemented scoring input (F&O appears only inside one seeded
//     historical narrative string; promoter holding only as an IPO
//     founder-name field and a suggested AI Search query prompt).
//   - "Fine-tuned on Indian financial data" and "RAG" were removed — no
//     evidence of either in the codebase. The real AI layer is a
//     multi-provider free-tier LLM fallback chain (Groq, Cerebras,
//     OpenRouter, Mistral, Cloudflare Workers AI, NVIDIA NIM).

const PIPELINE_SUMMARY = [
  { label: "Event", href: "/events" },
  { label: "Analysis", href: undefined },
  { label: "Classification", href: undefined },
  { label: "Ripple", href: "/ripple" },
  { label: "Companies", href: "/companies" },
  { label: "Historical Context", href: "/historical" },
  { label: "Opportunity", href: "/opportunity-radar" },
  { label: "Search", href: "/ai-search" },
];

const PIPELINE_STEPS = [
  {
    number: "01",
    icon: Radio,
    title: "Detect",
    sentence: "Market events enter the pipeline from supported exchanges, regulators, and financial news sources.",
    href: undefined,
  },
  {
    number: "02",
    icon: Brain,
    title: "Understand",
    sentence: "AI extracts entities, facts, and potential market relevance from each event.",
    href: undefined,
  },
  {
    number: "03",
    icon: Layers,
    title: "Structure",
    sentence: "Each event becomes a queryable Market Event with type, sector, company, and impact metadata.",
    href: "/events",
  },
  {
    number: "04",
    icon: Waves,
    title: "Connect",
    sentence: "Ripple relationships connect the event to other companies, sectors, and market entities.",
    href: "/ripple",
  },
  {
    number: "05",
    icon: GitFork,
    title: "Map",
    sentence: "Potentially affected companies and sectors are identified, direct and indirect.",
    href: "/companies",
  },
  {
    number: "06",
    icon: Scale,
    title: "Compare",
    sentence: "Similar historical events, where available, provide additional context.",
    href: "/historical",
  },
  {
    number: "07",
    icon: Radar,
    title: "Score",
    sentence: "Opportunity signals are evaluated using the Opportunity Radar's scoring engine.",
    href: "/opportunity-radar",
  },
  {
    number: "08",
    icon: FileCheck,
    title: "Explain",
    sentence: "Users receive structured, sourced intelligence through MarketRipple's products.",
    href: "/ai-search",
  },
] as const;

const DATA_SOURCES = [
  {
    icon: Landmark,
    title: "Exchanges",
    items: ["NSE", "BSE"],
    why: "Exchange filings provide company-level corporate disclosures — the ground-truth record of what a listed company has actually announced.",
  },
  {
    icon: ShieldCheck,
    title: "Regulators & Government",
    items: ["RBI", "SEBI", "PIB", "Ministry of Finance"],
    why: "Regulatory releases provide policy and market-rule changes — the source of most market-wide, cross-sector events.",
  },
  {
    icon: Newspaper,
    title: "Financial News",
    items: ["Economic Times", "Moneycontrol", "NDTV Profit", "Business Standard", "Livemint"],
    why: "Financial news provides developing market narratives and context that regulatory filings alone don't carry.",
  },
];

const COMPANY_EXPOSURE = [
  { title: "Direct", description: "Revenue, cost, or business exposure — the event affects this company's own operations or financials." },
  { title: "Indirect", description: "Sector or supply-chain spillover — the company isn't named in the event, but sits downstream or upstream of what is." },
  { title: "Thematic", description: "Longer-term structural implications — the event shifts a trend the company's business model depends on." },
];

const AI_SEARCH_EXAMPLES = [
  "What companies are exposed to crude oil prices?",
  "How did markets react to previous RBI rate hikes?",
  "Which sectors could benefit from rupee depreciation?",
];

const TECH_CARDS = [
  {
    icon: Cpu,
    title: "AI Models",
    description:
      "Event analysis, entity extraction, and summarisation run on a multi-provider large language model fallback chain — the pipeline automatically moves to the next available provider rather than depending on a single vendor. Company-impact analysis is grounded in real per-company price-move data fed into the same prompt, not generated from headline text alone.",
  },
  {
    icon: Database,
    title: "Data Pipeline",
    description:
      "News and exchange sources are polled on a fixed schedule (every 15 minutes for NSE/BSE/RSS, hourly for RBI/SEBI/PIB), with deduplication and entity normalisation before an event is classified. AIPE's article-generation cycle then runs every 5 minutes over the newly classified backlog.",
  },
  {
    icon: Network,
    title: "Intelligence / Graph Engine",
    description:
      "A market relationship graph spans 7 real dependency types — benefits, hurts, supplies, depends_on, competes_with, influences, triggered_by — connecting companies, sectors, and events. The graph grows as new events are processed and supports traversal for ripple analysis and exposure mapping.",
  },
];

const FAQS = [
  {
    id: "collect",
    q: "How does MarketRipple collect market information?",
    a: "MarketRipple polls exchange filings (NSE, BSE), regulatory and government sources (RBI, SEBI, PIB, Ministry of Finance), and financial news RSS feeds on a fixed schedule — every 15 minutes for exchange and news sources, hourly for regulatory sources. Each item is deduplicated and normalised before entering the analysis stage.",
  },
  {
    id: "analyze-news",
    q: "How does MarketRipple analyze financial news?",
    a: "AI extracts entities (companies, sectors, commodities, currencies) from each event and assesses market relevance. For company-impact analysis specifically, real per-company price-move data is fetched and included in the same prompt, so the analysis is grounded in an actual number rather than inferred from headline text alone.",
  },
  {
    id: "connect-companies",
    q: "How does MarketRipple connect news to companies?",
    a: "Events are matched to companies through the Ripple Engine's relationship graph — either directly named in the event, or connected through one of seven relationship types (supplies, depends_on, competes_with, and others) linking the event's sector or commodity to a company's real exposure.",
  },
  {
    id: "ripple-intelligence",
    q: "What is Ripple Intelligence?",
    a: "Ripple Intelligence is MarketRipple's system for tracing how one market event may affect other companies and sectors beyond the obvious one, through 7 defined relationship types. It's presented as a relationship graph with a confidence indicator on each connection — not a guarantee that every traced effect will materialise.",
  },
  {
    id: "opportunities",
    q: "How does MarketRipple identify investment opportunities?",
    a: "Opportunity Radar scores potential opportunities using a transparent formula based on real signal density: how many corroborating events, companies, and sectors are involved in a developing situation. It's an intelligence signal for further research, not a guaranteed return or a recommendation to buy or sell.",
  },
  {
    id: "historical-data",
    q: "Does MarketRipple use historical market data?",
    a: "Yes — MarketRipple compares current events against a set of verified historical market events (spanning 2008–2024) where a genuinely similar precedent exists. This adds context about how markets reacted to similar situations before. Historical patterns provide context, not a guarantee of future returns.",
  },
  {
    id: "hallucinations",
    q: "How does MarketRipple prevent AI hallucinations?",
    a: "Company-impact analysis is grounded in real fetched price data before generation, and deterministic (non-AI) validators check every draft afterward for shared boilerplate reasons reused across companies, sentiment tags that contradict the real price move, and status mismatches — before anything publishes.",
  },
  {
    id: "not-advice",
    q: "Is MarketRipple's analysis financial advice?",
    a: "No. MarketRipple is a market research and intelligence tool. It does not replace the personalised advice of a SEBI-registered investment advisor, and all investment decisions remain the responsibility of the user. See the Legal page for the full disclaimer.",
  },
  {
    id: "ai-search-works",
    q: "How does MarketRipple's AI Search work?",
    a: "A natural-language question is matched against MarketRipple's own event, company, and sector data, and an AI model synthesises a sourced answer from what's retrieved — for example, 'Which sectors could benefit from rupee depreciation?' Answers cite the underlying events, and quality can vary with how much real data exists on a topic.",
  },
  {
    id: "explained",
    q: "How are MarketRipple's AI outputs explained?",
    a: "Every AI Newsroom article carries an Evidence section split into Fact — what happened, sources, historical outcomes — and AI Interpretation — the model's own read, clearly labelled as such. The two are never blended into one undifferentiated claim.",
  },
];

const FAQ_JSONLD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQS.map((item) => ({
    "@type": "Question",
    name: item.q,
    acceptedAnswer: { "@type": "Answer", text: item.a },
  })),
};

const WEBPAGE_JSONLD = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "How MarketRipple Works",
  url: `${SITE_URL}/how-it-works`,
  description:
    "How MarketRipple turns market events and financial information into structured intelligence connecting events, sectors, companies, historical context and opportunities.",
  about: { "@type": "Organization", name: "MarketRipple", url: SITE_URL },
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function HowItWorksPage() {
  return (
    <main className="min-w-0 space-y-14 pb-20">
      <script
        type="application/ld+json"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: static JSON-LD
        dangerouslySetInnerHTML={{ __html: safeJsonLd(WEBPAGE_JSONLD) }}
      />
      <script
        type="application/ld+json"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: static JSON-LD
        dangerouslySetInnerHTML={{ __html: safeJsonLd(FAQ_JSONLD) }}
      />

      {/* ── Hero ── */}
      <section className="rounded-2xl border border-surface-border/8 bg-gradient-to-br from-emerald-500/[0.06] to-surface-bg p-8 md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-400">
          How It Works
        </p>
        <h1 className="mt-4 text-[26px] font-black leading-tight text-text-primary md:text-[38px]">
          How MarketRipple Turns Market News Into Intelligence
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-text-secondary">
          MarketRipple continuously processes market events, analyzes their potential impact,
          connects them across sectors and companies, and turns the resulting intelligence into
          searchable opportunities, risks, and market insights.
        </p>

        {/* Compact pipeline strip — the "what happens to one event" summary,
            visible above the fold with no scrolling required. */}
        <div className="mt-8 flex flex-wrap items-center gap-2 text-sm">
          {PIPELINE_SUMMARY.map((stage, i, arr) => (
            <div key={stage.label} className="flex items-center gap-2">
              {stage.href ? (
                <Link href={stage.href} className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary transition hover:bg-text-primary/[0.1] hover:text-text-primary">
                  {stage.label}
                </Link>
              ) : (
                <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary">
                  {stage.label}
                </span>
              )}
              {i < arr.length - 1 && <ArrowRight className="h-3 w-3 shrink-0 text-text-muted" aria-hidden="true" />}
            </div>
          ))}
        </div>
      </section>

      {/* ── Direct Answer (AEO) ── */}
      <section>
        <h2 className="text-[22px] font-black text-text-primary md:text-[26px]">
          How Does MarketRipple Work?
        </h2>
        <p className="mt-4 max-w-3xl text-[15px] leading-7 text-text-secondary">
          MarketRipple ingests market events and financial information from exchanges,
          regulators, and financial news. AI extracts the relevant entities and facts from each
          event, which is then classified and structured. Ripple relationships connect the event
          to affected sectors and companies, and historical context adds precedent where a
          genuinely similar past event exists. Opportunity Radar evaluates the resulting signals,
          and AI Search lets users explore the intelligence in natural language.
        </p>
      </section>

      {/* ── Visual Pipeline ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          The Pipeline
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          From Market Event to Market Intelligence
        </h2>
        <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {PIPELINE_STEPS.map((step) => (
            <article
              key={step.number}
              className="rounded-xl border border-surface-border/8 bg-surface-card p-4"
              aria-label={`Step ${step.number}: ${step.title}`}
            >
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <step.icon className="h-4 w-4 text-emerald-400" aria-hidden="true" />
                </div>
                <span className="text-[10px] font-black tracking-[0.14em] text-text-muted">{step.number}</span>
              </div>
              <h3 className="mt-3 text-sm font-bold text-text-primary">
                {step.href ? (
                  <Link href={step.href} className="underline-offset-4 hover:text-emerald-400 hover:underline">
                    {step.title}
                  </Link>
                ) : step.title}
              </h3>
              <p className="mt-1 text-xs leading-5 text-text-muted">{step.sentence}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── Trust: Fact vs AI Interpretation ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Trust
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          How MarketRipple Keeps AI Grounded
        </h2>
        <div className="mt-7 grid gap-5 sm:grid-cols-2">
          <article className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/20 bg-surface-card">
              <ShieldCheck className="h-5 w-5 text-emerald-400" aria-hidden="true" />
            </div>
            <h3 className="mt-4 text-base font-bold text-text-primary">Real Data &amp; Fact Grounding</h3>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Market data and event information are used as real inputs — for company-impact
              analysis specifically, real per-company price-move data is fetched and fed into
              the same prompt, so the AI writes from an actual number rather than inventing a
              direction or magnitude.
            </p>
          </article>
          <article className="rounded-xl border border-sky-500/20 bg-sky-500/[0.04] p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-sky-500/20 bg-surface-card">
              <FileCheck className="h-5 w-5 text-sky-400" aria-hidden="true" />
            </div>
            <h3 className="mt-4 text-base font-bold text-text-primary">Deterministic Validation</h3>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              Non-AI validators check every draft before publish for shared boilerplate reasons
              reused across companies, sentiment tags that contradict the real price move, and
              draft-vs-decided status mismatches.
            </p>
          </article>
        </div>

        <div className="mt-5 rounded-xl border border-surface-border/8 bg-surface-card p-6">
          <h3 className="text-sm font-bold text-text-primary">Fact vs. AI Interpretation</h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-emerald-500/15 bg-emerald-500/[0.03] p-4">
              <p className="text-[10px] font-black uppercase tracking-wide text-emerald-500">Fact</p>
              <p className="mt-1.5 text-sm leading-6 text-text-secondary">What the source or data indicates — sources, historical outcomes, real price moves.</p>
            </div>
            <div className="rounded-lg border border-violet-500/15 bg-violet-500/[0.03] p-4">
              <p className="text-[10px] font-black uppercase tracking-wide text-violet-500">AI Interpretation</p>
              <p className="mt-1.5 text-sm leading-6 text-text-secondary">MarketRipple&apos;s model-generated analysis based on the available evidence, clearly labelled as such.</p>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-text-secondary">
            Every article on the{" "}
            <Link href="/newsroom" className="underline decoration-dotted underline-offset-2 hover:text-sky-400">AI Newsroom</Link>{" "}
            carries an Evidence section built on this exact split, alongside an AI Investment
            Verdict — an aggregate stance derived from real company and sector data, never a
            fabricated buy or sell rating.
          </p>
        </div>
      </section>

      {/* ── Data Ingestion ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Sources
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          Where Does MarketRipple Get Market Information?
        </h2>
        <div className="mt-7 grid gap-5 sm:grid-cols-3">
          {DATA_SOURCES.map((s) => (
            <article key={s.title} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
              <s.icon className="h-6 w-6 text-sky-400" aria-hidden="true" />
              <h3 className="mt-3 text-sm font-bold text-text-primary">{s.title}</h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {s.items.map((item) => (
                  <span key={item} className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-2 py-0.5 text-[10.5px] text-text-secondary">{item}</span>
                ))}
              </div>
              <p className="mt-3 text-xs leading-5 text-text-muted">{s.why}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── Event Classification ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Event Structure
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          How Does MarketRipple Understand a Market Event?
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
          Every event is structured with the same metadata: event type, sector exposure,
          company exposure, impact duration, geographic scope, and an impact/relevance score.
        </p>
        <div className="mt-6 rounded-xl border border-surface-border/8 bg-surface-card p-6">
          <p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Explanatory example — not live data</p>
          <div className="mt-3 flex flex-col gap-2 text-sm text-text-secondary sm:flex-row sm:flex-wrap sm:items-center">
            {["RBI rate decision", "Banking / NBFC exposure", "Funding and margin implications", "Affected companies", "Historical comparison", "Opportunity / Risk"].map((step, i, arr) => (
              <span key={step} className="flex items-center gap-2">
                <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold">{step}</span>
                {i < arr.length - 1 && <ArrowRight className="hidden h-3 w-3 shrink-0 text-text-muted sm:block" aria-hidden="true" />}
              </span>
            ))}
          </div>
        </div>
        <Link href="/events" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
          See live events <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Ripple Intelligence ── */}
      <section className="rounded-2xl border border-violet-500/15 bg-violet-500/[0.03] p-8 md:p-10">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-400">
          Ripple Intelligence
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          How Does Ripple Intelligence Connect Market Events?
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary">
          MarketRipple traces cause-effect relationships from a market event across seven
          real relationship types — companies and sectors that may be affected, not always
          the obvious ones.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          {["benefits", "hurts", "supplies", "depends_on", "competes_with", "influences", "triggered_by"].map((t) => (
            <code key={t} className="rounded-md border border-violet-500/20 bg-violet-500/[0.06] px-2.5 py-1 text-[11px] font-mono text-violet-600 dark:text-violet-300">{t}</code>
          ))}
        </div>
        <div className="mt-6 rounded-xl border border-surface-border/8 bg-surface-card p-5">
          <p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Example — illustrative, not a guaranteed chain</p>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-text-secondary">
            <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold">Crude oil rises</span>
            <ArrowRight className="h-3 w-3 text-text-muted" aria-hidden="true" />
            <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold">Fuel costs may increase</span>
            <ArrowRight className="h-3 w-3 text-text-muted" aria-hidden="true" />
            <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold">Aviation / logistics costs can rise</span>
            <ArrowRight className="h-3 w-3 text-text-muted" aria-hidden="true" />
            <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold">Affected companies may see margin pressure</span>
          </div>
        </div>
        <Link href="/ripple" className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-violet-400 hover:text-violet-300">
          Explore Ripple Intelligence <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Market Dependency Graph ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          The Graph
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          From Events to Companies: The Market Dependency Graph
        </h2>
        <div className="mt-7 grid gap-5 lg:grid-cols-2">
          <div className="rounded-xl border border-surface-border/8 bg-surface-card p-6">
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Nodes</p>
                <p className="mt-1 text-xs leading-5 text-text-secondary">Companies, sectors, commodities, currencies, policy instruments.</p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Edges</p>
                <p className="mt-1 text-xs leading-5 text-text-secondary">Typed relationships between entities.</p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Confidence</p>
                <p className="mt-1 text-xs leading-5 text-text-secondary">How strongly the system supports a given relationship.</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-surface-border/8 bg-surface-card p-6">
            <p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Explanatory diagram — not a live graph</p>
            <div className="mt-3 space-y-2 text-sm">
              <p className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary">EVENT — RBI rate change</p>
              <p className="pl-4 text-xs text-text-muted">↓ influences</p>
              <p className="rounded-lg bg-violet-500/10 px-3 py-1.5 text-xs font-semibold text-violet-600 dark:text-violet-300">BANKING</p>
              <p className="pl-4 text-xs text-text-muted">↓ affects</p>
              <p className="rounded-lg bg-sky-500/10 px-3 py-1.5 text-xs font-semibold text-sky-600 dark:text-sky-300">BANKS / NBFCs</p>
              <p className="pl-4 text-xs text-text-muted">↓ changes</p>
              <p className="rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-300">FUNDING / MARGINS</p>
            </div>
          </div>
        </div>
        <Link href="/ripple" className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
          See the Ripple graph <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Company Identification ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Companies
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          How Does MarketRipple Identify Affected Companies?
        </h2>
        <div className="mt-7 grid gap-5 sm:grid-cols-3">
          {COMPANY_EXPOSURE.map((c) => (
            <article key={c.title} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
              <h3 className="text-sm font-bold text-text-primary">{c.title}</h3>
              <p className="mt-2 text-sm leading-6 text-text-muted">{c.description}</p>
            </article>
          ))}
        </div>
        <p className="mt-5 max-w-2xl text-sm leading-6 text-text-secondary">
          MarketRipple can combine these relationships with available market data and other
          signals to provide context around company exposure.
        </p>
        <Link href="/companies" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
          Browse companies <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Historical Context ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Historical Context
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          Why Does Historical Context Matter?
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
          MarketRipple can compare a current event with similar historical events where a
          genuinely similar precedent is available.
        </p>
        <div className="mt-6 flex flex-wrap items-center gap-2">
          {["Current Event", "Find Similar Historical Events", "Study Market Reaction", "Compare Sector / Company Response", "Add Context to Current Intelligence"].map((step, i, arr) => (
            <span key={step} className="flex items-center gap-2">
              <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary">{step}</span>
              {i < arr.length - 1 && <ArrowRight className="h-3 w-3 shrink-0 text-text-muted" aria-hidden="true" />}
            </span>
          ))}
        </div>
        <p className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 text-sm font-medium text-amber-700 dark:text-amber-300">
          Historical patterns provide context, not a guarantee of future returns.
        </p>
        <Link href="/historical" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
          View historical patterns <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Story Synthesis ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Market Stories
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          How Does MarketRipple Turn Multiple Events Into a Market Story?
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
          One event isn&apos;t always enough to understand a developing market narrative.
          MarketRipple connects related events into a persistent, evolving Story.
        </p>
        <div className="mt-6 flex flex-wrap items-center gap-2">
          {["Individual events", "Related events", "Theme clustering", "Timeline", "Affected sectors", "Affected companies", "Opportunity / risk context"].map((step, i, arr) => (
            <span key={step} className="flex items-center gap-2">
              <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary">{step}</span>
              {i < arr.length - 1 && <ArrowRight className="h-3 w-3 shrink-0 text-text-muted" aria-hidden="true" />}
            </span>
          ))}
        </div>
        <Link href="/newsroom/themes" className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
          See Market Stories <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Opportunity Radar ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Opportunity Radar
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          How Does MarketRipple Identify Opportunities?
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary">
          Opportunity Radar organizes potential opportunity signals by combining available
          event impact, corroborating events, and the breadth of companies and sectors
          involved in a developing situation.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          {["Event impact", "Corroborating events", "Company breadth", "Sector breadth", "Historical precedent (where available)"].map((f) => (
            <span key={f} className="rounded-full border border-amber-500/20 bg-amber-500/[0.06] px-3 py-1 text-[11px] font-medium text-amber-700 dark:text-amber-300">{f}</span>
          ))}
        </div>
        <p className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 text-sm font-medium text-amber-700 dark:text-amber-300">
          An opportunity score is an intelligence signal, not a guaranteed return or investment recommendation.
        </p>
        <Link href="/opportunity-radar" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
          Explore Opportunity Radar <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── AI Search ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          AI Search
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          How Does MarketRipple AI Search Work?
        </h2>
        <div className="mt-6 flex flex-wrap items-center gap-2">
          {["User question", "Intent understanding", "Market intelligence retrieval", "Relevant events / companies / sectors", "Evidence", "AI synthesis", "Answer"].map((step, i, arr) => (
            <span key={step} className="flex items-center gap-2">
              <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary">{step}</span>
              {i < arr.length - 1 && <ArrowRight className="h-3 w-3 shrink-0 text-text-muted" aria-hidden="true" />}
            </span>
          ))}
        </div>
        <div className="mt-6 flex flex-wrap gap-2">
          {AI_SEARCH_EXAMPLES.map((ex) => (
            <Link key={ex} href={`/ai-search?q=${encodeURIComponent(ex)}`} className="rounded-full border border-sky-500/20 bg-sky-500/[0.05] px-3.5 py-1.5 text-xs font-medium text-sky-700 dark:text-sky-300 transition hover:bg-sky-500/10">
              {ex}
            </Link>
          ))}
        </div>
        <p className="mt-4 max-w-2xl text-xs leading-5 text-text-muted">
          Answers are grounded in MarketRipple&apos;s own event, company, and sector data — not every
          answer is guaranteed correct, and quality depends on how much real data exists on a topic.
        </p>
        <Link href="/ai-search" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
          Try AI Search <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── Technology ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Technology
        </p>
        <h2 className="mt-3 text-[22px] font-black text-text-primary md:text-[26px]">
          What Powers the Pipeline?
        </h2>
        <div className="mt-7 grid gap-5 sm:grid-cols-3">
          {TECH_CARDS.map((card) => (
            <article key={card.title} className="rounded-xl border border-surface-border/8 bg-surface-card p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-surface-border/8 bg-text-primary/[0.03]">
                <card.icon className="h-5 w-5 text-sky-400" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-bold text-text-primary">{card.title}</h3>
              <p className="mt-2 text-sm leading-6 text-text-muted">{card.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ── FAQ ── */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Questions
        </p>
        <h2 className="mt-3 flex items-center gap-2 text-[22px] font-black text-text-primary md:text-[26px]">
          <HelpCircle className="h-5 w-5 text-emerald-400" aria-hidden="true" />
          Frequently Asked Questions About How MarketRipple Works
        </h2>
        <div className="mt-7 space-y-2">
          {FAQS.map((item) => (
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
        <Link href="/faq" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
          See all questions <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </section>

      {/* ── CTA ── */}
      <section className="rounded-2xl border border-surface-border/8 bg-gradient-to-br from-surface-card to-surface-bg p-8 text-center md:p-12">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-400">
          Go Deeper
        </p>
        <h2 className="mt-3 text-[20px] font-black text-text-primary md:text-[24px]">
          Understand How MarketRipple Thinks
        </h2>
        <p className="mt-3 max-w-xl mx-auto text-sm leading-6 text-text-secondary">
          Explore the AI reasoning, evidence standards, and confidence calibration that power
          every output on MarketRipple.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-4">
          <Link
            href="/how-marketripple-thinks"
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-sky-600 px-6 py-2.5 text-sm font-semibold text-text-primary transition hover:opacity-90"
          >
            How MarketRipple Thinks
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
          <Link
            href="/events"
            className="flex items-center gap-2 rounded-xl border border-surface-border/[0.12] bg-text-primary/[0.04] px-6 py-2.5 text-sm font-semibold text-text-primary transition hover:bg-text-primary/[0.07]"
          >
            See Live Events
            <ChevronRight className="h-4 w-4 text-text-secondary" aria-hidden="true" />
          </Link>
        </div>
      </section>
    </main>
  );
}
