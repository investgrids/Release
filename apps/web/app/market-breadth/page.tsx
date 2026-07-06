"use client";

import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, CartesianGrid,
} from "recharts";

// ⚠ All data below is illustrative — requires NSE Market Breadth API
const BREADTH = { advances: 1284, declines: 598, unchanged: 138, total: 2020 };

const AD_LINE = [
  { day: "Mon", ad: 620,  ratio: 2.1 },
  { day: "Tue", ad: 480,  ratio: 1.8 },
  { day: "Wed", ad: 750,  ratio: 2.6 },
  { day: "Thu", ad: 320,  ratio: 1.4 },
  { day: "Fri", ad: 686,  ratio: 2.15 },
];

const SECTOR_BREADTH = [
  { name: "Infra",   advances: 18, declines: 2  },
  { name: "Energy",  advances: 14, declines: 4  },
  { name: "Auto",    advances: 12, declines: 3  },
  { name: "Banking", advances: 10, declines: 5  },
  { name: "Pharma",  advances: 9,  declines: 3  },
  { name: "Metal",   advances: 8,  declines: 4  },
  { name: "FMCG",    advances: 5,  declines: 6  },
  { name: "IT",      advances: 3,  declines: 12 },
];

const FII_DII = [
  { day: "Mon", fii: 1240,  dii: -380  },
  { day: "Tue", fii: -620,  dii: 840   },
  { day: "Wed", fii: 2180,  dii: -240  },
  { day: "Thu", fii: 940,   dii: 560   },
  { day: "Fri", fii: 1820,  dii: -120  },
];

const adRatio = (BREADTH.advances / BREADTH.declines).toFixed(2);
const advPct   = ((BREADTH.advances / BREADTH.total) * 100).toFixed(1);
const declPct  = ((BREADTH.declines / BREADTH.total) * 100).toFixed(1);

export default function MarketBreadthPage() {
  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Market Overview</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Market Breadth</h1>
        <p className="mt-1 text-sm text-slate-400">Advance-decline ratio, sector breadth, and institutional flow.</p>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Advances",  value: BREADTH.advances,  sub: `${advPct}% of traded`,  color: "text-emerald-300", bg: "bg-emerald-500/10 border-emerald-500/20" },
          { label: "Declines",  value: BREADTH.declines,  sub: `${declPct}% of traded`, color: "text-rose-300",    bg: "bg-rose-500/10 border-rose-500/20" },
          { label: "Unchanged", value: BREADTH.unchanged, sub: "No movement",           color: "text-slate-300",   bg: "bg-white/5 border-white/10" },
          { label: "A/D Ratio", value: adRatio,           sub: "Bullish > 1.5",         color: "text-sky-300",     bg: "bg-sky-500/10 border-sky-500/20" },
        ].map(({ label, value, sub, color, bg }) => (
          <div key={label} className={`rounded-[20px] border p-5 ${bg}`}>
            <p className="text-[10px] uppercase tracking-widest text-slate-500">{label}</p>
            <p className={`mt-2 text-3xl font-bold ${color}`}>{value}</p>
            <p className="mt-1 text-xs text-slate-500">{sub}</p>
          </div>
        ))}
      </div>

      {/* A/D stacked bar + ratio line */}
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow">
          <p className="mb-4 text-sm font-semibold text-white">Advance / Decline — 5 Day</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={AD_LINE} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="day" stroke="#475569" axisLine={false} tickLine={false} />
              <YAxis stroke="#475569" axisLine={false} tickLine={false} width={32} />
              <Tooltip contentStyle={{ background: "#020617", border: "1px solid rgba(255,255,255,0.08)", color: "#fff", borderRadius: 12 }} />
              <Bar dataKey="ad" radius={[6,6,0,0]}>
                {AD_LINE.map((e) => <Cell key={e.day} fill={e.ad > 600 ? "#10b981" : "#f43f5e"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow">
          <p className="mb-4 text-sm font-semibold text-white">A/D Ratio — 5 Day</p>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={AD_LINE}>
              <defs>
                <linearGradient id="ratio-g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#38bdf8" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#38bdf8" stopOpacity={0}    />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="day" stroke="#475569" axisLine={false} tickLine={false} />
              <YAxis stroke="#475569" axisLine={false} tickLine={false} width={32} domain={[0, 3]} />
              <Tooltip contentStyle={{ background: "#020617", border: "1px solid rgba(255,255,255,0.08)", color: "#fff", borderRadius: 12 }} />
              <Area type="monotone" dataKey="ratio" stroke="#38bdf8" strokeWidth={2} fill="url(#ratio-g)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Sector breadth */}
      <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow">
        <p className="mb-5 text-sm font-semibold text-white">Breadth by Sector</p>
        <div className="space-y-3">
          {SECTOR_BREADTH.map((s) => {
            const total = s.advances + s.declines;
            const advW  = Math.round((s.advances / total) * 100);
            return (
              <div key={s.name}>
                <div className="mb-1.5 flex items-center justify-between text-xs text-slate-400">
                  <span>{s.name}</span>
                  <span className="flex gap-3">
                    <span className="text-emerald-400">{s.advances} up</span>
                    <span className="text-rose-400">{s.declines} down</span>
                  </span>
                </div>
                <div className="flex h-2 overflow-hidden rounded-full bg-rose-900/30">
                  <div className="rounded-full bg-emerald-500 transition-all" style={{ width: `${advW}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* FII / DII flow */}
      <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-semibold text-white">FII / DII Net Flow (₹ Cr)</p>
          <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-[10px] text-amber-300">
            Illustrative · Requires SEBI / NSE Data Feed
          </span>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={FII_DII} barGap={4}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="day" stroke="#475569" axisLine={false} tickLine={false} />
            <YAxis stroke="#475569" axisLine={false} tickLine={false} width={48} />
            <Tooltip contentStyle={{ background: "#020617", border: "1px solid rgba(255,255,255,0.08)", color: "#fff", borderRadius: 12 }} />
            <Bar dataKey="fii" name="FII" radius={[4,4,0,0]}>
              {FII_DII.map((e) => <Cell key={e.day} fill={e.fii >= 0 ? "#10b981" : "#f43f5e"} />)}
            </Bar>
            <Bar dataKey="dii" name="DII" radius={[4,4,0,0]}>
              {FII_DII.map((e) => <Cell key={`d-${e.day}`} fill={e.dii >= 0 ? "#38bdf8" : "#94a3b8"} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-3 flex gap-5 text-xs text-slate-400">
          <span className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-sm bg-emerald-500" /> FII net buy</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-sm bg-sky-400"    /> DII net buy</span>
        </div>
      </div>

      <p className="text-center text-[11px] text-slate-600">
        ⚠ All figures are illustrative · Real data requires{" "}
        <span className="text-slate-500">NSE Market Breadth API / SEBI NSDL FII Data Feed</span>
      </p>
    </main>
  );
}
