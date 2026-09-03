"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { TrendingUp, TrendingDown, Minus, LayoutGrid, List, LineChart, ChevronLeft, ChevronRight } from "lucide-react";
import { getRankedCompaniesForSector, enrichWithQuotes, type RankedCompany } from "@/lib/bestStocks";

const PAGE_SIZE = 10;

const TREND_ICON = { up: TrendingUp, down: TrendingDown, neutral: Minus } as const;
const TREND_COLOR = {
  up: "text-emerald-600 dark:text-emerald-300",
  down: "text-rose-600 dark:text-rose-300",
  neutral: "text-text-muted",
} as const;
const VERDICT_TONE: Record<string, string> = {
  positive: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 border-emerald-500/25",
  negative: "bg-rose-500/10 text-rose-600 dark:text-rose-300 border-rose-500/25",
  neutral:  "bg-text-primary/[0.05] text-text-secondary border-surface-border/10",
};
const RANK_BADGE = [
  "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-500/30",   // 1st
  "bg-slate-400/15 text-slate-600 dark:text-slate-300 border-slate-400/30",  // 2nd
  "bg-orange-600/15 text-orange-700 dark:text-orange-300 border-orange-600/30", // 3rd
];

function PickCard({ c }: { c: RankedCompany }) {
  const TrendIcon = TREND_ICON[c.trend as keyof typeof TREND_ICON] ?? Minus;
  const trendColor = TREND_COLOR[c.trend as keyof typeof TREND_COLOR] ?? "text-text-muted";
  const verdictCls = c.verdict ? (VERDICT_TONE[c.verdict.tone] ?? VERDICT_TONE.neutral) : null;

  return (
    <Link
      href={`/companies/${c.symbol}`}
      className="flex flex-col rounded-[20px] border border-surface-border/8 bg-surface-card p-4 transition hover:-translate-y-0.5 hover:border-violet-500/25 hover:shadow-lg"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[14px] font-bold text-text-primary">{c.name}</p>
          <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-text-muted">
            <span>{c.symbol}</span>
            {c.sector && <><span aria-hidden>·</span><span>{c.sector}</span></>}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <TrendIcon className={`h-3.5 w-3.5 ${trendColor}`} />
          <span className="text-[18px] font-black tabular-nums text-text-primary">{Math.round(c.impactScore)}</span>
        </div>
      </div>

      {c.verdict && (
        <span className={`mt-2.5 inline-flex w-fit items-center rounded-full border px-2 py-0.5 text-[10px] font-bold ${verdictCls}`}>
          {c.verdict.label}
        </span>
      )}

      <p className="mt-2.5 line-clamp-3 text-[12px] leading-relaxed text-text-secondary">{c.reason}</p>

      {/* CD3-C: c.confidence is company_score_engine.py's weighted mean of
          per-signal confidences (0.5-defaulted where absent) -- the same
          figure CompanyIntelligenceSection.tsx already retired from direct
          display elsewhere as "genuinely misleading on its own". Disclosed
          via tooltip here rather than removed. */}
      <div className="mt-3 flex items-center justify-between border-t border-surface-border/6 pt-2.5 text-[10.5px] text-text-muted">
        <span title={c.confidence != null ? "A weighted average of per-signal confidence -- not an independently verified score" : undefined}>{c.confidence != null ? `${Math.round(c.confidence * 100)}% confidence` : "Confidence n/a"}</span>
        <span>{c.signalCount} signal{c.signalCount === 1 ? "" : "s"}</span>
      </div>
    </Link>
  );
}

function ScoreLabel(score: number): string {
  if (score >= 80) return "Excellent";
  if (score >= 65) return "Very Good";
  if (score >= 50) return "Good";
  return "Fair";
}

