"use client";

/**
 * MarketSessionGate — wraps the homepage with:
 *  1. Auto-refresh via router.refresh() when an urgency >= 8 SSE event arrives
 *  2. A live market session indicator (Pre-Market / Live / After-Market)
 *
 * Mount this as a client component inside the server-rendered homepage layout.
 * It reads from the global AlertProvider SSE stream (no extra connections).
 */

import { useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAlerts } from "@/components/AlertProvider";

export function MarketSessionGate() {
  const { intelligenceEvents } = useAlerts();
  const router = useRouter();
  const lastRefreshRef = useRef<number>(0);
  const MIN_REFRESH_INTERVAL_MS = 60_000; // throttle: at most 1 refresh/minute

  const maybeRefresh = useCallback(() => {
    const now = Date.now();
    if (now - lastRefreshRef.current < MIN_REFRESH_INTERVAL_MS) return;
    lastRefreshRef.current = now;
    router.refresh();
  }, [router]);

  // Watch for high-urgency events that warrant a homepage refresh
  useEffect(() => {
    if (intelligenceEvents.length === 0) return;
    const latest = intelligenceEvents[0];
    if (latest?.refresh_homepage) {
      maybeRefresh();
    }
  }, [intelligenceEvents, maybeRefresh]);

  // No visible output — pure side-effect component
  return null;
}

// ── Session badge — purely client-side clock ──────────────────────────────────

export type MarketSession = "pre-market" | "live" | "after-market" | "closed";

function getSession(): MarketSession {
  const now = new Date();
  // Convert to IST (UTC+5:30)
  const istMs = now.getTime() + (5 * 60 + 30) * 60_000;
  const ist = new Date(istMs);
  const h = ist.getUTCHours();
  const m = ist.getUTCMinutes();
  const dow = ist.getUTCDay();
  const mins = h * 60 + m;

  if (dow === 0 || dow === 6) return "closed"; // weekend
  if (mins >= 9 * 60 + 15 && mins < 15 * 60 + 30) return "live";
  if (mins >= 9 * 60 && mins < 9 * 60 + 15) return "pre-market";
  if (mins >= 15 * 60 + 30 && mins < 19 * 60) return "after-market";
  return "closed";
}

const SESSION_STYLES: Record<MarketSession, { label: string; cls: string }> = {
  "live":        { label: "Market Live",        cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
  "pre-market":  { label: "Pre-Market",         cls: "bg-amber-500/15 text-amber-400 border-amber-500/30" },
  "after-market":{ label: "After-Market",       cls: "bg-blue-500/15 text-blue-400 border-blue-500/30" },
  "closed":      { label: "Market Closed",      cls: "bg-slate-500/15 text-slate-400 border-slate-500/30" },
};

export function MarketSessionBadge() {
  const session = getSession();
  const { label, cls } = SESSION_STYLES[session];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${cls}`}
    >
      {session === "live" && (
        <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
      )}
      {label}
    </span>
  );
}
