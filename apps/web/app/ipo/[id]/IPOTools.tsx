"use client";

import { useState } from "react";
import { Minus, Plus } from "lucide-react";

const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

/** Interactive lot calculator: how much one application costs at the lower and upper end of the price band. */
export function LotCalculator({ lotSize, priceMin, priceMax }: { lotSize: number; priceMin: number | null; priceMax: number }) {
  const [lots, setLots] = useState(1);
  const set = (n: number) => setLots(Math.min(99, Math.max(1, n)));
  const shares = lots * lotSize;
  return (
    <section aria-label="Lot calculator" className="rounded-[22px] border border-surface-border/12 bg-gradient-to-br from-violet-500/[0.06] to-sky-500/[0.06] p-5">
      <h2 className="text-[15px] font-bold text-text-primary">Lot calculator</h2>
      <p className="mt-0.5 text-[12px] text-text-muted">One lot is {lotSize.toLocaleString("en-IN")} shares. Pick how many lots to see the application amount.</p>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center rounded-[14px] border border-surface-border/15 bg-surface-card">
          <button onClick={() => set(lots - 1)} disabled={lots <= 1} aria-label="One lot fewer" className="px-3 py-2.5 text-text-secondary transition hover:text-text-primary disabled:opacity-30"><Minus className="h-4 w-4" /></button>
          <input value={lots} onChange={e => set(parseInt(e.target.value.replace(/\D/g, ""), 10) || 1)} inputMode="numeric" aria-label="Number of lots"
            className="w-12 bg-transparent text-center text-[15px] font-bold tabular-nums text-text-primary outline-none" />
          <button onClick={() => set(lots + 1)} disabled={lots >= 99} aria-label="One lot more" className="px-3 py-2.5 text-text-secondary transition hover:text-text-primary disabled:opacity-30"><Plus className="h-4 w-4" /></button>
        </div>
        <p className="text-[13px] text-text-secondary"><span className="font-bold tabular-nums text-text-primary">{shares.toLocaleString("en-IN")}</span> shares</p>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-4">
        {priceMin != null && priceMin !== priceMax && (
          <div><dt className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">At lower band ({inr(priceMin)})</dt><dd className="mt-0.5 text-lg font-bold tabular-nums text-text-primary">{inr(shares * priceMin)}</dd></div>
        )}
        <div><dt className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">At upper band ({inr(priceMax)})</dt><dd className="mt-0.5 text-lg font-bold tabular-nums text-text-primary">{inr(shares * priceMax)}</dd></div>
      </dl>
      <p className="mt-3 text-[11px] text-text-muted">A calculation from NSE&apos;s published price band and lot size. Applications are made at the cut-off or a price within the band; this is not an allotment estimate.</p>
    </section>
  );
}

type Step = { label: string; date: string; state: "done" | "active" | "next" };

/** Open → close → listing, coloured by where today falls. */
export function Timeline({ steps }: { steps: Step[] }) {
  const dot = { done: "bg-emerald-500 border-emerald-500", active: "bg-violet-500 border-violet-500 ring-4 ring-violet-500/20", next: "bg-transparent border-surface-border/40" } as const;
  return (
    <ol aria-label="IPO timeline" className="relative grid gap-5 sm:grid-cols-3 sm:gap-0">
      {steps.map((s, i) => (
        <li key={s.label} className="relative flex gap-3 sm:block sm:pr-4">
          {i < steps.length - 1 && <span aria-hidden className={`absolute left-[5px] top-4 h-[calc(100%+8px)] w-px sm:left-4 sm:top-[5px] sm:h-px sm:w-[calc(100%-16px)] ${s.state === "done" ? "bg-emerald-500/60" : "bg-surface-border/25"}`} />}
          <span className={`relative z-10 mt-0.5 block h-3 w-3 shrink-0 rounded-full border-2 ${dot[s.state]}`} />
          <div className="sm:mt-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">{s.label}</p>
            <p className={`text-[14px] font-bold tabular-nums ${s.state === "next" ? "text-text-secondary" : "text-text-primary"}`}>{s.date}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
