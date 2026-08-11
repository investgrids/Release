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
  ChevronRight,
  CircleDot,
  Banknote,
  Home,
  Car,
  Monitor,
  Landmark,
  Brain,
  Globe,
  Link2,
  BookOpen,
  Activity,
  Copy,
  Scale,
  History,
  Swords,
  Radio,
  Zap,
  ShieldCheck,
  Search,
  Database,
  Newspaper,
  HelpCircle,
  Building2,
  Radar,
  AlertTriangle,
  ShieldAlert,
} from "lucide-react";
import { safeJsonLd } from "@/lib/text";

const SITE_URL = "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "How MarketRipple AI Analyzes the Market",
  description:
    "See the data, reasoning, evidence and confidence behind every MarketRipple insight — from raw events to ripple effects, with real methodology.",
  alternates: { canonical: `${SITE_URL}/how-marketripple-thinks` },
  openGraph: {
    title: "How MarketRipple AI Analyzes the Market",
    description:
      "See the data, reasoning, evidence and confidence behind every MarketRipple insight — from raw events to ripple effects.",
    url: `${SITE_URL}/how-marketripple-thinks`,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

// ── Section wrapper (matches /ai-methodology) ─────────────────────────────
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

// ── Confidence Badge ──────────────────────────────────────────────────────────
function ConfidenceBadge({ pct }: { pct: number }) {
  const color =
    pct >= 90
      ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/25"
      : pct >= 75
      ? "text-sky-400 bg-sky-500/10 border-sky-500/25"
      : pct >= 50
      ? "text-amber-400 bg-amber-500/10 border-amber-500/25"
      : "text-text-secondary bg-text-primary/[0.07] border-surface-border/7";
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
}

// Depth 0 and 1 render open by default so the important part of the chain is
// visible immediately. From depth 2 onward, deeper effects sit behind a
// native <details> disclosure — expandable with no JavaScript required, and
// still fully present in the markup for crawlers.
function CascadeNode({ node, depth = 0 }: { node: ChainNode; depth?: number }) {
  const indent = depth * 20;
  const borderColor =
    node.type === "trigger"
      ? "border-rose-500/40 bg-rose-500/[0.06]"
      : node.type === "intermediate"
      ? "border-amber-500/20 bg-amber-500/[0.04]"
      : "border-surface-border/7 bg-text-primary/[0.02]";

  const dotColor =
    node.type === "trigger" ? "bg-rose-500" : node.type === "intermediate" ? "bg-amber-400" : "bg-slate-500";

  const nodeBody = (
    <div style={{ marginLeft: indent }} className="relative">
      {depth > 0 && (
        <div
          className="absolute left-[-20px] top-4 h-px w-5 border-t border-dashed border-surface-border/10"
          aria-hidden="true"
        />
      )}
      <div className={`rounded-xl border p-3 mb-1 ${borderColor}`}>
        <div className="flex flex-wrap items-start gap-2">
          <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${dotColor}`} aria-hidden="true" />
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-semibold text-text-primary leading-snug">{node.label}</span>
              {node.impactScore !== undefined && (
                <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-bold text-rose-600 dark:text-rose-300">
                  Impact Score: {node.impactScore}
                </span>
              )}
              {node.confidence !== undefined && <ConfidenceBadge pct={node.confidence} />}
            </div>
            {node.sublabel && <p className="mt-0.5 text-[11px] text-text-secondary">{node.sublabel}</p>}
            {node.why && <p className="mt-1 text-[11px] italic text-text-muted">Why: {node.why}</p>}
            {node.companies && node.companies.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {node.companies.map((c) => (
                  <span
                    key={c}
                    className="rounded-full border border-surface-border/10 bg-text-primary/[0.04] px-2 py-0.5 text-[10px] text-text-secondary"
                  >
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  if (!node.children || node.children.length === 0) return nodeBody;

  const childList = (
    <div className="ml-4 border-l border-dashed border-surface-border/10 pl-0">
      {node.children.map((child, i) => (
        <CascadeNode key={i} node={child} depth={depth + 1} />
      ))}
    </div>
  );

  if (depth < 1) {
    return (
      <>
        {nodeBody}
        {childList}
      </>
    );
  }

  return (
    <>
      {nodeBody}
      <details className="group ml-4" open={false}>
        <summary className="flex cursor-pointer list-none items-center gap-1 py-1 text-[11px] font-semibold text-violet-500 dark:text-violet-400">
          <ChevronRight className="h-3 w-3 transition group-open:rotate-90" aria-hidden="true" />
          Show {node.children.length} deeper effect{node.children.length > 1 ? "s" : ""}
        </summary>
        {childList}
      </details>
    </>
  );
}

// ── Israel-Iran Cascade Data (illustrative — see labeling below) ───────────
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

// ── RBI Rate Cut Chain (illustrative — see labeling below) ─────────────────
const rbiRateCutNodes: Array<{
  sector: string;
  direction: "positive" | "negative" | "mixed";
  effect: string;
  companies: string[];
  icon: ReactNode;
  confidence: number;
}> = [
  {
    sector: "Banking & NBFCs",
    direction: "positive",
    effect: "Net interest margins compress initially, but loan book growth accelerates. Retail credit demand rises.",
    companies: ["HDFC Bank", "ICICI Bank", "SBI", "Bajaj Finance", "Cholamandalam"],
    icon: <Landmark className="h-4 w-4" />,
    confidence: 82,
  },
  {
    sector: "Real Estate",
    direction: "positive",
    effect: "Home loan rates fall with a lag. Affordable housing enquiries typically pick up; inventory absorption accelerates.",
    companies: ["DLF", "Godrej Properties", "Macrotech (Lodha)", "Prestige Estates"],
    icon: <Home className="h-4 w-4" />,
    confidence: 78,
  },
  {
    sector: "Auto",
    direction: "positive",
    effect: "Two-wheeler and passenger vehicle EMIs fall. Consumer sentiment improves, especially heading into festive season.",
    companies: ["Maruti Suzuki", "Tata Motors", "Hero MotoCorp", "Bajaj Auto"],
    icon: <Car className="h-4 w-4" />,
    confidence: 75,
  },
  {
    sector: "IT / Technology",
    direction: "mixed",
    effect: "Rupee appreciation risk on rate cuts can reduce USD revenue value, though domestic IT spending typically improves as capex budgets loosen.",
    companies: ["TCS", "Infosys", "Wipro"],
    icon: <Monitor className="h-4 w-4" />,
    confidence: 58,
  },
];

// ── Relationship Types ─────────────────────────────────────────────────────
// The real, fixed taxonomy every edge in MarketRipple's knowledge graph is
// classified under (see IGEdge.edge_type in the backend graph model). The
// number of actual edges grows continuously as new events are ingested —
// these seven types are what stays constant.
const relationshipTypes = [
  {
    icon: <TrendingUp className="h-5 w-5" />,
    name: "Benefits",
    description: "The plainest edge in the graph — an event, trend, or entity creates a direct tailwind for another's revenue, margins, or sentiment.",
    example: "RBI repo rate cut → NBFCs & housing financiers benefits (lower cost of funds, faster credit growth)",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: <TrendingDown className="h-5 w-5" />,
    name: "Hurts",
    description: "The inverse of benefits — direct cost pressure, demand destruction, or margin compression flowing from one entity to another.",
    example: "Crude oil price spike → airlines hurts (ATF cost surge erodes margins)",
    color: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  },
  {
    icon: <Banknote className="h-5 w-5" />,
    name: "Supplies",
    description: "A literal upstream-to-downstream input relationship — raw materials, components, or intermediate goods. The most concrete, verifiable edge type in the graph.",
    example: "Chinese bulk-drug manufacturers supplies Indian pharma companies (API intermediates)",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: <GitBranch className="h-5 w-5" />,
    name: "Depends_on",
    description: "A broader structural reliance than a direct supply link — an entity's output or pricing is tied to an import, a benchmark, or a regulatory approval.",
    example: "Oil marketing companies depends_on the international Brent crude benchmark for retail fuel pricing",
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  },
  {
    icon: <Swords className="h-5 w-5" />,
    name: "Competes_with",
    description: "Two companies or sectors vie for the same customers, market share, or capital — a gain for one typically comes at the other's expense.",
    example: "IndiGo competes_with SpiceJet & Air India for domestic passenger market share",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: <Radio className="h-5 w-5" />,
    name: "Influences",
    description: "A softer, non-mechanical directional pull — sentiment, positioning, or correlation rather than a hard causal chain. Carries wider confidence bands than the harder edge types.",
    example: "Sustained FII selling influences INR direction, even without a direct fundamental link",
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    icon: <Zap className="h-5 w-5" />,
    name: "Triggered_by",
    description: "The root-cause edge — an effect's link back to the event that set it in motion. This is the edge the Ripple Engine walks backward to answer \"why\" at every node in a cascade, like the case study below.",
    example: "Crude oil price spike triggered_by Strait of Hormuz disruption risk",
    color: "text-fuchsia-400 bg-fuchsia-500/10 border-fuchsia-500/20",
  },
];

// ── Alternative Scenarios ──────────────────────────────────────────────────
// "meaning" replaces the previous "recommendation" fields, which used
// directive buy/sell/short language ("Buy on dip", "Short Nifty via puts").
// MarketRipple does not issue trade instructions (see /ai-methodology,
// "What MarketRipple Does — and Doesn't Do") — these now describe which
// sectors would likely see relief or pressure, not what to do about it.
const scenarios = [
  {
    label: "Scenario A — Bull Case",
    probability: "20%",
    trigger: "Conflict contained within 7 days; ceasefire brokered by US/Arab League",
    oilOutcome: "Crude retreats to $80–85/bbl within 2 weeks",
    marketOutcome: "Airlines and OMC stocks would likely see the sharpest relief rally. INR strengthens. A resumed RBI rate-cut path would be a broader tailwind.",
    meaning: "Sectors likely to see relief: Aviation, Oil Marketing Companies, Banking (if rate cuts resume).",
    icon: <TrendingUp className="h-5 w-5" />,
    color: "border-emerald-500/30 bg-emerald-500/[0.05]",
    badgeColor: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-emerald-500/30",
    recColor: "text-emerald-600 dark:text-emerald-400",
  },
  {
    label: "Scenario B — Base Case",
    probability: "55%",
    trigger: "Prolonged tension; tit-for-tat strikes but Strait remains open",
    oilOutcome: "Crude sustains $95–105/bbl for 2–3 months with high volatility",
    marketOutcome: "Aviation underperforms and OMCs stay margin-squeezed until the next price revision. Consumer staples lag. Defensives historically hold up better in this kind of prolonged, volatile-oil environment.",
    meaning: "Sectors historically more resilient: IT exporters, Pharma. Sectors typically under more pressure: Airlines, OMCs.",
    icon: <Minus className="h-5 w-5" />,
    color: "border-amber-500/30 bg-amber-500/[0.05]",
    badgeColor: "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-500/30",
    recColor: "text-amber-600 dark:text-amber-400",
  },
  {
    label: "Scenario C — Bear Case",
    probability: "25%",
    trigger: "Strait of Hormuz blocked; Iran mines shipping lanes",
    oilOutcome: "Crude spikes above $130/bbl; ATF and diesel shortages reported",
    marketOutcome: "Broad market stress: emergency policy response likely, FII selling pressure, INR at risk of new lows. Energy-import-dependent sectors face the most direct pressure.",
    meaning: "Most exposed: import-dependent sectors (aviation, chemicals). PSU energy names are typically more insulated in this scenario.",
    icon: <TrendingDown className="h-5 w-5" />,
    color: "border-rose-500/30 bg-rose-500/[0.05]",
    badgeColor: "bg-rose-500/15 text-rose-600 dark:text-rose-300 border-rose-500/30",
    recColor: "text-rose-600 dark:text-rose-400",
  },
];

// ── Confidence Levels ──────────────────────────────────────────────────────
const confidenceLevels = [
  {
    range: "90–100%",
    label: "Very High",
    bar: 95,
    color: "bg-emerald-500",
    textColor: "text-emerald-400",
    description:
      "Multiple corroborating primary sources. Strong historical precedent with similar outcomes observed repeatedly. Low sensitivity to alternative assumptions.",
    examples: "Official RBI announcements, Union Budget disclosures, NSE/BSE regulatory filings",
  },
  {
    range: "75–89%",
    label: "High",
    bar: 82,
    color: "bg-sky-500",
    textColor: "text-sky-400",
    description:
      "Strong evidence from reliable sources. Reasonable historical precedent. Some uncertainty factors present but not dominant.",
    examples: "Commodity price impacts on downstream sectors, well-documented macro-sector relationships",
  },
  {
    range: "50–74%",
    label: "Medium",
    bar: 62,
    color: "bg-amber-500",
    textColor: "text-amber-400",
    description:
      "Reasonable evidence base with moderate uncertainty. Conflicting signals possible. Historical patterns exist but with higher variance.",
    examples: "Currency impact on partially-hedged exporters, policy response timing estimates",
  },
  {
    range: "Below 50%",
    label: "Low",
    bar: 35,
    color: "bg-slate-500",
    textColor: "text-text-secondary",
    description:
      "Limited evidence. High uncertainty. Early-stage hypothesis based on reasoning rather than empirical confirmation. Treat as a directional signal only.",
    examples: "Second-order geopolitical ripple effects, long-horizon regulatory predictions",
  },
];

// ── Thinking Framework Steps ────────────────────────────────────────────────
// Two corrections from the previous version, both verified against the real
// backend on 2026-08-11 (the same corrections already applied on
// /ai-methodology, since both pages describe the same underlying systems):
//   - Connect: removed "and Bayesian inference" — no Bayesian inference
//     implementation exists anywhere in the codebase. The real mechanism is
//     a stored per-edge confidence value, multiplicatively attenuated as it
//     propagates through the graph.
//   - Conclude: removed "portfolio positioning recommendations" — MarketRipple
//     does not issue buy/sell/position instructions (see the "Does — and
//     Doesn't Do" section below); replaced with an accurate description of
//     what the pipeline actually outputs.
const frameworkSteps = [
  {
    number: "01",
    icon: <Eye className="h-6 w-6" />,
    name: "Observe",
    tagline: "Monitor & Detect",
    description: (
      <>
        MarketRipple continuously monitors RBI and SEBI releases, NSE/BSE announcements, global
        newswires, and commodity exchanges. News and exchange sources are polled every 15 minutes,
        and regulatory sources hourly — see{" "}
        <a href="#data-sources-heading" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">
          Data Sources
        </a>{" "}
        below for the full breakdown.
      </>
    ),
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    number: "02",
    icon: <Tag className="h-6 w-6" />,
    name: "Classify",
    tagline: "Categorise & Score",
    description: (
      <>
        Each event is classified by type (Monetary Policy, Geopolitical, Corporate, Commodity),
        assigned an impact score, and mapped to relevant sectors and{" "}
        <Link href="/companies" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">
          companies
        </Link>{" "}
        within MarketRipple&apos;s actively tracked universe of{" "}
        <Link href="/companies" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">
          512 NSE-listed companies
        </Link>
        .
      </>
    ),
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
  {
    number: "03",
    icon: <GitBranch className="h-6 w-6" />,
    name: "Connect",
    tagline: "Trace Relationships",
    description: (
      <>
        The{" "}
        <Link href="/ripple" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">
          Ripple Engine
        </Link>{" "}
        traverses MarketRipple&apos;s knowledge graph — a directed network of events, sectors,
        commodities, currencies, and companies connected by weighted causal edges. Each edge
        carries a stored confidence value, attenuated at each hop as effects propagate outward,
        grounded in{" "}
        <Link href="/historical" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">
          24 verified historical market events spanning 2008–2024
        </Link>
        .
      </>
    ),
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    number: "04",
    icon: <Lightbulb className="h-6 w-6" />,
    name: "Conclude",
    tagline: "Generate Insights",
    description: (
      <>
        After mapping the full dependency graph up to 4 levels deep, MarketRipple generates
        structured insights: primary impacts, second-order effects, affected companies with
        directional reads, and confidence-weighted scenarios for further research — surfaced on{" "}
        <Link href="/opportunity-radar" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">
          Opportunity Radar
        </Link>{" "}
        and{" "}
        <Link href="/newsroom" className="underline decoration-dotted underline-offset-2 hover:text-text-primary">
          AI Newsroom
        </Link>
        , never as a buy, sell, or position instruction.
      </>
    ),
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
];

// ── Fact-Grounding Validators ────────────────────────────────────────────────
const factGroundingChecks = [
  {
    icon: <Copy className="h-5 w-5" />,
    name: "Shared-Reason Detection",
    description:
      "Catches a real production bug: the same boilerplate causal explanation reused near word-for-word across two different companies, which reads like individual analysis but isn't. Flagged whenever two companies' stated reasons are a 90%+ text match.",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: <Scale className="h-5 w-5" />,
    name: "Sentiment/Magnitude Consistency",
    description:
      "Cross-checks every company's stated impact — positive, negative, or neutral — against its real price move for the day. A company down 5.84% but tagged “neutral,” or one that's up but tagged “negative,” gets flagged before publication.",
    color: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  },
  {
    icon: <History className="h-5 w-5" />,
    name: "Status-Tense Consistency",
    description:
      "Compares the article's language against the source event's own language to catch tense mismatches — a draft or proposed regulation described as finalized, or an already-decided policy described as still pending.",
    color: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  },
];

// ── Data Sources (compact) ───────────────────────────────────────────────────
const dataSourceGroups = [
  { icon: Landmark, title: "RBI & SEBI", use: "Monetary policy, circulars, and regulatory actions that trigger new events" },
  { icon: ShieldCheck, title: "NSE & BSE", use: "Exchange filings and announcements — the primary-source layer behind every event" },
  { icon: Newspaper, title: "Global & Business News", use: "Economic Times, Moneycontrol, Business Standard, Livemint, NDTV Profit, and global newswires" },
  { icon: Database, title: "Commodity & Market Data", use: "Live equity prices and commodity benchmarks used to ground company-impact analysis in real numbers" },
  { icon: History, title: "Historical Events", use: "24 verified historical events (2008–2024) used as precedent in confidence scoring" },
  { icon: Building2, title: "Company Universe", use: "512 actively tracked NSE-listed companies mapped to sectors and relationships" },
];

// ── JSON-LD ───────────────────────────────────────────────────────────────────
const FAQS = [
  { id: "what-is", q: "What is MarketRipple AI?", a: "MarketRipple AI is the reasoning layer behind MarketRipple's market intelligence platform. It observes market events, classifies them, traces their causal relationships through a knowledge graph, and generates confidence-scored insights — all traceable back to real source data." },
  { id: "how-analyzes", q: "How does MarketRipple analyze market events?", a: "Through a four-stage process: Observe (continuous monitoring of RBI, SEBI, exchange, news, and commodity sources), Classify (categorising the event and mapping it to sectors and companies), Connect (tracing causal relationships through the knowledge graph), and Conclude (generating confidence-weighted, evidence-backed insights)." },
  { id: "data-used", q: "What data does MarketRipple use?", a: "Only real, verifiable sources: RBI and SEBI releases, NSE/BSE filings and announcements, business and global news, live market and commodity price data, and a library of 24 verified historical market events." },
  { id: "confidence-calc", q: "How does MarketRipple calculate confidence?", a: "A point-based sum across 8 real evidence signals — source count, historical precedent (the largest factor), market confirmation, sector confirmation, macro alignment, company sensitivity, AI self-certainty, and a volatility adjustment — capped at 100. Confidence reflects the strength and consistency of the available evidence, not a probability that an investment outcome will occur." },
  { id: "ripple-intelligence", q: "What is Ripple Intelligence?", a: "Ripple Intelligence is MarketRipple's knowledge graph of events, sectors, commodities, currencies, and companies, connected by seven fixed relationship types (Benefits, Hurts, Supplies, Depends_on, Competes_with, Influences, Triggered_by). The Ripple Engine traverses this graph up to 4 levels deep to trace how one event cascades into downstream effects." },
  { id: "connect-companies", q: "How does MarketRipple connect events to companies?", a: "Events are matched to companies either directly — the company is named in the event — or through the Ripple Engine's relationship graph, which connects an event's sector or commodity to a company through one of the seven defined relationship types." },
  { id: "validate", q: "How does MarketRipple validate AI-generated analysis?", a: "Before generating a company-impact analysis, real per-company price-move data is fetched and fed directly into the generation prompt. Three deterministic checks — no LLM involved — then run against the output before it can publish: shared-reason detection, sentiment/magnitude consistency, and status-tense consistency. This is currently in shadow mode: violations are logged, not yet blocking publication." },
  { id: "predict", q: "Can MarketRipple predict stock prices?", a: "No. MarketRipple analyses probabilities and historical patterns — it cannot predict market movements with certainty. Confidence scores are calibrated uncertainty, not guarantees; a 75% confidence signal will be wrong roughly 25% of the time." },
  { id: "advice", q: "Is MarketRipple AI financial advice?", a: "No. MarketRipple is a market research and intelligence tool. It does not provide personalised investment advice and does not issue buy, sell, or position recommendations. It does not replace the advice of a SEBI-registered investment advisor, and all investment decisions remain the user's responsibility." },
  { id: "vs-news", q: "What is the difference between MarketRipple and a traditional financial news platform?", a: "A news platform reports what happened. MarketRipple connects what happened to why it matters — tracing an event through sectors and companies, weighting it against historical precedent, and attaching a confidence score to every claim — with full evidence behind each step." },
];

const FAQ_JSONLD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQS.map((item) => ({ "@type": "Question", name: item.q, acceptedAnswer: { "@type": "Answer", text: item.a } })),
};

const WEBPAGE_JSONLD = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "How MarketRipple AI Analyzes the Market",
  url: `${SITE_URL}/how-marketripple-thinks`,
  description:
    "See the data, reasoning, evidence and confidence behind every MarketRipple insight — from raw events to ripple effects, with real methodology.",
  about: { "@type": "Organization", name: "MarketRipple", url: SITE_URL },
};

// ── Page ───────────────────────────────────────────────────────────────────────
export default function HowMarketRippleThinksPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(WEBPAGE_JSONLD) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(FAQ_JSONLD) }} />
      <main className="min-w-0 space-y-14 pb-16" aria-label="How MarketRipple Thinks">

        {/* ── HERO ──────────────────────────────────────────────────────── */}
        <section aria-labelledby="hero-heading">
          <div className="rounded-2xl border border-surface-border/8 bg-gradient-to-br from-violet-500/[0.06] to-surface-bg px-8 py-12 md:px-12 md:py-16">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-400">Transparent AI</p>
            <h1 id="hero-heading" className="mt-3 text-[28px] font-black leading-tight text-text-primary md:text-[40px]">
              How MarketRipple AI Analyzes the Market
            </h1>
            <p className="mt-4 max-w-2xl text-[15px] leading-7 text-slate-700 dark:text-white">
              See the data, reasoning, evidence and confidence behind every MarketRipple insight —
              from raw events to ripple effects, traceable at every step.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-2">
              {["Data", "Observe", "Classify", "Connect", "Analyze", "Validate", "Explain"].map((step, i, arr) => (
                <span key={step} className="flex items-center gap-2">
                  <span className="rounded-lg bg-text-primary/[0.06] px-3 py-1.5 text-xs font-semibold text-text-secondary">{step}</span>
                  {i < arr.length - 1 && <ChevronRight className="h-3 w-3 shrink-0 text-text-muted" aria-hidden="true" />}
                </span>
              ))}
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/ai-search"
                className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-5 py-2.5 text-sm font-semibold text-text-primary transition hover:opacity-90"
              >
                <Search className="h-4 w-4" />
                Explore AI Search
              </Link>
              <Link
                href="/ai-methodology"
                className="flex items-center gap-2 rounded-xl border border-surface-border/15 bg-text-primary/[0.04] px-5 py-2.5 text-sm font-semibold text-text-secondary transition hover:border-surface-border/25 hover:text-text-primary"
              >
                <Brain className="h-4 w-4" />
                AI Methodology
              </Link>
            </div>
          </div>
        </section>

        {/* ── DIRECT ANSWER ─────────────────────────────────────────────── */}
        <section aria-labelledby="direct-answer-heading" className="rounded-xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Direct Answer</p>
          <h2 id="direct-answer-heading" className="mt-2 text-lg font-black text-text-primary">
            What is MarketRipple AI?
          </h2>
          <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
            MarketRipple AI is the reasoning system behind MarketRipple&apos;s market intelligence
            platform. It observes market events from real sources, classifies and maps them to
            affected sectors and companies, traces causal relationships through a knowledge graph,
            and produces confidence-scored insights — with the evidence behind every step shown,
            not hidden.
          </p>
        </section>

        {/* ── THINKING FRAMEWORK ────────────────────────────────────────── */}
        <section aria-labelledby="framework-heading" className="space-y-6">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Methodology</p>
            <h2 id="framework-heading" className="mt-2 text-[22px] font-black text-text-primary md:text-[28px]">
              How does MarketRipple think through a market event?
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-text-secondary">
              Every MarketRipple insight follows a four-stage reasoning process — from raw data
              ingestion to structured, evidence-backed intelligence.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {frameworkSteps.map((step) => (
              <div key={step.number} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div className={`flex h-11 w-11 items-center justify-center rounded-xl border ${step.color}`} aria-hidden="true">
                    {step.icon}
                  </div>
                  <span className="text-[32px] font-black text-text-primary/[0.06] leading-none">{step.number}</span>
                </div>
                <h3 className="text-base font-bold text-text-primary">{step.name}</h3>
                <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted mt-0.5 mb-2">{step.tagline}</p>
                <p className="text-[12px] leading-5 text-text-secondary">{step.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── DATA SOURCES (compact) ────────────────────────────────────── */}
        <Section
          id="data-sources-heading" badge="Data" badgeColor="text-sky-400"
          title="What data does MarketRipple use?"
          subtitle="Only real, verifiable sources feed the reasoning above — never a source claimed without a real connection behind it."
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {dataSourceGroups.map((g) => (
              <div key={g.title} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <g.icon className="h-6 w-6 text-sky-400" aria-hidden="true" />
                <h3 className="mt-3 text-[13px] font-bold text-text-primary">{g.title}</h3>
                <p className="mt-1.5 text-[12px] leading-5 text-text-muted">{g.use}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* ── EVENT → IMPACT → COMPANY ──────────────────────────────────── */}
        <Section
          id="event-impact-heading" badge="Worked Example" badgeColor="text-indigo-400"
          title="From event to company: how one signal flows through the graph"
          subtitle="A single trigger event doesn't map to one company — it maps to a sector, and the sector maps to specific companies with a confidence level at each step. Real relationship data from the RBI rate-cut example below."
        >
          <div className="rounded-xl border border-surface-border/8 bg-surface-card p-5 md:p-7">
            <div className="flex flex-col items-stretch gap-3 md:flex-row md:items-center">
              <div className="flex-1 rounded-xl border border-indigo-500/20 bg-indigo-500/[0.05] p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-indigo-400">1. Event</p>
                <p className="mt-1 text-[13px] font-bold text-text-primary">RBI Repo Rate Cut</p>
                <p className="mt-1 text-[11px] text-text-secondary">Detected from an RBI MPC release</p>
              </div>
              <ChevronRight className="hidden h-5 w-5 shrink-0 text-text-muted md:block" aria-hidden="true" />
              <div className="flex-1 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.05] p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-emerald-400">2. Sector Impact</p>
                <p className="mt-1 text-[13px] font-bold text-text-primary">Real Estate — Benefits</p>
                <p className="mt-1 text-[11px] text-text-secondary">78% confidence · home loan rates fall with a lag</p>
              </div>
              <ChevronRight className="hidden h-5 w-5 shrink-0 text-text-muted md:block" aria-hidden="true" />
              <div className="flex-1 rounded-xl border border-surface-border/8 bg-text-primary/[0.02] p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">3. Companies</p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {["DLF", "Godrej Properties", "Macrotech (Lodha)"].map((c) => (
                    <span key={c} className="rounded-full border border-surface-border/10 bg-text-primary/[0.04] px-2 py-0.5 text-[10px] text-text-secondary">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <p className="text-[11px] italic text-text-muted">
            The full sector breakdown for this example is in the RBI rate-cut case study further down this page.
          </p>
        </Section>

        {/* ── RELATIONSHIP TYPES ────────────────────────────────────────── */}
        <Section
          id="relationships-heading" badge="Causal Graph" badgeColor="text-fuchsia-400"
          title="What relationship types does MarketRipple's knowledge graph use?"
          subtitle="Every edge in MarketRipple's knowledge graph is classified under one of seven fixed relationship types. The graph itself keeps growing as new events are ingested — the number of actual relationships has no fixed ceiling — but these seven types are the taxonomy that stays constant."
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {relationshipTypes.map((rel) => (
              <div key={rel.name} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <div className={`mb-4 flex h-10 w-10 items-center justify-center rounded-xl border ${rel.color}`} aria-hidden="true">
                  {rel.icon}
                </div>
                <h3 className="text-[14px] font-bold text-text-primary">{rel.name}</h3>
                <p className="mt-2 text-[12px] leading-5 text-text-secondary">{rel.description}</p>
                <div className="mt-3 rounded-lg border border-surface-border/6 bg-text-primary/[0.02] p-3">
                  <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted mb-1">Example Chain</p>
                  <p className="text-[11px] leading-5 text-text-secondary italic">{rel.example}</p>
                </div>
              </div>
            ))}
          </div>
          <Link href="/ripple" className="inline-flex items-center gap-1 text-sm font-semibold text-fuchsia-400 hover:text-fuchsia-300">
            Explore Ripple Intelligence <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </Section>

        {/* ── CONFIDENCE SYSTEM ─────────────────────────────────────────── */}
        <section aria-labelledby="confidence-heading" className="space-y-6">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Uncertainty Quantification</p>
            <h2 id="confidence-heading" className="mt-2 text-[22px] font-black text-text-primary md:text-[28px]">
              How are confidence scores calculated?
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-text-secondary">
              Every claim MarketRipple makes carries a confidence level — so you always know how
              much weight to place on each insight.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {confidenceLevels.map((level) => (
              <div key={level.label} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <span className={`text-lg font-black ${level.textColor}`}>{level.label}</span>
                    <span className="ml-2 text-[12px] text-text-muted">{level.range}</span>
                  </div>
                  <div className="text-right">
                    <span className={`text-2xl font-black ${level.textColor}`}>{level.bar}%</span>
                  </div>
                </div>
                <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-text-primary/[0.05]">
                  <div className={`h-full rounded-full ${level.color}`} style={{ width: `${level.bar}%` }} aria-label={`${level.bar}% confidence level bar`} />
                </div>
                <p className="mt-3 text-[12px] leading-5 text-text-secondary">{level.description}</p>
                <p className="mt-2 text-[11px] italic text-text-muted">Examples: {level.examples}</p>
              </div>
            ))}
          </div>

          <p className="rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 text-sm font-medium text-amber-700 dark:text-amber-300">
            Confidence reflects the strength and consistency of the available evidence and analysis.
            It is not a probability that an investment outcome will occur.
          </p>
        </section>

        {/* ── FACT GROUNDING / AI VALIDATION ────────────────────────────── */}
        <Section
          id="fact-grounding-heading" badge="Validation Layer" badgeColor="text-rose-400"
          title="How does MarketRipple keep AI-written analysis honest?"
          subtitle={
            <>
              Before writing a company-impact analysis, MarketRipple&apos;s AI pipeline fetches
              each affected company&apos;s real percentage price move for the day from a live
              quote service — and feeds those real numbers directly into the generation prompt, so the model
              writes from what actually happened instead of inventing a direction or magnitude.
              After generation, three deterministic checks — no LLM involved — run against the
              output before it can publish.
            </>
          }
        >
          <div className="rounded-xl border border-surface-border/8 bg-surface-card p-5 md:p-6">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-emerald-500/20 bg-emerald-500/10 text-emerald-400" aria-hidden="true">
                <Activity className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-[14px] font-bold text-text-primary">Real Price Grounding</h3>
                <p className="mt-1 text-[12px] leading-5 text-text-secondary">
                  Every company mentioned in a draft analysis gets its real, live today&apos;s %
                  price change pulled in before a single word is generated — the model is never
                  left to guess whether a stock moved up, down, or sideways.
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {factGroundingChecks.map((check) => (
              <div key={check.name} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                <div className={`mb-4 flex h-10 w-10 items-center justify-center rounded-xl border ${check.color}`} aria-hidden="true">
                  {check.icon}
                </div>
                <h3 className="text-[14px] font-bold text-text-primary">{check.name}</h3>
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
        </Section>

        {/* ── CASE STUDY: ISRAEL–IRAN ───────────────────────────────────── */}
        <section aria-labelledby="case-study-1-heading" className="space-y-6">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-rose-400">Illustrative Case Study</p>
              <h2 id="case-study-1-heading" className="mt-2 text-[22px] font-black text-text-primary md:text-[28px]">
                Israel–Iran Conflict: Full Ripple Chain
              </h2>
              <p className="mt-2 max-w-2xl text-sm text-text-secondary">
                How MarketRipple&apos;s reasoning framework traces a geopolitical trigger all the
                way through to specific Indian listed companies — with a confidence level at every
                step. This walkthrough uses a worked example to demonstrate the framework, not a
                live-generated analysis.
              </p>
            </div>
            <div className="flex flex-col items-start gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/25 bg-amber-500/[0.08] px-3 py-1 text-[10px] font-bold text-amber-600 dark:text-amber-300">
                <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                Illustrative Example — Not Live Data
              </span>
              <div className="flex items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/[0.06] px-4 py-2">
                <Globe className="h-4 w-4 text-rose-400" />
                <span className="text-[12px] font-semibold text-rose-600 dark:text-rose-300">Geopolitical · Impact Score: 9.1</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-surface-border/8 bg-surface-card p-5 md:p-7">
            <div className="mb-4 flex flex-wrap gap-3 text-[11px] text-text-muted">
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

        {/* ── ALTERNATIVE OUTCOMES ──────────────────────────────────────── */}
        <section aria-labelledby="scenarios-heading" className="space-y-6">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Scenario Analysis</p>
            <h2 id="scenarios-heading" className="mt-2 text-[22px] font-black text-text-primary md:text-[28px]">
              Alternative Outcomes: Israel–Iran
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-text-secondary">
              MarketRipple never presents a single deterministic forecast. The same trigger event
              generates probability-weighted scenarios instead — this is scenario analysis, not a
              prediction, and not a buy, sell, or position recommendation.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {scenarios.map((s) => (
              <div key={s.label} className={`rounded-xl border p-5 ${s.color}`}>
                <div className="mb-3 flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-surface-border/10 bg-text-primary/[0.04]" aria-hidden="true">
                    {s.icon}
                  </div>
                  <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${s.badgeColor}`}>{s.probability} probability</span>
                </div>
                <h3 className="text-[14px] font-bold text-text-primary">{s.label}</h3>
                <div className="mt-3 space-y-3">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted">Trigger Condition</p>
                    <p className="mt-0.5 text-[12px] leading-5 text-text-secondary">{s.trigger}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted">Oil Outcome</p>
                    <p className="mt-0.5 text-[12px] leading-5 text-text-secondary">{s.oilOutcome}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted">Market Impact</p>
                    <p className="mt-0.5 text-[12px] leading-5 text-text-secondary">{s.marketOutcome}</p>
                  </div>
                  <div className="rounded-lg border border-surface-border/6 bg-text-primary/[0.02] p-3">
                    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted mb-1">What This Could Mean</p>
                    <p className={`text-[12px] font-semibold leading-5 ${s.recColor}`}>{s.meaning}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <p className="rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3 text-sm font-medium text-amber-700 dark:text-amber-300">
            These are illustrative reasoning patterns, not predictions. MarketRipple does not issue
            buy, sell, or position instructions.
          </p>
        </section>

        {/* ── CASE STUDY 2: RBI RATE CUT ────────────────────────────────── */}
        <section aria-labelledby="case-study-2-heading" className="space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-indigo-400">Illustrative Case Study</p>
              <h2 id="case-study-2-heading" className="mt-2 text-[22px] font-black text-text-primary md:text-[28px]">
                RBI Rate Cut: Monetary Policy Ripple Effects
              </h2>
              <p className="mt-2 max-w-2xl text-sm text-text-secondary">
                A repo rate cut flows through sectors in distinct ways — some benefit immediately,
                others face transitional pressure. A compact walkthrough of how MarketRipple maps
                the full picture.
              </p>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/25 bg-amber-500/[0.08] px-3 py-1 text-[10px] font-bold text-amber-600 dark:text-amber-300">
              <AlertTriangle className="h-3 w-3" aria-hidden="true" />
              Illustrative Example — Not Live Data
            </span>
          </div>

          <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/[0.04] p-4 md:p-5">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-indigo-400">
                <Landmark className="h-5 w-5" />
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">Trigger Event</p>
                <p className="text-[14px] font-bold text-text-primary">RBI MPC: Repo Rate Cut</p>
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
              const directionLabel = node.direction === "positive" ? "Beneficiary" : node.direction === "negative" ? "Headwind" : "Mixed Impact";
              return (
                <div key={node.sector} className="rounded-xl border border-surface-border/8 bg-surface-card p-5">
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-surface-border/8 bg-text-primary/[0.04] text-text-secondary">
                        {node.icon}
                      </div>
                      <h3 className="text-[14px] font-bold text-text-primary">{node.sector}</h3>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${directionStyle}`}>{directionLabel}</span>
                      <ConfidenceBadge pct={node.confidence} />
                    </div>
                  </div>
                  <p className="text-[12px] leading-5 text-text-secondary">{node.effect}</p>
                  {node.companies.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <p className="w-full text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">Key Companies</p>
                      {node.companies.map((c) => (
                        <span key={c} className="rounded-full border border-surface-border/10 bg-text-primary/[0.04] px-2 py-0.5 text-[10px] text-text-secondary">
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

        {/* ── WHAT MARKETRIPPLE DOES AND DOESN'T DO ─────────────────────── */}
        <section className="rounded-2xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
          <h2 className="text-[20px] font-black text-text-primary md:text-[24px]">What MarketRipple Does — and Doesn&apos;t Do</h2>
          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <div>
              <p className="text-[10px] font-black uppercase tracking-wide text-emerald-500">Does</p>
              <ul className="mt-3 space-y-2">
                {["Traces events through sectors and companies", "Shows confidence and evidence at every step", "Surfaces historical precedent", "Presents multiple probability-weighted scenarios", "Explains its reasoning in plain language"].map((d) => (
                  <li key={d} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
                    <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" aria-hidden="true" />
                    {d}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-wide text-rose-500">Does Not</p>
              <ul className="mt-3 space-y-2">
                {["Issue buy, sell, or position instructions", "Guarantee returns or predict markets with certainty", "Replace investor judgment", "Present illustrative examples as live, real-time analysis"].map((d) => (
                  <li key={d} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-500" aria-hidden="true" />
                    {d}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="mt-6 flex items-center gap-2 rounded-xl border border-sky-500/20 bg-sky-500/[0.06] p-3">
            <ShieldAlert className="h-4 w-4 shrink-0 text-sky-400" aria-hidden="true" />
            <p className="text-[12px] text-sky-600 dark:text-sky-300">
              MarketRipple does not provide personalised investment advice. All analysis is for
              informational purposes only. Past patterns do not guarantee future outcomes.
            </p>
          </div>
        </section>

        {/* ── FAQ ────────────────────────────────────────────────────────── */}
        <section>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Questions</p>
          <h2 className="mt-3 flex items-center gap-2 text-[20px] font-black text-text-primary md:text-[24px]">
            <HelpCircle className="h-5 w-5 text-violet-400" aria-hidden="true" />
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
          <Link href="/faq" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-violet-400 hover:text-violet-300">
            See all questions <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </section>

        {/* ── CTA ────────────────────────────────────────────────────────── */}
        <section aria-label="Further reading" className="rounded-xl border border-surface-border/8 bg-surface-card p-6 md:p-8">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Go Deeper</p>
          <h2 className="mt-2 text-xl font-black text-text-primary">See the system in action</h2>
          <p className="mt-2 text-sm text-text-secondary">
            Explore the live platform — where this reasoning framework runs on real, current market data.
          </p>
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {[
              { href: "/market-intelligence", label: "Markets", icon: <TrendingUp className="h-3.5 w-3.5" /> },
              { href: "/events", label: "Events", icon: <Radio className="h-3.5 w-3.5" /> },
              { href: "/ripple", label: "Ripple Intelligence", icon: <GitBranch className="h-3.5 w-3.5" /> },
              { href: "/opportunity-radar", label: "Opportunity Radar", icon: <Radar className="h-3.5 w-3.5" /> },
              { href: "/ai-search", label: "AI Search", icon: <Search className="h-3.5 w-3.5" /> },
              { href: "/companies", label: "Companies", icon: <Building2 className="h-3.5 w-3.5" /> },
              { href: "/newsroom", label: "Newsroom", icon: <Newspaper className="h-3.5 w-3.5" /> },
              { href: "/historical", label: "Historical Patterns", icon: <History className="h-3.5 w-3.5" /> },
              { href: "/calendar", label: "Economic Calendar", icon: <Activity className="h-3.5 w-3.5" /> },
              { href: "/how-it-works", label: "How It Works", icon: <GitBranch className="h-3.5 w-3.5" /> },
              { href: "/ai-methodology", label: "AI Methodology", icon: <Brain className="h-3.5 w-3.5" /> },
            ].map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className="flex items-center gap-2 rounded-xl border border-surface-border/12 bg-text-primary/[0.03] px-3.5 py-2.5 text-[12.5px] font-semibold text-text-secondary transition hover:border-surface-border/25 hover:text-text-primary"
              >
                {l.icon}
                {l.label}
              </Link>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              href="/ai-methodology"
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-5 py-2.5 text-sm font-semibold text-text-primary transition hover:opacity-90"
              aria-label="Read AI Methodology"
            >
              <Brain className="h-4 w-4" />
              AI Methodology
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/how-it-works"
              className="flex items-center gap-2 rounded-xl border border-surface-border/15 bg-text-primary/[0.04] px-5 py-2.5 text-sm font-semibold text-text-secondary transition hover:border-surface-border/25 hover:text-text-primary"
              aria-label="See How It Works"
            >
              <Link2 className="h-4 w-4" />
              How It Works
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}
