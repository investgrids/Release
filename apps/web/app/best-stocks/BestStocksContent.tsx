import Link from "next/link";
import { Sparkles, Layers, Target, Percent, Clock } from "lucide-react";
import {
  getSectorsWithCounts, getTopRankedCompanies, getRankingStats,
  getMarketRegime, getActiveOpportunityCount,
} from "@/lib/bestStocks";
import { RankingsView } from "./RankingsView";

function relativeTime(iso: string | null): string {
  if (!iso) return "just now";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} minute${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
  const days = Math.round(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

export async function BestStocksContent({ headingLevel = "h1" }: { headingLevel?: "h1" | "h2" }) {
  const Heading = headingLevel;
  const [sectors, topPicks, stats, marketRegime, activeOpportunities] = await Promise.all([
    getSectorsWithCounts(),
    getTopRankedCompanies(30, true),
    getRankingStats(),
    getMarketRegime(),
    getActiveOpportunityCount(),
  ]);

  const kpis = [
    { label: "Stocks Ranked", value: stats.stocksRanked.toLocaleString(), icon: Layers },
    { label: "Sectors Covered", value: String(stats.sectorsCovered), icon: Target },
    { label: "Active Opportunities", value: String(activeOpportunities), icon: Sparkles },
    { label: "Avg. AI Confidence", value: stats.avgConfidence != null ? `${Math.round(stats.avgConfidence)}%` : "—", icon: Percent },
  ];

  return (
    <main className="mx-auto max-w-[1400px] py-8 pb-16">
      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <div className="rounded-[28px] border border-surface-border/8 bg-gradient-to-br from-violet-500/[0.06] via-surface-card to-surface-card p-6 md:p-9">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl">
            <div className="mb-3 flex items-center gap-2">
              <span className="flex items-center gap-1.5 rounded-full border border-violet-500/25 bg-violet-500/10 px-3 py-1 text-[11px] font-bold text-violet-600 dark:text-violet-300">
                <Sparkles className="h-3 w-3" /> AI RANKED
              </span>
            </div>
            <Heading className="text-[30px] font-black leading-tight text-text-primary md:text-[38px]">
              Best Stocks
            </Heading>
            <p className="mt-3 text-[14px] leading-relaxed text-text-secondary">
              AI continuously ranks Indian stocks using live market events, sector strength, earnings
              momentum, institutional flows, historical patterns and opportunity intelligence — every
              score traces back to real, published evidence, never a generic screener filter.
            </p>
          </div>

          {/* Real stat stack — no single fabricated "hero number" */}
          <div className="flex shrink-0 flex-wrap gap-x-8 gap-y-5 lg:flex-col lg:gap-y-4 lg:border-l lg:border-surface-border/8 lg:pl-8">
            <div>
              <p className="text-[28px] font-black tabular-nums text-text-primary">
                {stats.avgScore != null ? stats.avgScore.toFixed(1) : "—"}<span className="text-[16px] text-text-muted">/100</span>
              </p>
              <p className="text-[10.5px] uppercase tracking-wide text-text-muted">Avg. AI Score</p>
            </div>
            <div className="flex gap-6 lg:gap-8">
              <div>
                <p className="text-[16px] font-bold tabular-nums text-text-primary">{stats.stocksRanked.toLocaleString()}</p>
                <p className="text-[10.5px] uppercase tracking-wide text-text-muted">Companies</p>
              </div>
              <div>
                <p className="text-[16px] font-bold text-text-primary">{marketRegime ?? "—"}</p>
                <p className="text-[10.5px] uppercase tracking-wide text-text-muted">Market Regime</p>
              </div>
            </div>
            <p className="flex items-center gap-1.5 text-[11px] text-text-muted">
              <Clock className="h-3 w-3" /> Updated {relativeTime(stats.updatedAt)}
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-2 border-t border-surface-border/6 pt-5">
          <Link href="#methodology" className="rounded-full border border-surface-border/10 bg-surface-card px-3.5 py-1.5 text-[12px] font-semibold text-text-secondary transition hover:border-violet-500/30 hover:text-text-primary">
            How Rankings Work
          </Link>
          <Link href="/ai-search" className="rounded-full border border-violet-500/25 bg-violet-500/10 px-3.5 py-1.5 text-[12px] font-semibold text-violet-600 dark:text-violet-300 transition hover:bg-violet-500/15">
            Ask AI Search
          </Link>
        </div>
      </div>

      {/* ── KPI cards ────────────────────────────────────────────────── */}
      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {kpis.map(k => (
          <div key={k.label} className="rounded-[18px] border border-surface-border/8 bg-surface-card p-4">
            <k.icon className="h-4 w-4 text-violet-500" />
            <p className="mt-2 text-[22px] font-black tabular-nums text-text-primary">{k.value}</p>
            <p className="text-[11px] text-text-muted">{k.label}</p>
          </div>
        ))}
      </div>

      {/* ── Top AI Picks (sector dropdown + pagination live inside) ────── */}
      <div className="mt-10">
        <RankingsView companies={topPicks} sectors={sectors} />
      </div>

      {/* ── Methodology ──────────────────────────────────────────────── */}
      <div id="methodology" className="mt-10 rounded-[20px] border border-surface-border/8 bg-text-primary/[0.02] p-6">
        <h2 className="text-[15px] font-bold text-text-primary">How These Rankings Work</h2>
        <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-text-secondary">
          Every ranked company is scored from real signals extracted from published AI intelligence
          articles and Opportunity Radar — never a fabricated number. Each signal (a company mentioned
          in a real article, or a real Opportunity Radar entry) contributes based on its confidence,
          quality, and how recent it is (recency decays over roughly 3 weeks). Companies with no real
          signals show no score at all, rather than a manufactured zero.
        </p>
      </div>
    </main>
  );
}
