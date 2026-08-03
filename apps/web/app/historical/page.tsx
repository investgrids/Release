import type { Metadata } from "next";
import Link from "next/link";
import { Clock, BookOpen } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

interface HistoricalListItem {
  id: string; event_title: string; event_date: string; category: string;
  sentiment: string | null; nifty_1w: number | null; nifty_1m: number | null;
}

async function fetchAll(): Promise<HistoricalListItem[]> {
  try {
    const res = await fetch(`${API}/api/historical/all?limit=200`, { next: { revalidate: 3600 } });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.events ?? []).map((e: HistoricalListItem) => ({ ...e, event_title: cleanText(e.event_title) }));
  } catch {
    return [];
  }
}

function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
}
function pctCls(v: number | null | undefined): string {
  if (v == null) return "text-text-muted";
  return v >= 0 ? "text-emerald-400" : "text-rose-400";
}
function normalizeCategory(c: string): string {
  return c.replace(/_/g, " ").trim().split(" ").map(w => w[0]?.toUpperCase() + w.slice(1)).join(" ");
}

export const metadata: Metadata = {
  title: "Historical Market Patterns — What Happened Before & What It Means | MarketRipple",
  description: "Real historical market data on Union Budgets, RBI rate cycles, market corrections and global shocks — how Nifty and key sectors actually reacted, with real winners and losers.",
  openGraph: {
    type: "website",
    title: "Historical Market Patterns — MarketRipple",
    description: "Real historical market data on how Indian markets reacted to past budgets, rate decisions, corrections and global shocks.",
    url: `${SITE}/historical`,
    siteName: "MarketRipple",
  },
  alternates: { canonical: `${SITE}/historical` },
};

export default async function HistoricalHubPage() {
  const events = await fetchAll();

  const groups = new Map<string, HistoricalListItem[]>();
  for (const e of events) {
    const key = normalizeCategory(e.category);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(e);
  }
  const sortedGroups = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);

  return (
    <main className="mx-auto max-w-[1100px] px-5 py-8 pb-16 sm:px-6">
      <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-text-muted">
        <BookOpen className="h-3.5 w-3.5" /> Historical Patterns
      </div>
      <h1 className="text-[28px] font-black leading-tight text-text-primary md:text-[34px]">
        What History Actually Shows
      </h1>
      <p className="mt-3 max-w-[680px] text-[14px] leading-relaxed text-text-secondary">
        {events.length} real, dated market events — Union Budgets, RBI rate decisions, corrections, and
        global shocks — with verified Nifty reactions and real historical winners/losers, not AI estimates.
      </p>

      {sortedGroups.length === 0 && (
        <p className="mt-10 text-[13px] text-text-muted">No historical data available right now.</p>
      )}

      {sortedGroups.map(([category, items]) => (
        <section key={category} className="mt-10">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-[13px] font-bold text-text-primary">{category}</h2>
            <span className="rounded-full bg-text-primary/[0.07] px-2 py-0.5 text-[10px] font-semibold text-text-muted">{items.length}</span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items
              .sort((a, b) => (b.event_date > a.event_date ? 1 : -1))
              .map(e => (
                <Link
                  key={e.id}
                  href={`/historical/${e.id}`}
                  className="rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-4 transition hover:border-sky-500/25 hover:bg-text-primary/[0.03]"
                >
                  <p className="flex items-center gap-1 text-[10px] text-text-muted"><Clock className="h-2.5 w-2.5" /> {e.event_date}</p>
                  <p className="mt-1.5 text-[13px] font-semibold leading-snug text-text-primary line-clamp-2">{e.event_title}</p>
                  <div className="mt-2.5 flex items-center gap-3 text-[11px]">
                    <span className="text-text-muted">Nifty 1W</span>
                    <span className={`font-bold tabular-nums ${pctCls(e.nifty_1w)}`}>{pct(e.nifty_1w)}</span>
                    <span className="text-text-muted">1M</span>
                    <span className={`font-bold tabular-nums ${pctCls(e.nifty_1m)}`}>{pct(e.nifty_1m)}</span>
                  </div>
                </Link>
              ))}
          </div>
        </section>
      ))}
    </main>
  );
}
