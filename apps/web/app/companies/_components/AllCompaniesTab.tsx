import Link from "next/link";
import { WatchlistButton } from "@/components/WatchlistButton";
import { CompanySearchInput } from "../_components/SearchInput";
import { FilterSidebar } from "../_components/FilterSidebar";
import { filterAndRank, ALL_SECTORS } from "@/lib/companies-data";

// Extracted verbatim from the former app/companies/page.tsx (pre-hub-refactor)
// — same filterAndRank/live-quotes pipeline, just relocated so it can be one
// tab of the Companies hub instead of the entire route. Header/stats moved
// to the shared HubHero.

const BACKEND = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const PAGE_SIZE = 20;

const SECTOR_DOT: Record<string, string> = {
  Technology:      "bg-sky-400",
  Banking:         "bg-indigo-400",
  Finance:         "bg-cyan-400",
  Energy:          "bg-amber-400",
  Power:           "bg-yellow-400",
  Infrastructure:  "bg-orange-400",
  Defence:         "bg-rose-400",
  Pharmaceuticals: "bg-emerald-400",
  Healthcare:      "bg-green-400",
  FMCG:            "bg-lime-400",
  Consumer:        "bg-teal-400",
  Automotive:      "bg-blue-400",
  Metals:          "bg-slate-400",
  Chemicals:       "bg-purple-400",
  Cement:          "bg-stone-400",
  "Real Estate":   "bg-pink-400",
  Telecom:         "bg-violet-400",
};

const AVATAR_COLORS = [
  "bg-blue-700",   "bg-violet-700", "bg-emerald-700", "bg-amber-700",
  "bg-rose-700",   "bg-sky-700",    "bg-indigo-700",  "bg-teal-700",
  "bg-orange-700", "bg-pink-700",   "bg-cyan-700",    "bg-green-700",
];

function avatarColor(symbol: string) {
  const idx = [...symbol].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_COLORS.length;
  return AVATAR_COLORS[idx];
}

