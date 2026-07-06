"use client";

import { useState } from "react";

// Dummy Nifty 50 stock data — requires NSE constituent API for real values
const NIFTY50 = [
  { symbol: "RELIANCE",    name: "Reliance Industries",    sector: "Energy",    pct: 2.4,  mcap: 19 },
  { symbol: "TCS",         name: "Tata Consultancy",       sector: "IT",        pct: -0.9, mcap: 15 },
  { symbol: "HDFCBANK",    name: "HDFC Bank",              sector: "Banking",   pct: 1.2,  mcap: 14 },
  { symbol: "BHARTIARTL",  name: "Bharti Airtel",          sector: "Telecom",   pct: 1.8,  mcap: 10 },
  { symbol: "ICICIBANK",   name: "ICICI Bank",             sector: "Banking",   pct: 1.5,  mcap: 9  },
  { symbol: "INFY",        name: "Infosys",                sector: "IT",        pct: -1.1, mcap: 8  },
  { symbol: "SBIN",        name: "State Bank of India",    sector: "Banking",   pct: 0.4,  mcap: 7  },
  { symbol: "LT",          name: "Larsen & Toubro",        sector: "Infra",     pct: 3.1,  mcap: 7  },
  { symbol: "HINDUNILVR",  name: "Hindustan Unilever",     sector: "FMCG",      pct: -0.3, mcap: 6  },
  { symbol: "ITC",         name: "ITC Limited",            sector: "FMCG",      pct: 0.2,  mcap: 6  },
  { symbol: "KOTAKBANK",   name: "Kotak Mahindra Bank",    sector: "Banking",   pct: 0.8,  mcap: 5  },
  { symbol: "BAJFINANCE",  name: "Bajaj Finance",          sector: "NBFC",      pct: 1.4,  mcap: 5  },
  { symbol: "AXISBANK",    name: "Axis Bank",              sector: "Banking",   pct: 0.9,  mcap: 5  },
  { symbol: "MARUTI",      name: "Maruti Suzuki",          sector: "Auto",      pct: 1.8,  mcap: 4  },
  { symbol: "SUNPHARMA",   name: "Sun Pharmaceutical",     sector: "Pharma",    pct: 0.6,  mcap: 4  },
  { symbol: "TATASTEEL",   name: "Tata Steel",             sector: "Metal",     pct: 0.7,  mcap: 4  },
  { symbol: "WIPRO",       name: "Wipro Limited",          sector: "IT",        pct: -0.7, mcap: 4  },
  { symbol: "ULTRACEMCO",  name: "UltraTech Cement",       sector: "Cement",    pct: 0.5,  mcap: 4  },
  { symbol: "TECHM",       name: "Tech Mahindra",          sector: "IT",        pct: -2.3, mcap: 3  },
  { symbol: "TITAN",       name: "Titan Company",          sector: "Consumer",  pct: 0.9,  mcap: 3  },
  { symbol: "POWERGRID",   name: "Power Grid Corp",        sector: "Energy",    pct: 1.6,  mcap: 3  },
  { symbol: "NTPC",        name: "NTPC Limited",           sector: "Energy",    pct: 1.4,  mcap: 3  },
  { symbol: "ONGC",        name: "Oil & Natural Gas",      sector: "Energy",    pct: 1.8,  mcap: 3  },
  { symbol: "COALINDIA",   name: "Coal India",             sector: "Energy",    pct: 0.6,  mcap: 3  },
  { symbol: "HCLTECH",     name: "HCL Technologies",       sector: "IT",        pct: -1.3, mcap: 3  },
  { symbol: "BAJAJFINSV",  name: "Bajaj Finserv",          sector: "NBFC",      pct: 1.2,  mcap: 3  },
  { symbol: "ASIANPAINT",  name: "Asian Paints",           sector: "Consumer",  pct: -0.4, mcap: 3  },
  { symbol: "TATAMOTORS",  name: "Tata Motors",            sector: "Auto",      pct: 1.4,  mcap: 3  },
  { symbol: "NESTLEIND",   name: "Nestlé India",           sector: "FMCG",      pct: -0.5, mcap: 2  },
  { symbol: "ADANIPORTS",  name: "Adani Ports",            sector: "Infra",     pct: 2.8,  mcap: 2  },
  { symbol: "DRREDDY",     name: "Dr. Reddy's Lab",        sector: "Pharma",    pct: 0.4,  mcap: 2  },
  { symbol: "CIPLA",       name: "Cipla Limited",          sector: "Pharma",    pct: 0.8,  mcap: 2  },
  { symbol: "MM",          name: "Mahindra & Mahindra",    sector: "Auto",      pct: 2.1,  mcap: 2  },
  { symbol: "EICHERMOT",   name: "Eicher Motors",          sector: "Auto",      pct: 1.1,  mcap: 2  },
  { symbol: "BRITANNIA",   name: "Britannia Industries",   sector: "FMCG",      pct: -0.2, mcap: 2  },
  { symbol: "INDUSINDBK",  name: "IndusInd Bank",          sector: "Banking",   pct: 0.5,  mcap: 2  },
  { symbol: "DIVISLAB",    name: "Divi's Laboratories",    sector: "Pharma",    pct: 1.0,  mcap: 2  },
  { symbol: "GRASIM",      name: "Grasim Industries",      sector: "Cement",    pct: 0.8,  mcap: 2  },
  { symbol: "JSWSTEEL",    name: "JSW Steel",              sector: "Metal",     pct: 0.6,  mcap: 2  },
  { symbol: "HEROMOTOCO",  name: "Hero MotoCorp",          sector: "Auto",      pct: 0.9,  mcap: 2  },
  { symbol: "TATACONSUM",  name: "Tata Consumer",          sector: "FMCG",      pct: 0.3,  mcap: 2  },
  { symbol: "BPCL",        name: "BPCL",                   sector: "Energy",    pct: 1.2,  mcap: 2  },
  { symbol: "HINDALCO",    name: "Hindalco Industries",    sector: "Metal",     pct: 0.9,  mcap: 2  },
  { symbol: "SBILIFE",     name: "SBI Life Insurance",     sector: "Insurance", pct: 0.6,  mcap: 2  },
  { symbol: "HDFCLIFE",    name: "HDFC Life Insurance",    sector: "Insurance", pct: 0.4,  mcap: 2  },
  { symbol: "APOLLOHOSP",  name: "Apollo Hospitals",       sector: "Healthcare",pct: 1.3,  mcap: 2  },
  { symbol: "LTIM",        name: "LTIMindtree",            sector: "IT",        pct: -0.8, mcap: 2  },
  { symbol: "ADANIENT",    name: "Adani Enterprises",      sector: "Conglomerate",pct: 2.1, mcap: 2 },
  { symbol: "UPL",         name: "UPL Limited",            sector: "Agri",      pct: -1.8, mcap: 1  },
  { symbol: "BAJAJ-AUTO",  name: "Bajaj Auto",             sector: "Auto",      pct: 1.5,  mcap: 1  },
];