function RankingsTable({ companies, startRank = 0 }: { companies: RankedCompany[]; startRank?: number }) {
  return (
    <div className="overflow-x-auto rounded-[20px] border border-surface-border/8 bg-surface-card">
      <table className="w-full min-w-[720px] border-collapse text-left">
        <thead>
          <tr className="border-b border-surface-border/8 text-[10.5px] uppercase tracking-wide text-text-muted">
            <th className="px-4 py-3 font-semibold">Rank</th>
            <th className="px-4 py-3 font-semibold">Company</th>
            <th className="px-4 py-3 font-semibold text-right">AI Score</th>
            <th className="px-4 py-3 font-semibold text-right">Price</th>
            <th className="px-4 py-3 font-semibold text-right">1D Change</th>
            <th className="px-4 py-3 font-semibold text-right">Market Cap</th>
            <th className="px-4 py-3 font-semibold">Sector</th>
            <th className="px-4 py-3 font-semibold text-right">View</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((c, i) => {
            const rank = startRank + i;
            const TrendIcon = TREND_ICON[c.trend as keyof typeof TREND_ICON] ?? Minus;
            const trendColor = TREND_COLOR[c.trend as keyof typeof TREND_COLOR] ?? "text-text-muted";
            const badgeCls = RANK_BADGE[rank] ?? "bg-text-primary/[0.05] text-text-secondary border-surface-border/10";
            const changeCls = c.changePct == null ? "text-text-muted"
              : c.changePct > 0 ? "text-emerald-600 dark:text-emerald-300"
              : c.changePct < 0 ? "text-rose-600 dark:text-rose-300" : "text-text-muted";

            return (
              <tr key={c.symbol} className="border-b border-surface-border/5 text-[13px] transition hover:bg-text-primary/[0.02] last:border-0">
                <td className="px-4 py-3">
                  <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-black ${badgeCls}`}>
                    {rank + 1}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/companies/${c.symbol}`} className="group">
                    <p className="font-semibold text-text-primary group-hover:text-violet-600 dark:group-hover:text-violet-300">{c.name}</p>
                    <p className="text-[11px] text-text-muted">{c.symbol}</p>
                  </Link>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1.5">
                    <TrendIcon className={`h-3 w-3 ${trendColor}`} />
                    <span className="font-black tabular-nums text-text-primary">{Math.round(c.impactScore)}</span>
                  </div>
                  <p className="text-[10.5px] text-text-muted">{ScoreLabel(c.impactScore)}</p>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-text-primary">
                  {c.price ? `₹${c.price}` : <span className="text-text-muted">—</span>}
                </td>
                <td className={`px-4 py-3 text-right tabular-nums font-semibold ${changeCls}`}>
                  {c.changePct != null ? `${c.changePct > 0 ? "+" : ""}${c.changePct.toFixed(2)}%` : "—"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-text-secondary">
                  {c.marketCap ?? <span className="text-text-muted">—</span>}
                </td>
                <td className="px-4 py-3 text-text-secondary">{c.sector ?? "—"}</td>
                <td className="px-4 py-3 text-right">
                  <Link href={`/companies/${c.symbol}`} className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-surface-border/10 text-text-muted transition hover:border-violet-500/30 hover:text-violet-600 dark:hover:text-violet-300">
                    <LineChart className="h-3.5 w-3.5" />
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function RankingsView({
  companies, sectors,
}: {
  companies: RankedCompany[];
  sectors: { sector: string; slug: string; companyCount: number }[];
}) {
  const [view, setView] = useState<"cards" | "table">("table");
  const [sector, setSector] = useState<string>("All");
  const [cap, setCap] = useState<"All" | "large" | "mid" | "small">("All");
  const [sectorCompanies, setSectorCompanies] = useState<RankedCompany[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  // Sector switch fetches the ranking WITHOUT quotes (fast — just the real
  // score/verdict/reasons, no per-symbol price/market-cap calls yet). Quotes
  // get fetched only for whichever 10 rows are actually on screen (below),
  // not the whole sector — fetching all 50 up front for a page that only
  // ever shows 10 at a time was the real cause of "taking too much time".
  useEffect(() => {
    setPage(1);
    if (sector === "All") {
      setSectorCompanies(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    getRankedCompaniesForSector(sector, false)
      .then(list => { if (!cancelled) setSectorCompanies(list); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sector]);

  useEffect(() => { setPage(1); }, [cap]);

  const bySector = sector === "All" ? companies : (sectorCompanies ?? []);
  // cap ("large"/"mid"/"small") comes from the same real NSE universe data
  // the Companies directory uses — companies whose cap isn't classified
  // there (rare) just don't match a specific cap filter, never miscategorized.
  const active = cap === "All" ? bySector : bySector.filter(c => c.cap === cap);
  const totalPages = Math.max(1, Math.ceil(active.length / PAGE_SIZE));
  const rawPaged = useMemo(
    () => active.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [active, page],
  );

  // Quote enrichment for just the visible page. The "All Sectors" default
  // list already arrives pre-enriched from the server (see
  // BestStocksContent.tsx), so this only actually fetches anything for a
  // sector-filtered page that hasn't been enriched yet.
  const [paged, setPaged] = useState<RankedCompany[]>([]);
  const [quotesLoading, setQuotesLoading] = useState(false);
  const pageKey = rawPaged.map(c => c.symbol).join(",");
  useEffect(() => {
    if (rawPaged.length === 0) { setPaged([]); return; }
    if (rawPaged.every(c => c.price !== null)) { setPaged(rawPaged); return; }
    let cancelled = false;
    setQuotesLoading(true);
    enrichWithQuotes(rawPaged)
      .then(list => { if (!cancelled) setPaged(list); })
      .finally(() => { if (!cancelled) setQuotesLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageKey]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-[18px] font-black text-text-primary">Top AI Picks</h2>
          <p className="mt-0.5 text-[12.5px] text-text-secondary">
            Ranked by real signal evidence — published analysis and Opportunity Radar, weighted by confidence and recency.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <select
            value={sector}
            onChange={e => setSector(e.target.value)}
            className="rounded-full border border-surface-border/10 bg-surface-card px-3.5 py-1.5 text-[12px] font-semibold text-text-primary outline-none transition hover:border-violet-500/30"
          >
            <option value="All">All Sectors</option>
            {sectors.map(s => (
              <option key={s.slug} value={s.sector}>{s.sector} ({s.companyCount})</option>
            ))}
          </select>
          <div className="flex rounded-full border border-surface-border/10 bg-text-primary/[0.03] p-1">
            <button
              onClick={() => setView("cards")}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-semibold transition ${view === "cards" ? "bg-surface-card text-text-primary shadow-sm" : "text-text-muted hover:text-text-secondary"}`}
            >
              <LayoutGrid className="h-3.5 w-3.5" /> Cards
            </button>
            <button
              onClick={() => setView("table")}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-semibold transition ${view === "table" ? "bg-surface-card text-text-primary shadow-sm" : "text-text-muted hover:text-text-secondary"}`}
            >
              <List className="h-3.5 w-3.5" /> Table
            </button>
          </div>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {([
          { id: "All", label: "All Cap" },
          { id: "large", label: "Large Cap" },
          { id: "mid", label: "Mid Cap" },
          { id: "small", label: "Small Cap" },
        ] as const).map(t => (
          <button
            key={t.id}
            onClick={() => setCap(t.id)}
            className={`rounded-full border px-3.5 py-1.5 text-[12px] font-semibold transition ${
              cap === t.id
                ? "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-300"
                : "border-surface-border/10 bg-surface-card text-text-secondary hover:border-surface-border/20 hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center rounded-[20px] border border-surface-border/8 bg-text-primary/[0.02] py-16">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
        </div>
      ) : active.length === 0 ? (
        <p className="rounded-[20px] border border-surface-border/8 bg-text-primary/[0.02] py-16 text-center text-[13px] text-text-muted">
          No ranked companies in this sector right now.
        </p>
      ) : (
        <>
          {view === "cards" ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {paged.map(c => <PickCard key={c.symbol} c={c} />)}
            </div>
          ) : (
            <RankingsTable companies={paged} startRank={(page - 1) * PAGE_SIZE} />
          )}

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-[12px] text-text-muted">
                Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, active.length)} of {active.length}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="flex h-8 w-8 items-center justify-center rounded-full border border-surface-border/10 text-text-secondary transition hover:border-violet-500/30 disabled:opacity-40 disabled:hover:border-surface-border/10"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-[12px] font-semibold text-text-primary">{page} / {totalPages}</span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="flex h-8 w-8 items-center justify-center rounded-full border border-surface-border/10 text-text-secondary transition hover:border-violet-500/30 disabled:opacity-40 disabled:hover:border-surface-border/10"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
