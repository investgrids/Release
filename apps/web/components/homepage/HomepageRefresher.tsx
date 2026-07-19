"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMarketIntelligence } from "@/hooks/useMarketIntelligence";

/**
 * Watches the shared MarketIntelligenceProvider state (already refreshed
 * every 60s, and sooner on live SSE signal) for a change and re-runs the
 * homepage's server-rendered sections. No longer polls its own endpoint —
 * see MarketIntelligenceProvider for the actual refresh/SSE logic.
 */
export function HomepageRefresher() {
  const router  = useRouter();
  const { state } = useMarketIntelligence();
  const seenRef = useRef<string | null>(null);
  const [toast, setToast] = useState(false);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const marker = state?.story?.generated_at ?? null;
    if (!marker) return;

    if (seenRef.current === null) {
      seenRef.current = marker;
      return;
    }
    if (marker !== seenRef.current) {
      seenRef.current = marker;
      router.refresh();
      setToast(true);
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      toastTimerRef.current = setTimeout(() => setToast(false), 4_000);
    }
  }, [state?.story?.generated_at, router]);

  useEffect(() => () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); }, []);

  if (!toast) return null;

  return (
    <div className="fixed left-1/2 top-20 z-50 -translate-x-1/2">
      <div className="flex items-center gap-2 rounded-full border border-violet-500/35 bg-[#0d0820]/95 px-4 py-2 text-[12px] font-semibold text-violet-300 shadow-xl backdrop-blur">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" />
        Market intelligence updated
      </div>
    </div>
  );
}
