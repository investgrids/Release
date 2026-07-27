"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Research Session Memory (Phase 1.7) — sessionStorage-backed, NOT
 * localStorage: this is deliberately scoped to the current browser tab
 * session (spec: "Never remember across browser sessions. Across users.
 * After Clear Session."), unlike AI Search History's localStorage, which
 * persists across visits on purpose. Closing the tab loses it; that's
 * correct, not a bug.
 */
const STORAGE_KEY = "mr_research_session";
const SESSION_EVENT = "research-session-updated";

export interface SessionEntity {
  symbol: string;
  name: string;
}
export interface SessionQuery {
  id: string;
  text: string;
  responseId: string | null;
  timestamp: number;
}
export interface ResearchSessionState {
  companies: SessionEntity[];
  sectors: string[];
  events: string[];
  policies: string[];
  themes: string[];
  queries: SessionQuery[];
  timeHorizon: string | null;
  riskTolerance: string | null;
  investmentGoal: string | null;
  currentPosition: string | null;
  currentVerdict: string | null;
}

const EMPTY_STATE: ResearchSessionState = {
  companies: [], sectors: [], events: [], policies: [], themes: [], queries: [],
  timeHorizon: null, riskTolerance: null, investmentGoal: null, currentPosition: null, currentVerdict: null,
};

function read(): ResearchSessionState {
  if (typeof window === "undefined") return EMPTY_STATE;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_STATE;
    return { ...EMPTY_STATE, ...JSON.parse(raw) };
  } catch {
    return EMPTY_STATE;
  }
}

function write(state: ResearchSessionState) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    window.dispatchEvent(new Event(SESSION_EVENT));
  } catch {
    /* sessionStorage unavailable (private mode, quota) — session memory just doesn't persist across renders in that case */
  }
}

const MAX_LIST = 12;
function dedupePush<T>(list: T[], items: T[], key: (t: T) => string, max = MAX_LIST): T[] {
  const seen = new Set(list.map(key));
  const out = [...list];
  for (const item of items) {
    const k = key(item);
    if (!seen.has(k)) {
      seen.add(k);
      out.push(item);
    }
  }
  return out.slice(-max);
}

/**
 * Companies/sectors/events/policies/themes accumulated purely from real
 * response data (never invented) — see the call site in ai-search/page.tsx
 * for exactly what gets folded in after each successful search.
 */
export function useResearchSession() {
  const [state, setState] = useState<ResearchSessionState>(EMPTY_STATE);

  useEffect(() => {
    setState(read());
    const onUpdate = () => setState(read());
    window.addEventListener(SESSION_EVENT, onUpdate);
    window.addEventListener("storage", onUpdate);
    return () => {
      window.removeEventListener(SESSION_EVENT, onUpdate);
      window.removeEventListener("storage", onUpdate);
    };
  }, []);

  const addFromResult = useCallback((query: string, responseId: string | null, data: {
    companies?: SessionEntity[]; sectors?: string[]; events?: string[]; policies?: string[]; themes?: string[];
    verdict?: string | null;
  }) => {
    const prev = read();
    const next: ResearchSessionState = {
      ...prev,
      companies: dedupePush(prev.companies, data.companies ?? [], c => c.symbol),
      sectors: dedupePush(prev.sectors, data.sectors ?? [], s => s),
      events: dedupePush(prev.events, data.events ?? [], e => e),
      policies: dedupePush(prev.policies, data.policies ?? [], p => p),
      themes: dedupePush(prev.themes, data.themes ?? [], t => t),
      queries: dedupePush(prev.queries, [{ id: `q-${Date.now()}`, text: query, responseId, timestamp: Date.now() }], q => q.text, 30),
      currentVerdict: data.verdict ?? prev.currentVerdict,
    };
    write(next);
    setState(next);
  }, []);

  const setPreference = useCallback((key: "timeHorizon" | "riskTolerance" | "investmentGoal" | "currentPosition", value: string | null) => {
    const prev = read();
    const next = { ...prev, [key]: value };
    write(next);
    setState(next);
  }, []);

  const removeCompany = useCallback((symbol: string) => {
    const prev = read();
    const next = { ...prev, companies: prev.companies.filter(c => c.symbol !== symbol) };
    write(next);
    setState(next);
  }, []);

  const removeSector = useCallback((sector: string) => {
    const prev = read();
    const next = { ...prev, sectors: prev.sectors.filter(s => s !== sector) };
    write(next);
    setState(next);
  }, []);

  const clear = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
      window.dispatchEvent(new Event(SESSION_EVENT));
    } catch { /* */ }
    setState(EMPTY_STATE);
  }, []);

  // Compact form sent to the backend — symbols/names only, not the full
  // per-query history, keeping the request body small (spec: "Session
  // state should be lightweight").
  const toApiContext = useCallback(() => {
    if (state.companies.length === 0 && state.sectors.length === 0) return undefined;
    return {
      companies: state.companies.map(c => c.symbol),
      sectors: state.sectors,
      time_horizon: state.timeHorizon,
      risk_tolerance: state.riskTolerance,
      investment_goal: state.investmentGoal,
      current_position: state.currentPosition,
    };
  }, [state]);

  return { ...state, addFromResult, setPreference, removeCompany, removeSector, clear, toApiContext };
}
