import Link from "next/link";
import type { AllCompanyRankingRow, AllCompanyRankingsPage } from "@/lib/companyRankings";
import { marketRippleRatingColor, marketRippleScoreDisplayInt } from "@/lib/scoring";

// Full-directory paginated Company Rankings (owner instruction,
// 2026-09-27, "Company Rankings and UI"): every real company from the
// same directory list_companies() itself reads, one row each, sorted by
// name. Only `status === "ranked"` ever shows a real score/rating/rank —
// everything else is an explicit, honest "N/A" with its own real reason,
// never a fabricated number and never a rank. A company's rank (when
// present) is always scoped to its own real sector peer group, never a
// cross-sector position.

const STATUS_LABEL: Record<string, string> = {
  not_processed: "Not processed yet",
  needs_refresh: "Score needs refresh",
  insufficient_data: "Insufficient data",
  unsupported: "Not supported yet",
  peer_group_review: "Peer group under review",
  score_hold: "Score on hold",
  no_peer_group: "No matching peer group",
  partial_coverage: "Building evidence",
  no_snapshot_computed_yet: "Not yet computed",
  publication_locked: "Publication pending",
  ineligible: "Insufficient data",
  stale: "Needs refresh",
  unsupported_sector: "Sector not yet supported",
  not_yet_scored: "Not yet scored",
};

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

function buildPageList(page: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | "…")[] = [1];
  if (page > 3) pages.push("…");
  for (let p = Math.max(2, page - 1); p <= Math.min(total - 1, page + 1); p++) pages.push(p);
  if (page < total - 2) pages.push("…");
  pages.push(total);
  return pages;
}

function pageHref(p: number) {
  return `/company-rankings?page=${p}`;
}

// LOCAL-DEV-ONLY (2026-09-27) — row.localPreview is a real score/rating/
// rank regardless of `publishable`; the backend already returns it as
// null in real production (settings.is_production strip), so this
// NODE_ENV check is a second, independent guard, not the only one —
// either alone already prevents this from ever showing to a real user.
const isDev = process.env.NODE_ENV === "development";

function RankingCell({ row }: { row: AllCompanyRankingRow }) {
  if (row.status === "ranked" && row.score != null) {
    return (
      <>
        <span className={`font-black tabular-nums ${marketRippleRatingColor(row.rating)}`}>{marketRippleScoreDisplayInt(row.score)}</span>
        {row.rating && (
          <p className={`text-[10.5px] font-semibold ${marketRippleRatingColor(row.rating)}`}>{row.rating}</p>
        )}
      </>
    );
  }
  if (isDev && row.localPreview) {
    return (
      <>
        <span className="inline-flex items-center gap-1">
          <span className={`font-black tabular-nums ${marketRippleRatingColor(row.localPreview.rating)}`}>{marketRippleScoreDisplayInt(row.localPreview.score)}</span>
          <span className="rounded border border-amber-500/30 bg-amber-500/10 px-1 py-0.5 text-[7px] font-bold uppercase tracking-wide text-amber-500" title="Local unpublished preview — never shown in production">
            preview
          </span>
        </span>
        {row.localPreview.rating && (
          <p className={`text-[10.5px] font-semibold ${marketRippleRatingColor(row.localPreview.rating)}`}>{row.localPreview.rating}</p>
        )}
      </>
    );
  }
  return <span className="text-[12px] font-semibold text-text-muted">N/A</span>;
}

