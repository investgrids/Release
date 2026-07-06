import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import {
  Eye,
  Tag,
  GitBranch,
  Lightbulb,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowRight,
  CircleDot,
  Banknote,
  Home,
  Car,
  Monitor,
  Landmark,
  DollarSign,
  BarChart2,
  Brain,
  Globe,
  Link2,
  BookOpen,
} from "lucide-react";

export const metadata: Metadata = {
  title: "How MarketRipple Thinks — AI Reasoning & Market Relationships",
  description:
    "Understand how MarketRipple's AI reasons through market events — from triggers to ripple effects — with full transparency on confidence levels and alternative scenarios.",
  openGraph: {
    title: "How MarketRipple Thinks — AI Reasoning & Market Relationships",
    description:
      "See the full reasoning chain behind every market insight: confidence levels, causal relationships, and alternative scenario analysis.",
  },
};

// ── Confidence Badge ──────────────────────────────────────────────────────────
function ConfidenceBadge({ pct }: { pct: number }) {
  const color =
    pct >= 90
      ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/25"
      : pct >= 75
      ? "text-sky-400 bg-sky-500/10 border-sky-500/25"
      : pct >= 50
      ? "text-amber-400 bg-amber-500/10 border-amber-500/25"
      : "text-slate-400 bg-slate-700/30 border-slate-600/30";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${color}`}>
      <CircleDot className="h-2.5 w-2.5" />
      {pct}% confidence
    </span>
  );
}

// ── Node in the cascade chain ─────────────────────────────────────────────────
interface ChainNode {
  label: string;
  sublabel?: string;
  confidence?: number;
  why?: string;
  companies?: string[];
  type: "trigger" | "intermediate" | "leaf";
  impactScore?: number;
  children?: ChainNode[];
  color?: string;
}

function CascadeNode({
  node,
  depth = 0,
}: {
  node: ChainNode;
  depth?: number;
}) {
  const indent = depth * 20;
  const borderColor =
    node.type === "trigger"
      ? "border-rose-500/40 bg-rose-500/[0.06]"
      : node.type === "intermediate"
      ? "border-amber-500/20 bg-amber-500/[0.04]"
      : "border-slate-600/30 bg-white/[0.02]";

  const dotColor =
    node.type === "trigger"
      ? "bg-rose-500"
      : node.type === "intermediate"
      ? "bg-amber-400"
      : "bg-slate-500";

  return (
    <div style={{ marginLeft: indent }} className="relative">
      {depth > 0 && (
        <div
          className="absolute left-[-20px] top-4 h-px w-5 border-t border-dashed border-slate-700"
          aria-hidden="true"
        />
      )}
      <div
        className={`rounded-xl border p-3 mb-1 ${borderColor}`}
      >
        <div className="flex flex-wrap items-start gap-2">
          <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${dotColor}`} aria-hidden="true" />
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-semibold text-white leading-snug">
                {node.label}
              </span>
              {node.impactScore !== undefined && (
                <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-bold text-rose-300">
                  Impact Score: {node.impactScore}
                </span>
              )}
              {node.confidence !== undefined && (
                <ConfidenceBadge pct={node.confidence} />
              )}
            </div>
            {node.sublabel && (
              <p className="mt-0.5 text-[11px] text-slate-400">{node.sublabel}</p>
            )}
            {node.why && (
              <p className="mt-1 text-[11px] italic text-slate-500">
                Why: {node.why}
              </p>
            )}
            {node.companies && node.companies.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {node.companies.map((c) => (
                  <span
                    key={c}
                    className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-300"
                  >
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {node.children && node.children.length > 0 && (
        <div className="ml-4 border-l border-dashed border-slate-700 pl-0">
          {node.children.map((child, i) => (
            <CascadeNode key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Israel-Iran Cascade Data ───────────────────────────────────────────────────
const israelIranChain: ChainNode = {
  type: "trigger",
  label: "Israel–Iran Military Conflict",
  sublabel: "Geopolitical Trigger Event",
  impactScore: 9.1,
  why: "Direct military confrontation between two major Middle Eastern powers",
  children: [
    {
      type: "intermediate",
      label: "Strait of Hormuz Disruption Risk",
      sublabel: "Shipping route closure or restricted passage",
      confidence: 88,
      why: "20% of global oil transits this 33 km-wide chokepoint daily",
      children: [
        {
          type: "intermediate",
          label: "Crude Oil Price Spike (+15–25%)",
          sublabel: "Brent crude surges on supply disruption fears",
          confidence: 85,
          why: "Historical precedent: Gulf War 1990 drove oil from $18 to $46/bbl in 4 months",
          children: [
            {
              type: "intermediate",
              label: "Brent Sustained Above $100/bbl",
              sublabel: "Elevated for 2–3 months in base case",
              confidence: 72,
              children: [
                {
                  type: "leaf",
                  label: "India Aviation Turbine Fuel +18%",
                  sublabel: "ATF pricing linked to international crude benchmarks",
                  confidence: 80,
                  why: "India imports 85% of crude oil requirements; ATF has no price cap",
                  companies: ["IndiGo (INDIGO)", "Air India", "SpiceJet (SPICEJET)", "InterGlobe Aviation"],
                },
                {
                  type: "leaf",
                  label: "India Petrol / Diesel +₹8–12 per litre",
                  sublabel: "Retail fuel prices under pressure from OMC margin squeeze",
                  confidence: 74,
                  why: "OMCs absorb short-term losses; government must adjust or subsidise",
                  companies: ["HPCL", "BPCL", "Indian Oil (IOC)"],
                  children: [
                    {
                      type: "leaf",
                      label: "Consumer Inflation (CPI) +0.6–0.8%",
                      sublabel: "Fuel feeds into core and food inflation via transport costs",
                      confidence: 71,
                      children: [
                        {
                          type: "leaf",
                          label: "RBI Forced to Pause Rate Cuts",
                          sublabel: "Monetary policy becomes more restrictive than base case",
                          confidence: 68,
                          why: "RBI inflation target is 4%; shock pushes CPI toward 5.5%+",
                          children: [
                            {
                              type: "leaf",
                              label: "Real Estate Demand Softens",
                              sublabel: "Higher cost of home loans dampens buyer sentiment",
                              confidence: 65,
                              companies: ["DLF", "Godrej Properties", "Prestige Estates"],
                            },
                            {
                              type: "leaf",
                              label: "Auto Loans More Expensive",
                              sublabel: "NBFCs and banks raise auto loan rates; two-wheeler volumes at risk",
                              confidence: 63,
                              companies: ["Bajaj Finance", "Shriram Finance", "M&M Financial"],
                            },
                          ],
                        },
                      ],
                    },
                  ],
                },
                {
                  type: "leaf",
                  label: "INR/USD Depreciation Risk",
                  sublabel: "India's current account deficit widens on higher import bill",
                  confidence: 67,
                  why: "Every $10/bbl rise in crude adds ~$15 bn to India's annual import bill",
                  children: [
                    {
                      type: "leaf",
                      label: "IT Sector Margin Pressure",
                      sublabel: "Foreign revenue in USD but costs in INR; hedging reduces but doesn't eliminate risk",
                      confidence: 71,
                      companies: ["TCS", "Infosys", "Wipro", "HCL Tech"],
                    },
                    {
                      type: "leaf",
                      label: "Pharma: API Imports Costlier",
                      sublabel: "~68% of India's API imports from China; priced in USD",
                      confidence: 64,
                      companies: ["Sun Pharma", "Dr. Reddy's", "Cipla"],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    },
  ],
};

// ── RBI Rate Cut Chain ─────────────────────────────────────────────────────────
const rbiRateCutNodes: Array<{ sector: string; direction: "positive" | "negative" | "mixed"; effect: string; companies: string[]; icon: ReactNode; confidence: number }> = [
  {
    sector: "Banking & NBFCs",
    direction: "positive",
    effect: "Net interest margins compress initially, but loan book growth accelerates. Retail credit demand rises. Asset quality improves as borrowers find EMIs more manageable.",
    companies: ["HDFC Bank", "ICICI Bank", "SBI", "Bajaj Finance", "Cholamandalam"],
    icon: <Landmark className="h-4 w-4" />,
    confidence: 82,
  },
  {
    sector: "Real Estate",
    direction: "positive",
    effect: "Home loan rates fall by 25–40 bps with a 6–8 week lag. Affordable housing segment sees 12–18% uptick in enquiries. Inventory absorption accelerates in Tier-1 cities.",
    companies: ["DLF", "Godrej Properties", "Macrotech (Lodha)", "Prestige Estates"],
    icon: <Home className="h-4 w-4" />,
    confidence: 78,
  },
  {
    sector: "Auto",
    direction: "positive",
    effect: "Two-wheeler and passenger vehicle EMIs fall ₹300–500/month. Consumer sentiment improves. Festive season impact amplified if cuts coincide with H2.",
    companies: ["Maruti Suzuki", "Tata Motors", "Hero MotoCorp", "Bajaj Auto"],
    icon: <Car className="h-4 w-4" />,
    confidence: 75,
  },
  {
    sector: "IT / Technology",
    direction: "mixed",
    effect: "Rupee appreciation risk on rate cuts reduces USD revenue value. However, domestic IT spending improves as capex budgets loosen.",
    companies: ["TCS", "Infosys", "Wipro"],
    icon: <Monitor className="h-4 w-4" />,
    confidence: 58,
  },
];

// ── Relationship Types ─────────────────────────────────────────────────────────
const relationshipTypes = [
  {
    icon: <Banknote className="h-5 w-5" />,
    name: "Commodity Chain",
    description: "How a change in commodity price (crude, gold, copper, natural gas) propagates through downstream industries, affecting input costs, margins, and consumer prices.",
    example: "Crude oil rise → ATF rise → airline cost pressure → ticket price inflation → tourism slowdown",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: <DollarSign className="h-5 w-5" />,
    name: "Currency Effect",
    description: "How INR movement creates asymmetric impact — exporters benefit from a weak rupee while importers face higher costs. Tracks hedging ratios and natural hedges.",
    example: "INR weakens → IT exports get USD revenue boost → Pharma API imports costlier → Oil companies' margins compress",
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    icon: <GitBranch className="h-5 w-5" />,
    name: "Sector Contagion",
    description: "How weakness in one sector spreads to adjacent sectors through supply chains, credit linkages, or sentiment contagion. Critical for understanding systemic risks.",
    example: "NBFC liquidity crisis → developer project stalls → cement & steel demand drops → infra stocks re-rate",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: <Landmark className="h-5 w-5" />,
    name: "Policy Response",
    description: "How government ministries and RBI react to economic conditions. Models historical policy response functions and likely intervention timelines and magnitudes.",
    example: "Inflation spike → RBI hawkish pivot → rate hikes → credit tightening → consumption slowdown",
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  },
  {
    icon: <BarChart2 className="h-5 w-5" />,
    name: "Corporate Earnings",
    description: "Direct P&L impact modeling — revenue sensitivity, cost pass-through ability, margin elasticity, and leverage effects on EPS for each event scenario.",
    example: "Raw material cost +15% → Company with pricing power absorbs 60%, passes 40% → EPS impact calculated",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: <Brain className="h-5 w-5" />,
    name: "Sentiment Shift",
    description: "How market psychology — FII flows, retail participation, options positioning — amplifies or dampens fundamental impacts. Tracks fear/greed indicators.",
    example: "Global risk-off → FII sell Indian equities → INR weakens → Nifty corrects → VIX spikes → options skew shifts",
    color: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  },
];

// ── Alternative Scenarios ──────────────────────────────────────────────────────
const scenarios = [
  {
    label: "Scenario A — Bull Case",
    probability: "20%",
    trigger: "Conflict contained within 7 days; ceasefire brokered by US/Arab League",
    oilOutcome: "Crude retreats to $80–85/bbl within 2 weeks",
    marketOutcome:
      "Airlines recover sharply. OMC stocks rally. INR strengthens. RBI resumes rate cut path in next MPC. Aviation stocks offer a tactical buy opportunity on the initial spike.",
    recommendation: "Buy on dip: IndiGo, SpiceJet. Overweight HPCL, BPCL.",
    icon: <TrendingUp className="h-5 w-5" />,
    color: "border-emerald-500/30 bg-emerald-500/[0.05]",
    badgeColor: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    recColor: "text-emerald-400",
  },
  {
    label: "Scenario B — Base Case",
    probability: "55%",
    trigger: "Prolonged tension; tit-for-tat strikes but Strait remains open",
    oilOutcome: "Crude sustains $95–105/bbl for 2–3 months with high volatility",
    marketOutcome:
      "Aviation sector underperforms. OMCs margin-squeezed until price revision. Consumer staples lag. Defensives (IT exporters, pharma) outperform. Selective sector rotation advised.",
    recommendation: "Defensive positioning: Overweight IT, Pharma, Gold ETFs. Underweight Airlines, OMCs.",
    icon: <Minus className="h-5 w-5" />,
    color: "border-amber-500/30 bg-amber-500/[0.05]",
    badgeColor: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    recColor: "text-amber-400",
  },
  {
    label: "Scenario C — Bear Case",
    probability: "25%",
    trigger: "Strait of Hormuz blocked; Iran mines shipping lanes",
    oilOutcome: "Crude spikes above $130/bbl; ATF and diesel shortages reported",
    marketOutcome:
      "Emergency RBI action. Government announces fuel subsidy. Nifty50 corrects 8–12%. FII sell-off. INR hits new lows. Broad market sell-off with PSU energy sector as only safe haven.",
    recommendation: "Risk-off: Raise cash. Buy Sovereign Gold Bonds. Short Nifty via puts.",
    icon: <TrendingDown className="h-5 w-5" />,
    color: "border-rose-500/30 bg-rose-500/[0.05]",
    badgeColor: "bg-rose-500/15 text-rose-300 border-rose-500/30",
    recColor: "text-rose-400",
  },
];

// ── Confidence Levels ──────────────────────────────────────────────────────────
const confidenceLevels = [
  {
    range: "90–100%",
    label: "Very High",
    bar: 95,
    color: "bg-emerald-500",
    textColor: "text-emerald-400",
    description:
      "Multiple corroborating primary sources. Strong historical precedent with similar outcomes observed 3+ times. High analytical consensus across models. Low sensitivity to alternative assumptions.",
    examples: "Official RBI announcements, Union Budget disclosures, NSE/BSE regulatory filings",
  },
  {
    range: "75–89%",
    label: "High",
    bar: 82,
    color: "bg-sky-500",
    textColor: "text-sky-400",
    description:
      "Strong evidence from reliable sources. Reasonable historical precedent. Some uncertainty factors present but not dominant. Model outputs converge on similar directional conclusions.",
    examples: "Commodity price impacts on downstream sectors, well-documented macro-sector relationships",
  },
  {
    range: "50–74%",
    label: "Medium",
    bar: 62,
    color: "bg-amber-500",
    textColor: "text-amber-400",
    description:
      "Reasonable evidence base with moderate uncertainty. Conflicting signals possible. Historical patterns exist but with higher variance. Alternative outcomes cannot be ruled out.",
    examples: "Currency impact on partially-hedged exporters, policy response timing estimates",
  },
  {
    range: "Below 50%",
    label: "Low",
    bar: 35,
    color: "bg-slate-500",
    textColor: "text-slate-400",
    description:
      "Limited evidence. High uncertainty. Early-stage hypothesis based on theoretical reasoning rather than empirical confirmation. Treat as directional signal only, not actionable intelligence.",
    examples: "Second-order geopolitical ripple effects, long-horizon regulatory predictions",
  },
];

// ── Thinking Framework Steps ───────────────────────────────────────────────────
const frameworkSteps = [
  {
    number: "01",
    icon: <Eye className="h-6 w-6" />,
    name: "Observe",
    tagline: "Monitor & Detect",
    description:
      "MarketRipple continuously monitors 40+ data streams including RBI press releases, SEBI circulars, NSE/BSE announcements, global newswires, and commodity exchanges. Events are detected within minutes of occurrence.",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    number: "02",
    icon: <Tag className="h-6 w-6" />,
    name: "Classify",
    tagline: "Categorise & Score",
    description:
      "Each event is classified by type (Monetary Policy, Geopolitical, Corporate, Commodity), assigned an impact score (0–10), and mapped to relevant sectors and listed companies using a trained entity recognition model.",
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    number: "03",
    icon: <GitBranch className="h-6 w-6" />,
    name: "Connect",
    tagline: "Trace Relationships",
    description:
      "The Ripple Engine traverses MarketRipple's knowledge graph — a directed network of events, sectors, commodities, currencies, and companies connected by weighted causal edges. Each edge carries a confidence score derived from historical data (2010–2024) and Bayesian inference.",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    number: "04",
    icon: <Lightbulb className="h-6 w-6" />,
    name: "Conclude",
    tagline: "Generate Insights",
    description:
      "After mapping the full dependency graph up to 4 levels deep, MarketRipple generates structured insights: primary impacts, second-order effects, affected companies with directional calls, confidence-weighted scenarios, and portfolio positioning recommendations.",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
];

// ── Page ───────────────────────────────────────────────────────────────────────
export default function HowMarketRippleThinksPage() {
  return (
    <main className="min-w-0 space-y-16 pb-16" aria-label="How MarketRipple Thinks">

      {/* ── HERO ──────────────────────────────────────────────────────── */}
      <section aria-labelledby="hero-heading">
        <div className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-violet-950/60 via-[#080c14] to-sky-950/40 px-8 py-12 md:px-12 md:py-16">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-400">
            Transparent AI
          </p>
          <h1
            id="hero-heading"
            className="mt-3 text-[28px] font-black leading-tight text-white md:text-[40px]"
          >
            AI That Shows Its Work
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300 md:text-lg">
            MarketRipple doesn&apos;t just give you answers — it shows you the reasoning chain,
            the confidence levels, and the alternative scenarios. Every insight is
            traceable back to its source events, historical analogues, and causal logic.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/ai-methodology"
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:opacity-90"
            >
              <Brain className="h-4 w-4" />
              AI Methodology
            </Link>
            <Link
              href="/data-sources"
              className="flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] px-5 py-2.5 text-sm font-semibold text-slate-300 transition hover:border-white/25 hover:text-white"
            >
              <BookOpen className="h-4 w-4" />
              Data Sources
            </Link>
          </div>
        </div>
      </section>

      {/* ── THINKING FRAMEWORK ────────────────────────────────────────── */}
      <section aria-labelledby="framework-heading" className="space-y-6">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            Methodology
          </p>
          <h2
            id="framework-heading"
            className="mt-2 text-[22px] font-black text-white md:text-[28px]"
          >
            The Thinking Framework
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Every MarketRipple insight follows a four-stage reasoning process — from raw
            data ingestion to structured, actionable intelligence.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {frameworkSteps.map((step) => (
            <div
              key={step.number}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5"
            >
              <div className="mb-4 flex items-center justify-between">
                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-xl border ${step.color}`}
                  aria-hidden="true"
                >
                  {step.icon}
                </div>
                <span className="text-[32px] font-black text-white/[0.06] leading-none">
                  {step.number}
                </span>
              </div>
              <h3 className="text-base font-bold text-white">{step.name}</h3>
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500 mt-0.5 mb-2">
                {step.tagline}
              </p>
              <p className="text-[12px] leading-5 text-slate-400">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CASE STUDY: ISRAEL–IRAN ───────────────────────────────────── */}
      <section aria-labelledby="case-study-1-heading" className="space-y-6">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-rose-400">
              Live Case Study
            </p>
            <h2
              id="case-study-1-heading"
              className="mt-2 text-[22px] font-black text-white md:text-[28px]"
            >
              Israel–Iran Conflict: Full Ripple Chain
            </h2>
            <p className="mt-2 text-sm text-slate-400">
              How MarketRipple traces a geopolitical trigger all the way through to specific
              Indian listed companies — with confidence levels at every step.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-2">
            <Globe className="h-4 w-4 text-rose-400" />
            <span className="text-[12px] font-semibold text-rose-300">
              Geopolitical · Impact Score: 9.1
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5 md:p-7">
          <div className="mb-4 flex flex-wrap gap-3 text-[11px] text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-rose-500" />
              Trigger Event
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              Intermediate Effect
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-slate-500" />
              Downstream Impact
            </span>
            <span className="flex items-center gap-1.5">
              <CircleDot className="h-3 w-3 text-emerald-400" />
              Confidence score at each step
            </span>
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[500px]">
              <CascadeNode node={israelIranChain} depth={0} />
            </div>
          </div>
        </div>
      </section>

      {/* ── CONFIDENCE SYSTEM ─────────────────────────────────────────── */}
      <section aria-labelledby="confidence-heading" className="space-y-6">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            Uncertainty Quantification
          </p>
          <h2
            id="confidence-heading"
            className="mt-2 text-[22px] font-black text-white md:text-[28px]"
          >
            The Confidence System
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Every claim MarketRipple makes carries a confidence level — so you always know
            how much weight to place on each insight.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {confidenceLevels.map((level) => (
            <div
              key={level.label}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5"
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <span className={`text-lg font-black ${level.textColor}`}>
                    {level.label}
                  </span>
                  <span className="ml-2 text-[12px] text-slate-500">{level.range}</span>
                </div>
                <div className="text-right">
                  <span className={`text-2xl font-black ${level.textColor}`}>
                    {level.bar}%
                  </span>
                </div>
              </div>
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
                <div
                  className={`h-full rounded-full ${level.color}`}
                  style={{ width: `${level.bar}%` }}
                  aria-label={`${level.bar}% confidence level bar`}
                />
              </div>
              <p className="mt-3 text-[12px] leading-5 text-slate-300">
                {level.description}
              </p>
              <p className="mt-2 text-[11px] italic text-slate-500">
                Examples: {level.examples}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── RELATIONSHIP TYPES ────────────────────────────────────────── */}
      <section aria-labelledby="relationships-heading" className="space-y-6">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            Causal Graph
          </p>
          <h2
            id="relationships-heading"
            className="mt-2 text-[22px] font-black text-white md:text-[28px]"
          >
            How Relationships Are Built
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            MarketRipple&apos;s knowledge graph recognises six fundamental relationship types
            between events and market outcomes. Each type carries its own confidence
            model and propagation rules.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {relationshipTypes.map((rel) => (
            <div
              key={rel.name}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5"
            >
              <div
                className={`mb-4 flex h-10 w-10 items-center justify-center rounded-xl border ${rel.color}`}
                aria-hidden="true"
              >
                {rel.icon}
              </div>
              <h3 className="text-[14px] font-bold text-white">{rel.name}</h3>
              <p className="mt-2 text-[12px] leading-5 text-slate-400">
                {rel.description}
              </p>
              <div className="mt-3 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-600 mb-1">
                  Example Chain
                </p>
                <p className="text-[11px] leading-5 text-slate-400 italic">
                  {rel.example}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── ALTERNATIVE OUTCOMES ──────────────────────────────────────── */}
      <section aria-labelledby="scenarios-heading" className="space-y-6">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            Scenario Analysis
          </p>
          <h2
            id="scenarios-heading"
            className="mt-2 text-[22px] font-black text-white md:text-[28px]"
          >
            Alternative Outcomes: Israel–Iran
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            MarketRipple never presents a single deterministic forecast. The same trigger
            event generates three probability-weighted scenarios so you can position for
            multiple futures.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {scenarios.map((s) => (
            <div
              key={s.label}
              className={`rounded-xl border p-5 ${s.color}`}
            >
              <div className="mb-3 flex items-center gap-2">
                <div className={`flex h-8 w-8 items-center justify-center rounded-lg border ${s.badgeColor.replace("text-", "border-").replace("/15", "/30").replace("bg-", "").split(" ")[0]} bg-transparent`}>
                  {s.icon}
                </div>
                <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${s.badgeColor}`}>
                  {s.probability} probability
                </span>
              </div>
              <h3 className="text-[14px] font-bold text-white">{s.label}</h3>
              <div className="mt-3 space-y-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                    Trigger Condition
                  </p>
                  <p className="mt-0.5 text-[12px] leading-5 text-slate-300">
                    {s.trigger}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                    Oil Outcome
                  </p>
                  <p className="mt-0.5 text-[12px] leading-5 text-slate-300">
                    {s.oilOutcome}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                    Market Impact
                  </p>
                  <p className="mt-0.5 text-[12px] leading-5 text-slate-300">
                    {s.marketOutcome}
                  </p>
                </div>
                <div className={`rounded-lg border border-white/[0.06] bg-white/[0.02] p-3`}>
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500 mb-1">
                    AI Recommendation
                  </p>
                  <p className={`text-[12px] font-semibold leading-5 ${s.recColor}`}>
                    {s.recommendation}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── CASE STUDY 2: RBI RATE CUT ────────────────────────────────── */}
      <section aria-labelledby="case-study-2-heading" className="space-y-6">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-indigo-400">
            Case Study 2
          </p>
          <h2
            id="case-study-2-heading"
            className="mt-2 text-[22px] font-black text-white md:text-[28px]"
          >
            RBI Rate Cut: Monetary Policy Ripple Effects
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            A 50 bps repo rate cut flows through four major sectors in distinct ways —
            some benefit immediately, others face transitional pressure. Here&apos;s how
            MarketRipple maps the full picture.
          </p>
        </div>

        <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/[0.04] p-4 md:p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-indigo-400">
              <Landmark className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">
                Trigger Event
              </p>
              <p className="text-[14px] font-bold text-white">
                RBI MPC: Repo Rate Cut 50 bps (6.5% → 6.0%)
              </p>
            </div>
            <ConfidenceBadge pct={95} />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {rbiRateCutNodes.map((node) => {
            const directionStyle =
              node.direction === "positive"
                ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/[0.05]"
                : node.direction === "negative"
                ? "text-rose-400 border-rose-500/20 bg-rose-500/[0.05]"
                : "text-amber-400 border-amber-500/20 bg-amber-500/[0.05]";
            const directionLabel =
              node.direction === "positive"
                ? "Beneficiary"
                : node.direction === "negative"
                ? "Headwind"
                : "Mixed Impact";
            return (
              <div
                key={node.sector}
                className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5"
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-slate-400">
                      {node.icon}
                    </div>
                    <h3 className="text-[14px] font-bold text-white">{node.sector}</h3>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${directionStyle}`}>
                      {directionLabel}
                    </span>
                    <ConfidenceBadge pct={node.confidence} />
                  </div>
                </div>
                <p className="text-[12px] leading-5 text-slate-400">
                  {node.effect}
                </p>
                {node.companies.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <p className="w-full text-[10px] font-bold uppercase tracking-[0.15em] text-slate-600">
                      Key Companies
                    </p>
                    {node.companies.map((c) => (
                      <span
                        key={c}
                        className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-300"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────────────── */}
      <section aria-label="Further reading" className="rounded-xl border border-white/[0.08] bg-[#080c14] p-6 md:p-8">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Go Deeper
        </p>
        <h2 className="mt-2 text-xl font-black text-white">
          Understand the full system
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          Explore how our AI models are built, validated, and kept honest — and where
          all the underlying data comes from.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            href="/ai-methodology"
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:opacity-90"
            aria-label="Read AI Methodology"
          >
            <Brain className="h-4 w-4" />
            AI Methodology
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
