"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import {
  Clock, TrendingUp, TrendingDown, ArrowLeft, Landmark, Share2,
  ChevronDown, Sparkles, ShieldCheck, Target, Layers, CheckCircle2,
  Star, ArrowRight, Repeat, Info,
} from "lucide-react";
import { truncateForQuery } from "@/lib/text";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// HistoricalDonutChart.tsx's own header comment for why.
const HistoricalDonutChart = dynamic(() => import("./HistoricalDonutChart").then(m => m.HistoricalDonutChart), { ssr: false });

// ── Types — mirror the real /api/historical/{id} response shape ───────────
interface WinLoser { symbol: string; name: string; return_1d?: number | null; return_1w?: number | null; return_1m?: number | null; reason: string }
interface PatternCompany { symbol: string; name: string; wins: number; losses: number; appearances: number; avg_return: number; win_rate: number; reason: string | null }
interface PatternSector { sector: string; occurrences: number; positive: number; avg_reaction: number; positive_rate: number }
interface ScoreBreakdownItem { label: string; weight: number; score: number }
interface HistoricalScore { score: number; stars: number; band: string; breakdown: ScoreBreakdownItem[] }
interface PatternSnapshotScore { score: number; reliability: { label: string; emoji: string; tone: string }; breakdown: ScoreBreakdownItem[] }
interface TimelineItem { id: string; event_title: string; event_date: string; sentiment: string | null; nifty_1m: number | null; nifty_1w: number | null; opportunity_score: number | null; is_current: boolean; historical_score?: HistoricalScore }
interface ConsistencyFact { value: string; occurrences: number; of: number; pct: number }
interface Pattern {
  category_occurrences: number;
  date_range: { earliest: string | null; latest: string | null };
  timeline: TimelineItem[];
  avg_nifty_1m: number | null;
  bull_count: number; bear_count: number;
  win_rate_pct: number | null;
  avg_confidence: number | null;
  top_winners: PatternCompany[];
  top_losers: PatternCompany[];
  total_winner_appearances: number;
  total_loser_appearances: number;
  best_sectors: PatternSector[];
  worst_sectors: PatternSector[];
  consistency: {
    interest_rate_trend: ConsistencyFact | null;
    crude_trend: ConsistencyFact | null;
    market_regime: ConsistencyFact | null;
    nifty_direction: ConsistencyFact | null;
  };
  holding_period: { label: string; avg_return: number; positive_rate: number } | null;
  historical_confidence: { score: number; breakdown: { label: string; weight: number; score: number }[] };
}

export interface HistoricalDetail {
  id: string; event_title: string; event_date: string; category: string;
  sentiment: string | null; sectors: string[]; companies: string[]; tags: string[];
  market_regime: string | null; interest_rate_trend: string | null; crude_trend: string | null;
  interest_rate_level: number | null; vix_level: number | null;
  nifty_1d: number | null; nifty_3d: number | null; nifty_1w: number | null; nifty_1m: number | null;
  sector_reactions: Record<string, number>;
  historical_winners: WinLoser[];
  historical_losers: WinLoser[];
  opportunity_score: number | null; risk_score: number | null; confidence: number | null;
  what_happened: string | null; key_lesson: string | null; source: string | null;
  verdict: { label: string; tone: string; reasoning: string } | null;
  pattern: Pattern;
  pattern_snapshot: PatternSnapshotScore;
  historical_score: HistoricalScore;
}

