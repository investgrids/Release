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
    <form onSubmit={handleSubmit} className="relative">
      <div className="flex items-center overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] transition focus-within:border-sky-500/40 focus-within:bg-sky-500/[0.02]">
        <Search className="ml-4 h-4 w-4 shrink-0 text-slate-500" />
        <input
          type="text"
          value={value}
          onChange={handleChange}
          placeholder="TCS, Tata, Reliance, HAL, Manappuram, L&T, Natco…"
          className="flex-1 bg-transparent px-4 py-4 text-sm text-white outline-none placeholder:text-slate-500"
          autoComplete="off"
          spellCheck={false}
        />
        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="mr-2 p-1.5 text-slate-500 hover:text-slate-300 transition"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </form>
  );
}
