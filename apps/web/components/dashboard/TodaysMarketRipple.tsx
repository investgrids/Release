import Link from "next/link";
import {
  Waves, Sparkles, TrendingUp, TrendingDown, AlertTriangle,
  Zap, Target, Activity, ChevronRight, ArrowRight, Clock,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────
interface MarketEvent {
  id: string | number;
  title: string;
  summary?: string;
  category?: string;
  impact_score: number;
  sectors?: string[];
  companies?: string[];
}

interface RadarItem {
  id: string | number;
  slug?: string;
  title: string;
  summary?: string;
  opportunity_score: number;
  sectors?: string[];
  risk_level?: string;
}

interface Mover {
  company?: string;
  ticker?: string;
  value?: string;
  positive?: boolean;
}

export interface TodaysMarketRippleProps {
  aiSummary: string;
  trendingEvents: MarketEvent[];
  topMovers: { gainers?: Mover[]; losers?: Mover[]; active?: Mover[] };
  radarItems: RadarItem[];
  heroDate: string;
  marketStatus: "Market Open" | "Market Closed";
}

// ── Static lookup tables ───────────────────────────────────────────────────────
const SECTOR_COLORS: Record<string, string> = {
  Banking:        "border-blue-500/20 bg-blue-500/10 text-blue-300",
  NBFC:           "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
  "Real Estate":  "border-amber-500/20 bg-amber-500/10 text-amber-300",
  Energy:         "border-orange-500/20 bg-orange-500/10 text-orange-300",
  IT:             "border-cyan-500/20 bg-cyan-500/10 text-cyan-300",
  Technology:     "border-cyan-500/20 bg-cyan-500/10 text-cyan-300",
  Pharma:         "border-green-500/20 bg-green-500/10 text-green-300",
  Auto:           "border-teal-500/20 bg-teal-500/10 text-teal-300",
  Infrastructure: "border-violet-500/20 bg-violet-500/10 text-violet-300",
  Metals:         "border-stone-500/20 bg-stone-500/10 text-stone-300",
  Macro:          "border-slate-500/20 bg-slate-500/10 text-slate-300",
  Defence:        "border-rose-500/20 bg-rose-500/10 text-rose-300",
  FMCG:           "border-lime-500/20 bg-lime-500/10 text-lime-300",
};
const DEFAULT_SECTOR_COLOR = "border-violet-500/20 bg-violet-500/10 text-violet-300";

const CATEGORY_PATTERNS: Record<string, { name: string; similarity: number; outcome: string }> = {
  Macro:      { name: "Post-Budget Infra Rally (2023)",    similarity: 84, outcome: "Infra sector gained 22% over 3 months after similar macro pivot" },
  Banking:    { name: "RBI Rate Pivot Cycle (2024)",       similarity: 78, outcome: "Banking index outperformed Nifty by 15% in the following 6 weeks" },
  Technology: { name: "AI Sector Re-rating Wave (2024)",   similarity: 82, outcome: "IT multiples expanded 18% in 4 months on similar demand signals" },
  Energy:     { name: "Crude Shock Absorption (2022)",     similarity: 71, outcome: "Energy sector rotated toward renewables over a 6-month window" },
  Auto:       { name: "EV Adoption Inflection (2024)",     similarity: 76, outcome: "Auto sector leadership shifted to EV-adjacent plays within 5 months" },
  Defence:    { name: "Make-in-India Defence Rally (2023)", similarity: 88, outcome: "Defence PSUs delivered 35%+ returns in the 12 months following the order" },
  Pharma:     { name: "Post-US FDA Bounce (2023)",          similarity: 74, outcome: "Pharma exporters re-rated by 12% in 8 weeks after comparable approval" },
};

function sectorColor(s: string) { return SECTOR_COLORS[s] ?? DEFAULT_SECTOR_COLOR; }
function impactSeverity(score: number): "critical" | "high" | "medium" {
  return score >= 80 ? "critical" : score >= 65 ? "high" : "medium";
}

// ── Component ─────────────────────────────────────────────────────────────────
export function TodaysMarketRipple({
  aiSummary,
  trendingEvents,
  topMovers,
  radarItems,
  heroDate,
  marketStatus,
}: TodaysMarketRippleProps) {
  const isOpen    = marketStatus === "Market Open";
  const topEvent  = trendingEvents[0];
  const eventCat  = topEvent?.category ?? "Macro";
  const rippleChain: string[] = topEvent?.sectors?.slice(0, 5) ?? ["Banking", "NBFC", "Real Estate"];

  const gainers = topMovers.gainers ?? [];
  const losers  = topMovers.losers  ?? [];

  // ── Derive drivers ─────────────────────────────────────────────────────────
  const drivers = [
    {
      type: "bull" as const,
      title: gainers.length
        ? `${gainers.slice(0, 2).map(g => g.ticker ?? g.company ?? "").filter(Boolean).join(", ")} Leading`
        : "Institutional Buying",
      detail: trendingEvents.find(e => e.impact_score >= 72)?.title?.slice(0, 90)
        ?? "Strong FII and domestic institutional flows supporting broad rally",
      importance: "critical" as const,
    },
    {
      type: "bear" as const,
      title: losers.length
        ? `${losers.slice(0, 2).map(l => l.ticker ?? l.company ?? "").filter(Boolean).join(", ")} Under Pressure`
        : "Sector Headwinds",
      detail: trendingEvents.find(e => e.impact_score >= 55 && e.impact_score < 72)?.title?.slice(0, 90)
        ?? "Global rate uncertainty and currency volatility affecting select sectors",
      importance: "high" as const,
    },
    {
      type: "watch" as const,
      title: trendingEvents[2]?.title?.slice(0, 55) ?? "Key Events Ahead",
      detail: trendingEvents[2]?.summary?.slice(0, 90) ?? trendingEvents[1]?.summary?.slice(0, 90)
        ?? "Monitor earnings releases and macro data for clear directional signals",
      importance: "medium" as const,
    },
  ] as const;

  // ── Derive risk alerts ─────────────────────────────────────────────────────
  const risks = trendingEvents
    .filter(e => e.impact_score >= 65)
    .slice(0, 3)
    .map(e => ({
      label:    e.title.slice(0, 60),
      severity: impactSeverity(e.impact_score),
      sectors:  (e.sectors ?? []).slice(0, 2),
    }));

  // ── Derive AI insights ─────────────────────────────────────────────────────
  const insights = trendingEvents.slice(0, 3).map(e => ({
    text:   e.summary?.slice(0, 105) ?? e.title.slice(0, 85),
    sector: e.sectors?.[0] ?? e.category ?? "Market",
    score:  e.impact_score,
  }));

  // ── Pattern match ──────────────────────────────────────────────────────────
  const pattern = CATEGORY_PATTERNS[eventCat] ?? CATEGORY_PATTERNS.Macro;

  // ── Expected evolution ─────────────────────────────────────────────────────
  const evolution = [
    { phase: "Today",      desc: `${rippleChain[0] ?? "Market"} digests event impact` },
    { phase: "1–2 Weeks",  desc: `Ripple to ${rippleChain.slice(1, 3).join(" & ") || "adjacent sectors"}` },
    { phase: "1–3 Months", desc: "Policy response and earnings guidance revision" },
    { phase: "3–12 Months", desc: topEvent && topEvent.impact_score >= 80 ? "Fundamental sector re-rating likely" : "Gradual normalization expected" },
    { phase: ">1 Year",    desc: "Structural market leadership shift if policy changes stick" },
  ];

  // ── Top opportunities ──────────────────────────────────────────────────────
  const opportunities = radarItems.slice(0, 3);

  // ── Why it matters (top event summary fallback) ────────────────────────────
  const whyItMatters = topEvent?.summary
    ?? "This market development affects institutional positioning, sector allocations, and retail sentiment — understanding it today positions you ahead of the crowd.";

  return (
    <div className="relative overflow-hidden rounded-[28px] border border-indigo-500/20 bg-gradient-to-br from-indigo-950/40 via-slate-950 to-slate-950">
      {/* Ripple ring animation */}
      <style>{`
        @keyframes tmrRing {
          0%   { transform: scale(0.4); opacity: 0.55; }
          100% { transform: scale(2.6); opacity: 0; }
        }
        .tmr-ring { animation: tmrRing 2.8s ease-out infinite; }
        .tmr-ring-2 { animation-delay: 0.95s; }
        .tmr-ring-3 { animation-delay: 1.9s; }
      `}</style>

      {/* Background glow blobs */}
      <div className="pointer-events-none absolute -top-24 right-24 h-96 w-96 rounded-full bg-indigo-600/[0.08] blur-[90px]" />
      <div className="pointer-events-none absolute -bottom-10 left-0 h-56 w-56 rounded-full bg-violet-700/[0.07] blur-[70px]" />

      {/* Animated ripple rings (top-right corner) */}
      <div aria-hidden className="pointer-events-none absolute right-8 top-8 h-40 w-40">
        <div className="tmr-ring absolute inset-0 rounded-full border-2 border-indigo-400/20" />
        <div className="tmr-ring tmr-ring-2 absolute inset-0 rounded-full border border-indigo-400/15" />
        <div className="tmr-ring tmr-ring-3 absolute inset-0 rounded-full border border-indigo-400/10" />
        <div className="absolute inset-[38%] rounded-full bg-indigo-500/25 blur-sm" />
      </div>

      <div className="relative p-6">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-400">
              <Waves className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-[18px] font-bold text-white">Today's Market Ripple</h2>
                <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-indigo-400">
                  AI Powered
                </span>
              </div>
              <p className="text-[12px] text-slate-500 mt-0.5">{heroDate} · What matters most in Indian markets today</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold ${
              isOpen
                ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border border-slate-600/30 bg-slate-700/20 text-slate-400"
            }`}>
              <span className={`h-1.5 w-1.5 rounded-full ${isOpen ? "bg-emerald-400 animate-pulse" : "bg-slate-500"}`} />
              {marketStatus}
            </span>
          </div>
        </div>

        {/* ── Executive Brief + Why It Matters ────────────────────────────── */}
        <div className="mb-4 grid gap-3 lg:grid-cols-[1fr_1fr]">
          <div className="rounded-[16px] border border-white/[0.06] bg-white/[0.03] p-4">
            <div className="mb-2 flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400">Executive Brief</span>
            </div>
            <p className="text-[13px] leading-6 text-slate-300">{aiSummary}</p>
          </div>

          <div className="rounded-[16px] border border-amber-500/15 bg-amber-500/[0.04] p-4">
            <div className="mb-2 flex items-center gap-2">
              <Zap className="h-3.5 w-3.5 text-amber-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Why It Matters</span>
            </div>
            {topEvent && (
              <p className="mb-1 text-[11px] font-semibold text-white line-clamp-1">{topEvent.title}</p>
            )}
            <p className="text-[12px] leading-5 text-slate-400 line-clamp-4">{whyItMatters}</p>
          </div>
        </div>

        {/* ── Key Market Drivers ──────────────────────────────────────────── */}
        <div className="mb-4">
          <h3 className="mb-2.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">Key Market Drivers</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            {drivers.map(d => (
              <div
                key={d.type}
                className={`rounded-[14px] border p-3.5 ${
                  d.type === "bull"
                    ? "border-emerald-500/20 bg-emerald-500/[0.05]"
                    : d.type === "bear"
                    ? "border-rose-500/20 bg-rose-500/[0.05]"
                    : "border-amber-500/20 bg-amber-500/[0.05]"
                }`}
              >
                <div className="mb-2 flex items-center justify-between gap-1">
                  <span className={`flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide ${
                    d.type === "bull" ? "text-emerald-400" : d.type === "bear" ? "text-rose-400" : "text-amber-400"
                  }`}>
                    {d.type === "bull"
                      ? <TrendingUp className="h-3 w-3" />
                      : d.type === "bear"
                      ? <TrendingDown className="h-3 w-3" />
                      : <Activity className="h-3 w-3" />}
                    {d.type === "bull" ? "Positive" : d.type === "bear" ? "Headwind" : "Monitor"}
                  </span>
                  <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${
                    d.importance === "critical"
                      ? "bg-rose-500/20 text-rose-400"
                      : d.importance === "high"
                      ? "bg-amber-500/20 text-amber-400"
                      : "bg-slate-500/20 text-slate-400"
                  }`}>
                    {d.importance}
                  </span>
                </div>
                <p className="text-[11px] font-semibold text-white leading-snug line-clamp-2">{d.title}</p>
                <p className="mt-1 text-[10px] leading-[14px] text-slate-500 line-clamp-2">{d.detail}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Ripple | Opportunities | Risks ──────────────────────────────── */}
        <div className="mb-4 grid gap-3 lg:grid-cols-3">

          {/* Ripple Chain */}
          <div className="rounded-[14px] border border-indigo-500/15 bg-indigo-500/[0.04] p-4">
            <div className="mb-3 flex items-center gap-2">
              <Waves className="h-3.5 w-3.5 text-indigo-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400">Today's Ripple Chain</span>
            </div>

            {topEvent && (
              <div className="mb-3 rounded-[10px] border border-white/[0.06] bg-white/[0.03] p-2.5">
                <p className="mb-0.5 text-[9px] font-bold uppercase tracking-wide text-indigo-400">Trigger Event</p>
                <p className="text-[11px] font-medium text-white line-clamp-2 leading-snug">{topEvent.title}</p>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/5">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
                      style={{ width: `${Math.min(topEvent.impact_score, 100)}%` }}
                    />
                  </div>
                  <span className="text-[9px] font-bold text-indigo-300">{Math.round(topEvent.impact_score)}</span>
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              {rippleChain.slice(0, 4).map((sector, i) => (
                <div key={`${sector}-${i}`} className="flex items-center gap-2">
                  <div className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-[9px] font-bold text-indigo-300">
                    {i + 1}
                  </div>
                  <ArrowRight className="h-3 w-3 shrink-0 text-slate-600" />
                  <span className={`rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${sectorColor(sector)}`}>
                    {sector}
                  </span>
                </div>
              ))}
            </div>

            <Link
              href={topEvent ? `/ripple/${topEvent.id}` : "/ripple"}
              className="mt-3 flex items-center gap-1 text-[10px] font-medium text-indigo-400 transition hover:text-indigo-300"
            >
              View full analysis <ChevronRight className="h-3 w-3" />
            </Link>
          </div>

          {/* Opportunity Highlights */}
          <div className="rounded-[14px] border border-emerald-500/15 bg-emerald-500/[0.04] p-4">
            <div className="mb-3 flex items-center gap-2">
              <Target className="h-3.5 w-3.5 text-emerald-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Opportunity Highlights</span>
            </div>

            {opportunities.length > 0 ? (
              <div className="space-y-2">
                {opportunities.map(op => (
                  <Link
                    key={String(op.id)}
                    href={`/radar/${op.slug ?? op.id}`}
                    className="group block rounded-[10px] border border-white/[0.05] bg-white/[0.02] p-2.5 transition hover:border-emerald-500/20 hover:bg-emerald-500/[0.04]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[11px] font-medium text-white leading-snug line-clamp-2 transition group-hover:text-emerald-200">
                        {op.title}
                      </p>
                      <span className="shrink-0 text-[13px] font-black text-emerald-400">
                        {Math.round(op.opportunity_score)}
                      </span>
                    </div>
                    {op.sectors && op.sectors.length > 0 && (
                      <span className={`mt-1 inline-block rounded-full border px-1.5 py-0.5 text-[9px] ${sectorColor(op.sectors[0])}`}>
                        {op.sectors[0]}
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-slate-500">AI radar scanning for opportunities…</p>
            )}

            <Link
              href="/radar"
              className="mt-3 flex items-center gap-1 text-[10px] font-medium text-emerald-400 transition hover:text-emerald-300"
            >
              View all opportunities <ChevronRight className="h-3 w-3" />
            </Link>
          </div>

          {/* Risk Alerts */}
          <div className="rounded-[14px] border border-rose-500/15 bg-rose-500/[0.04] p-4">
            <div className="mb-3 flex items-center gap-2">
              <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400">Risk Alerts</span>
            </div>

            {risks.length > 0 ? (
              <div className="space-y-2">
                {risks.map((risk, i) => (
                  <div key={i} className="rounded-[10px] border border-white/[0.05] bg-white/[0.02] p-2.5">
                    <div className="flex items-start gap-2">
                      <span className={`mt-0.5 shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${
                        risk.severity === "critical"
                          ? "bg-rose-500/20 text-rose-400"
                          : risk.severity === "high"
                          ? "bg-orange-500/20 text-orange-400"
                          : "bg-amber-500/20 text-amber-400"
                      }`}>
                        {risk.severity}
                      </span>
                      <p className="text-[11px] text-slate-300 leading-snug line-clamp-2">{risk.label}</p>
                    </div>
                    {risk.sectors.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {risk.sectors.map(s => (
                          <span key={s} className={`rounded-full border px-1.5 py-0.5 text-[9px] ${sectorColor(s)}`}>{s}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-[10px] border border-white/[0.05] bg-white/[0.02] p-2.5">
                <p className="text-[11px] text-slate-500">No critical risk alerts at this time. Markets stable.</p>
              </div>
            )}
          </div>
        </div>

        {/* ── AI Insights + Pattern Match ──────────────────────────────────── */}
        <div className="mb-4 grid gap-3 lg:grid-cols-[1.4fr_1fr]">

          {/* AI Insights */}
          {insights.length > 0 && (
            <div className="rounded-[14px] border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2">
                <Sparkles className="h-3.5 w-3.5 text-amber-400" />
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Today's AI Insights</span>
              </div>
              <div className="space-y-3">
                {insights.map((ins, i) => (
                  <div key={i} className="flex items-start gap-2.5">
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-500/15 text-[9px] font-bold text-amber-400">
                      {i + 1}
                    </span>
                    <div>
                      <p className="text-[11px] text-slate-300 leading-[15px] line-clamp-2">{ins.text}</p>
                      <span className={`mt-1 inline-block rounded-full border px-1.5 py-0.5 text-[9px] ${sectorColor(ins.sector)}`}>
                        {ins.sector}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Pattern Match + Expected Evolution */}
          <div className="rounded-[14px] border border-violet-500/15 bg-violet-500/[0.04] p-4">
            {/* Pattern Match */}
            <div className="mb-3">
              <div className="mb-2 flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-violet-400" />
                <span className="text-[10px] font-bold uppercase tracking-wider text-violet-400">Today's Pattern Match</span>
              </div>
              <div className="rounded-[10px] border border-white/[0.06] bg-white/[0.03] p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[11px] font-semibold text-white leading-snug">{pattern.name}</p>
                  <span className="shrink-0 rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-bold text-violet-300">
                    {pattern.similarity}%
                  </span>
                </div>
                <p className="mt-1 text-[10px] leading-[13px] text-slate-500 line-clamp-2">{pattern.outcome}</p>
              </div>
            </div>

            {/* Expected Evolution */}
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-violet-400" />
                <span className="text-[10px] font-bold uppercase tracking-wider text-violet-400">Expected Evolution</span>
              </div>
              <div className="space-y-1.5">
                {evolution.map((ev, i) => (
                  <div key={ev.phase} className="flex items-start gap-2">
                    <div className={`mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                      i === 0 ? "bg-emerald-400" : i === 1 ? "bg-amber-400" : "bg-slate-600"
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-[9px] font-bold text-violet-400 whitespace-nowrap">{ev.phase}</span>
                        <p className="text-[10px] text-slate-400 leading-[13px] line-clamp-1">{ev.desc}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── CTAs ────────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/ripple"
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-[12px] font-semibold text-white transition hover:bg-indigo-500"
          >
            <Waves className="h-3.5 w-3.5" />
            Explore Ripple Intelligence
          </Link>
          <Link
            href="/radar"
            className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-[12px] font-semibold text-emerald-400 transition hover:bg-emerald-500/20"
          >
            <Target className="h-3.5 w-3.5" />
            View Top Opportunities
          </Link>
          <Link
            href="/ai-search"
            className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-[12px] font-medium text-slate-300 transition hover:bg-white/[0.08]"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Ask AI About Today
          </Link>
        </div>

      </div>
    </div>
  );
}
