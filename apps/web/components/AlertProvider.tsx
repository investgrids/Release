"use client";

import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { API_BASE_URL as API } from "@/lib/api";

const DISMISSED_KEY = "ig_dismissed_alerts";
const FRESH_MS = 30 * 60 * 1000;

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

/** Lightweight intelligence event from the SSE stream. */
export interface IntelligenceEvent {
  id: string;
  headline: string;
  urgency: number;
  sentiment: string;
  direction: string;
  one_liner: string;
  themes: string[];
  sectors: string[];
  tickers: string[];
  refresh_homepage: boolean;
  source: string;
  ts: string;
}

interface AlertCtx {
  alerts: BreakingAlert[];
  intelligenceEvents: IntelligenceEvent[];
  dismiss: (id: string) => void;
}

const Ctx = createContext<AlertCtx>({ alerts: [], intelligenceEvents: [], dismiss: () => {} });
export const useAlerts = () => useContext(Ctx);

function getDismissed(): string[] {
  try { return JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? "[]"); }
  catch { return []; }
}

export function AlertProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<BreakingAlert[]>([]);
  const [intelligenceEvents, setIntelligenceEvents] = useState<IntelligenceEvent[]>([]);
  const dismissedRef = useRef<string[]>([]);
  const seenOnLoadRef = useRef<Set<string> | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { dismissedRef.current = getDismissed(); }, []);

  // ── Initial poll for existing breaking alerts ─────────────────────────────
  const pollAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/alerts/breaking`);
      if (!res.ok) return;
      const data = await res.json();
      const now = Date.now();

      const incoming = (data.alerts as BreakingAlert[]).filter(a => {
        if (dismissedRef.current.includes(a.id)) return false;
        const age = now - new Date(a.created_at).getTime();
        return age <= FRESH_MS;
      });

      if (seenOnLoadRef.current === null) {
        seenOnLoadRef.current = new Set(incoming.map(a => a.id));
        return;
      }

      const brandNew = incoming.filter(a => !seenOnLoadRef.current!.has(a.id));
      if (brandNew.length > 0) setAlerts(brandNew);
    } catch { /* backend offline */ }
  }, []);

  // ── SSE connection for live intelligence events ───────────────────────────
  const connectSSE = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
    }

    const es = new EventSource(`${API}/api/stream/events`);
    esRef.current = es;

    es.addEventListener("alert", (e: MessageEvent) => {
      try {
        const evt: IntelligenceEvent = JSON.parse(e.data);
        setIntelligenceEvents(prev => {
          const next = [evt, ...prev.filter(x => x.id !== evt.id)].slice(0, 30);
          return next;
        });
        // If urgency >= 8, also surface as a breaking-alert-style notification
        if (evt.urgency >= 8) {
          const synth: BreakingAlert = {
            id: `intel-${evt.id}`,
            headline: evt.headline,
            summary: evt.one_liner || evt.headline,
            urgency: evt.urgency >= 9 ? "critical" : "high",
            sentiment: evt.sentiment === "bullish" ? "bullish" : evt.sentiment === "bearish" ? "bearish" : "mixed",
            stocks: evt.tickers.slice(0, 3).map(sym => ({
              symbol: sym, name: sym,
              direction: evt.direction === "up" ? "up" : "down",
              reason: evt.one_liner || "",
              magnitude: evt.urgency >= 8 ? "high" : "medium",
            })),
            sectors: evt.sectors,
            source: evt.source,
            created_at: evt.ts,
            query: evt.headline,
          };
          setAlerts(prev => {
            if (dismissedRef.current.includes(synth.id)) return prev;
            return [synth, ...prev.filter(a => a.id !== synth.id)];
          });
        }
      } catch { /* parse error */ }
    });

    es.addEventListener("update", (e: MessageEvent) => {
      try {
        const evt: IntelligenceEvent = JSON.parse(e.data);
        setIntelligenceEvents(prev => [evt, ...prev.filter(x => x.id !== evt.id)].slice(0, 30));
      } catch { /* parse error */ }
    });

    es.onerror = () => {
      es.close();
      esRef.current = null;
      // Reconnect after 10s
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      reconnectTimer.current = setTimeout(connectSSE, 10_000);
    };
  }, []);

  useEffect(() => {
    pollAlerts();
    connectSSE();

    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [pollAlerts, connectSSE]);

  const dismiss = useCallback((id: string) => {
    dismissedRef.current = [...dismissedRef.current, id];
    try {
      localStorage.setItem(DISMISSED_KEY, JSON.stringify(dismissedRef.current));
    } catch {}
    setAlerts(prev => prev.filter(a => a.id !== id));
  }, []);

  return (
    <Ctx.Provider value={{ alerts, intelligenceEvents, dismiss }}>
      {children}
    </Ctx.Provider>
  );
}
