"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const POPULAR_META = [
  { symbol: "RELIANCE",  name: "Reliance Industries",       sector: "Energy"   },
  { symbol: "TCS",       name: "Tata Consultancy Services", sector: "IT"       },
  { symbol: "HDFCBANK",  name: "HDFC Bank",                 sector: "Banking"  },
  { symbol: "INFY",      name: "Infosys",                   sector: "IT"       },
  { symbol: "LT",        name: "Larsen & Toubro",           sector: "Infra"    },
  { symbol: "ICICIBANK", name: "ICICI Bank",                sector: "Banking"  },
  { symbol: "BEL",       name: "Bharat Electronics",        sector: "Defence"  },
  { symbol: "HAL",       name: "Hindustan Aeronautics",     sector: "Defence"  },
  { symbol: "NTPC",      name: "NTPC Ltd.",                 sector: "Energy"   },
  { symbol: "TATAMOTORS",name: "Tata Motors",               sector: "Auto"     },
  { symbol: "SUNPHARMA", name: "Sun Pharmaceutical",        sector: "Pharma"   },
  { symbol: "WIPRO",     name: "Wipro",                     sector: "IT"       },
  { symbol: "ADANIENT",  name: "Adani Enterprises",         sector: "Infra"    },
  { symbol: "SBIN",      name: "State Bank of India",       sector: "Banking"  },
  { symbol: "RVNL",      name: "Rail Vikas Nigam",          sector: "Infra"    },
  { symbol: "HINDUNILVR",name: "Hindustan Unilever",        sector: "FMCG"     },
  { symbol: "MARUTI",    name: "Maruti Suzuki",             sector: "Auto"     },
  { symbol: "BAJFINANCE",name: "Bajaj Finance",             sector: "Finance"  },
];

const TRENDING = ["BEL", "HAL", "RVNL", "RELIANCE", "HDFCBANK", "LT", "NTPC", "TATAMOTORS", "INFY", "TCS"];

const SECTOR_COLORS: Record<string, string> = {
  IT:      "border-sky-500/20 bg-sky-500/10 text-sky-300",
  Banking: "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
  Energy:  "border-amber-500/20 bg-amber-500/10 text-amber-300",
  Defence: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  Infra:   "border-violet-500/20 bg-violet-500/10 text-violet-300",
  Auto:    "border-rose-500/20 bg-rose-500/10 text-rose-300",
  Pharma:  "border-teal-500/20 bg-teal-500/10 text-teal-300",
  FMCG:    "border-orange-500/20 bg-orange-500/10 text-orange-300",
  Finance: "border-cyan-500/20 bg-cyan-500/10 text-cyan-300",
};

interface StockRow {
  symbol: string; name: string; sector: string;
  price?: string; change?: string; positive?: boolean; loading?: boolean;
}

