"use client";

/**
 * MarketIntelligenceProvider — the single global owner of the frontend's
 * Market Intelligence Engine state.
 *
 * Owns:
 *   - the MIE state cache (via mieClient, one 60s-refreshed fetch shared by
 *     every consumer — no page fetches /api/mie/state on its own)
 *   - the 60s refresh timer
 *   - reacting to live signal from the app's one shared SSE connection
 *     (AlertProvider → /api/stream/events) by debouncing a forced refresh,
 *     rather than opening a second SSE connection of its own
 *   - version tracking, so consumers can tell when the underlying state
 *     actually changed vs. just re-rendered
 *
 * Pages never call mieClient or fetch /api/mie/* directly — they read this
 * Provider through the hooks in hooks/useMarketIntelligence.ts.
 */

import { createContext, useContext, useCallback, useEffect, useRef, useState } from "react";
import { mieClient } from "@/services/intelligence/mie-client";
import { useAlerts } from "@/components/AlertProvider";
import type { MarketIntelligenceState } from "@/types/intelligence";

interface MarketIntelligenceContextValue {
  state:       MarketIntelligenceState | null;
  loading:     boolean;
  error:       string | null;
  lastUpdated: number | null;
  refresh:     () => Promise<void>;
}

const MarketIntelligenceContext = createContext<MarketIntelligenceContextValue>({
  state: null,
  loading: true,
  error: null,
  lastUpdated: null,
  refresh: async () => {},
});

/** Internal — prefer the hooks in hooks/useMarketIntelligence.ts. */
export const useMarketIntelligenceContext = () => useContext(MarketIntelligenceContext);

const REFRESH_INTERVAL_MS = 60_000;
const LIVE_SIGNAL_DEBOUNCE_MS = 3_000;

export function MarketIntelligenceProvider({ children }: { children: React.ReactNode }) {
  const [state,       setState]       = useState<MarketIntelligenceState | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const versionRef = useRef<string | null>(null);

  const load = useCallback(async (force = false) => {
    try {
      const data = await mieClient.getState(force);
      setState(prev => {
        // Skip the state update (and the re-render it'd trigger everywhere)
        // if the version genuinely hasn't changed since last time.
        if (prev && data.version === versionRef.current && data.generated_at === prev.generated_at) {
          return prev;
        }
        versionRef.current = data.version;
        return data;
      });
      setLastUpdated(Date.now());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load market intelligence");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + steady 60s refresh.
  useEffect(() => {
    load();
    const id = setInterval(() => load(), REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  // Live signal from the app's single shared SSE connection: when a new
  // triaged event or score update arrives, debounce a forced refresh rather
  // than waiting for the next 60s tick — this is the "SSE updates" the
  // Provider is responsible for, without opening its own connection.
  const { intelligenceEvents, scoreUpdates } = useAlerts();
  const signalCount = intelligenceEvents.length + scoreUpdates.length;
  const prevSignalCount = useRef(signalCount);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (signalCount === prevSignalCount.current) return;
    prevSignalCount.current = signalCount;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => load(true), LIVE_SIGNAL_DEBOUNCE_MS);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [signalCount, load]);

  const refresh = useCallback(async () => { await load(true); }, [load]);

  return (
    <MarketIntelligenceContext.Provider value={{ state, loading, error, lastUpdated, refresh }}>
      {children}
    </MarketIntelligenceContext.Provider>
  );
}