// ── Shared formatting helpers ───────────────────────────────────────────────
function pct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`;
}
function pctCls(v: number | null | undefined): string {
  if (v == null) return "text-text-muted";
  return v >= 0 ? "text-accent-emerald" : "text-accent-rose";
}
function bestReturn(w: WinLoser): number {
  return w.return_1w ?? w.return_1m ?? w.return_1d ?? 0;
}
function riskBucket(score: number | null): { label: string; cls: string } {
  if (score == null) return { label: "Unknown", cls: "text-text-muted" };
  if (score >= 60) return { label: "High", cls: "text-accent-rose" };
  if (score >= 30) return { label: "Medium", cls: "text-amber-500" };
  return { label: "Low", cls: "text-accent-emerald" };
}
const SENTIMENT_STYLE: Record<string, string> = {
  bullish: "text-accent-emerald border-accent-emerald/25 bg-accent-emerald/10",
  bearish: "text-accent-rose border-accent-rose/25 bg-accent-rose/10",
  mixed:   "text-amber-500 border-amber-500/25 bg-amber-500/10",
  neutral: "text-text-secondary border-surface-border/15 bg-text-primary/5",
};
const DONUT_COLORS = ["#10b981", "#f43f5e", "#f59e0b", "#0ea5e9", "#8b5cf6"];

function fadeUp(delay = 0) {
  return {
    initial: { opacity: 0, y: 14 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, margin: "-60px" },
    transition: { duration: 0.4, delay },
  };
}

export function HistoricalDetailContent({ d, faqs, category }: {
  d: HistoricalDetail;
  faqs: { q: string; a: string }[];
  category: string;
}) {
  const p = d.pattern;
  const multi = p.category_occurrences > 1;
  const sentimentCls = SENTIMENT_STYLE[(d.sentiment ?? "neutral").toLowerCase()] ?? SENTIMENT_STYLE.neutral;
  const risk = riskBucket(d.risk_score);

  const winners = multi ? p.top_winners : d.historical_winners.map(w => ({
    symbol: w.symbol, name: w.name || w.symbol, wins: 1, losses: 0, appearances: 1,
    avg_return: bestReturn(w), win_rate: 100, reason: w.reason,
  }));
  const losers = multi ? p.top_losers : d.historical_losers.map(l => ({
    symbol: l.symbol, name: l.name || l.symbol, wins: 0, losses: 1, appearances: 1,
    avg_return: bestReturn(l), win_rate: 0, reason: l.reason,
  }));

  // best_sectors/worst_sectors are each a top-5 slice of the same
  // underlying set sorted in opposite directions — merged + de-duped so
  // the full sector table shows every tracked sector, not just the
  // positive half.
  const allSectorsMap = new Map<string, PatternSector>();
  for (const s of [...p.best_sectors, ...p.worst_sectors]) allSectorsMap.set(s.sector, s);
  const bestSectorsAll = [...allSectorsMap.values()].sort((a, b) => b.avg_reaction - a.avg_reaction);
  const negativeSectors = p.worst_sectors.filter(s => s.avg_reaction < 0);

  const shareUrl = typeof window !== "undefined" ? window.location.href : "";
  const handleShare = () => {
    if (typeof navigator !== "undefined" && navigator.share) {
      navigator.share({ title: d.event_title, url: shareUrl }).catch(() => {});
    } else if (typeof navigator !== "undefined") {
      navigator.clipboard?.writeText(shareUrl);
    }
  };

  return (
    <main className="mx-auto max-w-[1100px] py-8 pb-16">
      <nav className="mb-5 flex items-center justify-between text-[12px] text-text-muted">
        <Link href="/historical" className="flex items-center gap-1 hover:text-text-secondary transition">
          <ArrowLeft className="h-3 w-3" /> Historical Patterns
        </Link>
        <button onClick={handleShare} className="flex items-center gap-1 rounded-full border border-surface-border/12 px-2.5 py-1 hover:border-accent-violet/30 hover:text-accent-violet transition">
          <Share2 className="h-3 w-3" /> Share
        </button>
      </nav>

      {/* ── Section 1: Header ─────────────────────────────────────────── */}
      <motion.div {...fadeUp()}>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-text-primary/[0.07] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-text-secondary">{category}</span>
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${sentimentCls}`}>{d.sentiment ?? "Neutral"}</span>
          <span className="flex items-center gap-1 text-[11px] text-text-muted"><Clock className="h-3 w-3" /> {d.event_date}</span>
        </div>

        <h1 className="text-[26px] font-black leading-tight text-text-primary md:text-[34px]" style={{ textWrap: "balance" }}>{d.event_title}</h1>

        <p className="mt-3 max-w-[720px] text-[14px] leading-relaxed text-text-secondary">
          {multi
            ? `Based on ${p.category_occurrences} verified historical occurrences of this pattern between ${p.date_range.earliest} and ${p.date_range.latest}.`
            : "This is the only verified occurrence of this pattern in our historical database — treat it as a single data point, not a repeating trend."}
        </p>

        <div className="mt-5 flex flex-wrap gap-x-8 gap-y-2 text-[12px]">
          <div><span className="text-text-muted">First Occurrence </span><span className="font-semibold text-text-primary">{p.date_range.earliest ?? "—"}</span></div>
          <div><span className="text-text-muted">Latest Occurrence </span><span className="font-semibold text-text-primary">{p.date_range.latest ?? "—"}</span></div>
          <div><span className="text-text-muted">Occurrences </span><span className="font-semibold text-text-primary">{p.category_occurrences}</span></div>
          <div><span className="text-text-muted">Data Confidence </span><span className="font-semibold text-text-primary">{d.confidence != null ? `${d.confidence}%` : "—"}</span></div>
        </div>
      </motion.div>

      {/* ── Hero Summary Card ─────────────────────────────────────────── */}
      <motion.div {...fadeUp(0.05)} className="mt-6 grid grid-cols-1 gap-5 rounded-2xl border border-surface-border/10 bg-surface-card p-6 shadow-sm md:grid-cols-[auto_1fr]">
        <ConfidenceGauge score={d.pattern_snapshot.score} breakdown={d.pattern_snapshot.breakdown} />
        <div className="flex flex-col justify-center">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-3 py-1 text-[13px] font-bold ${
              d.verdict?.tone === "positive" ? "border-accent-emerald/25 bg-accent-emerald/10 text-accent-emerald"
              : d.verdict?.tone === "negative" ? "border-accent-rose/25 bg-accent-rose/10 text-accent-rose"
              : "border-surface-border/15 bg-text-primary/5 text-text-secondary"
            }`}>
              {d.verdict?.label ?? "Neutral"}
            </span>
            <span className="text-[11px] text-text-muted">Historical Verdict</span>
            <span className="ml-1 text-[12px] font-semibold">
              {d.pattern_snapshot.reliability.emoji} {d.pattern_snapshot.reliability.label}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <RatingStars historicalScore={d.historical_score} size="h-3.5 w-3.5" />
            <span className="text-[11px] text-text-muted">{d.historical_score.stars.toFixed(1)}/5 · {d.historical_score.band}</span>
            <RatingBreakdownPopover historicalScore={d.historical_score} />
          </div>
          <p className="mt-0.5 text-[10.5px] text-text-muted">
            Based on {p.category_occurrences} historical {category} event{p.category_occurrences === 1 ? "" : "s"}
          </p>
          {d.verdict?.reasoning && <p className="mt-2 text-[12px] text-text-muted">{d.verdict.reasoning}</p>}
          <p className="mt-3 max-w-[520px] text-[13.5px] leading-relaxed text-text-secondary">
            {bestSectorsAll[0]
              ? `Historically, ${bestSectorsAll[0].sector} reacted positively ${bestSectorsAll[0].positive_rate}% of the time (avg. ${pct(bestSectorsAll[0].avg_reaction)}) around events like this.`
              : (d.key_lesson ?? "")}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <a href="#timeline" className="rounded-full bg-accent-violet px-3.5 py-1.5 text-[12px] font-semibold text-white hover:opacity-90 transition">View Timeline</a>
            <a href="#similar" className="rounded-full border border-surface-border/15 px-3.5 py-1.5 text-[12px] font-semibold text-text-secondary hover:border-accent-violet/30 hover:text-accent-violet transition">Similar Events</a>
            <Link href={`/ai-search?q=${encodeURIComponent(`Does the historical pattern from "${truncateForQuery(d.event_title)}" apply to current market conditions?`)}`} className="rounded-full border border-surface-border/15 px-3.5 py-1.5 text-[12px] font-semibold text-text-secondary hover:border-accent-violet/30 hover:text-accent-violet transition">
              Compare With Today
            </Link>
          </div>
        </div>
      </motion.div>

      {/* ── Section 2: Historical Snapshot ────────────────────────────── */}
      <motion.div {...fadeUp(0.1)} className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-4">
        <SnapshotCard label="Historical Occurrences" value={String(p.category_occurrences)} sub={multi ? `since ${p.date_range.earliest}` : "single event"} />
        <SnapshotCard label="Avg. Nifty Reaction (1M)" value={pct(p.avg_nifty_1m)} sub="across all occurrences" cls={pctCls(p.avg_nifty_1m)} />
        <SnapshotCard label="Historically Positive" value={p.win_rate_pct != null ? `${p.win_rate_pct}%` : "—"} sub={`${p.bull_count} of ${p.bull_count + p.bear_count} times`} />
        <SnapshotCard label="Avg. Data Confidence" value={p.avg_confidence != null ? `${p.avg_confidence}%` : "—"} sub="across occurrences" />
      </motion.div>

      {/* ── Section 3: Timeline ───────────────────────────────────────── */}
      {p.timeline.length > 1 && (
        <motion.section id="timeline" {...fadeUp(0.1)} className="mt-10 scroll-mt-20">
          <SectionHeading icon={<Repeat className="h-3.5 w-3.5" />} title="Occurrence Timeline" />
          <div className="flex gap-3 overflow-x-auto pb-2 [scrollbar-width:thin]">
            {p.timeline.map(t => (
              <Link
                key={t.id}
                href={`/historical/${t.id}`}
                className={`flex w-[180px] shrink-0 flex-col gap-1.5 rounded-xl border p-3.5 transition ${
                  t.is_current ? "border-accent-violet/40 bg-accent-violet/[0.06]" : "border-surface-border/10 bg-text-primary/[0.02] hover:border-accent-violet/25"
                }`}
              >
                <span className="text-[10px] font-bold uppercase tracking-wide text-text-muted">{t.event_date}</span>
                <span className="line-clamp-2 text-[12.5px] font-semibold leading-snug text-text-primary">{t.event_title}</span>
                <div className="mt-auto flex items-center justify-between pt-1">
                  <span className={`text-[12px] font-bold tabular-nums ${pctCls(t.nifty_1m)}`}>{pct(t.nifty_1m)}</span>
                  {t.is_current && <span className="rounded-full bg-accent-violet/15 px-1.5 py-0.5 text-[9px] font-bold text-accent-violet">This Event</span>}
                </div>
              </Link>
            ))}
          </div>
        </motion.section>
      )}

      {/* ── Section 4: Winners / Losers ───────────────────────────────── */}
      {(winners.length > 0 || losers.length > 0) && (
        <motion.section {...fadeUp(0.1)} className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2">
          <WinLoseCard title="Historical Winners" tone="positive" icon={<TrendingUp className="h-3.5 w-3.5" />} items={winners} multi={multi} />
          <WinLoseCard title="Historical Losers" tone="negative" icon={<TrendingDown className="h-3.5 w-3.5" />} items={losers} multi={multi} />
        </motion.section>
      )}

      {/* ── Section 5: Sector Performance ─────────────────────────────── */}
      {bestSectorsAll.length > 0 && (
        <motion.section {...fadeUp(0.1)} className="mt-10">
          <SectionHeading icon={<Layers className="h-3.5 w-3.5" />} title="Sector Performance" sub={multi ? `Average reaction across ${p.category_occurrences} occurrences` : "This event's sector reactions"} />
          <div className="space-y-1.5">
            {bestSectorsAll.map(s => {
              const magnitude = Math.min(100, Math.abs(s.avg_reaction) * 12);
              return (
                <div key={s.sector} className="flex items-center gap-3 rounded-lg border border-surface-border/8 bg-text-primary/[0.015] px-3 py-2">
                  <span className="w-[140px] shrink-0 truncate text-[12.5px] font-semibold text-text-primary">{s.sector}</span>
                  <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-text-primary/[0.06]">
                    <div
                      className={`h-full rounded-full ${s.avg_reaction >= 0 ? "bg-accent-emerald" : "bg-accent-rose"}`}
                      style={{ width: `${magnitude}%` }}
                    />
                  </div>
                  <span className={`w-[64px] shrink-0 text-right text-[12.5px] font-bold tabular-nums ${pctCls(s.avg_reaction)}`}>{pct(s.avg_reaction)}</span>
                  <span className="w-[86px] shrink-0 text-right text-[10.5px] text-text-muted">{s.positive_rate}% of {s.occurrences}x</span>
                </div>
              );
            })}
          </div>
        </motion.section>
      )}

      {/* ── Section 6: Pattern Recognition ────────────────────────────── */}
      <motion.section {...fadeUp(0.1)} className="mt-10">
        <SectionHeading icon={<Sparkles className="h-3.5 w-3.5" />} title="Pattern Recognition" />
        {multi ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {bestSectorsAll[0] && (
              <PatternCard
                icon={<Layers className="h-4 w-4" />}
                title={`${bestSectorsAll[0].sector} leads most reliably`}
                body={`Reacted positively in ${bestSectorsAll[0].positive_rate}% of ${bestSectorsAll[0].occurrences} occurrences, averaging ${pct(bestSectorsAll[0].avg_reaction)}.`}
              />
            )}
            {winners[0] && (
              <PatternCard
                icon={<Star className="h-4 w-4" />}
                title={`${winners[0].name} is the most consistent winner`}
                body={`Gained an average of ${pct(winners[0].avg_return)} and won in ${winners[0].win_rate}% of its ${winners[0].appearances} appearances.`}
              />
            )}
            {p.consistency.nifty_direction && (
              <PatternCard
                icon={<Target className="h-4 w-4" />}
                title={`Nifty moved ${p.consistency.nifty_direction.value} most of the time`}
                body={`${p.consistency.nifty_direction.pct}% of ${p.consistency.nifty_direction.of} occurrences (${p.consistency.nifty_direction.occurrences} of them).`}
              />
            )}
          </div>
        ) : (
          <p className="rounded-xl border border-surface-border/10 bg-text-primary/[0.02] p-4 text-[13px] text-text-muted">
            Pattern recognition needs multiple occurrences of this event type — this is currently the only one recorded. <Link href="/historical" className="text-accent-violet hover:underline">Browse other patterns →</Link>
          </p>
        )}
      </motion.section>

      {/* ── Section 7: Historical Market Statistics ───────────────────── */}
      {multi && (
        <motion.section {...fadeUp(0.1)} className="mt-10">
          <SectionHeading icon={<Target className="h-3.5 w-3.5" />} title="Historical Market Statistics" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <DonutStat
              title="Market Direction"
              data={[{ name: "Bullish", value: p.bull_count }, { name: "Bearish", value: p.bear_count }]}
              centerLabel={`${p.win_rate_pct ?? 0}%`}
              centerSub="Bullish"
            />
            <DonutStat
              title="Company Outcomes"
              data={[{ name: "Winners", value: p.total_winner_appearances }, { name: "Losers", value: p.total_loser_appearances }]}
              centerLabel={String(p.total_winner_appearances + p.total_loser_appearances)}
              centerSub="tracked"
            />
            <DonutStat
              title="Sector Leadership"
              data={p.best_sectors.slice(0, 5).map(s => ({ name: s.sector, value: s.positive }))}
              centerLabel={p.best_sectors[0]?.sector.slice(0, 6) ?? "—"}
              centerSub="top sector"
              multi
            />
          </div>
        </motion.section>
      )}

      {/* ── Section 8: What Changed Every Time ────────────────────────── */}
      {multi && (
        <motion.section {...fadeUp(0.1)} className="mt-10">
          <SectionHeading icon={<CheckCircle2 className="h-3.5 w-3.5" />} title="What Changed Every Time" sub="Real consistency across every occurrence — not a guarantee" />
          <div className="space-y-2">
            {p.consistency.nifty_direction && (
              <ConsistencyRow label={`Nifty moved ${p.consistency.nifty_direction.value}`} fact={p.consistency.nifty_direction} />
            )}
            {p.consistency.interest_rate_trend && (
              <ConsistencyRow label={`Interest rates were ${p.consistency.interest_rate_trend.value}`} fact={p.consistency.interest_rate_trend} />
            )}
            {p.consistency.crude_trend && (
              <ConsistencyRow label={`Crude oil trend was ${p.consistency.crude_trend.value}`} fact={p.consistency.crude_trend} />
            )}
            {p.consistency.market_regime && (
              <ConsistencyRow label={`Market regime was ${p.consistency.market_regime.value}`} fact={p.consistency.market_regime} />
            )}
            {bestSectorsAll[0] && (
              <ConsistencyRow label={`${bestSectorsAll[0].sector} reacted positively`} fact={{ value: "", occurrences: bestSectorsAll[0].positive, of: bestSectorsAll[0].occurrences, pct: bestSectorsAll[0].positive_rate }} />
            )}
          </div>
        </motion.section>
      )}

      {/* ── Section 9: Investment Playbook ────────────────────────────── */}
      <motion.section {...fadeUp(0.1)} className="mt-10 rounded-2xl border border-accent-violet/15 bg-accent-violet/[0.03] p-6">
        <SectionHeading icon={<ShieldCheck className="h-3.5 w-3.5" />} title="Investment Playbook" sub="Derived from real historical data — a research framework, not a recommendation" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-2.5">
            <Row label="Historical Verdict" value={d.verdict?.label ?? "—"} />
            <Row label="Historical Win Rate" value={p.win_rate_pct != null ? `${p.win_rate_pct}%` : "—"} />
            <Row label="Ideal Holding Period" value={p.holding_period ? `~${p.holding_period.label} (${pct(p.holding_period.avg_return)} avg.)` : "—"} />
            <Row label="Risk Level" value={risk.label} cls={risk.cls} />
            <Row label="Pattern Match Score" value={`${d.pattern_snapshot.score}%`} />
            <Row label="Historical Score" value={`${d.historical_score.score}/100 (${d.historical_score.stars.toFixed(1)}★)`} />
          </div>
          <div className="space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-widest text-text-muted">Action Checklist</p>
            {bestSectorsAll[0] && <Checklist text={`Watch ${bestSectorsAll.slice(0, 3).map(s => s.sector).join(", ")} for continued strength`} />}
            {negativeSectors[0] && <Checklist text={`Be cautious on ${negativeSectors.map(s => s.sector).join(", ")}`} />}
            {p.holding_period && <Checklist text={`Historical moves typically play out over ${p.holding_period.label.toLowerCase()}`} />}
            <Checklist text={`Cross-check with current market regime before acting — history is context, not certainty`} />
          </div>
        </div>
      </motion.section>

      {/* ── Section 10: Similar Historical Patterns ───────────────────── */}
      {p.timeline.filter(t => !t.is_current).length > 0 && (
        <motion.section id="similar" {...fadeUp(0.1)} className="mt-10 scroll-mt-20">
          <SectionHeading icon={<Repeat className="h-3.5 w-3.5" />} title="Similar Historical Patterns" sub={`Other ${category} events in our database`} />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {p.timeline.filter(t => !t.is_current).slice(0, 6).map(t => (
              <Link key={t.id} href={`/historical/${t.id}`} className="group rounded-xl border border-surface-border/10 bg-text-primary/[0.02] p-4 transition hover:border-accent-violet/25">
                <div className="flex items-center justify-between">
                  <RatingStars historicalScore={t.historical_score} />
                  <span className="text-[10px] text-text-muted">{t.event_date}</span>
                </div>
                <p className="mt-2 line-clamp-2 text-[13px] font-semibold leading-snug text-text-primary group-hover:text-accent-violet transition">{t.event_title}</p>
                <div className="mt-2 flex items-center justify-between">
                  <span className={`text-[12px] font-bold tabular-nums ${pctCls(t.nifty_1m)}`}>{pct(t.nifty_1m)} · 1M</span>
                  <ArrowRight className="h-3.5 w-3.5 text-text-muted transition group-hover:translate-x-0.5 group-hover:text-accent-violet" />
                </div>
              </Link>
            ))}
          </div>
        </motion.section>
      )}

      {/* ── Companies Involved ─────────────────────────────────────────── */}
      {d.companies.length > 0 && (
        <motion.section {...fadeUp(0.1)} className="mt-10">
          <SectionHeading icon={<Landmark className="h-3.5 w-3.5" />} title="Companies Involved" />
          <div className="flex flex-wrap gap-2">
            {d.companies.map(sym => (
              <Link key={sym} href={`/companies/${sym}`} className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-3 py-1 text-[12px] font-semibold text-text-secondary hover:border-accent-sky/30 hover:text-accent-sky transition">
                {sym}
              </Link>
            ))}
          </div>
        </motion.section>
      )}

      {/* ── Section 11: FAQ ────────────────────────────────────────────── */}
      {faqs.length > 0 && (
        <motion.section {...fadeUp(0.1)} className="mt-10">
          <SectionHeading title="Frequently Asked" />
          <div className="space-y-2">
            {faqs.map((f, i) => <FaqRow key={i} q={f.q} a={f.a} />)}
          </div>
        </motion.section>
      )}

      <div className="mt-10 flex items-center justify-between border-t border-surface-border/6 pt-5">
        <Link href="/historical" className="text-[12px] font-semibold text-accent-violet hover:underline">← All Historical Patterns</Link>
        <span className="text-[10px] text-text-muted">MarketRipple Historical Memory Engine</span>
      </div>
    </main>
  );
}

// ── Small building blocks ───────────────────────────────────────────────────

function SectionHeading({ icon, title, sub }: { icon?: React.ReactNode; title: string; sub?: string }) {
  return (
    <div className="mb-3">
      <h2 className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-text-muted">
        {icon}{title}
      </h2>
      {sub && <p className="mt-0.5 text-[11.5px] text-text-muted">{sub}</p>}
    </div>
  );
}

function SnapshotCard({ label, value, sub, cls }: { label: string; value: string; sub?: string; cls?: string }) {
  return (
    <div className="rounded-xl border border-surface-border/10 bg-surface-card p-4">
      <p className="text-[9.5px] font-bold uppercase tracking-widest text-text-muted">{label}</p>
      <p className={`mt-1.5 text-[22px] font-black tabular-nums ${cls ?? "text-text-primary"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[10.5px] text-text-muted">{sub}</p>}
    </div>
  );
}