export default function CompaniesPage() {
  const [query, setQuery] = useState("");
  const [stocks, setStocks] = useState<StockRow[]>(
    POPULAR_META.map(m => ({ ...m, loading: true }))
  );
  const router = useRouter();

  useEffect(() => {
    Promise.all(
      POPULAR_META.map(meta =>
        fetch(`${API}/api/stocks/${meta.symbol}`)
          .then(r => r.ok ? r.json() : null)
          .catch(() => null)
      )
    ).then(results => {
      setStocks(
        POPULAR_META.map((meta, idx) => {
          const data = results[idx];
          if (!data) return { ...meta, loading: false };
          const isPos = (data.pct_change ?? 0) >= 0;
          const sign  = isPos ? "+" : "";
          return {
            ...meta,
            price:    data.price,
            change:   `${sign}${(data.pct_change ?? 0).toFixed(2)}%`,
            positive: isPos,
            loading:  false,
          };
        })
      );
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = query.trim()
    ? stocks.filter(s =>
        s.symbol.toLowerCase().includes(query.toLowerCase()) ||
        s.name.toLowerCase().includes(query.toLowerCase()) ||
        s.sector.toLowerCase().includes(query.toLowerCase())
      )
    : stocks;

  // Best-guess NSE symbol: strip spaces, uppercase
  const guessedSymbol = query.trim().toUpperCase().replace(/\s+/g, "");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (guessedSymbol) router.push(`/companies/${guessedSymbol}`);
  }

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Research</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Companies</h1>
        <p className="mt-1 text-sm text-slate-400">Search any NSE stock to explore its events, news, and financial context.</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="relative">
        <div className="flex items-center overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] shadow-glow transition focus-within:border-sky-500/40 focus-within:bg-sky-500/[0.02]">
          <span className="pl-5 text-slate-500">🔍</span>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search by symbol, company name, or sector…"
            className="flex-1 bg-transparent px-4 py-4 text-sm text-white outline-none placeholder:text-slate-500"
          />
          {query && (
            <button type="submit"
              className="mr-2 rounded-xl bg-sky-500/20 px-4 py-2 text-xs font-semibold text-sky-300 transition hover:bg-sky-500/30">
              Go →
            </button>
          )}
        </div>
      </form>

      {/* Trending chips */}
      <div>
        <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Trending</p>
        <div className="flex flex-wrap gap-2">
          {TRENDING.map(s => (
            <Link key={s} href={`/companies/${s}`}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 transition hover:border-sky-500/30 hover:bg-sky-500/10 hover:text-sky-300">
              {s}
            </Link>
          ))}
        </div>
      </div>

      {/* Stock grid */}
      <div>
        <p className="mb-3 text-[10px] uppercase tracking-widest text-slate-500">
          {query ? `${filtered.length} result${filtered.length !== 1 ? "s" : ""}` : "NSE Listed Companies"}
        </p>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map(s => (
            <Link key={s.symbol} href={`/companies/${s.symbol}`}
              className="group rounded-[18px] border border-white/10 bg-white/[0.03] p-4 shadow-glow transition hover:-translate-y-0.5 hover:border-white/20">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-xs font-bold text-slate-300">
                    {s.symbol.slice(0, 2)}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white group-hover:text-sky-300">{s.symbol}</p>
                    <p className="truncate text-[11px] text-slate-500">{s.name}</p>
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  {s.loading ? (
                    <div className="flex flex-col items-end gap-1">
                      <div className="h-3.5 w-16 animate-pulse rounded bg-white/[0.06]" />
                      <div className="h-3 w-10 animate-pulse rounded bg-white/[0.04]" />
                    </div>
                  ) : s.price ? (
                    <>
                      <p className="text-sm font-semibold text-white">₹{s.price}</p>
                      <p className={`text-xs font-medium ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.change}</p>
                    </>
                  ) : (
                    <span className="text-xs text-slate-600">—</span>
                  )}
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${SECTOR_COLORS[s.sector] ?? "border-white/8 bg-white/5 text-slate-500"}`}>
                  {s.sector}
                </span>
                <span className="text-[11px] text-slate-600 group-hover:text-slate-400 transition">View details →</span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {filtered.length === 0 && query.trim() && (
        <div className="flex flex-col items-center gap-4 rounded-[20px] border border-white/10 bg-white/[0.03] py-16 text-center">
          <span className="text-3xl">🔍</span>
          <p className="text-sm text-slate-400">
            &quot;{query}&quot; is not in the popular list — but we can look it up directly.
          </p>
          <button
            onClick={() => router.push(`/companies/${guessedSymbol}`)}
            className="rounded-xl bg-sky-500/20 px-6 py-2.5 text-sm font-semibold text-sky-300 transition hover:bg-sky-500/30"
          >
            Search &quot;{guessedSymbol}&quot; on NSE →
          </button>
          <p className="text-[11px] text-slate-600">
            Works for any NSE-listed company — NATCOPHARMA, DRREDDY, CIPLA, etc.
          </p>
        </div>
      )}
    </main>
  );
}
