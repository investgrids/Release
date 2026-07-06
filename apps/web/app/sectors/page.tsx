import { fetchAPI } from "@/lib/api";

interface SectorRow {
  id: string;
  name: string;
  value: string;
  positive: boolean;
}

// Dummy top-3 stocks per sector — replace with NSE sectoral-index constituents API
const SECTOR_STOCKS: Record<string, { ticker: string; change: string; positive: boolean }[]> = {
  "IT":          [{ ticker: "TCS",        change: "-0.9%",  positive: false }, { ticker: "INFY",      change: "-1.1%", positive: false }, { ticker: "WIPRO",     change: "-0.7%", positive: false }],
  "Banking":     [{ ticker: "HDFCBANK",   change: "+1.2%",  positive: true  }, { ticker: "ICICIBANK", change: "+1.5%", positive: true  }, { ticker: "AXISBANK",  change: "+0.9%", positive: true  }],
  "Pharma":      [{ ticker: "SUNPHARMA",  change: "+0.6%",  positive: true  }, { ticker: "DRREDDY",   change: "+0.4%", positive: true  }, { ticker: "CIPLA",     change: "+0.8%", positive: true  }],
  "Auto":        [{ ticker: "MARUTI",     change: "+1.8%",  positive: true  }, { ticker: "M&M",       change: "+2.1%", positive: true  }, { ticker: "TATAMOTORS",change: "+1.4%", positive: true  }],
  "Energy":      [{ ticker: "RELIANCE",   change: "+2.4%",  positive: true  }, { ticker: "ONGC",      change: "+1.8%", positive: true  }, { ticker: "NTPC",      change: "+1.6%", positive: true  }],
  "FMCG":        [{ ticker: "HINDUNILVR", change: "-0.3%",  positive: false }, { ticker: "ITC",       change: "+0.2%", positive: true  }, { ticker: "NESTLEIND", change: "-0.4%", positive: false }],
  "Infra":       [{ ticker: "LT",         change: "+3.1%",  positive: true  }, { ticker: "ADANIPORTS",change: "+2.8%", positive: true  }, { ticker: "IRCON",     change: "+4.2%", positive: true  }],
  "Metal":       [{ ticker: "TATASTEEL",  change: "+0.7%",  positive: true  }, { ticker: "HINDALCO",  change: "+0.9%", positive: true  }, { ticker: "JSWSTEEL",  change: "+0.6%", positive: true  }],
  "Realty":      [{ ticker: "DLF",        change: "+1.5%",  positive: true  }, { ticker: "GODREJPROP",change: "+1.2%", positive: true  }, { ticker: "OBEROIRLTY",change: "+0.8%", positive: true  }],
  "PSU Bank":    [{ ticker: "SBIN",       change: "+0.4%",  positive: true  }, { ticker: "PNB",       change: "+0.6%", positive: true  }, { ticker: "BANKBARODA",change: "+0.3%", positive: true  }],
  "Pvt Bank":    [{ ticker: "HDFCBANK",   change: "+1.1%",  positive: true  }, { ticker: "KOTAKBANK", change: "+0.8%", positive: true  }, { ticker: "BANDHANBNK",change: "+0.5%", positive: true  }],
  "Media":       [{ ticker: "ZEEL",       change: "-1.2%",  positive: false }, { ticker: "SUNTV",     change: "-0.9%", positive: false }, { ticker: "PVRINOX",   change: "-1.4%", positive: false }],
};

async function getSectors() {
  try {
    return await fetchAPI<SectorRow[]>("/api/sectors");
  } catch {
    return null;
  }
}

export default async function SectorsPage() {
  const sectors = await getSectors() ?? [];

  const positive = sectors.filter((s) => s.positive).length;
  const negative = sectors.filter((s) => !s.positive).length;

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Market Overview</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Sectors</h1>
        <p className="mt-1 text-sm text-slate-400">Performance breakdown across NSE sectoral indices.</p>
      </div>

      {/* Summary bar */}
      <div className="flex flex-wrap gap-4">
        {[
          { label: "Advancing", count: positive, color: "text-emerald-300", bg: "bg-emerald-500/10 border-emerald-500/20" },
          { label: "Declining",  count: negative, color: "text-rose-300",    bg: "bg-rose-500/10 border-rose-500/20" },
          { label: "Total Sectors", count: sectors.length, color: "text-slate-300", bg: "bg-white/5 border-white/10" },
        ].map(({ label, count, color, bg }) => (
          <div key={label} className={`rounded-2xl border px-5 py-3 ${bg}`}>
            <p className="text-[10px] uppercase tracking-widest text-slate-500">{label}</p>
            <p className={`mt-1 text-2xl font-bold ${color}`}>{count}</p>
          </div>
        ))}
      </div>

      {/* Sector cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {sectors.map((s) => {
          const pct = parseFloat(s.value.replace("%", ""));
          const stocks = SECTOR_STOCKS[s.name] ?? [];
          const barWidth = Math.min(Math.abs(pct) * 15, 100);

          return (
            <div key={s.id}
              className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow transition hover:-translate-y-0.5 hover:border-white/20">
              {/* Header */}
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-white">{s.name}</p>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${s.positive ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
                  {s.value}
                </span>
              </div>

              {/* Performance bar */}
              <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                <div
                  className={`h-full rounded-full transition-all ${s.positive ? "bg-emerald-500" : "bg-rose-500"}`}
                  style={{ width: `${barWidth}%` }}
                />
              </div>

              {/* Top stocks */}
              {stocks.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-[10px] uppercase tracking-widest text-slate-500">Top stocks</p>
                  <div className="flex flex-wrap gap-2">
                    {stocks.map((st) => (
                      <span key={st.ticker}
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${st.positive ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300" : "border-rose-500/20 bg-rose-500/10 text-rose-300"}`}>
                        {st.ticker}
                        <span className="opacity-70">{st.change}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <p className="mt-4 text-[10px] text-slate-600">
                ⚠ Top stocks are illustrative · Requires{" "}
                <span className="text-slate-500">NSE Sectoral Index API</span>
              </p>
            </div>
          );
        })}
      </div>
    </main>
  );
}