function WinLoseCard({ title, tone, icon, items, multi }: {
  title: string; tone: "positive" | "negative"; icon: React.ReactNode;
  items: { symbol: string; name: string; wins: number; losses: number; appearances: number; avg_return: number; win_rate: number; reason: string | null }[];
  multi: boolean;
}) {
  const border = tone === "positive" ? "border-accent-emerald/15 bg-accent-emerald/[0.04]" : "border-accent-rose/15 bg-accent-rose/[0.04]";
  const head = tone === "positive" ? "text-accent-emerald" : "text-accent-rose";
  const valCls = tone === "positive" ? "text-accent-emerald" : "text-accent-rose";
  // Consistency = how often this company landed on THIS side of the
  // pattern (win_rate for winners, its complement for losers) — real,
  // derived from the same appearances/wins/losses already shown.
  const consistencyScore = (it: typeof items[number]) => tone === "positive" ? it.win_rate : 100 - it.win_rate;
  return (
    <div className={`rounded-2xl border p-4 ${border}`}>
      <h3 className={`mb-3 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest ${head}`}>{icon}{title}</h3>
      {items.length ? (
        <div className="space-y-3">
          {items.slice(0, 5).map((it, i) => (
            <div key={i}>
              <div className="flex items-center justify-between">
                <Link href={`/companies/${it.symbol}`} className="text-[13px] font-semibold text-text-primary hover:text-accent-violet transition">{it.name}</Link>
                <span className={`text-[13px] font-bold tabular-nums ${valCls}`}>{pct(it.avg_return)}</span>
              </div>
              <div className="mt-0.5 flex items-center justify-between gap-2">
                <span className="text-[11px] text-text-muted">
                  {multi ? `Appeared in ${it.appearances} similar event${it.appearances === 1 ? "" : "s"}` : it.reason}
                </span>
                {multi && (
                  <span className="flex shrink-0 items-center gap-1">
                    <span className="text-[9.5px] text-text-muted">Consistency</span>
                    <RatingStars historicalScore={{ score: consistencyScore(it), stars: consistencyScore(it) / 20, band: "", breakdown: [] }} size="h-2.5 w-2.5" />
                  </span>
                )}
              </div>
            </div>
          ))}
          {items[0] && (
            <Link href={`/companies/${items[0].symbol}`} className={`flex items-center gap-1 pt-0.5 text-[11px] font-semibold hover:underline ${head}`}>
              View History <ArrowRight className="h-3 w-3" />
            </Link>
          )}
        </div>
      ) : <p className="text-[12px] text-text-muted">No clear pattern in the historical data.</p>}
    </div>
  );
}

function PatternCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-xl border border-surface-border/10 bg-surface-card p-4">
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-violet/10 text-accent-violet">{icon}</span>
      <p className="mt-2.5 text-[13px] font-bold leading-snug text-text-primary">{title}</p>
      <p className="mt-1 text-[12px] leading-relaxed text-text-muted">{body}</p>
    </div>
  );
}

function DonutStat({ title, data, centerLabel, centerSub, multi }: {
  title: string; data: { name: string; value: number }[]; centerLabel: string; centerSub: string; multi?: boolean;
}) {
  const filtered = data.filter(d => d.value > 0);
  return (
    <div className="rounded-xl border border-surface-border/10 bg-surface-card p-4">
      <p className="text-[10px] font-bold uppercase tracking-widest text-text-muted">{title}</p>
      <div className="relative mt-2 h-[140px]">
        <HistoricalDonutChart filtered={filtered} />
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[15px] font-black text-text-primary">{centerLabel}</span>
          <span className="text-[9px] text-text-muted">{centerSub}</span>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        {filtered.map((d, i) => (
          <span key={d.name} className="flex items-center gap-1 text-[10px] text-text-muted">
            <span className="h-2 w-2 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
            {d.name}{!multi && ` (${d.value})`}
          </span>
        ))}
      </div>
    </div>
  );
}

