"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarClock, ChevronDown, Clock, Rocket, Search, ShieldCheck } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

// Everything on this page comes from NSE's public issue lists (see backend app/services/ipo_feed.py).
// NSE does not publish grey-market premium, analyst ratings, sector or financials, so none are shown here.

type Status = "Upcoming" | "Ongoing" | "Closed" | "Listed" | "Withdrawn";
interface IPO {
  id: string; name: string; symbol: string; type: "Mainboard" | "SME" | null; status: Status;
  priceMin: number | null; priceMax: number | null; issuePrice: number | null;
  lotSize: number | null; sharesOffered: number | null; issueValue: string | null;
  openDate: string | null; closeDate: string | null; listingDate: string | null;
  subscription: { total?: number; retail?: number; nii?: number; qib?: number } | null;
}
export interface IPOData {
  ipos: IPO[];
  stats: { upcoming: number; ongoing: number; closed: number; listed: number; mainboard: number; sme: number };
  as_of: string | null; data_source: string; stale?: boolean;
}

const STATUS_LABEL: Record<Status, string> = { Upcoming: "Opens soon", Ongoing: "Open now", Closed: "Awaiting listing", Listed: "Listed", Withdrawn: "Withdrawn" };
const STATUS_STYLE: Record<Status, string> = {
  Upcoming: "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/25",
  Ongoing:  "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/25",
  Closed:   "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/25",
  Listed:   "bg-violet-500/10 text-violet-700 dark:text-violet-300 border-violet-500/25",
  Withdrawn: "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/25",
};
const ORDER: Record<Status, number> = { Ongoing: 0, Upcoming: 1, Closed: 2, Listed: 3, Withdrawn: 4 };

const day = (iso: string | null) => (iso ? new Date(iso + "T00:00:00+05:30") : null);
const fmt = (iso: string | null, withYear = false) =>
  iso ? new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", ...(withYear ? { year: "numeric" } : {}), timeZone: "Asia/Kolkata" }).format(day(iso)!) : "—";
const rupee = (n: number | null) => (n == null ? "—" : `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`);
const band = (i: IPO) =>
  i.priceMin != null && i.priceMax != null ? (i.priceMin === i.priceMax ? rupee(i.priceMax) : `${rupee(i.priceMin)} – ${rupee(i.priceMax)}`) : "—";

function daysFromToday(iso: string | null): number | null {
  if (!iso) return null;
  const today = new Date(new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date()) + "T00:00:00+05:30");
  return Math.round((day(iso)!.getTime() - today.getTime()) / 86_400_000);
}
function when(i: IPO): string {
  if (i.status === "Upcoming") {
    const d = daysFromToday(i.openDate);
    return d === 0 ? "Opens today" : d === 1 ? "Opens tomorrow" : d != null && d > 1 ? `Opens in ${d} days` : `Opens ${fmt(i.openDate)}`;
  }
  if (i.status === "Ongoing") {
    const d = daysFromToday(i.closeDate);
    return d === 0 ? "Closes today" : d === 1 ? "Closes tomorrow" : `Closes ${fmt(i.closeDate)}`;
  }
  if (i.status === "Withdrawn") return "Issue withdrawn or postponed";
  if (i.status === "Closed") return i.listingDate ? `Lists ${fmt(i.listingDate)}` : (daysFromToday(i.closeDate) ?? 0) < -21 ? "No listing on record" : "Listing date awaited";
  return `Listed ${fmt(i.listingDate)}`;
}
const minInvest = (i: IPO) => (i.lotSize && i.priceMax ? i.lotSize * i.priceMax : null);

