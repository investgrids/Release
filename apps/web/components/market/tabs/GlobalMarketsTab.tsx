"use client";

import { useEffect, useState } from "react";
import { Globe } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

export function GlobalMarketsTab() {
  const [indices, setIndices] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/market/global`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setIndices(Array.isArray(d?.indices) ? d.indices : []))
      .catch(() => setIndices([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="space-y-5">
      {[1, 2, 3].map(i => <div key={i} className="h-32 animate-pulse rounded-2xl border border-white/[0.05] bg-white/[0.02]" />)}
    </div>
  );

  const rows = indices ?? [];

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-[#080c14] py-16 text-center">
        <Globe className="mb-3 h-8 w-8 text-slate-600" />
        <p className="text-[14px] font-semibold text-slate-400">Global market data is unavailable right now.</p>
        <p className="mt-1 text-[12px] text-slate-600">Try again shortly — nothing is shown rather than a stale estimate.</p>
      </div>
    );
  }

  const positiveCount = rows.filter(r => r.positive).length;
  const globalSentiment = positiveCount >= rows.length * 0.7 ? "Bullish" : positiveCount >= rows.length * 0.4 ? "Mixed" : "Bearish";
  const sentColor = globalSentiment === "Bullish" ? "text-emerald-400" : globalSentiment === "Mixed" ? "text-amber-400" : "text-rose-400";

  return (
    <div className="space-y-5">
      {/* Global sentiment header */}
      <div className="flex flex-col gap-4 rounded-2xl border border-white/[0.07] bg-[#080c14] px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wider text-slate-500">Global Sentiment</p>
          <p className={`text-[24px] font-black ${sentColor}`}>{globalSentiment}</p>
        </div>
        <div className="flex gap-6">
          {[
            { label: "Advancing", val: positiveCount,                color: "text-emerald-400" },
            { label: "Declining", val: rows.length - positiveCount,  color: "text-rose-400"    },
            { label: "Total",     val: rows.length,                  color: "text-slate-400"   },
          ].map(s => (
            <div key={s.label} className="text-center">
              <p className={`text-[22px] font-black ${s.color}`}>{s.val}</p>
              <p className="text-[10px] text-slate-500">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Index grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {rows.map((idx) => (
          <div key={idx.name}
            className="flex items-center justify-between gap-3 rounded-2xl border border-white/[0.07] bg-[#080c14] px-5 py-4 hover:border-sky-500/15 transition">
            <div className="flex min-w-0 items-center gap-3">
              <span className="shrink-0 text-[24px]">{idx.flag}</span>
              <div className="min-w-0">
                <p className="truncate text-[13px] font-bold text-white">{idx.name}</p>
                <p className="mt-0.5 text-[11px] text-slate-500">{idx.value !== "—" ? `Last: ${idx.value}` : "No data"}</p>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-[16px] font-black text-white">{idx.value}</p>
              <p className={`text-[12px] font-bold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.pct}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Regional summary */}
      <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
        <h3 className="mb-4 text-[13px] font-bold text-white">Regional Summary</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[
            { region: "Americas",     indices: ["Dow Jones", "S&P 500", "Nasdaq"],    cls: "border-sky-500/10 bg-sky-500/[0.04]"     },
            { region: "Europe",       indices: ["FTSE 100", "DAX", "CAC 40"],          cls: "border-violet-500/10 bg-violet-500/[0.04]" },
            { region: "Asia Pacific", indices: ["Nikkei 225", "Hang Seng", "KOSPI"],   cls: "border-emerald-500/10 bg-emerald-500/[0.04]" },
          ].map(({ region, indices: names, cls }) => {
            const regionRows = rows.filter(r => names.includes(r.name));
            if (regionRows.length === 0) return null;
            const regPos = regionRows.filter(r => r.positive).length;
            const regSent = regPos === regionRows.length ? "All Up" : regPos === 0 ? "All Down" : "Mixed";
            const regColor = regPos === regionRows.length ? "text-emerald-400" : regPos === 0 ? "text-rose-400" : "text-amber-400";
            return (
              <div key={region} className={`rounded-2xl border p-4 ${cls}`}>
                <p className="mb-2 text-[11px] font-bold text-slate-400">{region}</p>
                <p className={`mb-3 text-[18px] font-black ${regColor}`}>{regSent}</p>
                <div className="space-y-1">
                  {regionRows.map(r => (
                    <div key={r.name} className="flex justify-between text-[10px]">
                      <span className="text-slate-500">{r.name}</span>
                      <span className={r.positive ? "text-emerald-400" : "text-rose-400"}>{r.pct}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