function ConsistencyRow({ label, fact }: { label: string; fact: ConsistencyFact }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-surface-border/8 bg-text-primary/[0.015] px-3.5 py-2.5">
      <CheckCircle2 className="h-4 w-4 shrink-0 text-accent-emerald" />
      <span className="flex-1 text-[12.5px] text-text-primary">{label}</span>
      <div className="hidden w-[100px] shrink-0 overflow-hidden rounded-full bg-text-primary/[0.06] sm:block">
        <div className="h-1.5 rounded-full bg-accent-violet" style={{ width: `${fact.pct}%` }} />
      </div>
      <span className="w-[86px] shrink-0 text-right text-[11px] font-semibold text-text-secondary">{fact.pct}% ({fact.occurrences}/{fact.of})</span>
    </div>
  );
}

function Row({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-surface-border/5 pb-2.5 last:border-0 last:pb-0">
      <span className="text-[12px] text-text-muted">{label}</span>
      <span className={`text-[12.5px] font-semibold ${cls ?? "text-text-primary"}`}>{value}</span>
    </div>
  );
}

function Checklist({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2">
      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-violet" />
      <span className="text-[12.5px] leading-snug text-text-secondary">{text}</span>
    </div>
  );
}

// Real, mathematically-derived rating (compute_historical_score in the
// backend) — supports half-stars since the banded score→star conversion
// produces values like 3.5/4.5.
function RatingStars({ historicalScore, size = "h-3 w-3" }: { historicalScore: HistoricalScore | null | undefined; size?: string }) {
  const stars = historicalScore?.stars ?? null;
  const title = historicalScore ? `${historicalScore.stars.toFixed(1)}/5 · ${historicalScore.band} (${historicalScore.score}/100)` : "No score";
  return (
    <span className="flex items-center gap-0.5" title={title}>
      {Array.from({ length: 5 }).map((_, i) => {
        const fill = stars == null ? 0 : Math.max(0, Math.min(1, stars - i));
        if (fill >= 1) return <Star key={i} className={`${size} fill-sky-500 text-sky-500`} />;
        if (fill > 0) {
          return (
            <span key={i} className={`relative ${size} inline-block shrink-0`}>
              <Star className={`${size} absolute inset-0 text-surface-border`} />
              <span className="absolute inset-0 overflow-hidden" style={{ width: "50%" }}>
                <Star className={`${size} fill-sky-500 text-sky-500`} />
              </span>
            </span>
          );
        }
        return <Star key={i} className={`${size} text-surface-border`} />;
      })}
    </span>
  );
}

