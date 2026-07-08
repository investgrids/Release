"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  sectors: string[];
  initialSector: string;
  initialCap: string;
  initialSort: string;
  initialQ: string;
}

export function FilterSidebar({ sectors, initialSector, initialCap, initialSort, initialQ }: Props) {
  const router = useRouter();
  const [sector, setSector] = useState(initialSector);
  const [cap, setCap] = useState(initialCap);
  const [sort, setSort] = useState(initialSort || "name");

  function apply() {
    const sp = new URLSearchParams();
    if (initialQ.trim()) sp.set("q", initialQ.trim());
    if (sector) sp.set("sector", sector);
    if (cap) sp.set("cap", cap);
    if (sort && sort !== "name") sp.set("sort", sort);
    sp.set("page", "1");
    const qs = sp.toString();
    router.push(`/companies${qs ? `?${qs}` : ""}`);
  }

  function reset() {
    setSector("");
    setCap("");
    setSort("name");
    router.push("/companies");
  }

  const selectCls =
    "w-full rounded-lg border border-white/10 bg-[#131826] px-3 py-2 text-[12px] text-white outline-none transition focus:border-indigo-500/50 cursor-pointer";

  return (
    <aside className="w-[220px] shrink-0 space-y-5 rounded-xl border border-white/[0.07] bg-[#0a0d16] p-4 self-start">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-bold text-white">Filters</span>
        <button
          onClick={reset}
          className="text-[11px] text-sky-400 hover:text-sky-300 transition"
        >
          Reset
        </button>
      </div>

      {/* Exchange */}
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Exchange</p>
        <label className="mb-2 flex cursor-pointer items-center gap-2 text-[12px] text-slate-300">
          <div className="flex h-4 w-4 items-center justify-center rounded border border-indigo-500 bg-indigo-500/20">
            <div className="h-2 w-2 rounded-sm bg-indigo-400" />
          </div>
          NSE
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-[12px] text-slate-500">
          <div className="h-4 w-4 rounded border border-white/10 bg-white/[0.03]" />
          BSE
        </label>
      </div>

      {/* Sector */}
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Sector</p>
        <select value={sector} onChange={e => setSector(e.target.value)} className={selectCls}>
          <option value="">All Sectors</option>
          {sectors.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Market Cap */}
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Market Cap</p>
        <select value={cap} onChange={e => setCap(e.target.value)} className={selectCls}>
          <option value="">All Market Caps</option>
          <option value="large">Large Cap</option>
          <option value="mid">Mid Cap</option>
          <option value="small">Small Cap</option>
        </select>
      </div>

      {/* Sort */}
      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Sort By</p>
        <select value={sort} onChange={e => setSort(e.target.value)} className={selectCls}>
          <option value="name">Name A–Z</option>
          <option value="cap">Market Cap</option>
          <option value="sector">Sector</option>
        </select>
      </div>

      {/* Apply */}
      <button
        onClick={apply}
        className="w-full rounded-lg bg-indigo-600 py-2.5 text-[13px] font-bold text-white transition hover:bg-indigo-500 active:scale-[0.98]"
      >
        Apply Filters
      </button>
    </aside>
  );
}
