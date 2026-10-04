"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Zap, GitBranch, History, ArrowRight } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { InvestmentWatchPanel, type WatchResponse, type WatchSubject } from "@/components/ai/InvestmentWatchPanel";
import { distinctHeadlines } from "@/lib/intelligenceView";

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
export function CompanyIntelligenceSection({ symbol, govScore, pricePositive }: { symbol: string; govScore?: number | null; pricePositive?: boolean | null }) {
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
              <p className={SUB}>Its sector and the same-industry companies it is usually compared with.</p>
              <dl className="space-y-3 text-[12px]">
                {ripple.upstream.length > 0 && (
                  <div>
                    <dt className="mb-1 text-[10px] uppercase tracking-wider text-text-muted">Sector</dt>
                    <dd className="flex flex-wrap gap-1.5">
                      {ripple.upstream.map((u, i) => <span key={i} className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-2.5 py-1 text-text-secondary">{u}</span>)}
                    </dd>
                  </div>
                )}
                <div>
                  <dt className="mb-1 text-[10px] uppercase tracking-wider text-text-muted">This company</dt>
                  <dd><span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 font-bold text-violet-600 dark:text-violet-300">{ripple.company}</span></dd>
                </div>
                {ripple.downstream.length > 0 && (
                  <div>
                    <dt className="mb-1 text-[10px] uppercase tracking-wider text-text-muted">Peers</dt>
                    <dd className="flex flex-wrap gap-1.5">
                      {ripple.downstream.map((d, i) => (
                        <Link key={i} href={`/companies/${d}` as any} className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-2.5 py-1 text-text-secondary transition hover:border-violet-500/30 hover:text-violet-600 dark:hover:text-violet-300">{d}</Link>
                      ))}
                    </dd>
                  </div>
                )}
              </dl>
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