// Answers "why N stars?" with the real breakdown the score is computed
// from (compute_historical_score) — not a second, different explanation.
// Per-factor mini-stars are score/20, a plain visual proxy for the % shown
// right next to it, not a separate rating.
function RatingBreakdownPopover({ historicalScore }: { historicalScore: HistoricalScore }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-flex items-center">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1 rounded-full px-1.5 py-0.5 text-text-muted transition hover:bg-text-primary/[0.06] hover:text-accent-violet"
        title="Why this rating?"
      >
        <Info className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-30 mt-2 w-[260px] rounded-xl border border-surface-border/12 bg-surface-card p-4 shadow-xl">
          <p className="mb-3 text-[11px] font-bold uppercase tracking-wide text-text-muted">Historical Rating Breakdown</p>
          <div className="space-y-2.5">
            {historicalScore.breakdown.map(b => (
              <div key={b.label} className="flex items-center justify-between gap-2">
                <span className="text-[11.5px] text-text-secondary">{b.label}</span>
                <span className="flex items-center gap-1.5">
                  <span className="text-[11px] font-bold tabular-nums text-text-primary">{b.score}</span>
                  <RatingStars historicalScore={{ score: b.score, stars: b.score / 20, band: "", breakdown: [] }} size="h-2.5 w-2.5" />
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-surface-border/10 pt-3">
            <span className="text-[11.5px] font-bold text-text-primary">Overall</span>
            <span className="flex items-center gap-1.5">
              <span className="text-[12px] font-black text-accent-violet">{historicalScore.stars.toFixed(1)}/5</span>
              <RatingStars historicalScore={historicalScore} size="h-3 w-3" />
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function FaqRow({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-surface-border/6 bg-text-primary/[0.02]">
      <button onClick={() => setOpen(o => !o)} className="flex w-full items-center justify-between gap-3 p-4 text-left">
        <span className="text-[13px] font-semibold text-text-primary">{q}</span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <p className="px-4 pb-4 text-[13px] leading-relaxed text-text-secondary">{a}</p>}
    </div>
  );
}

function ConfidenceGauge({ score, breakdown }: { score: number; breakdown: { label: string; weight: number; score: number }[] }) {
  const r = 46, c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;
  const tone = score >= 70 ? "#10b981" : score >= 45 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-[124px] w-[124px]">
        <svg width="124" height="124" viewBox="0 0 124 124" className="-rotate-90">
          <circle cx="62" cy="62" r={r} fill="none" stroke="rgb(var(--text-primary) / 0.08)" strokeWidth="10" />
          <circle cx="62" cy="62" r={r} fill="none" stroke={tone} strokeWidth="10" strokeLinecap="round"
            strokeDasharray={c} strokeDashoffset={offset} style={{ transition: "stroke-dashoffset 0.6s ease" }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[24px] font-black tabular-nums text-text-primary">{score}</span>
          <span className="text-[8.5px] font-bold uppercase tracking-wide text-text-muted">Pattern Match</span>
        </div>
      </div>
      <div className="flex flex-col gap-0.5">
        {breakdown.map(b => (
          <div key={b.label} className="flex items-center justify-between gap-3 text-[9.5px] text-text-muted">
            <span>{b.label} ({b.weight}%)</span>
            <span className="font-semibold text-text-secondary">{b.score}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