function Badge({ status }: { status: Status }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</span>;
}
function BoardTag({ type }: { type: IPO["type"] }) {
  if (!type) return null;   // NSE does not state the board for trade-for-trade (BE) listings, so none is shown
  return <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${type === "SME" ? "bg-amber-500/15 text-amber-700 dark:text-amber-300" : "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300"}`}>{type}</span>;
}
function Fact({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">{label}</dt>
      <dd className="mt-0.5 truncate text-[13px] font-semibold tabular-nums text-text-primary">{value}</dd>
      {hint && <p className="text-[10px] text-text-muted">{hint}</p>}
    </div>
  );
}

function BidProgress({ open, close }: { open: string | null; close: string | null }) {
  const total = Math.max(1, (daysFromToday(close) ?? 0) - (daysFromToday(open) ?? 0));
  const done = Math.min(total, Math.max(0, -(daysFromToday(open) ?? 0)));
  const pct = Math.round(((done + 1) / (total + 1)) * 100);
  return (
    <div className="mt-2.5" role="progressbar" aria-label="Bidding window progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
      <div className="h-1.5 overflow-hidden rounded-full bg-text-primary/10"><div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-sky-400 transition-all duration-700" style={{ width: `${pct}%` }} /></div>
      <p className="mt-1 text-[10px] text-text-muted">Bidding window {pct}% elapsed</p>
    </div>
  );
}

function Spotlight({ ipo }: { ipo: IPO }) {
  const min = minInvest(ipo);
  return (
    <article className="group relative overflow-hidden rounded-[22px] border border-surface-border/12 bg-gradient-to-br from-violet-500/[0.07] via-transparent to-sky-500/[0.07] p-5 transition hover:border-violet-500/30">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><BoardTag type={ipo.type} /><span className="text-[11px] font-semibold text-text-muted">{ipo.symbol}</span></div>
          <h3 className="mt-1.5 text-[17px] font-bold leading-snug tracking-tight text-text-primary">{ipo.name}</h3>
        </div>
        <Badge status={ipo.status} />
      </div>
      <p className="mt-3 flex items-center gap-1.5 text-[13px] font-semibold text-violet-700 dark:text-violet-300"><Clock className="h-3.5 w-3.5" />{when(ipo)}</p>
      {ipo.status === "Ongoing" && <BidProgress open={ipo.openDate} close={ipo.closeDate} />}
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Fact label="Price band" value={band(ipo)} />
        <Fact label="Bidding" value={`${fmt(ipo.openDate)} – ${fmt(ipo.closeDate)}`} />
        <Fact label="Lot size" value={ipo.lotSize ? `${ipo.lotSize.toLocaleString("en-IN")} shares` : "—"} />
        <Fact label="Min. investment" value={min ? rupee(min) : "—"} hint={min ? "1 lot at upper band" : undefined} />
      </dl>
      {ipo.subscription?.total != null && (
        <p className="mt-3 text-[12px] text-text-secondary">Subscribed <span className="font-bold tabular-nums text-text-primary">{ipo.subscription.total}×</span> so far</p>
      )}
    </article>
  );
}

function Row({ ipo }: { ipo: IPO }) {
  const [open, setOpen] = useState(false);
  const min = minInvest(ipo);
  return (
    <li className="border-b border-surface-border/8 last:border-0">
      <button onClick={() => setOpen(o => !o)} aria-expanded={open}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-3 px-4 py-3 text-left transition hover:bg-text-primary/[0.03] md:grid-cols-[minmax(0,2.2fr)_110px_minmax(0,1.3fr)_minmax(0,1.4fr)_minmax(0,1.2fr)_20px]">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><p className="truncate text-[13px] font-semibold text-text-primary">{ipo.name}</p><BoardTag type={ipo.type} /></div>
          <p className="mt-0.5 text-[11px] text-text-muted">{ipo.symbol}<span className="md:hidden"> · {when(ipo)}</span></p>
        </div>
        <div className="hidden md:block"><Badge status={ipo.status} /></div>
        <p className="hidden text-[12px] tabular-nums text-text-secondary md:block">{fmt(ipo.openDate)} – {fmt(ipo.closeDate)}</p>
        <p className="text-right text-[12.5px] font-semibold tabular-nums text-text-primary md:text-left">{ipo.status === "Listed" && ipo.issuePrice ? rupee(ipo.issuePrice) : band(ipo)}</p>
        <p className="hidden text-[12px] text-text-secondary md:block">{when(ipo)}</p>
        <ChevronDown className={`hidden h-4 w-4 text-text-muted transition md:block ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="grid gap-4 bg-text-primary/[0.025] px-4 pb-4 pt-3 sm:grid-cols-2 lg:grid-cols-4">
          <Fact label="Status" value={STATUS_LABEL[ipo.status]} />
          <Fact label="Bidding window" value={`${fmt(ipo.openDate, true)} – ${fmt(ipo.closeDate, true)}`} />
          <Fact label="Listing date" value={ipo.listingDate ? fmt(ipo.listingDate, true) : "Not announced yet"} />
          <Fact label="Price band" value={band(ipo)} />
          <Fact label="Final issue price" value={ipo.issuePrice ? rupee(ipo.issuePrice) : "—"} />
          <Fact label="Lot size" value={ipo.lotSize ? `${ipo.lotSize.toLocaleString("en-IN")} shares` : "—"} hint={min ? `Min. investment ${rupee(min)} at upper band` : undefined} />
          <Fact label="Shares on offer" value={ipo.sharesOffered ? ipo.sharesOffered.toLocaleString("en-IN") : "—"} />
          <Fact label="Issue value (est.)" value={ipo.issueValue ?? "—"} hint={ipo.issueValue ? "Shares × upper price band" : undefined} />
          {ipo.subscription && (
            <Fact label="Subscription" value={Object.entries(ipo.subscription).map(([k, v]) => `${k.toUpperCase()} ${v}×`).join(" · ")} />
          )}
        </div>
      )}
    </li>
  );
}