const SECTORS = [...new Set(NIFTY50.map((s) => s.sector))];

function tileColor(pct: number): string {
  if (pct >= 3)    return "bg-emerald-500 text-white";
  if (pct >= 2)    return "bg-emerald-600/90 text-white";
  if (pct >= 1)    return "bg-emerald-700/80 text-white";
  if (pct >= 0.5)  return "bg-emerald-800/70 text-emerald-100";
  if (pct >= 0)    return "bg-emerald-900/50 text-emerald-200";
  if (pct >= -0.5) return "bg-rose-900/50 text-rose-200";
  if (pct >= -1)   return "bg-rose-800/70 text-rose-100";
  if (pct >= -2)   return "bg-rose-700/80 text-white";
  return "bg-rose-600/90 text-white";
}

function tileSize(mcap: number) {
  if (mcap >= 14) return "col-span-2 row-span-2 min-h-[120px]";
  if (mcap >= 7)  return "col-span-2 row-span-1 min-h-[60px]";
  return "col-span-1 row-span-1 min-h-[60px]";
}

export default function HeatmapPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const [filterSector, setFilterSector] = useState<string>("All");

  const filtered = filterSector === "All" ? NIFTY50 : NIFTY50.filter((s) => s.sector === filterSector);

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Market Overview</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Market Heatmap</h1>
        <p className="mt-1 text-sm text-slate-400">Nifty 50 stocks by market cap and 1-day performance.</p>
      </div>

      {/* Legend + filters */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span>Performance:</span>
          {[["≥+3%","bg-emerald-500"],["≥+1%","bg-emerald-700/80"],["0%","bg-emerald-900/50"],
            ["≤−1%","bg-rose-800/70"],["≤−3%","bg-rose-600/90"]].map(([label, bg]) => (
            <span key={label} className="flex items-center gap-1">
              <span className={`h-3 w-3 rounded-sm ${bg}`} />
              {label}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {["All", ...SECTORS].map((s) => (
            <button key={s} onClick={() => setFilterSector(s)}
              className={`rounded-full px-3 py-1 text-xs transition ${filterSector === s ? "bg-sky-500/20 text-sky-300 border border-sky-500/30" : "border border-white/10 bg-white/5 text-slate-400 hover:text-white"}`}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Heatmap grid */}
      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4 shadow-glow">
        <div className="grid grid-cols-6 gap-1.5 auto-rows-[60px]">
          {filtered.map((stock) => (
            <button key={stock.symbol} onClick={() => setSelected(selected === stock.symbol ? null : stock.symbol)}
              className={`${tileSize(stock.mcap)} ${tileColor(stock.pct)} rounded-[10px] p-2 text-left transition hover:opacity-90 hover:ring-1 hover:ring-white/30 ${selected === stock.symbol ? "ring-2 ring-white" : ""}`}>
              <p className="text-[11px] font-bold leading-tight">{stock.symbol}</p>
              <p className="mt-0.5 text-[10px] opacity-80 leading-tight">{stock.pct > 0 ? "+" : ""}{stock.pct}%</p>
            </button>
          ))}
        </div>
      </div>

      {/* Detail panel */}
      {selected && (() => {
        const s = NIFTY50.find((x) => x.symbol === selected)!;
        return (
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs text-slate-500">{s.sector}</p>
                <p className="mt-0.5 text-lg font-bold text-white">{s.symbol} — {s.name}</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-sm font-bold ${s.pct >= 0 ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
                {s.pct > 0 ? "+" : ""}{s.pct}%
              </span>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Real-time price and OHLC data requires <span className="text-amber-400">NSE Live Data API</span> or <span className="text-amber-400">Upstox / Zerodha Kite Connect</span>.
            </p>
          </div>
        );
      })()}

      <p className="text-center text-[11px] text-slate-600">
        ⚠ Performance values are illustrative · Requires <span className="text-slate-500">NSE Constituent API</span> for live stock-level data
      </p>
    </main>
  );
}
