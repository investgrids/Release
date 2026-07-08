"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, X } from "lucide-react";

interface Props {
  defaultValue: string;
  sector: string;
  cap: string;
  sort: string;
}

export function CompanySearchInput({ defaultValue, sector, cap, sort }: Props) {
  const [value, setValue] = useState(defaultValue);
  const router = useRouter();
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const navigate = useCallback(
    (q: string) => {
      const sp = new URLSearchParams();
      if (q.trim()) sp.set("q", q.trim());
      if (sector) sp.set("sector", sector);
      if (cap) sp.set("cap", cap);
      if (sort && sort !== "name") sp.set("sort", sort);
      sp.set("page", "1");
      const qs = sp.toString();
      router.push(`/companies${qs ? `?${qs}` : ""}`);
    },
    [router, sector, cap, sort],
  );

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    setValue(v);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => navigate(v), 350);
  }

  function handleClear() {
    setValue("");
    clearTimeout(timer.current);
    navigate("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    clearTimeout(timer.current);
    navigate(value);
  }

  return (
    <form onSubmit={handleSubmit} className="relative w-full">
      <div className="flex items-center overflow-hidden rounded-xl border border-white/10 bg-[#0a0d16] transition focus-within:border-indigo-500/40">
        <Search className="ml-4 h-4 w-4 shrink-0 text-slate-500" />
        <input
          type="text"
          value={value}
          onChange={handleChange}
          placeholder="Search by company name, ticker, keyword…"
          className="flex-1 bg-transparent px-3 py-3 text-[13px] text-white outline-none placeholder:text-slate-500"
          autoComplete="off"
          spellCheck={false}
        />
        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="mr-1 rounded-md border border-white/10 px-2.5 py-1 text-[11px] text-slate-400 transition hover:text-white"
          >
            Clear
          </button>
        )}
      </div>
    </form>
  );
}
