"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Zap, GitBranch, History, ArrowRight } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { InvestmentWatchPanel, type WatchResponse, type WatchSubject } from "@/components/ai/InvestmentWatchPanel";
import { distinctHeadlines } from "@/lib/intelligenceView";
import { peerSentences } from "@/lib/peerCompare";

interface ActiveEvent { id: string; slug?: string; headline: string; urgency: number; sentiment: string; lifecycle: string; active_score: number; direct: boolean; }
interface RipplePosition { upstream: string[]; company: string; downstream: string[]; }
interface Historical { event_title: string; similarity: number; key_lesson: string | null; winners: string[]; losers: string[]; }
interface CompanyIntel {
  available: boolean;
  symbol?: string;
  name?: string;
  active_events?: ActiveEvent[];
  ripple_position?: RipplePosition;
  historical?: Historical | null;
  investment_watch?: WatchResponse | null;
}

const LIFECYCLE_DOT: Record<string, string> = {
  LIVE: "bg-rose-400", Developing: "bg-amber-400", Active: "bg-sky-400", Historical: "bg-slate-500",
};
const LIFECYCLE_LABEL: Record<string, string> = { LIVE: "Live", Developing: "Developing", Active: "Active", Historical: "Past" };

export interface SelfFigures { name?: string; price?: string; pct_change?: number; market_cap?: string; pe?: string; roe?: string }
interface PeerRow { symbol: string; name?: string; price?: string; pct_change?: number; pe?: string; roe?: string }

