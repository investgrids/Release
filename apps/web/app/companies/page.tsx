import Link from "next/link";
import { CompanySearchInput } from "./_components/SearchInput";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────
interface Company {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  cap: "large" | "mid" | "small";
  price?: string | null;
  pct?: number | null;
  positive?: boolean | null;
}

interface CompaniesResponse {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  companies: Company[];
}

// ── Data fetching ─────────────────────────────────────────────────────────────
async function fetchCompanies(params: {
  q: string; sector: string; cap: string; sort: string; page: number;
}): Promise<CompaniesResponse> {
  const qs = new URLSearchParams({
    q:         params.q,
    sector:    params.sector,
    cap:       params.cap,
    sort:      params.sort,
    page:      String(params.page),
    page_size: "24",
  });
  try {
    const res = await fetch(`${API}/api/companies/?${qs}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  } catch {
    return { total: 0, page: 1, page_size: 24, total_pages: 1, companies: [] };
  }
}

async function fetchSectors(): Promise<string[]> {
  try {
    const res = await fetch(`${API}/api/companies/sectors`, { next: { revalidate: 3600 } });
    if (!res.ok) return [];
    const json = await res.json();
    return json.sectors ?? [];
  } catch {
    return [];
  }
}

// ── Design helpers ────────────────────────────────────────────────────────────
const SECTOR_STYLE: Record<string, string> = {
  Technology:      "border-sky-500/20 bg-sky-500/10 text-sky-300",
  Banking:         "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
  Finance:         "border-cyan-500/20 bg-cyan-500/10 text-cyan-300",
  Energy:          "border-amber-500/20 bg-amber-500/10 text-amber-300",
  Power:           "border-yellow-500/20 bg-yellow-500/10 text-yellow-300",
  Infrastructure:  "border-violet-500/20 bg-violet-500/10 text-violet-300",
  Defence:         "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  Pharmaceuticals: "border-teal-500/20 bg-teal-500/10 text-teal-300",
  Healthcare:      "border-green-500/20 bg-green-500/10 text-green-300",
  FMCG:            "border-orange-500/20 bg-orange-500/10 text-orange-300",
  Consumer:        "border-rose-500/20 bg-rose-500/10 text-rose-300",
  Automotive:      "border-red-500/20 bg-red-500/10 text-red-300",
  Metals:          "border-zinc-500/20 bg-zinc-500/10 text-zinc-300",
  Chemicals:       "border-purple-500/20 bg-purple-500/10 text-purple-300",
  Cement:          "border-stone-500/20 bg-stone-500/10 text-stone-300",
  "Real Estate":   "border-lime-500/20 bg-lime-500/10 text-lime-300",
  Telecom:         "border-blue-500/20 bg-blue-500/10 text-blue-300",
};

const CAP_STYLE: Record<string, string> = {
  large: "border-sky-500/15 bg-sky-500/8 text-sky-400",
  mid:   "border-violet-500/15 bg-violet-500/8 text-violet-400",
  small: "border-slate-500/15 bg-slate-500/8 text-slate-400",
};
const CAP_LABEL: Record<string, string> = {
  large: "Large Cap",
  mid:   "Mid Cap",
  small: "Small Cap",
};

// Build a URL for filter links — preserves existing active filters
function filterUrl(
  base: Record<string, string>,
  key: string,
  val: string,
): string {
  const sp = new URLSearchParams({ ...base });
  if (sp.get(key) === val) sp.delete(key); // toggle off
  else sp.set(key, val);
  sp.set("page", "1");
  // Clean empty keys
  for (const [k, v] of [...sp.entries()]) if (!v) sp.delete(k);
  const qs = sp.toString();
  return `/companies${qs ? `?${qs}` : ""}`;
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default async function CompaniesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp   = await searchParams;
  const q       = typeof sp.q      === "string" ? sp.q      : "";
  const sector  = typeof sp.sector === "string" ? sp.sector : "";
  const cap     = typeof sp.cap    === "string" ? sp.cap    : "";
  const sort    = typeof sp.sort   === "string" ? sp.sort   : "name";
  const page    = Math.max(1, Number(sp.page ?? 1));

  // Active filter map for building href strings
  const active = Object.fromEntries(
    [["q", q], ["sector", sector], ["cap", cap], ["sort", sort]].filter(([, v]) => v)
  );

  const [data, sectors] = await Promise.all([
    fetchCompanies({ q, sector, cap, sort, page }),
    fetchSectors(),
  ]);

  const { companies, total, total_pages } = data;

  // ── Pagination links ──────────────────────────────────────────────────────
  function pageUrl(p: number) {
    const s = new URLSearchParams({ ...active });
    s.set("page", String(p));
    for (const [k, v] of [...s.entries()]) if (!v) s.delete(k);
    return `/companies?${s}`;
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <main className="min-w-0 space-y-6 pb-12">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Research</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Companies</h1>
        <p className="mt-1 text-sm text-slate-400">
          Browse {total > 0 ? total.toLocaleString() : "250+"} NSE-listed companies — live prices, events, and AI analysis.
        </p>
      </div>

      {/* ── Search ──────────────────────────────────────────────────────── */}
      <CompanySearchInput
        defaultValue={q}
        sector={sector}
        cap={cap}
        sort={sort}
      />

      {/* ── Filters ─────────────────────────────────────────────────────── */}
      <div className="space-y-3">
        {/* Sector chips */}
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Sector</p>
          <div className="flex flex-wrap gap-1.5">
            {sectors.map(s => {
              const active_sector = sector === s;
              return (
                <Link
                  key={s}
                  href={filterUrl({ ...active }, "sector", s)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition
                    ${active_sector
                      ? (SECTOR_STYLE[s] ?? "border-white/20 bg-white/10 text-white")
                      : "border-white/8 bg-white/[0.03] text-slate-400 hover:border-white/15 hover:text-slate-200"
                    }`}
                >
                  {s}
                  {active_sector && " ×"}
                </Link>
              );
            })}
          </div>
        </div>

        {/* Cap + Sort row */}
        <div className="flex flex-wrap items-center gap-4">
          {/* Cap filters */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-widest text-slate-500 mr-1">Cap</span>
            {(["large", "mid", "small"] as const).map(c => (
              <Link
                key={c}
                href={filterUrl({ ...active }, "cap", c)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition
                  ${cap === c
                    ? (CAP_STYLE[c] ?? "border-white/20 bg-white/10 text-white")
                    : "border-white/8 bg-white/[0.03] text-slate-400 hover:border-white/15 hover:text-slate-200"
                  }`}
              >
                {CAP_LABEL[c]}
                {cap === c && " ×"}
              </Link>
            ))}
          </div>

          {/* Sort */}
          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-[10px] uppercase tracking-widest text-slate-500 mr-1">Sort</span>
            {[
              { val: "name", label: "A–Z" },
              { val: "cap",  label: "Market Cap" },
              { val: "sector", label: "Sector" },
            ].map(({ val, label }) => (
              <Link
                key={val}
                href={filterUrl({ ...active }, "sort", val)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition
                  ${sort === val
                    ? "border-sky-500/30 bg-sky-500/15 text-sky-300"
                    : "border-white/8 bg-white/[0.03] text-slate-400 hover:border-white/15 hover:text-slate-200"
                  }`}
              >
                {label}
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* ── Results header ───────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <p className="text-[11px] text-slate-500">
          {total > 0
            ? `${total.toLocaleString()} compan${total !== 1 ? "ies" : "y"}${q ? ` matching "${q}"` : ""}${sector ? ` · ${sector}` : ""}${cap ? ` · ${CAP_LABEL[cap]}` : ""}`
            : q || sector || cap ? "No matching companies" : "All companies"
          }
          {total > 0 && total_pages > 1 && ` · Page ${page} of ${total_pages}`}
        </p>
        {(q || sector || cap) && (
          <Link href="/companies" className="text-[11px] text-sky-400 hover:text-sky-300 transition">
            Clear filters ×
          </Link>
        )}
      </div>

      {/* ── Company grid ─────────────────────────────────────────────────── */}
      {companies.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {companies.map(co => {
            const sectorCls = SECTOR_STYLE[co.sector] ?? "border-white/8 bg-white/5 text-slate-400";
            const capCls    = CAP_STYLE[co.cap]       ?? "border-white/8 bg-white/5 text-slate-500";
            const pctPos    = co.pct !== null && co.pct !== undefined ? co.pct >= 0 : null;

            return (
              <Link
                key={co.symbol}
                href={`/companies/${co.symbol}`}
                className="group rounded-[18px] border border-white/10 bg-white/[0.03] p-4 transition hover:-translate-y-0.5 hover:border-white/20 hover:shadow-[0_8px_32px_rgba(0,0,0,0.35)]"
              >
                <div className="flex items-start justify-between gap-3">
                  {/* Avatar + name */}
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-xs font-bold text-slate-300">
                      {co.symbol.slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white group-hover:text-sky-300 transition">
                        {co.symbol}
                      </p>
                      <p className="truncate text-[11px] text-slate-500">{co.name}</p>
                    </div>
                  </div>

                  {/* Price */}
                  <div className="shrink-0 text-right">
                    {co.price ? (
                      <>
                        <p className="text-sm font-semibold text-white tabular-nums">₹{co.price}</p>
                        {co.pct !== null && co.pct !== undefined && (
                          <p className={`text-xs font-medium tabular-nums ${pctPos ? "text-emerald-400" : "text-rose-400"}`}>
                            {pctPos ? "+" : ""}{co.pct.toFixed(2)}%
                          </p>
                        )}
                      </>
                    ) : (
                      <span className="text-xs text-slate-600">—</span>
                    )}
                  </div>
                </div>

                {/* Footer: badges + arrow */}
                <div className="mt-3 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className={`inline-block shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${sectorCls}`}>
                      {co.sector}
                    </span>
                    <span className={`inline-block shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${capCls}`}>
                      {CAP_LABEL[co.cap] ?? co.cap}
                    </span>
                  </div>
                  <span className="shrink-0 text-[11px] text-slate-600 group-hover:text-slate-400 transition">
                    View →
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      ) : (
        /* ── Empty state ────────────────────────────────────────────────── */
        <div className="flex flex-col items-center gap-5 rounded-[20px] border border-white/8 bg-white/[0.02] py-16 text-center">
          <span className="text-4xl">🔍</span>
          <div>
            <p className="text-base font-medium text-white">No matching company found</p>
            <p className="mt-1 text-sm text-slate-400">
              {q ? `"${q}" didn't match any of our supported companies.` : "No companies match the selected filters."}
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            {q && (
              <Link
                href={`/companies/${q.trim().toUpperCase().replace(/\s+/g, "")}`}
                className="rounded-xl border border-sky-500/25 bg-sky-500/10 px-5 py-2 text-sm font-medium text-sky-300 hover:bg-sky-500/18 transition"
              >
                Try {q.trim().toUpperCase()} on NSE →
              </Link>
            )}
            <Link
              href="/ai-search"
              className="rounded-xl border border-white/10 bg-white/[0.05] px-5 py-2 text-sm font-medium text-slate-300 hover:bg-white/[0.09] transition"
            >
              Ask Market AI
            </Link>
            <Link
              href="/companies"
              className="rounded-xl border border-white/8 bg-white/[0.03] px-5 py-2 text-sm font-medium text-slate-400 hover:text-slate-300 transition"
            >
              Browse all companies
            </Link>
          </div>
        </div>
      )}

      {/* ── Pagination ───────────────────────────────────────────────────── */}
      {total_pages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          {page > 1 && (
            <Link
              href={pageUrl(page - 1)}
              className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-slate-300 hover:bg-white/[0.08] hover:text-white transition"
            >
              ← Previous
            </Link>
          )}

          {/* Page number pills — show window around current page */}
          {Array.from({ length: total_pages }, (_, i) => i + 1)
            .filter(p => p === 1 || p === total_pages || Math.abs(p - page) <= 2)
            .reduce<(number | "...")[]>((acc, p, i, arr) => {
              if (i > 0 && p - (arr[i - 1] as number) > 1) acc.push("...");
              acc.push(p);
              return acc;
            }, [])
            .map((p, i) =>
              p === "..." ? (
                <span key={`ellipsis-${i}`} className="px-2 text-slate-600">…</span>
              ) : (
                <Link
                  key={p}
                  href={pageUrl(p as number)}
                  className={`rounded-xl border px-4 py-2 text-sm transition
                    ${p === page
                      ? "border-sky-500/40 bg-sky-500/15 text-sky-300 font-semibold"
                      : "border-white/10 bg-white/[0.04] text-slate-400 hover:bg-white/[0.08] hover:text-white"
                    }`}
                >
                  {p}
                </Link>
              ),
            )}

          {page < total_pages && (
            <Link
              href={pageUrl(page + 1)}
              className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-slate-300 hover:bg-white/[0.08] hover:text-white transition"
            >
              Next →
            </Link>
          )}
        </div>
      )}
    </main>
  );
}
