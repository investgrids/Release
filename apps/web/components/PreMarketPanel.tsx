"use client";

import Link from "next/link";

// Real mini-chart from actual backend data
function MiniChart({ chart, positive }: { chart?: { value: number }[]; positive: boolean }) {
  if (!chart || chart.length < 3) {
    return <div className={`h-5 w-12 shrink-0 rounded ${positive ? "bg-emerald-500/10" : "bg-rose-500/10"}`} />;
  }
  const vals = chart.map(p => p.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const pts = vals
    .map((v, i) => `${(i / (vals.length - 1)) * 60},${36 - ((v - min) / range) * 32}`)
    .join(" ");
  const color = positive ? "#22c55e" : "#f43f5e";
  return (
    <svg viewBox="0 0 60 36" className="h-9 w-12 shrink-0" fill="none">
      <polyline points={pts} stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Hero pre-market card (Gift Nifty / India VIX / US Futures / Commodity)
function PreMarketCard({ q, idx }: { q: any; idx: number }) {
  return (
    <div className="flex flex-col justify-between rounded-2xl border border-white/[0.07] bg-white/[0.03] p-3.5">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[11px] font-semibold text-slate-300 leading-tight">{q.name}</p>
        <MiniChart chart={q.chart} positive={q.positive !== false} />
      </div>
      <p className="text-[15px] font-black text-white leading-none">{q.value}</p>
      <p className={`mt-1 text-[11px] font-semibold ${q.positive !== false ? "text-emerald-400" : "text-rose-400"}`}>
        {q.change_str ?? q.pct ?? "—"}
      </p>
      {/* Show VIX interpretation as a badge */}
      {q.level_label && (
        <span className={`mt-1.5 self-start rounded-full px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide border
          ${q.color === "emerald" ? "bg-emerald-500/10 border-emerald-500/25 text-emerald-400" :
            q.color === "amber"   ? "bg-amber-500/10  border-amber-500/25  text-amber-400"   :
            q.color === "rose"    ? "bg-rose-500/10   border-rose-500/25   text-rose-400"    :
                                    "bg-slate-500/10  border-slate-500/25  text-slate-400"}`}>
          {q.level_label}
        </span>
      )}
    </div>
  );
}

// Build dynamic insight bullets from real data — no hardcoding
function buildInsights(data: any): string[] {
  const out: string[] = [];

  const gift = data?.gift_nifty;
  if (gift?.value && gift.value !== "—") {
    const dir = gift.positive ? "positive" : "under pressure";
    const prem = gift.premium_pct ? ` (${gift.premium_pct} vs spot)` : "";
    out.push(`Nifty Futures ${dir} at ${gift.value}${prem}`);
  }

  const vix = data?.india_vix;
  if (vix?.value && vix.value !== "—") {
    out.push(`India VIX at ${vix.value} — ${vix.interpretation ?? "neutral volatility"}`);
  }

  const sp = (data?.us_futures ?? []).find((f: any) => f.name?.includes("S&P"));
  if (sp?.value && sp.value !== "—") {
    const word = sp.positive ? "rallied" : "fell";
    out.push(`S&P 500 Futures ${word} to ${sp.value} (${sp.pct})`);
  }

  const fii = data?.fii_dii;
  if (fii?.available && fii.fii_net != null) {
    const n = fii.fii_net as number;
    const sign = n >= 0 ? "+" : "";
    out.push(`FII net: ${sign}₹${Math.abs(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}Cr — ${n >= 0 ? "buying" : "selling"}`);
  } else {
    const usd = (data?.currencies ?? []).find((c: any) => c.name === "USD/INR");
    if (usd?.value && usd.value !== "—") {
      const rupee = usd.positive ? "Rupee weakening — watch import costs" : "Rupee firm vs USD";
      out.push(`USD/INR at ${usd.value} — ${rupee}`);
    }
  }

  const crude = (data?.commodities ?? []).find((c: any) => c.name?.includes("Brent"));
  if (crude?.value && crude.value !== "—") {
    out.push(`Brent crude at ${crude.value} (${crude.change_str ?? "—"})`);
  }

  if (!out.length) {
    out.push(
      "Pre-market data loading…",
      "NSE opens at 9:15 AM IST",
      "Monitor FII/DII activity at open",
    );
  }

  return out.slice(0, 4);
}

export function PreMarketPanel({ data, timeIST }: { data: any | null; timeIST: string }) {
  if (!data) return null;

  // Build the 4 highlight cards:
  // 1 → Nifty Futures  2 → Bank Nifty Futures  3 → India VIX  4 → S&P 500 Futures
  const highlights: any[] = [];

  if (data.gift_nifty?.value) {
    highlights.push({ ...data.gift_nifty, name: "Nifty Futures" });
  } else if (data.asian?.[0]) {
    highlights.push(data.asian[0]);
  }

  if (data.banknifty_futures?.value) {
    highlights.push({ ...data.banknifty_futures, name: "Bank Nifty Fut." });
  } else if (data.india_vix?.value) {
    highlights.push({ ...data.india_vix, name: "India VIX" });
  }

  if (data.india_vix?.value && highlights.length < 3) {
    highlights.push({ ...data.india_vix, name: "India VIX" });
  }

  const spFut = (data.us_futures ?? []).find((f: any) => f.name?.includes("S&P"));
  if (spFut) {
    highlights.push(spFut);
  } else if (data.us?.[0]) {
    highlights.push(data.us[0]);
  }

  if (!highlights.length) return null;

  const insights = buildInsights(data);

  return (
    <div className="rounded-[28px] border border-amber-500/15 bg-gradient-to-br from-amber-500/[0.04] via-transparent to-orange-500/[0.04] p-5 shadow-lg">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-500/15">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-amber-400">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
            </svg>
          </div>
          <div>
            <p className="text-[13px] font-bold text-white">Pre-Market Overview</p>
            <p className="text-[10px] text-slate-500">As of {timeIST} IST · NSE opens 9:15 AM</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400">
            Pre-Open
          </span>
          <Link href="/market-intelligence?tab=pre-market" className="text-[11px] text-sky-400 hover:text-sky-300 transition">
            View All →
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-[1fr_auto] gap-5">
        {/* Left: metric cards (real data) */}
        <div className="grid grid-cols-4 gap-3">
          {highlights.slice(0, 4).map((q, i) => (
            <PreMarketCard key={q.ticker ?? q.name ?? i} q={q} idx={i} />
          ))}
        </div>

        {/* Right: dynamic AI insights (no hardcoding) */}
        <div className="w-[220px] shrink-0 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-3.5">
          <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
            Pre-Market Signals
          </p>
          <ul className="space-y-1.5">
            {insights.map((ins, i) => (
              <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-300">
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
                {ins}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="mt-2.5 text-[10px] text-slate-700">
        Data via yfinance · refreshed every 15 min · Gift Nifty = NSE near-month futures proxy
      </p>
    </div>
  );
}