function PeerTable({ symbol, self, sector, peers }: { symbol: string; self?: SelfFigures; sector: string[]; peers: string[] }) {
  const [rows, setRows] = useState<Record<string, PeerRow | null> | null>(null);
  useEffect(() => {
    let cancelled = false;
    setRows(null);
    Promise.all(peers.slice(0, 4).map(p => fetch(`${API}/api/stocks/${p}`).then(r => (r.ok ? r.json() : null)).catch(() => null)))
      .then(res => { if (!cancelled) setRows(Object.fromEntries(peers.slice(0, 4).map((p, i) => [p, res[i]]))); });
    return () => { cancelled = true; };
  }, [symbol, peers.join(",")]);

  const loading = rows === null;
  const peerRows: PeerRow[] = peers.slice(0, 4).map(p => ({ symbol: p, ...(rows?.[p] ?? {}) }));
  const sentences = rows ? peerSentences({ symbol, pe: self?.pe, roe: self?.roe }, peerRows) : [];
  const pct = (v?: number) => (typeof v === "number" && Number.isFinite(v) ? <span className={v >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}>{v >= 0 ? "+" : ""}{v.toFixed(2)}%</span> : "—");
  const cell = "py-2.5 text-right tabular-nums";
  const Skel = () => <span className="ml-auto block h-3 w-10 animate-pulse rounded bg-text-primary/[0.06]" />;
  return (
    <div>
      {sector.length > 0 && <p className="mb-2 text-[11.5px] text-text-muted">Sector: <span className="font-medium text-text-secondary">{sector.join(" · ")}</span></p>}
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-surface-border/10 text-[10px] uppercase tracking-wider text-text-muted">
              <th className="pb-2 text-left font-medium">Company</th><th className="pb-2 text-right font-medium">Price</th><th className="pb-2 text-right font-medium">Today</th>
              <th className="pb-2 text-right font-medium">P/E</th><th className="pb-2 text-right font-medium">ROE</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/5">
            <tr className="bg-violet-500/[0.05]">
              <td className="py-2.5 pl-2"><span className="font-bold text-violet-700 dark:text-violet-300">{symbol}</span> <span className="ml-1 rounded-full bg-violet-500/15 px-1.5 py-0.5 text-[9px] font-bold text-violet-700 dark:text-violet-300">This company</span></td>
              <td className={`${cell} font-semibold text-text-primary`}>{self?.price ? `₹${self.price}` : "—"}</td>
              <td className={cell}>{pct(self?.pct_change)}</td>
              <td className={`${cell} font-semibold text-text-primary`}>{self?.pe || "—"}</td>
              <td className={`${cell} font-semibold text-text-primary`}>{self?.roe || "—"}</td>
            </tr>
            {peerRows.map(r => (
              <tr key={r.symbol}>
                <td className="py-2.5 pl-2"><Link href={`/companies/${r.symbol}` as any} className="font-semibold text-text-primary transition hover:text-violet-600 dark:hover:text-violet-300">{r.symbol}</Link>{r.name ? <span className="ml-2 hidden text-[10.5px] text-text-muted xl:inline">{r.name.length > 22 ? r.name.slice(0, 21) + "…" : r.name}</span> : null}</td>
                <td className={`${cell} text-text-secondary`}>{loading ? <Skel /> : r.price ? `₹${r.price}` : "—"}</td>
                <td className={cell}>{loading ? <Skel /> : pct(r.pct_change)}</td>
                <td className={`${cell} text-text-secondary`}>{loading ? <Skel /> : r.pe || "—"}</td>
                <td className={`${cell} text-text-secondary`}>{loading ? <Skel /> : r.roe || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sentences.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-surface-border/10 pt-3 text-[11.5px] leading-5 text-text-secondary">
          {sentences.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      )}
    </div>
  );
}

const CARD = "rounded-[20px] border border-surface-border/7 bg-text-primary/[0.02] p-5";
const HEAD = "mb-1 flex items-center gap-1.5 text-[13px] font-semibold text-text-primary";
const SUB = "mb-3 text-[11.5px] leading-5 text-text-muted";

function IntelSkeleton() {
  return (
    <div className="space-y-5 animate-pulse" aria-busy="true" aria-label="Loading intelligence">
      <div className="h-[170px] rounded-[20px] bg-text-primary/[0.04]" />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="h-[190px] rounded-[20px] bg-text-primary/[0.04]" />
        <div className="h-[190px] rounded-[20px] bg-text-primary/[0.04]" />
      </div>
    </div>
  );
}

/**
 * Company Intelligence — one consolidated read of where the company stands, built from the single /api/company-intelligence response (it already carries
 * the Investment Watch verdict, so no second request is made). Previously this stacked a "Why it matters" verdict card, a separate Investment Watch panel
 * (a second fetch of the same verdict), the same event headlines twice, and related opportunities that the Related Intelligence block below repeats.
 * Now: the verdict card, what is affecting the company, where it sits in its sector, and a similar past situation.
 */
export function CompanyIntelligenceSection({ symbol, govScore, pricePositive, self }: { symbol: string; govScore?: number | null; pricePositive?: boolean | null; self?: SelfFigures }) {
  const [data, setData] = useState<CompanyIntel | null>(null);

  // `cancelled` stops a stale in-flight request for a previously viewed company from overwriting the current company's data.
  useEffect(() => {
    let cancelled = false;
    setData(null);
    const params = new URLSearchParams();
    if (govScore != null) params.set("gov_score", String(govScore));
    if (pricePositive != null) params.set("price_positive", String(pricePositive));
    fetch(`${API}/api/company-intelligence/${symbol}?${params.toString()}`)
      .then(r => r.json())
      .then(d => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData({ available: false }); });
    return () => { cancelled = true; };
  }, [symbol, govScore, pricePositive]);

  if (data === null) return <IntelSkeleton />;
  if (!data.available) return null;

  const events = distinctHeadlines(data.active_events);
  const ripple = data.ripple_position;
  const hasChain = !!ripple && (ripple.upstream.length > 0 || ripple.downstream.length > 0);
  const name = data.name ?? symbol;

  return (
    <div className="space-y-5">
      {/* Where it stands: verdict, confidence, last change, what is being watched. */}
      <InvestmentWatchPanel
        subject={{ subject_key: `company:${symbol}`, subject_type: "company", subject_label: symbol } as WatchSubject}
        initialData={data.investment_watch ?? null}
      />

      {(events.length > 0 || hasChain) && (
        <div className={`grid grid-cols-1 gap-5 ${events.length > 0 && hasChain ? "lg:grid-cols-2" : ""}`}>
          {events.length > 0 && (
            <div className={CARD}>
              <p className={HEAD}><Zap className="h-3.5 w-3.5 text-amber-400" /> What is affecting {symbol} right now</p>
              <p className={SUB}>Recent market events linked to {name} or its sector, most urgent first.</p>
              <div className="space-y-2">
                {events.map(e => (
                  <Link key={e.id} href={`/events/${e.slug || e.id}` as any}
                    className="group flex items-start gap-2.5 rounded-xl border border-surface-border/5 bg-text-primary/[0.02] p-3 transition hover:border-surface-border/[0.12]">
                    <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${LIFECYCLE_DOT[e.lifecycle] ?? "bg-slate-500"}`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[12.5px] leading-snug text-text-secondary group-hover:text-text-primary transition">{e.headline}</p>
                      <p className="mt-1 text-[10.5px] text-text-muted">
                        {LIFECYCLE_LABEL[e.lifecycle] ?? e.lifecycle} · {e.direct ? `Mentions ${symbol}` : "Sector-wide"}
                      </p>
                    </div>
                    <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-text-muted opacity-0 group-hover:opacity-100 transition" />
                  </Link>
                ))}
              </div>
            </div>
          )}

          {hasChain && ripple && (
            <div className={CARD}>
              <p className={HEAD}><GitBranch className="h-3.5 w-3.5 text-sky-400" /> Where {symbol} sits</p>
              <p className={SUB}>How {name} compares with the same-industry companies it is usually measured against.</p>
              <PeerTable symbol={symbol} self={self} sector={ripple.upstream} peers={ripple.downstream} />
            </div>
          )}
        </div>
      )}

      {data.historical && (
        <div className="rounded-[20px] border border-amber-500/15 bg-amber-500/[0.04] p-5">
          <p className="mb-2 flex items-center gap-1.5 text-[13px] font-semibold text-amber-700 dark:text-amber-300">
            <History className="h-3.5 w-3.5" /> A similar past situation
          </p>
          <div className="flex items-center justify-between gap-3">
            <p className="text-[13px] font-semibold text-text-primary">{data.historical.event_title}</p>
            <span className="shrink-0 rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-0.5 text-[11px] font-bold text-amber-700 dark:text-amber-300">
              {Math.round(data.historical.similarity)}% similar
            </span>
          </div>
          {data.historical.key_lesson && <p className="mt-1.5 text-[12px] leading-5 text-text-secondary">{data.historical.key_lesson}</p>}
          {(data.historical.winners.length > 0 || data.historical.losers.length > 0) && (
            <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
              {data.historical.winners.map((w, i) => <span key={`w${i}`} className="text-emerald-500">▲ {w} did well</span>)}
              {data.historical.losers.map((l, i) => <span key={`l${i}`} className="text-rose-500">▼ {l} struggled</span>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