function Sparkline({ positive }: { positive?: boolean }) {
  if (positive === undefined || positive === null) {
    return <div className="h-6 w-[72px]" />;
  }
  const pts = positive
    ? "2,18 15,14 28,15 41,10 54,12 67,8 80,9 93,5 106,3"
    : "2,3 15,5 28,4 41,9 54,6 67,12 80,10 93,15 106,19";
  const color = positive ? "#10b981" : "#f43f5e";
  return (
    <svg width="72" height="24" viewBox="0 0 108 22">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function capBadge(cap: string) {
  if (cap === "large") return { label: "Large Cap", cls: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" };
  if (cap === "mid")   return { label: "Mid Cap",   cls: "text-amber-400 bg-amber-500/10 border-amber-500/20" };
  if (cap === "small") return { label: "Small Cap", cls: "text-sky-400 bg-sky-500/10 border-sky-500/20" };
  return { label: "—", cls: "text-text-muted" };
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

function pageHref(base: URLSearchParams, p: number) {
  const sp = new URLSearchParams(base);
  sp.set("page", String(p));
  sp.set("tab", "all-companies");
  return `/companies?${sp.toString()}`;
}

export async function AllCompaniesTab({
  q, sector, cap, sort, page,
}: { q: string; sector: string; cap: string; sort: string; page: number }) {
  const filtered    = filterAndRank(q, sector, cap, sort);
  const total       = filtered.length;
  const totalPages  = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const safePage    = Math.min(page, totalPages);
  const pageItems   = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  type Quote = { symbol: string; price_str: string; change_percent: number; positive: boolean };
  let priceMap: Record<string, Quote> = {};
  if (pageItems.length > 0) {
    try {
      const symbols = pageItems.map(c => c.symbol).join(",");
      const res = await fetch(`${BACKEND}/api/data/quotes?symbols=${encodeURIComponent(symbols)}`, {
        cache: "no-store", signal: AbortSignal.timeout(8000),
      });
      if (res.ok) {
        const data = await res.json();
        const quotes: Quote[] = data.quotes ?? [];
        priceMap = Object.fromEntries(quotes.map(q => [q.symbol, q]));
      }
    } catch { /* price fetch failed — show placeholders; data still loads */ }
  }

  const companies = pageItems.map(co => ({
    ...co,
    price:    priceMap[co.symbol]?.price_str     ?? null,
    pct:      priceMap[co.symbol]?.change_percent ?? null,
    positive: priceMap[co.symbol]?.positive       ?? null,
  }));

  const baseParams = new URLSearchParams();
  if (q)                       baseParams.set("q", q);
  if (sector)                  baseParams.set("sector", sector);
  if (cap)                     baseParams.set("cap", cap);
  if (sort && sort !== "name") baseParams.set("sort", sort);

  const from     = total > 0 ? (safePage - 1) * PAGE_SIZE + 1 : 0;
  const to       = Math.min(safePage * PAGE_SIZE, total);
  const pageList = buildPageList(safePage, totalPages);
  const colGrid = "grid-cols-[3fr_1fr_1.5fr_1.2fr_1.2fr_1fr_80px_44px]";

  return (
    <div className="flex items-start gap-5">
      <FilterSidebar sectors={ALL_SECTORS} initialSector={sector} initialCap={cap} initialSort={sort} initialQ={q} />

      <div className="min-w-0 flex-1 space-y-3">
        <CompanySearchInput defaultValue={q} sector={sector} cap={cap} sort={sort} />

        <div className="overflow-hidden rounded-xl border border-surface-border/6 bg-surface-card">
          <div className={`grid ${colGrid} border-b border-surface-border/6 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted`}>
            <span>Company</span><span>Ticker</span><span>Sector</span><span>Market Cap</span>
            <span>Price</span><span>Change %</span><span>1D Chart</span><span />
          </div>

          {companies.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <p className="text-[14px] text-text-muted">No companies found</p>
              <p className="mt-1 text-[12px] text-text-muted">Try adjusting your search or filters</p>
              <Link href="/companies?tab=all-companies" className="mt-3 text-[12px] text-sky-400 transition hover:text-sky-600 dark:text-sky-300">
                Clear all filters
              </Link>
            </div>
          ) : (
            <div>
              {companies.map((co, i) => {
                const pct       = co.pct as number | null;
                const positive  = co.positive as boolean | null;
                const pctStr    = pct != null ? `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%` : "—";
                const dotColor  = SECTOR_DOT[co.sector] ?? "bg-slate-400";
                const cap_badge = capBadge(co.cap);
                return (
                  <Link
                    key={co.symbol}
                    href={`/companies/${co.symbol}`}
                    className={`grid ${colGrid} items-center border-b border-surface-border/4 px-4 py-3 transition last:border-0 hover:bg-text-primary/[0.025] ${i % 2 !== 0 ? "bg-text-primary/[0.01]" : ""}`}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[9px] font-bold uppercase text-text-primary ${avatarColor(co.symbol)}`}>
                        {co.symbol.slice(0, 2)}
                      </div>
                      <span className="truncate text-[12px] font-semibold text-text-primary">{co.name}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-[11px] font-bold text-text-secondary">{co.symbol}</span>
                      <span className="rounded border border-indigo-500/20 bg-indigo-500/10 px-1 py-0.5 text-[8px] font-bold text-indigo-400">NSE</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div className={`h-2 w-2 shrink-0 rounded-full ${dotColor}`} />
                      <span className="truncate text-[11px] text-text-secondary">{co.sector}</span>
                    </div>
                    <span className={`rounded border px-2 py-0.5 text-[10px] font-semibold w-fit ${cap_badge.cls}`}>{cap_badge.label}</span>
                    <span className="font-mono text-[12px] font-semibold tabular-nums text-text-primary">{co.price ? `₹${co.price}` : "—"}</span>
                    <span className={`text-[12px] font-bold tabular-nums ${positive === true ? "text-emerald-400" : positive === false ? "text-rose-400" : "text-text-muted"}`}>{pctStr}</span>
                    <div className="flex items-center"><Sparkline positive={positive ?? undefined} /></div>
                    <div className="flex justify-center">
                      <WatchlistButton item={{ id: co.symbol, type: "company", label: co.name, ticker: co.symbol }} size="sm" />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {(totalPages > 1 || total > 0) && (
          <div className="flex flex-wrap items-center justify-between gap-3 py-1">
            <span className="text-[12px] text-text-muted">
              {total > 0 ? `Showing ${from.toLocaleString()} to ${to.toLocaleString()} of ${total.toLocaleString()} companies` : "No companies found"}
            </span>
            {totalPages > 1 && (
              <div className="flex items-center gap-1">
                {safePage > 1 && (
                  <Link href={pageHref(baseParams, safePage - 1)} className="flex h-7 w-7 items-center justify-center rounded-lg border border-surface-border/7 bg-surface-card text-[13px] text-text-muted transition hover:border-indigo-500/30 hover:text-text-primary">‹</Link>
                )}
                {pageList.map((p, i) => p === "…" ? (
                  <span key={`e${i}`} className="px-1 text-[12px] text-text-muted">…</span>
                ) : (
                  <Link
                    key={p}
                    href={pageHref(baseParams, p as number)}
                    className={`flex h-7 w-7 items-center justify-center rounded-lg text-[12px] transition ${p === safePage ? "bg-indigo-600 font-bold text-text-primary" : "border border-surface-border/7 bg-surface-card text-text-secondary hover:border-indigo-500/30 hover:text-text-primary"}`}
                  >
                    {p}
                  </Link>
                ))}
                {safePage < totalPages && (
                  <Link href={pageHref(baseParams, safePage + 1)} className="flex h-7 w-7 items-center justify-center rounded-lg border border-surface-border/7 bg-surface-card text-[13px] text-text-muted transition hover:border-indigo-500/30 hover:text-text-primary">›</Link>
                )}
              </div>
            )}
            <span className="text-[12px] text-text-muted">Rows per page: 20</span>
          </div>
        )}
      </div>
    </div>
  );
}
