"use client";

import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DISMISSED_KEY = "ig_dismissed_alerts";
const POLL_MS = 45_000;
const FRESH_MS = 30 * 60 * 1000; // only show alerts from last 30 minutes

export interface StockImpact {
  symbol: string; name: string;
  direction: "up" | "down";
  reason: string;
  magnitude: "high" | "medium" | "low";
}
export interface BreakingAlert {
  id: string; headline: string; summary: string;
  urgency: "critical" | "high";
  sentiment: "bearish" | "bullish" | "mixed";
  stocks: StockImpact[];
  sectors: string[];
  source: string; created_at: string; query: string;
}

interface AlertCtx {
  alerts: BreakingAlert[];
  dismiss: (id: string) => void;
}

const Ctx = createContext<AlertCtx>({ alerts: [], dismiss: () => {} });
export const useAlerts = () => useContext(Ctx);

function getDismissed(): string[] {
  try { return JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? "[]"); }
  catch { return []; }
}

export function AlertProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<BreakingAlert[]>([]);
  const dismissedRef  = useRef<string[]>([]);
  const seenOnLoadRef = useRef<Set<string> | null>(null); // IDs present at page-load (not shown)

  // Load dismissed list once on mount
  useEffect(() => { dismissedRef.current = getDismissed(); }, []);

  const check = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/alerts/breaking`);
      if (!res.ok) return;
      const data = await res.json();
      const now = Date.now();

      const incoming = (data.alerts as BreakingAlert[]).filter(a => {
        // Already dismissed by user
        if (dismissedRef.current.includes(a.id)) return false;
        // Older than 30 minutes — stale, skip
        const age = now - new Date(a.created_at).getTime();
        if (age > FRESH_MS) return false;
        return true;
      });

      // First poll: record existing IDs so we don't pop them up immediately
      if (seenOnLoadRef.current === null) {
        seenOnLoadRef.current = new Set(incoming.map(a => a.id));
        return; // don't show anything on first load
      }

      // Only surface alerts that weren't there when the page loaded
      const brandNew = incoming.filter(a => !seenOnLoadRef.current!.has(a.id));
      setAlerts(brandNew);
    } catch { /* backend offline — silently skip */ }
  }, []);

  useEffect(() => {
    check();
    const id = setInterval(check, POLL_MS);
    return () => clearInterval(id);
  }, [check]);

  const dismiss = useCallback((id: string) => {
    dismissedRef.current = [...dismissedRef.current, id];
    try {
      localStorage.setItem(DISMISSED_KEY, JSON.stringify(dismissedRef.current));
    } catch {}
    setAlerts(prev => prev.filter(a => a.id !== id));
  }, []);

  return <Ctx.Provider value={{ alerts, dismiss }}>{children}</Ctx.Provider>;
}
