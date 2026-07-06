"use client";

import { useEffect, useState } from "react";

type Metrics = { fcp: number | null; lcp: number | null };

function grade(ms: number | null): { letter: string; color: string } {
  if (ms === null) return { letter: "…",  color: "text-slate-500" };
  if (ms < 300)   return { letter: "A+",  color: "text-emerald-400" };
  if (ms < 600)   return { letter: "A",   color: "text-emerald-400" };
  if (ms < 1000)  return { letter: "B",   color: "text-amber-400" };
  if (ms < 2500)  return { letter: "C",   color: "text-orange-400" };
  return           { letter: "D",   color: "text-rose-400" };
}

export function PerfBadge() {
  const [m, setM] = useState<Metrics>({ fcp: null, lcp: null });
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const observers: PerformanceObserver[] = [];

    try {
      const fObs = new PerformanceObserver((list) => {
        const e = list.getEntriesByName("first-contentful-paint")[0];
        if (e) setM(p => ({ ...p, fcp: Math.round(e.startTime) }));
      });
      fObs.observe({ type: "paint", buffered: true });
      observers.push(fObs);
    } catch {}

    try {
      const lObs = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const last = entries[entries.length - 1] as any;
        if (last) setM(p => ({ ...p, lcp: Math.round(last.startTime) }));
      });
      lObs.observe({ type: "largest-contentful-paint", buffered: true });
      observers.push(lObs);
    } catch {}

    return () => observers.forEach(o => { try { o.disconnect(); } catch {} });
  }, []);

  if (!visible) return null;

  const fGrade = grade(m.fcp);
  const lGrade = grade(m.lcp);

  return (
    <div className="fixed bottom-20 right-4 z-50 rounded-2xl border border-white/10 bg-black/85 px-4 py-3 shadow-2xl font-mono select-none">
      <div className="flex items-center justify-between gap-4 mb-2">
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400">Fake Glass · Perf</p>
        </div>
        <button onClick={() => setVisible(false)} className="text-[10px] text-slate-600 hover:text-slate-400">✕</button>
      </div>
      <div className="space-y-1">
        <Row label="FCP" ms={m.fcp} g={fGrade} />
        <Row label="LCP" ms={m.lcp} g={lGrade} />
      </div>
      <p className="mt-2 text-[8px] text-slate-700">no backdrop-filter · 0 compositing layers</p>
    </div>
  );
}

function Row({ label, ms, g }: { label: string; ms: number | null; g: { letter: string; color: string } }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-7 text-[10px] text-slate-500">{label}</span>
      <span className="text-[13px] font-bold text-white w-16">{ms != null ? `${ms}ms` : "loading"}</span>
      <span className={`text-[11px] font-black ${g.color}`}>{g.letter}</span>
    </div>
  );
}
