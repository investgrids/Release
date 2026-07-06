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
  Link2,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
  Database,
  Zap,
  Sigma,
} from "lucide-react";

export const metadata: Metadata = {
  title: "AI & Methodology — How MarketRipple's Intelligence Works",
  description:
    "Deep dive into how MarketRipple's AI search, Ripple Engine, Opportunity Radar, and Stories generation systems work — with full transparency on algorithms and limitations.",
  openGraph: {
    title: "AI & Methodology — How MarketRipple's Intelligence Works",
    description:
      "Transparent AI: understand the NLP, graph algorithms, Bayesian inference, and scoring models that power MarketRipple's market intelligence.",
  },
};

// ── Section wrapper ─────────────────────────────────────────────────────────
function Section({
  id,
  badge,
  badgeColor = "text-slate-500",
  title,
  subtitle,
  children,
}: {
  id: string;
  badge: string;
  badgeColor?: string;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-6">
      <div>
        <p className={`text-[10px] font-bold uppercase tracking-[0.18em] ${badgeColor}`}>
          {badge}
        </p>
        <h2 id={id} className="mt-2 text-[22px] font-black text-white md:text-[28px]">
          {title}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

// ── Stat Tile ────────────────────────────────────────────────────────────────
function StatTile({
  label,
  value,
  sub,
  color = "text-white",
}: {
  label: string;
  value: string;
  sub: string;
  color?: string;
}) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#080c14] px-4 py-3">
      <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">
        {label}
      </p>
      <p className={`mt-1 text-2xl font-black ${color}`}>{value}</p>
      <p className="mt-0.5 text-[11px] text-slate-500">{sub}</p>
    </div>
  );
}

