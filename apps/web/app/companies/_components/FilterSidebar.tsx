"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  sectors: string[];
  initialSector: string;
  initialCap: string;
  initialSort: string;
  initialQ: string;
  initialMinScore: string;
}

export function FilterSidebar({ sectors, initialSector, initialCap, initialSort, initialQ, initialMinScore }: Props) {
  const router = useRouter();
  const [sector, setSector] = useState(initialSector);
  const [cap, setCap] = useState(initialCap);
  const [sort, setSort] = useState(initialSort || "name");
  const [minScore, setMinScore] = useState(initialMinScore);

  // Real bug fixed here (found live, 2026-09-27): neither apply() nor
  // reset() ever set tab=all-companies, so using ANY sidebar filter
  // silently navigated back to the Overview tab (CompaniesHubPage
  // defaults to "overview" whenever `tab` is absent) instead of staying
  // on the filtered All Companies list the user was just looking at.
  function apply() {
    const sp = new URLSearchParams();
    sp.set("tab", "all-companies");
    if (initialQ.trim()) sp.set("q", initialQ.trim());
    if (sector) sp.set("sector", sector);
    if (cap) sp.set("cap", cap);
    if (sort && sort !== "name") sp.set("sort", sort);
    if (minScore) sp.set("min_score", minScore);
    sp.set("page", "1");
    router.push(`/companies?${sp.toString()}`);
  }

  function reset() {
    setSector("");
    setCap("");
    setSort("name");
    setMinScore("");
    router.push("/companies?tab=all-companies");
  }

  const selectCls =
    "w-full rounded-lg border border-surface-border/10 bg-surface-card px-3 py-2 text-[12px] text-text-primary outline-none transition focus:border-indigo-500/50 cursor-pointer";

  return (
    <aside className="w-[220px] shrink-0 space-y-5 rounded-xl border border-surface-border/7 bg-surface-card p-4 self-start">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-bold text-text-primary">Filters</span>
        <button
          onClick={reset}
          className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition"
        >
          Reset
        </button>
      </div>

      {/* Sector */}
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">Sector</p>
        <select value={sector} onChange={e => setSector(e.target.value)} className={selectCls}>
          <option value="">All Sectors</option>
          {sectors.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Market Cap */}
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">Market Cap</p>
        <select value={cap} onChange={e => setCap(e.target.value)} className={selectCls}>
          <option value="">All Market Caps</option>
          <option value="large">Large Cap</option>
          <option value="mid">Mid Cap</option>
          <option value="small">Small Cap</option>
        </select>
      </div>

      {/* MarketRipple Score */}
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">MarketRipple Score</p>
        <select value={minScore} onChange={e => setMinScore(e.target.value)} className={selectCls}>
          <option value="">Any Score</option>
          <option value="50">50+</option>
          <option value="60">60+</option>
          <option value="70">70+</option>
          <option value="80">80+</option>
          <option value="90">90+</option>
        </select>
      </div>

      {/* Sort */}
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">Sort By</p>
        <select value={sort} onChange={e => setSort(e.target.value)} className={selectCls}>
          <option value="name">Name A–Z</option>
          <option value="cap">Market Cap</option>
          <option value="sector">Sector</option>
          <option value="ticker">Ticker A–Z</option>
          <option value="score_desc">Score: High to Low</option>
          <option value="score_asc">Score: Low to High</option>
        </select>
      </div>

      {/* Apply */}
      <button
        onClick={apply}
        className="w-full rounded-lg bg-indigo-600 py-2.5 text-[13px] font-bold text-text-primary transition hover:bg-indigo-500 active:scale-[0.98]"
      >
        Apply Filters
      </button>
    </aside>
  );
}