function RankBadgeCell({ row }: { row: AllCompanyRankingRow }) {
  if (row.status === "ranked" && row.rank != null) {
    return (
      <span className="inline-flex items-center rounded-full border border-surface-border/10 bg-text-primary/[0.04] px-2 py-0.5 text-[11px] font-bold tabular-nums text-text-secondary">
        #{row.rank}{row.totalRankedInSector ? ` of ${row.totalRankedInSector}` : ""}{row.peerGroup ? ` · ${row.peerGroup}` : ""}
      </span>
    );
  }
  if (isDev && row.localPreview) {
    return (
      <span className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-bold tabular-nums text-amber-500">
        #{row.localPreview.rank} of {row.localPreview.totalRankedInSector}
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center rounded-full border border-surface-border/10 px-2 py-0.5 text-[10.5px] font-semibold text-text-muted"
      title={row.message ?? undefined}
    >
      {STATUS_LABEL[row.status] ?? "Not ranked"}
    </span>
  );
}

export function AllCompaniesRankingsView({ data }: { data: AllCompanyRankingsPage }) {
  const { companies, page, totalPages, total, pageSize } = data;
  const from = total > 0 ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(page * pageSize, total);
  const pageList = buildPageList(page, totalPages);

  return (
    <div>
      <p className="mb-3 text-[12px] leading-5 text-text-muted" data-testid="rankings-peer-note">
        Each score is ranked against the companies in its own sector, so it can change when companies are added to that sector.
        A company without a score shows why.{" "}
        <Link href="/methodology/marketripple-score#peer-groups-heading" className="text-sky-400 hover:text-sky-600 dark:text-sky-300">How scores work</Link>
      </p>
      <div className="mb-4">
        <h2 className="text-[18px] font-black text-text-primary">Every Company — MarketRipple Score</h2>
        <p className="mt-0.5 text-[12.5px] text-text-secondary">
          One shared MarketRipple Score formula, ranked within each company&apos;s own real sector peer group — a
          Banking score is never compared to a Technology score. A company shown as N/A simply hasn&apos;t cleared
          the real evidence bar yet, or its sector doesn&apos;t have an approved methodology — never a fabricated
          number, never a fake rank.
        </p>
      </div>

      {companies.length === 0 ? (
        <div className="rounded-[20px] border border-surface-border/8 bg-text-primary/[0.02] py-16 text-center">
          <p className="text-[14px] font-semibold text-text-primary">No companies found.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-[20px] border border-surface-border/8 bg-surface-card">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr className="border-b border-surface-border/8 text-[10.5px] uppercase tracking-wide text-text-muted">
                <th className="px-4 py-3 font-semibold">Company</th>
                <th className="px-4 py-3 font-semibold">Sector</th>
                <th className="px-4 py-3 font-semibold text-right">Score</th>
                <th className="px-4 py-3 font-semibold text-right">Rank</th>
                <th className="px-4 py-3 font-semibold text-right">Updated</th>
              </tr>
            </thead>
            <tbody>
              {companies.map(row => (
                <tr key={row.symbol} className="border-b border-surface-border/5 text-[13px] transition hover:bg-text-primary/[0.02] last:border-0">
                  <td className="px-4 py-3">
                    <Link href={`/companies/${row.symbol}`} className="group">
                      <p className="font-semibold text-text-primary group-hover:text-violet-600 dark:group-hover:text-violet-300">{row.companyName}</p>
                      <p className="text-[11px] text-text-muted">{row.symbol}</p>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[12px] text-text-secondary">{row.sector}</td>
                  <td className="px-4 py-3 text-right"><RankingCell row={row} /></td>
                  <td className="px-4 py-3 text-right"><RankBadgeCell row={row} /></td>
                  <td className="px-4 py-3 text-right text-[11px] text-text-muted">{relativeTime(row.calculatedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(totalPages > 1 || total > 0) && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <span className="text-[12px] text-text-muted">
            {total > 0 ? `Showing ${from.toLocaleString()} to ${to.toLocaleString()} of ${total.toLocaleString()} companies` : "No companies found"}
          </span>
          {totalPages > 1 && (
            <div className="flex flex-wrap items-center gap-1">
              {page > 1 && (
                <Link href={pageHref(page - 1)} className="flex h-7 w-7 items-center justify-center rounded-lg border border-surface-border/7 bg-surface-card text-[13px] text-text-muted transition hover:border-indigo-500/30 hover:text-text-primary">‹</Link>
              )}
              {pageList.map((p, i) => p === "…" ? (
                <span key={`e${i}`} className="px-1 text-[12px] text-text-muted">…</span>
              ) : (
                <Link
                  key={p}
                  href={pageHref(p as number)}
                  className={`flex h-7 w-7 items-center justify-center rounded-lg text-[12px] transition ${p === page ? "bg-indigo-600 font-bold text-text-primary" : "border border-surface-border/7 bg-surface-card text-text-secondary hover:border-indigo-500/30 hover:text-text-primary"}`}
                >
                  {p}
                </Link>
              )) }
              {page < totalPages && (
                <Link href={pageHref(page + 1)} className="flex h-7 w-7 items-center justify-center rounded-lg border border-surface-border/7 bg-surface-card text-[13px] text-text-muted transition hover:border-indigo-500/30 hover:text-text-primary">›</Link>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
