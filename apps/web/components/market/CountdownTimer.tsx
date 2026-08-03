"use client";

import { useEffect, useState } from "react";

export function CountdownTimer({
  initialSeconds,
  label,
  onComplete,
}: {
  initialSeconds: number | null;
  label: string;
  onComplete?: () => void;
}) {
  const [secs, setSecs] = useState<number | null>(initialSeconds);

  useEffect(() => {
    if (secs === null || secs <= 0) return;
    const id = setInterval(() => {
      setSecs(prev => {
        if (prev === null || prev <= 1) { onComplete?.(); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  if (secs === null || secs <= 0) return null;

  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;

  const pad = (n: number) => String(n).padStart(2, "0");

  return (
    <div className="flex flex-col items-center">
      <p className="text-[9px] font-semibold uppercase tracking-widest text-text-muted mb-1">{label}</p>
      <div className="flex items-end gap-0.5">
        {h > 0 && (
          <>
            <div className="flex flex-col items-center">
              <span className="text-[20px] font-black text-text-primary leading-none tabular-nums">{pad(h)}</span>
              <span className="text-[8px] text-text-muted mt-0.5">HRS</span>
            </div>
            <span className="text-[17px] font-black text-text-muted mb-0.5">:</span>
          </>
        )}
        <div className="flex flex-col items-center">
          <span className="text-[20px] font-black text-text-primary leading-none tabular-nums">{pad(m)}</span>
          <span className="text-[8px] text-text-muted mt-0.5">MINS</span>
        </div>
        <span className="text-[17px] font-black text-text-muted mb-0.5">:</span>
        <div className="flex flex-col items-center">
          <span className="text-[20px] font-black text-text-primary leading-none tabular-nums">{pad(s)}</span>
          <span className="text-[8px] text-text-muted mt-0.5">SECS</span>
        </div>
      </div>
    </div>
  );
}
