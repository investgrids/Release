"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Telescope, Sparkles, CheckCircle2, XCircle } from "lucide-react";
import { compareScoresDesc, impactToStyle } from "@/lib/scoring";
import { API_BASE_URL as API } from "@/lib/api";
import { useMarketIntelligence } from "@/hooks/useMarketIntelligence";


function StatCard({ label, value, positive, sub }: { label: string; value: string; positive?: boolean; sub?: string }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="text-[24px] font-black leading-none text-white">{value}</p>
      {sub && <p className={`mt-1 text-[12px] font-semibold ${positive ? "text-emerald-400" : positive === false ? "text-rose-400" : "text-slate-400"}`}>{sub}</p>}
    </div>
  );
}

function deriveFromOverview(ov: any) {
  if (!ov) return null;
  const indices = ov.indices ?? [];
  const nifty   = indices.find((i: any) => i.name?.includes("NIFTY 50")) ?? {};
  const sensex  = indices.find((i: any) => i.name?.includes("SENSEX"))   ?? {};
  return {
    closing: {
      nifty:           nifty.value    ?? "—",
      sensex:          sensex.value   ?? "—",
      nifty_change:    nifty.change   ?? "—",
      sensex_change:   sensex.change  ?? "—",
      nifty_positive:  nifty.positive ?? true,
      sensex_positive: sensex.positive?? true,
    },
    sectors:  ov.sectors ?? [],
    gainers:  ov.movers?.gainers ?? [],
    losers:   ov.movers?.losers  ?? [],
    breadth:  ov.breadth,
  };
}