// ── Step Card ────────────────────────────────────────────────────────────────
function StepCard({
  number,
  icon,
  title,
  description,
  color,
}: {
  number: string;
  icon: ReactNode;
  title: string;
  description: string;
  color: string;
}) {
  return (
    <div className="relative rounded-xl border border-white/[0.08] bg-[#080c14] p-5">
      <div className="mb-4 flex items-center justify-between">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl border ${color}`}
          aria-hidden="true"
        >
          {icon}
        </div>
        <span className="text-[32px] font-black text-white/[0.05] leading-none select-none">
          {number}
        </span>
      </div>
      <h3 className="text-[14px] font-bold text-white">{title}</h3>
      <p className="mt-2 text-[12px] leading-5 text-slate-400">{description}</p>
    </div>
  );
}

// ── AI Search Process ─────────────────────────────────────────────────────────
const aiSearchSteps = [
  {
    step: "1",
    icon: <Search className="h-4 w-4" />,
    title: "Query Understanding",
    detail:
      "NLP pipeline performs entity extraction (companies, sectors, events, time periods), intent classification (comparison, trend, causation, prediction), and query decomposition into sub-questions.",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/25",
  },
  {
    step: "2",
    icon: <Database className="h-4 w-4" />,
    title: "Semantic Search",
    detail:
      "Query is embedded into vector space and matched against MarketRipple's knowledge graph containing 50,000+ event-company-sector relationships. Semantic similarity retrieves top-K relevant context passages.",
    color: "text-sky-400 bg-sky-500/10 border-sky-500/25",
  },
  {
    step: "3",
    icon: <GitMerge className="h-4 w-4" />,
    title: "Multi-Step Reasoning",
    detail:
      "For complex financial queries, the model chains reasoning steps — first identifying affected sectors, then companies within those sectors, then evaluating historical analogues before forming a conclusion.",
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/25",
  },
  {
    step: "4",
    icon: <Filter className="h-4 w-4" />,
    title: "Evidence Retrieval",
    detail:
      "Supporting evidence is assembled from event timelines, corporate filings, regulatory announcements, and quantitative data. Each evidence piece is ranked by recency, source credibility, and relevance.",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/25",
  },
  {
    step: "5",
    icon: <BookOpen className="h-4 w-4" />,
    title: "Response with Citations",
    detail:
      "Final response is generated with inline citations linking back to source events, data points, and companies — so you can verify every claim independently.",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/25",
  },
];

// ── Opportunity Score Weights ─────────────────────────────────────────────────
const scoreWeights = [
  {
    factor: "Event Impact Score",
    weight: 30,
    icon: <Zap className="h-4 w-4" />,
    description:
      "Magnitude (scale of financial impact) × Breadth (number of sectors and companies affected) × Duration (transient vs. structural change). Scored 0–10, then normalised to 0–30 contribution.",
    color: "bg-violet-500",
    textColor: "text-violet-400",
  },
  {
    factor: "AI Confidence Score",
    weight: 25,
    icon: <Brain className="h-4 w-4" />,
    description:
      "Aggregate confidence across the full ripple chain. Higher confidence = more actionable signal. Computed as geometric mean of confidence at each causal step, weighted by depth.",
    color: "bg-sky-500",
    textColor: "text-sky-400",
  },
  {
    factor: "Sector Momentum",
    weight: 20,
    icon: <TrendingUp className="h-4 w-4" />,
    description:
      "Current price momentum, earnings revision trend, and FII/DII flow direction for the affected sector. Trailing 30-day momentum with mean-reversion adjustment for over-extended moves.",
    color: "bg-emerald-500",
    textColor: "text-emerald-400",
  },
  {
    factor: "Historical Precedent",
    weight: 15,
    icon: <BarChart2 className="h-4 w-4" />,
    description:
      "Outcome of similar past events — how the sector and specific companies actually performed. Backtested on 14 years of Indian market data (2010–2024). Adjusted for regime changes.",
    color: "bg-amber-500",
    textColor: "text-amber-400",
  },
  {
    factor: "Time Sensitivity",
    weight: 10,
    icon: <Clock className="h-4 w-4" />,
    description:
      "Urgency of the opportunity (event recency, information decay rate) and reversibility (is this a one-time event or a structural change?). Higher score for time-sensitive, irreversible shifts.",
    color: "bg-rose-500",
    textColor: "text-rose-400",
  },
];

// ── Ripple Engine Architecture ────────────────────────────────────────────────
const rippleSteps = [
  {
    number: "01",
    icon: <Network className="h-5 w-5" />,
    title: "Graph Construction",
    description:
      "MarketRipple maintains a live knowledge graph with nodes representing events, companies, sectors, commodities, currencies, and macroeconomic indicators. Edges represent causal relationships, each weighted by a confidence score derived from historical co-movement analysis and domain expertise.",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    number: "02",
    icon: <Layers className="h-5 w-5" />,
    title: "Relationship Detection",
    description:
      "Trained on 14 years of Indian market data (NSE/BSE price movements, earnings, macro releases). The model identifies which event-outcome pairs have statistically significant and economically meaningful relationships, filtering spurious correlations.",
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    number: "03",
    icon: <Sigma className="h-5 w-5" />,
    title: "Confidence Calculation",
    description:
      "Bayesian inference combining: Source Reliability (official vs. secondary) × Historical Accuracy (backtested prediction accuracy) × Analyst Consensus (cross-model agreement) × Recency Weight (recent data weighted higher). Updated continuously as new evidence arrives.",
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  },
  {
    number: "04",
    icon: <GitMerge className="h-5 w-5" />,
    title: "Cascade Simulation",
    description:
      "Breadth-first propagation through the dependency graph up to 4 levels deep. Each level attenuates confidence by the edge weight, preventing overconfident downstream claims. Parallel branches are tracked independently to surface both positive and negative effects on the same company.",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    number: "05",
    icon: <Zap className="h-5 w-5" />,
    title: "Real-Time Updating",
    description:
      "New events trigger automatic graph re-evaluation within minutes. The confidence of existing ripple chains is updated as confirming or disconfirming evidence accumulates. Stale predictions are flagged with a decay indicator when underlying conditions change.",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
];

// ── Stories Generation Pipeline ───────────────────────────────────────────────
const storiesSteps = [
  {
    icon: <Filter className="h-5 w-5" />,
    title: "Event Clustering",
    description:
      "Related events are grouped using semantic similarity and temporal proximity. A cluster of events about government infrastructure spending, RBI rate decisions, and NBFC credit growth would be grouped into a \"Credit-Driven Infrastructure\" story candidate.",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: <Lightbulb className="h-5 w-5" />,
    title: "Theme Identification",
    description:
      "The core investment hypothesis is extracted from the cluster: the fundamental driver, expected timeframe, and primary beneficiary profile. This becomes the story's thesis statement.",
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    icon: <Database className="h-5 w-5" />,
    title: "Evidence Assembly",
    description:
      "Supporting data is linked: affected companies (with rationale), quantitative data points (earnings, revenue exposure), historical analogues from prior market cycles, and expert viewpoints from analyst reports.",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: <BookOpen className="h-5 w-5" />,
    title: "Narrative Generation",
    description:
      "A coherent investment narrative is generated with a clear timeline (what has happened, what is happening, what is likely to happen next), risk factors, and actionable conclusions for different investor time horizons.",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: <CheckCircle2 className="h-5 w-5" />,
    title: "Quality Control",
    description:
      "Automated fact-checking cross-references all named companies against their actual sector classifications, verifies that stated financial metrics are within plausible ranges, and flags internal contradictions before publishing.",
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  },
];

// ── AI Limitations ────────────────────────────────────────────────────────────
const limitations = [
  {
    icon: <AlertTriangle className="h-5 w-5" />,
    title: "No Certainty in Market Prediction",
    description:
      "MarketRipple analyses probabilities and historical patterns. It cannot predict market movements with certainty. All insights are probabilistic — treat high-confidence signals as strong hypotheses, not facts.",
    severity: "high",
  },
  {
    icon: <Database className="h-5 w-5" />,
    title: "Public Information Only",
    description:
      "Analysis is based exclusively on publicly available information — regulatory filings, market data, news, and official announcements. MarketRipple does not have access to private or insider information.",
    severity: "medium",
  },
  {
    icon: <BarChart2 className="h-5 w-5" />,
    title: "Novel Situations Lack Precedent",
    description:
      "Historical patterns are the foundation of confidence scoring. In unprecedented events (novel pandemics, first-of-kind policy changes), confidence scores will be lower and scenario analysis wider — as they should be.",
    severity: "medium",
  },
  {
    icon: <Sigma className="h-5 w-5" />,
    title: "Confidence Scores Are Estimates",
    description:
      "Confidence percentages represent the AI model's calibrated uncertainty — not statistical guarantees. A 75% confidence signal will be wrong roughly 25% of the time. Size positions accordingly.",
    severity: "high",
  },
  {
    icon: <Clock className="h-5 w-5" />,
    title: "Training Data Cutoffs",
    description:
      "AI models have training cutoff dates. For very recent structural changes in market microstructure or new regulations, historical pattern recognition may be less reliable until the model incorporates new data.",
    severity: "low",
  },
  {
    icon: <Zap className="h-5 w-5" />,
    title: "Real-Time Latency",
    description:
      "Analysis quality depends on data source refresh rates. Breaking news may take 3–10 minutes to fully propagate through the ripple engine. For intraday trading decisions, always verify against primary sources.",
    severity: "medium",
  },
];

// ── Example Query Walkthrough ─────────────────────────────────────────────────
const exampleQuerySteps = [
  { step: "Query", content: "\"Which sectors benefit from a weak rupee?\"", color: "text-slate-300" },
  { step: "Entity Extraction", content: "Entity: INR (Indian Rupee) · Relationship: weakness/depreciation · Outcome: sector beneficiaries", color: "text-violet-300" },
  { step: "Intent Classification", content: "Intent: Causal analysis → sector screening → beneficiary identification", color: "text-sky-300" },
  { step: "Graph Traversal", content: "INR depreciation node → outgoing edges to: IT Services (positive, conf 88%), Pharmaceuticals (positive, conf 82%), OMCs (negative, conf 79%), Airlines (negative, conf 81%)", color: "text-emerald-300" },
  { step: "Evidence Retrieval", content: "Pulled: 14-year INR/sector performance correlation, Infosys FY24 earnings call (INR hedge ratio), historical ATF-INR relationship data", color: "text-amber-300" },
  { step: "Response Generated", content: "Primary beneficiaries: IT (dollar revenue, INR costs), Pharma exporters (US market revenue). Primary losers: Airlines (USD fuel), OMCs (crude imports). With citations.", color: "text-white" },
];

// ── Page ───────────────────────────────────────────────────────────────────────
export default function AIMethodologyPage() {
  return (
    <main className="min-w-0 space-y-16 pb-16" aria-label="AI Methodology">

      {/* ── HERO ──────────────────────────────────────────────────────── */}
      <section aria-labelledby="hero-heading">
        <div className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-indigo-950/60 via-[#080c14] to-sky-950/40 px-8 py-12 md:px-12 md:py-16">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-sky-400">
            AI & Methodology
          </p>
          <h1
            id="hero-heading"
            className="mt-3 text-[28px] font-black leading-tight text-white md:text-[40px]"
          >
            Transparent AI.{" "}
            <span className="text-sky-400">Explainable Decisions.</span>
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300 md:text-lg">
            We believe investors deserve to understand not just what the AI concludes,
            but how it reached that conclusion. Every model, every score, every
            confidence level — explained in plain language.
          </p>
          <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Knowledge Graph Nodes" value="50K+" sub="Events, companies, sectors" color="text-violet-400" />
            <StatTile label="Historical Data" value="14 yrs" sub="2010–2024 Indian markets" color="text-sky-400" />
            <StatTile label="Relationship Types" value="6" sub="Causal edge categories" color="text-emerald-400" />
            <StatTile label="Cascade Depth" value="4 levels" sub="Upstream to downstream" color="text-amber-400" />
          </div>
        </div>
      </section>

      {/* ── AI SEARCH ─────────────────────────────────────────────────── */}
      <Section
        id="ai-search-heading"
        badge="Feature Deep-Dive"
        badgeColor="text-violet-400"
        title="AI Search: How It Works"
        subtitle="MarketRipple's AI search goes far beyond keyword matching. It understands the financial intent behind your question and reasons through the answer step by step."
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {aiSearchSteps.map((s) => (
            <div
              key={s.step}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5"
            >
              <div className="mb-3 flex items-center gap-2.5">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg border ${s.color}`}
                  aria-hidden="true"
                >
                  {s.icon}
                </div>
                <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">
                  Step {s.step}
                </span>
              </div>
              <h3 className="text-[14px] font-bold text-white">{s.title}</h3>
              <p className="mt-2 text-[12px] leading-5 text-slate-400">{s.detail}</p>
            </div>
          ))}
        </div>

        {/* Example walkthrough */}
        <div className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5 md:p-7">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500 mb-4">
            Example: Query Processing Walkthrough
          </p>
          <div className="space-y-3">
            {exampleQuerySteps.map((item, i) => (
              <div key={i} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[10px] font-bold text-slate-400">
                    {i + 1}
                  </div>
                  {i < exampleQuerySteps.length - 1 && (
                    <div className="mt-1 w-px flex-1 bg-white/[0.06]" />
                  )}
                </div>
                <div className="pb-3 min-w-0 flex-1">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                    {item.step}
                  </p>
                  <p className={`mt-1 text-[12px] leading-5 font-medium ${item.color}`}>
                    {item.content}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── RIPPLE ENGINE ─────────────────────────────────────────────── */}
      <Section
        id="ripple-heading"
        badge="Core Algorithm"
        badgeColor="text-sky-400"
        title="Ripple Engine: Dependency Cascade"
        subtitle="The Ripple Engine is MarketRipple's proprietary system for tracing how a single market event propagates through the Indian economy — sector by sector, company by company."
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {rippleSteps.map((step) => (
            <StepCard
              key={step.number}
              number={step.number}
              icon={step.icon}
              title={step.title}
              description={step.description}
              color={step.color}
            />
          ))}
        </div>
      </Section>

      {/* ── OPPORTUNITY RADAR SCORING ─────────────────────────────────── */}
      <Section
        id="radar-heading"
        badge="Scoring Model"
        badgeColor="text-emerald-400"
        title="Opportunity Radar: Score Methodology"
        subtitle="Every opportunity on the Radar is assigned a composite score (0–100) built from five independently weighted factors. Here is exactly how the maths works."
      >
        <div className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5 md:p-7">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
              <Target className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[12px] font-bold text-white">Opportunity Score Formula</p>
              <p className="text-[11px] text-slate-500 font-mono mt-0.5">
                Score = Σ (factor_score × weight) — normalised to 0–100
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {scoreWeights.map((item) => (
              <div key={item.factor}>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] ${item.textColor}`}
                      aria-hidden="true"
                    >
                      {item.icon}
                    </div>
                    <div>
                      <p className="text-[13px] font-bold text-white">{item.factor}</p>
                      <p className={`text-[10px] font-bold ${item.textColor}`}>
                        Weight: {item.weight}%
                      </p>
                    </div>
                  </div>
                  <span className={`shrink-0 text-2xl font-black ${item.textColor}`}>
                    {item.weight}%
                  </span>
                </div>
                <div className="mb-2 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
                  <div
                    className={`h-full rounded-full ${item.color}`}
                    style={{ width: `${item.weight * 3.33}%` }}
                    aria-label={`${item.weight}% weight`}
                  />
                </div>
                <p className="text-[12px] leading-5 text-slate-400">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── STORIES GENERATION ────────────────────────────────────────── */}
      <Section
        id="stories-heading"
        badge="Narrative Engine"
        badgeColor="text-amber-400"
        title="Stories: How AI Creates Investment Narratives"
        subtitle="MarketRipple's story generation pipeline transforms clusters of related events into coherent investment theses — with evidence, timeline, and risk factors."
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {storiesSteps.map((step, i) => (
            <div
              key={step.title}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5"
            >
              <div className="mb-3 flex items-center gap-2.5">
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-xl border ${step.color}`}
                  aria-hidden="true"
                >
                  {step.icon}
                </div>
                <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">
                  Stage {i + 1}
                </span>
              </div>
              <h3 className="text-[14px] font-bold text-white">{step.title}</h3>
              <p className="mt-2 text-[12px] leading-5 text-slate-400">{step.description}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ── CONFIDENCE SCORE CALCULATION ──────────────────────────────── */}
      <Section
        id="confidence-heading"
        badge="Scoring Detail"
        badgeColor="text-indigo-400"
        title="Confidence Score: The Full Calculation"
        subtitle="Confidence is not a gut feeling — it is a computed estimate that accounts for evidence quality, recency, corroboration, and domain-specific model accuracy."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            {
              icon: <CheckCircle2 className="h-5 w-5" />,
              factor: "Source Credibility",
              weight: "30%",
              detail:
                "Official regulatory sources (RBI, SEBI, NSE, BSE, Ministry filings) receive maximum credibility weight. Verified financial journalism is weighted at 70–80%. Social media and unverified sources receive minimal weight and are flagged as low-credibility inputs.",
              color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
            },
            {
              icon: <Clock className="h-5 w-5" />,
              factor: "Recency Weighting",
              weight: "20%",
              detail:
                "Information decays in relevance. Events from the past 7 days carry full weight; 7–30 days carry 80% weight; 30–90 days carry 60%. For structural relationships (sector-commodity linkages), historical data retains higher relevance.",
              color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
            },
            {
              icon: <Layers className="h-5 w-5" />,
              factor: "Source Corroboration",
              weight: "25%",
              detail:
                "When 3+ independent sources confirm the same fact or relationship, confidence receives a significant boost. A single-source claim carries baseline confidence; five or more independent confirmations pushes a signal to Very High confidence tier.",
              color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
            },
            {
              icon: <BarChart2 className="h-5 w-5" />,
              factor: "Historical Accuracy",
              weight: "15%",
              detail:
                "Each event-outcome relationship is backtested on 14 years of data. The model's own historical prediction accuracy for that specific relationship type adjusts the base confidence. A relationship the model has predicted correctly 90% of the time earns higher confidence.",
              color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
            },
            {
              icon: <Target className="h-5 w-5" />,
              factor: "Domain Expertise",
              weight: "10%",
              detail:
                "Sector-specific sub-models for Banking, IT, Pharma, Commodities, and Infrastructure have been calibrated on sector-expert knowledge. Cross-sector effects use the general model; within-sector effects benefit from the specialised sub-model's higher precision.",
              color: "text-rose-400 bg-rose-500/10 border-rose-500/20",
            },
          ].map((item) => (
            <div
              key={item.factor}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5"
            >
              <div className="mb-3 flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${item.color}`}
                    aria-hidden="true"
                  >
                    {item.icon}
                  </div>
                  <div>
                    <p className="text-[14px] font-bold text-white">{item.factor}</p>
                    <p className="text-[10px] text-slate-500">
                      Contributes {item.weight} of total confidence
                    </p>
                  </div>
                </div>
              </div>
              <p className="text-[12px] leading-5 text-slate-400">{item.detail}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ── AI LIMITATIONS ────────────────────────────────────────────── */}
      <Section
        id="limitations-heading"
        badge="Honest Disclosure"
        badgeColor="text-rose-400"
        title="AI Limitations"
        subtitle="Transparency requires honesty about what AI can and cannot do. These are the genuine limitations of MarketRipple's analytical systems."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {limitations.map((lim) => {
            const severityColor =
              lim.severity === "high"
                ? "border-rose-500/20 bg-rose-500/[0.04]"
                : lim.severity === "medium"
                ? "border-amber-500/20 bg-amber-500/[0.04]"
                : "border-slate-600/30 bg-white/[0.02]";
            const iconColor =
              lim.severity === "high"
                ? "text-rose-400 bg-rose-500/10 border-rose-500/25"
                : lim.severity === "medium"
                ? "text-amber-400 bg-amber-500/10 border-amber-500/25"
                : "text-slate-400 bg-slate-700/20 border-slate-600/30";
            return (
              <div
                key={lim.title}
                className={`rounded-xl border p-5 ${severityColor}`}
              >
                <div
                  className={`mb-3 flex h-9 w-9 items-center justify-center rounded-xl border ${iconColor}`}
                  aria-hidden="true"
                >
                  {lim.icon}
                </div>
                <h3 className="text-[14px] font-bold text-white">{lim.title}</h3>
                <p className="mt-2 text-[12px] leading-5 text-slate-400">
                  {lim.description}
                </p>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ── WHY INDEPENDENT RESEARCH MATTERS ─────────────────────────── */}
      <section aria-labelledby="human-judgment-heading">
        <div className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6 md:p-8">
          <div className="flex items-start gap-4">
            <div
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-sky-500/25 bg-sky-500/10 text-sky-400"
              aria-hidden="true"
            >
              <UserCheck className="h-6 w-6" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500 mb-1">
                Human Judgment
              </p>
              <h2
                id="human-judgment-heading"
                className="text-xl font-black text-white"
              >
                Why Independent Research Matters
              </h2>
              <p className="mt-3 text-sm leading-6 text-slate-400 max-w-2xl">
                MarketRipple is designed to augment human investment judgment, not replace it.
                AI excels at processing large volumes of structured information, identifying
                historical patterns, and surfacing non-obvious connections across thousands
                of data points simultaneously.
              </p>
              <p className="mt-3 text-sm leading-6 text-slate-400 max-w-2xl">
                Human investors bring irreplaceable judgment: qualitative assessment of
                management quality, reading between the lines of regulatory intent,
                contrarian thinking that departs from consensus, and the lived experience
                of navigating market cycles.
              </p>
              <p className="mt-3 text-sm leading-6 text-slate-400 max-w-2xl">
                We recommend using MarketRipple to generate and stress-test hypotheses, then
                verifying your conclusions against primary sources (BSE/NSE filings, RBI
                releases, company annual reports) before making any investment decision.
                MarketRipple is a powerful second opinion — your first opinion should always
                be your own informed judgment.
              </p>
              <div className="mt-5 flex items-center gap-2 rounded-xl border border-sky-500/20 bg-sky-500/[0.06] p-3">
                <ShieldAlert className="h-4 w-4 shrink-0 text-sky-400" aria-hidden="true" />
                <p className="text-[12px] text-sky-300">
                  MarketRipple does not provide personalised investment advice. All analysis
                  is for informational purposes only. Past patterns do not guarantee future outcomes.
                </p>
              </div>
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
          See the system in action
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          Explore how MarketRipple reasons through real market events — and discover where all the underlying data comes from.
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
            href="/data-sources"
            className="flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] px-5 py-2.5 text-sm font-semibold text-slate-300 transition hover:border-white/25 hover:text-white"
            aria-label="View Data Sources"
          >
            <Link2 className="h-4 w-4" />
            Data Sources
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </section>
    </main>
  );
}
