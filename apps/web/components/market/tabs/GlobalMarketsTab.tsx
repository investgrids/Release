"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function Spark({ positive, seed }: { positive: boolean; seed: number }) {
  const pts: number[] = [];
  let v = 50;
  for (let i = 0; i < 10; i++) {
    v += Math.sin(seed + i * 1.2) * 7 + (positive ? 1.5 : -1.5);
    v = Math.max(15, Math.min(85, v));
    pts.push(v);
  }
  const W = 64, H = 32;
  const coords = pts.map((p, i) => `${(i / 9) * W},${H - (p / 100) * H}`).join(" ");
  const color = positive ? "#22c55e" : "#f43f5e";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-8 w-16" fill="none">
      <polyline points={coords} stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <defs>
        <linearGradient id={`gf-${seed}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={`0,${H} ${coords} ${W},${H}`} fill={`url(#gf-${seed})`}/>
    </svg>
  );
}

export function GlobalMarketsTab() {
  const [indices, setIndices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/market/global`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.indices) setIndices(d.indices); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Fallback static data
  const FB = [
    { name: "Dow Jones",          flag: "🇺🇸", value: "41,860.44", pct: "+0.32%", positive: true  },
    { name: "S&P 500",            flag: "🇺🇸", value: "5,842.01",  pct: "+0.41%", positive: true  },
    { name: "Nasdaq",             flag: "🇺🇸", value: "18,872.64", pct: "+0.67%", positive: true  },
    { name: "FTSE 100",           flag: "🇬🇧", value: "8,402.57",  pct: "+0.28%", positive: true  },
    { name: "DAX",                flag: "🇩🇪", value: "18,235.45", pct: "+0.52%", positive: true  },
    { name: "CAC 40",             flag: "🇫🇷", value: "7,984.13",  pct: "+0.33%", positive: true  },
    { name: "Nikkei 225",         flag: "🇯🇵", value: "38,529.48", pct: "+0.20%", positive: true  },
    { name: "Hang Seng",          flag: "🇭🇰", value: "19,544.31", pct: "+0.91%", positive: true  },
    { name: "Shanghai Composite", flag: "🇨🇳", value: "3,045.22",  pct: "-0.15%", positive: false },
    { name: "KOSPI",              flag: "🇰🇷", value: "2,512.78",  pct: "+0.44%", positive: true  },
  ];

  const rows = indices.length ? indices : FB;
  const positiveCount = rows.filter(r => r.positive).length;
  const globalSentiment = positiveCount >= rows.length * 0.7 ? "Bullish" : positiveCount >= rows.length * 0.4 ? "Mixed" : "Bearish";
  const sentColor = globalSentiment === "Bullish" ? "text-emerald-400" : globalSentiment === "Mixed" ? "text-amber-400" : "text-rose-400";

  if (loading) return (
    <div className="space-y-4">
      {[1,2,3].map(i => <div key={i} className="h-32 rounded-xl border border-white/[0.05] bg-white/[0.02] animate-pulse"/>)}
    </div>
  );

  return (
    <div className="space-y-5">
      {/* Global sentiment header */}
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-[#0a0d16] px-6 py-4">
        <div>
          <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1">Global Sentiment</p>
          <p className={`text-[24px] font-black ${sentColor}`}>{globalSentiment}</p>
        </div>
        <div className="flex gap-6">
          {[
            { label: "Advancing", val: positiveCount,                    color: "text-emerald-400" },
            { label: "Declining", val: rows.length - positiveCount,     color: "text-rose-400"    },
            { label: "Total",     val: rows.length,                      color: "text-slate-400"   },
          ].map(s => (
            <div key={s.label} className="text-center">
              <p className={`text-[22px] font-black ${s.color}`}>{s.val}</p>
              <p className="text-[10px] text-slate-500">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Index grid */}
      <div className="grid grid-cols-2 gap-4">
        {rows.map((idx, i) => (
          <div key={idx.name}
            className="flex items-center justify-between rounded-xl border border-white/[0.07] bg-white/[0.03] px-5 py-4 hover:border-sky-500/15 hover:bg-white/[0.05] transition">
            <div className="flex items-center gap-3">
              <span className="text-[24px]">{idx.flag}</span>
              <div>
                <p className="text-[13px] font-bold text-white">{idx.name}</p>
                <p className="text-[11px] text-slate-500 mt-0.5">{idx.value !== "—" ? `Last: ${idx.value}` : "No data"}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <Spark positive={idx.positive} seed={i * 6.1}/>
              <div className="text-right">
                <p className="text-[16px] font-black text-white">{idx.value}</p>
                <p className={`text-[12px] font-bold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.pct}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Asia-Pacific summary */}
      <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
        <h3 className="mb-3 text-[14px] font-bold text-white">Regional Summary</h3>
        <div className="grid grid-cols-3 gap-4">
          {[
            { region: "Americas",    indices: ["Dow Jones","S&P 500","Nasdaq"],   color: "sky"    },
            { region: "Europe",      indices: ["FTSE 100","DAX","CAC 40"],        color: "violet" },
            { region: "Asia Pacific",indices: ["Nikkei 225","Hang Seng","KOSPI"], color: "emerald"},
          ].map(({ region, indices: names, color }) => {
            const regionRows = rows.filter(r => names.includes(r.name));
            const regPos = regionRows.filter(r => r.positive).length;
            const regSent = regPos === regionRows.length ? "All Up" : regPos === 0 ? "All Down" : "Mixed";
            const regColor = regPos === regionRows.length ? "text-emerald-400" : regPos === 0 ? "text-rose-400" : "text-amber-400";
            return (
              <div key={region} className={`rounded-2xl border border-${color}-500/10 bg-${color}-500/[0.04] p-4`}>
                <p className="text-[11px] font-bold text-slate-400 mb-2">{region}</p>
                <p className={`text-[18px] font-black mb-3 ${regColor}`}>{regSent}</p>
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
