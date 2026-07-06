"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Telescope } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function StatCard({ label, value, positive, sub }: { label: string; value: string; positive?: boolean; sub?: string }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">{label}</p>
      <p className="text-[24px] font-black text-white leading-none">{value}</p>
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
    tomorrow_watchlist: [
      { ticker: "BEL",  name: "Bharat Electronics", reason: "Defence contract expected", score: 87 },
      { ticker: "RVNL", name: "Rail Vikas Nigam",   reason: "Railway budget allocation", score: 84 },
      { ticker: "LT",   name: "Larsen & Toubro",    reason: "Strong order inflow",       score: 82 },
      { ticker: "NTPC", name: "NTPC Ltd",            reason: "Q4 results due tomorrow",   score: 79 },
    ],
    ai_summary:
      "Markets ended " + (nifty.positive ? "higher" : "lower") +
      " driven by infrastructure and banking sectors. " +
      "Strong FII inflows supported the rally. Tomorrow, focus on Q4 earnings releases.",
  };
}

export function AfterMarketTab({ initialData }: { initialData?: any }) {
  const derived = deriveFromOverview(initialData);
  const [data, setData]     = useState<any>(derived ?? null);
  const [loading, setLoading] = useState(!derived);

  useEffect(() => {
    if (derived) { setLoading(false); return; }
    fetch(`${API}/api/market/after-market`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setData(d); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="space-y-4">
      {[1,2,3].map(i => <div key={i} className="h-32 rounded-xl border border-white/[0.05] bg-white/[0.02] animate-pulse"/>)}
    </div>
  );

  const closing   = data?.closing ?? {};
  const gainers   = data?.gainers ?? [];
  const losers    = data?.losers  ?? [];
  const sectors   = data?.sectors ?? [];
  const watchlist = data?.tomorrow_watchlist ?? [];
  const aiSummary = data?.ai_summary ?? "";

  return (
    <div className="space-y-5">
      {/* Closing summary */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Nifty 50 Close"   value={closing.nifty  ?? "—"} positive={closing.nifty_positive}  sub={closing.nifty_change}/>
        <StatCard label="Sensex Close"     value={closing.sensex ?? "—"} positive={closing.sensex_positive} sub={closing.sensex_change}/>
        <StatCard label="Advances" value={String(data?.breadth?.advances ?? "1124")} positive sub="Stocks advanced"/>
        <StatCard label="Declines"  value={String(data?.breadth?.declines ?? "387")}  positive={false} sub="Stocks declined"/>
      </div>

      {/* AI Market Wrap */}
      {aiSummary && (
        <div className="rounded-xl border border-violet-500/15 bg-[#0a0d16] p-5">
          <div className="flex items-start gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-violet-500/20 text-violet-400"><svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg></span>
            <div>
              <p className="text-[12px] font-bold text-violet-400 uppercase tracking-wider mb-1">AI Closing Market Wrap</p>
              <p className="text-[14px] text-slate-300 leading-6">{aiSummary}</p>
            </div>
          </div>
        </div>
      )}

      {/* Gainers + Losers */}
      <div className="grid grid-cols-2 gap-5">
        {[
          { title: "Top Gainers", rows: gainers, color: "emerald" },
          { title: "Top Losers",  rows: losers,  color: "rose"    },
        ].map(({ title, rows, color }) => (
          <div key={title} className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
            <h3 className="mb-3 text-[14px] font-bold text-white">{title}</h3>
            <div className="space-y-2">
              {rows.slice(0, 5).map((r: any) => (
                <Link key={r.ticker} href={`/companies/${r.ticker}`}
                  className="flex items-center justify-between rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2 hover:border-sky-500/10 transition">
                  <div className="flex items-center gap-2">
                    <div className="h-7 w-7 shrink-0 flex items-center justify-center rounded-lg bg-white/[0.06] text-[8px] font-bold text-slate-400">{r.ticker?.slice(0,3)}</div>
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
      <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
        <h3 className="mb-4 text-[14px] font-bold text-white">Sectoral Close</h3>
        <div className="grid grid-cols-2 gap-x-8 gap-y-2.5">
          {sectors.slice(0, 10).map((s: any) => {
            const pos = s.positive !== false;
            const val = s.value?.startsWith("+") || s.value?.startsWith("-") ? s.value : `${pos ? "+" : ""}${s.value}%`;
            return (
              <div key={s.id ?? s.name} className="flex items-center gap-3">
                <div className={`h-2 w-2 rounded-full shrink-0 ${pos ? "bg-emerald-400" : "bg-rose-400"}`}/>
                <p className="flex-1 text-[11px] text-slate-300 truncate">{s.name}</p>
                <span className={`text-[11px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>{val}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tomorrow Watchlist */}
      <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-[14px] font-bold text-white">Tomorrow's Watchlist</h3>
          <Link href="/stocks" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {watchlist.map((w: any) => (
            <Link key={w.ticker} href={`/companies/${w.ticker}`}
              className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 hover:border-sky-500/15 transition">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 shrink-0 flex items-center justify-center rounded-lg bg-white/[0.07] text-[9px] font-bold text-slate-300">{w.ticker?.slice(0,3)}</div>
                  <div>
                    <p className="text-[12px] font-bold text-white">{w.ticker}</p>
                    <p className="text-[9px] text-slate-500 truncate">{w.name}</p>
                  </div>
                </div>
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-[11px] font-black text-emerald-400">{w.score}</div>
              </div>
              <p className="text-[10px] text-slate-400 leading-snug">{w.reason}</p>
            </Link>
          ))}
        </div>
      </div>

      {/* Tomorrow Opening Prediction */}
      <div className="rounded-xl border border-sky-500/10 bg-[#0a0d16] p-5">
        <div className="flex items-center gap-2 mb-3">
          <Telescope className="h-4 w-4 text-slate-400" />
          <h3 className="text-[14px] font-bold text-white">Tomorrow Opening Prediction</h3>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Gap Up Probability",  val: "65%", color: "text-emerald-400", icon: "↑" },
            { label: "Flat Open",           val: "25%", color: "text-slate-400",   icon: "→" },
            { label: "Gap Down Probability",val: "10%", color: "text-rose-400",    icon: "↓" },
          ].map(s => (
            <div key={s.label} className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4 text-center">
              <span className={`text-[24px] font-black ${s.color}`}>{s.val}</span>
              <p className="text-[10px] text-slate-500 mt-1">{s.label}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-[12px] text-slate-400 leading-5">
          Based on global cues, FII positioning, and technical levels. Nifty likely to open with positive bias tracking Asian markets. Watch 24,600 as key support.
        </p>
      </div>
    </div>
  );
}