export function AfterMarketTab({ initialData }: { initialData?: any }) {
  const derived = deriveFromOverview(initialData);
  const [data, setData]       = useState<any>(derived ?? null);
  const [loading, setLoading] = useState(!derived);

  // Real market story from the shared MarketIntelligenceProvider — replaces
  // both a previously templated boilerplate summary and this component's
  // own fetch to /api/intelligence/market/story.
  const { state: mie } = useMarketIntelligence();
  const story = mie?.story ?? null;
  const [recentEvents, setEvents]   = useState<any[]>([]);
  const [openingPred, setOpeningPred] = useState<any>(null);
  const [predLoading, setPredLoading] = useState(true);

  useEffect(() => {
    if (derived) { setLoading(false); return; }
    fetch(`${API}/api/market/after-market`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setData(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetch(`${API}/api/events/?sort_by=impact_score&page_size=10`)
      .then(r => r.ok ? r.json() : null)
      .then(eventsRes => {
        const evs = eventsRes?.results ?? eventsRes ?? [];
        if (Array.isArray(evs)) setEvents(evs);
      })
      .catch(() => {});

    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), 90_000);
    fetch(`${API}/api/market/opening-prediction`, { signal: ac.signal })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setOpeningPred(d); })
      .catch(() => {})
      .finally(() => { clearTimeout(t); setPredLoading(false); });
    return () => { clearTimeout(t); ac.abort(); };
  }, []);

  if (loading) return (
    <div className="space-y-4">
      {[1,2,3].map(i => <div key={i} className="h-32 animate-pulse rounded-2xl border border-white/[0.05] bg-white/[0.02]"/>)}
    </div>
  );

  const closing   = data?.closing ?? {};
  const gainers   = data?.gainers ?? [];
  const losers    = data?.losers  ?? [];
  const sectors   = data?.sectors ?? [];
  const breadth   = data?.breadth;

  // "Tomorrow's Watchlist" — real event-linked companies (same honest pattern
  // as Live Market's Companies That Matter), not a hardcoded fallback list.
  const sortedEvents = [...recentEvents].sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score));
  const seen = new Set<string>();
  const watchlist: { ticker: string; name: string; reason: string; score: number | null }[] = [];
  outer:
  for (const e of sortedEvents) {
    for (const c of (e.companies ?? [])) {
      if (!c.symbol || seen.has(c.symbol)) continue;
      seen.add(c.symbol);
      watchlist.push({ ticker: c.symbol, name: c.name ?? c.symbol, reason: e.title, score: e.impact_score ?? null });
      if (watchlist.length >= 4) break outer;
    }
  }

  const pred = openingPred?.prediction;
  const dirUp = pred?.direction === "Positive";
  const dirDown = pred?.direction === "Negative";
  const predLabel = dirUp ? "Bullish" : dirDown ? "Bearish" : "Neutral";
  const predCls   = dirUp ? "text-emerald-400" : dirDown ? "text-rose-400" : "text-amber-400";

  return (
    <div className="space-y-5">
      {/* Closing summary */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Nifty 50 Close" value={closing.nifty  ?? "—"} positive={closing.nifty_positive}  sub={closing.nifty_change}/>
        <StatCard label="Sensex Close"   value={closing.sensex ?? "—"} positive={closing.sensex_positive} sub={closing.sensex_change}/>
        <StatCard label="Advances" value={breadth?.advances != null ? String(breadth.advances) : "—"} positive       sub="Stocks advanced"/>
        <StatCard label="Declines" value={breadth?.declines != null ? String(breadth.declines) : "—"} positive={false} sub="Stocks declined"/>
      </div>

      {/* AI Market Wrap — real story text, not templated boilerplate */}
      {story?.text && (
        <div className="rounded-2xl border border-violet-500/15 bg-[#080c14] p-5">
          <div className="flex items-start gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-violet-500/20 text-violet-400"><Sparkles className="h-4 w-4" /></span>
            <div className="min-w-0">
              <p className="mb-1 text-[12px] font-bold uppercase tracking-wider text-violet-400">AI Closing Market Wrap</p>
              <p className="text-[13px] leading-6 text-slate-300">{story.text}</p>
            </div>
          </div>
        </div>
      )}

      {/* Gainers + Losers */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        {[
          { title: "Top Gainers", rows: gainers, color: "emerald" },
          { title: "Top Losers",  rows: losers,  color: "rose"    },
        ].map(({ title, rows, color }) => (
          <div key={title} className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
            <h3 className="mb-3 text-[13px] font-bold text-white">{title}</h3>
            <div className="space-y-2">
              {rows.slice(0, 5).map((r: any) => (
                <Link key={r.ticker} href={`/companies/${r.ticker}`}
                  className="flex items-center justify-between rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2 hover:border-sky-500/10 transition">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-[8px] font-bold text-slate-400">{r.ticker?.slice(0,3)}</div>
                    <p className="text-[11px] font-semibold text-white">{r.ticker}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[11px] text-slate-400">{r.subtitle}</p>
                    <p className={`text-[11px] font-bold text-${color}-400`}>{r.value}</p>
                  </div>
                </Link>
              ))}
              {rows.length === 0 && <p className="py-4 text-center text-[11px] text-slate-600">No data available</p>}
            </div>
          </div>
        ))}
      </div>

      {/* Sector Winners + Losers */}
      <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
        <h3 className="mb-4 text-[13px] font-bold text-white">Sectoral Close</h3>
        {sectors.length === 0 ? (
          <p className="py-4 text-center text-[12px] text-slate-600">Sector data unavailable.</p>
        ) : (
          <div className="grid grid-cols-1 gap-x-8 gap-y-2.5 sm:grid-cols-2">
            {sectors.slice(0, 10).map((s: any) => {
              const pos = s.positive !== false;
              const val = s.value?.startsWith("+") || s.value?.startsWith("-") ? s.value : `${pos ? "+" : ""}${s.value}%`;
              return (
                <div key={s.id ?? s.name} className="flex items-center gap-3">
                  <div className={`h-2 w-2 shrink-0 rounded-full ${pos ? "bg-emerald-400" : "bg-rose-400"}`}/>
                  <p className="flex-1 truncate text-[11px] text-slate-300">{s.name}</p>
                  <span className={`text-[11px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>{val}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Tomorrow's Watchlist — real event-linked companies */}
      <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-[13px] font-bold text-white">Tomorrow's Watchlist</h3>
          <Link href="/companies" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
        </div>
        {watchlist.length === 0 ? (
          <p className="py-4 text-center text-[12px] text-slate-600">No scored events to derive a watchlist from yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {watchlist.map((w) => {
              const style = impactToStyle(w.score);
              return (
                <Link key={w.ticker} href={`/companies/${w.ticker}`}
                  className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 hover:border-sky-500/15 transition">
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.07] text-[9px] font-bold text-slate-300">{w.ticker.slice(0,3)}</div>
                      <div>
                        <p className="text-[12px] font-bold text-white">{w.ticker}</p>
                        <p className="truncate text-[9px] text-slate-500">{w.name}</p>
                      </div>
                    </div>
                    <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-black ${style.circle}`}>
                      {w.score != null ? Math.round(w.score) : "—"}
                    </div>
                  </div>
                  <p className="line-clamp-2 text-[10px] leading-snug text-slate-400">{w.reason}</p>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Tomorrow Opening Prediction — real 5-layer signal service */}
      <div className="rounded-2xl border border-sky-500/10 bg-[#080c14] p-5">
        <div className="mb-3 flex items-center gap-2">
          <Telescope className="h-4 w-4 text-slate-400" />
          <h3 className="text-[13px] font-bold text-white">Tomorrow Opening Prediction</h3>
        </div>
        {predLoading ? (
          <div className="space-y-2">{[1, 2].map(i => <div key={i} className="h-6 animate-pulse rounded bg-white/[0.03]" />)}</div>
        ) : !pred ? (
          <p className="py-4 text-center text-[12px] text-slate-600">Prediction unavailable.</p>
        ) : (
          <>
            <div className="flex items-baseline gap-3">
              <span className={`text-[30px] font-black leading-none ${predCls}`}>{pred.confidence}%</span>
              <span className={`text-[14px] font-bold ${predCls}`}>{predLabel}</span>
              {pred.ai_generated === false && <span className="text-[10px] text-slate-600">Signal-based estimate</span>}
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">Main Drivers</p>
                <div className="space-y-1">
                  {(pred.primary_drivers ?? []).slice(0, 3).map((d: string, i: number) => (
                    <div key={i} className="flex items-start gap-1.5">
                      <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
                      <span className="text-[11px] leading-snug text-slate-400">{d}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">Key Risks</p>
                <div className="space-y-1">
                  {(pred.risks ?? []).slice(0, 3).map((d: string, i: number) => (
                    <div key={i} className="flex items-start gap-1.5">
                      <XCircle className="mt-0.5 h-3 w-3 shrink-0 text-rose-400" />
                      <span className="text-[11px] leading-snug text-slate-400">{d}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            {pred.reasoning && <p className="mt-4 text-[12px] leading-5 text-slate-400">{pred.reasoning}</p>}
          </>
        )}
      </div>
    </div>
  );
}