type Filter = "all" | Status;
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" }, { id: "Ongoing", label: "Open now" }, { id: "Upcoming", label: "Opens soon" },
  { id: "Closed", label: "Awaiting listing" }, { id: "Listed", label: "Listed" },
];

// Named export (not default) so it can carry a `headingLevel` prop — see best-stocks/page.tsx's BestStocksContent.
export function IPOHubContent({ headingLevel = "h1", initialData = null }: { headingLevel?: "h1" | "h2"; initialData?: IPOData | null }) {
  const Heading = headingLevel;
  const [data, setData] = useState<IPOData | null>(initialData);
  const [failed, setFailed] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [board, setBoard] = useState<"all" | "Mainboard" | "SME">("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"status" | "newest" | "price">("status");
  const [shown, setShown] = useState(15);

  useEffect(() => {
    if (initialData && initialData.data_source === "nse") return;   // the server already rendered real data (10-minute ISR)
    fetch(`${API}/api/ipo/`)
      .then(r => (r.ok ? r.json() : Promise.reject()))
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  const ipos = data?.ipos ?? [];
  const spotlight = useMemo(
    () => ipos.filter(i => i.status === "Ongoing" || i.status === "Upcoming")
      .sort((a, b) => ORDER[a.status] - ORDER[b.status] || (a.openDate ?? "").localeCompare(b.openDate ?? "")).slice(0, 4),
    [ipos]);
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return ipos
      .filter(i => (filter === "all" || i.status === filter) && (board === "all" || i.type === board)
        && (!needle || i.name.toLowerCase().includes(needle) || i.symbol.toLowerCase().includes(needle)))
      .sort((a, b) =>
        sort === "newest" ? (b.openDate ?? "").localeCompare(a.openDate ?? "")
        : sort === "price" ? (b.priceMax ?? 0) - (a.priceMax ?? 0)
        : ORDER[a.status] - ORDER[b.status]
          || (a.status === "Listed" || a.status === "Closed" ? (b.openDate ?? "").localeCompare(a.openDate ?? "") : (a.openDate ?? "").localeCompare(b.openDate ?? "")));
  }, [ipos, filter, board, q, sort]);

  useEffect(() => { setShown(15); }, [filter, board, q, sort]);

  const header = (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="mb-1 flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-[12px] border border-surface-border/10 bg-gradient-to-br from-violet-500/20 to-sky-500/20 text-violet-600 dark:text-violet-300"><Rocket className="h-5 w-5" /></div>
          <Heading className="text-3xl font-bold tracking-tight text-text-primary">IPO Hub</Heading>
        </div>
        <p className="text-[13px] text-text-secondary">Live IPO issues on NSE: dates, price bands and listings, straight from the exchange.</p>
      </div>
      {data && data.data_source === "nse" && (
        <p className="flex items-center gap-1.5 rounded-full border border-surface-border/12 px-3 py-1 text-[11px] text-text-muted">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
          Source: NSE{data.as_of ? ` · updated ${new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }).format(new Date(data.as_of))} IST` : ""}
          {data.stale && <span className="font-semibold text-amber-600"> · showing last known data</span>}
        </p>
      )}
    </div>
  );

  if (failed || data?.data_source === "unavailable") {
    return (
      <main className="min-w-0 space-y-5 pb-10">
        {header}
        <div className="flex flex-col items-center justify-center gap-3 rounded-[24px] border border-surface-border/10 bg-text-primary/[0.02] px-6 py-20 text-center">
          <CalendarClock className="h-9 w-9 text-text-muted" />
          <p className="text-base font-semibold text-text-primary">IPO data is temporarily unavailable</p>
          <p className="max-w-md text-sm text-text-secondary">We couldn&apos;t reach the exchange&apos;s IPO list just now. We only show exchange-published data, so nothing is shown instead of a guess. Please try again in a few minutes.</p>
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="min-w-0 space-y-5 pb-10" aria-busy="true">
        {header}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map(i => <div key={i} className="h-20 animate-pulse rounded-[18px] bg-text-primary/5" />)}</div>
        <div className="h-72 animate-pulse rounded-[24px] bg-text-primary/5" />
      </main>
    );
  }

  const s = data.stats;
  const KPIS: { label: string; value: number; sub: string; style: string }[] = [
    { label: "Open now", value: s.ongoing, sub: "bidding in progress", style: "text-emerald-600 dark:text-emerald-300" },
    { label: "Opens soon", value: s.upcoming, sub: "announced, not yet open", style: "text-sky-600 dark:text-sky-300" },
    { label: "Awaiting listing", value: s.closed, sub: "bidding closed", style: "text-amber-600 dark:text-amber-300" },
    { label: "Listed", value: s.listed, sub: "last 120 days", style: "text-violet-600 dark:text-violet-300" },
  ];

  return (
    <main className="min-w-0 space-y-6 pb-10">
      {header}

      <section aria-label="IPO summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {KPIS.map(k => (
          <div key={k.label} className="rounded-[18px] border border-surface-border/10 bg-text-primary/[0.02] px-4 py-3.5">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">{k.label}</p>
            <p className={`mt-1 text-3xl font-bold tabular-nums ${k.style}`}>{k.value}</p>
            <p className="text-[11px] text-text-muted">{k.sub}</p>
          </div>
        ))}
      </section>

      {spotlight.length > 0 ? (
        <section aria-label="Open and upcoming IPOs">
          <h2 className="mb-3 text-[15px] font-bold text-text-primary">Open and opening soon</h2>
          <div className="grid gap-4 lg:grid-cols-2">{spotlight.map(i => <Spotlight key={i.id} ipo={i} />)}</div>
        </section>
      ) : (
        <section className="rounded-[20px] border border-surface-border/10 bg-text-primary/[0.02] px-5 py-6 text-[13px] text-text-secondary">
          No IPO is open or announced on NSE at the moment. New issues appear here as soon as the exchange lists them.
        </section>
      )}

      <section aria-label="All IPOs" className="rounded-[24px] border border-surface-border/10 bg-text-primary/[0.02]">
        <div className="flex flex-wrap items-center gap-3 border-b border-surface-border/8 p-4">
          <div role="tablist" aria-label="Status" className="flex flex-wrap gap-1 rounded-[14px] bg-text-primary/[0.05] p-1">
            {FILTERS.map(f => (
              <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => setFilter(f.id)}
                className={`rounded-[10px] px-3 py-1.5 text-[12px] font-semibold transition ${filter === f.id ? "bg-surface-card text-text-primary shadow-sm" : "text-text-muted hover:text-text-primary"}`}>{f.label}</button>
            ))}
          </div>
          <div role="group" aria-label="Board" className="flex gap-1 rounded-[14px] bg-text-primary/[0.05] p-1">
            {(["all", "Mainboard", "SME"] as const).map(b => (
              <button key={b} aria-pressed={board === b} onClick={() => setBoard(b)}
                className={`rounded-[10px] px-3 py-1.5 text-[12px] font-semibold transition ${board === b ? "bg-surface-card text-text-primary shadow-sm" : "text-text-muted hover:text-text-primary"}`}>{b === "all" ? "All boards" : b}</button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-[11px] font-semibold text-text-muted">
            Sort
            <select value={sort} onChange={e => setSort(e.target.value as typeof sort)} aria-label="Sort IPOs"
              className="rounded-[10px] border border-surface-border/12 bg-transparent px-2 py-1.5 text-[12px] font-semibold text-text-primary outline-none focus:border-violet-500/40">
              <option value="status">Status</option><option value="newest">Newest first</option><option value="price">Highest price</option>
            </select>
          </label>
          <label className="relative ml-auto min-w-[200px] flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search company or symbol" aria-label="Search IPOs"
              className="w-full rounded-[12px] border border-surface-border/12 bg-transparent py-2 pl-9 pr-3 text-[12.5px] text-text-primary outline-none placeholder:text-text-muted focus:border-violet-500/40" />
          </label>
        </div>

        <div className="hidden grid-cols-[minmax(0,2.2fr)_110px_minmax(0,1.3fr)_minmax(0,1.4fr)_minmax(0,1.2fr)_20px] gap-3 border-b border-surface-border/8 px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted md:grid">
          <span>Company</span><span>Status</span><span>Bidding</span><span>Price (band / issue)</span><span>Timeline</span><span />
        </div>
        {rows.length === 0 ? (
          <p className="px-5 py-12 text-center text-[13px] text-text-muted">No IPOs match these filters.</p>
        ) : (
          <>
            <ul>{rows.slice(0, shown).map(i => <Row key={i.id} ipo={i} />)}</ul>
            <div className="flex items-center justify-between gap-3 border-t border-surface-border/8 px-4 py-3 text-[12px] text-text-muted">
              <span>Showing {Math.min(shown, rows.length)} of {rows.length}</span>
              {rows.length > shown && (
                <button onClick={() => setShown(n => n + 25)} className="rounded-[10px] border border-surface-border/15 px-3 py-1.5 font-semibold text-text-primary transition hover:border-violet-500/40 hover:bg-violet-500/5">Show 25 more</button>
              )}
            </div>
          </>
        )}
      </section>

      <p className="text-[11.5px] leading-relaxed text-text-muted">
        Dates, price bands, lot sizes and issue prices are as published by NSE. &ldquo;Min. investment&rdquo; and &ldquo;Issue value&rdquo; are simple calculations (lot size × upper band, shares × upper band).
        MarketRipple does not publish grey-market premiums or subscribe/avoid ratings. This is information, not investment advice.
      </p>
    </main>
  );
}
