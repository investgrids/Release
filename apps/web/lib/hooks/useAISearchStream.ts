"use client";

import { useCallback, useRef, useState } from "react";
import { API_BASE_URL as API } from "@/lib/api";

export type StreamStage = "idle" | "intent" | "entities" | "evidence" | "reasoning" | "finalizing" | "done";

export interface StageEvent {
  stage: StreamStage;
  label: string;
  elapsedMs: number; // real, measured client-side at the moment this event arrived — never estimated
}

// Delivery-context for the current result — everything the feedback
// component needs to attach to a submission (see AISearchFeedback on the
// backend). Comes straight from SearchResponseV3 / the SSE "answer"
// envelope, never re-derived client-side.
export interface ResponseMeta {
  responseId: string | null;
  cached: boolean;
  latencyMs: number | null;
  provider: string | null;
}

interface UseAISearchStreamState {
  stage: StreamStage;
  stageLabel: string;
  stageHistory: StageEvent[];
  elapsedMs: number;
  result: any | null;
  meta: ResponseMeta | null;
  error: string | null;
  loading: boolean;
}

const INITIAL_STATE: UseAISearchStreamState = {
  stage: "idle",
  stageLabel: "",
  stageHistory: [],
  elapsedMs: 0,
  result: null,
  meta: null,
  error: null,
  loading: false,
};

/**
 * Consumes GET /api/ai/search/stream (SSE). Every stage label and elapsed-
 * time value shown to the user traces to a real backend checkpoint or a
 * real Date.now() delta — never a fabricated progress estimate (see the
 * V3 plan's explicit "never fake progress" principle, carried over from
 * the original loading-state redesign this session).
 *
 * Falls back to a blocking POST /api/ai/search/v3 if the EventSource
 * connection fails outright (proxy buffering, browser incompatibility,
 * network blip) — the query still resolves, just without live stage
 * updates, rather than hanging forever.
 */
export function useAISearchStream() {
  const [state, setState] = useState<UseAISearchStreamState>(INITIAL_STATE);
  const esRef = useRef<EventSource | null>(null);
  const t0Ref = useRef<number>(0);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cleanup = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  const fallbackToBlocking = useCallback(async (query: string, history: string[], sessionContext?: Record<string, unknown>) => {
    try {
      const res = await fetch(`${API}/api/ai/search/v3`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, history, session_context: sessionContext ?? null }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setState(s => ({
        ...s, result: data.result, loading: false, stage: "done",
        meta: {
          responseId: data.response_id ?? null, cached: !!data.cached,
          latencyMs: data.latency_ms ?? null, provider: data.provider ?? null,
        },
      }));
    } catch (err: any) {
      setState(s => ({ ...s, error: err?.message || "Search failed", loading: false }));
    }
  }, []);

  const run = useCallback((query: string, history: string[] = [], sessionContext?: Record<string, unknown>) => {
    cleanup();
    t0Ref.current = Date.now();
    setState({ ...INITIAL_STATE, loading: true, stage: "intent" });

    tickRef.current = setInterval(() => {
      setState(s => (s.loading ? { ...s, elapsedMs: Date.now() - t0Ref.current } : s));
    }, 100);

    // EventSource can only issue GET — query fits comfortably in a URL
    // (backend caps it at 500 chars); history is capped client-side too.
    // session_context (Phase 1.7) travels the same way, JSON-encoded —
    // it's deliberately compact (symbols/names only, see
    // useResearchSession.toApiContext), so this stays well under any URL
    // length concern even with a full session's worth of companies.
    const params = new URLSearchParams({
      q: query,
      history: JSON.stringify(history.slice(0, 10)),
      ...(sessionContext ? { session_context: JSON.stringify(sessionContext) } : {}),
    });
    const es = new EventSource(`${API}/api/ai/search/stream?${params.toString()}`);
    esRef.current = es;

    es.addEventListener("stage", (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      const elapsedMs = Date.now() - t0Ref.current;
      setState(s => ({
        ...s,
        stage: data.stage,
        stageLabel: data.label,
        elapsedMs,
        stageHistory: [...s.stageHistory, { stage: data.stage, label: data.label, elapsedMs }],
      }));
    });

    es.addEventListener("answer", (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setState(s => ({
        ...s, result: data.result, elapsedMs: Date.now() - t0Ref.current,
        meta: {
          responseId: data.response_id ?? null, cached: !!data.cached,
          latencyMs: data.latency_ms ?? null, provider: data.provider ?? null,
        },
      }));
    });

    es.addEventListener("done", () => {
      setState(s => ({ ...s, loading: false, stage: "done" }));
      cleanup();
    });

    es.addEventListener("error", (e: MessageEvent) => {
      // Server-side error emitted as a real SSE event (pipeline exception) —
      // distinct from EventSource's own connection-level onerror below.
      try {
        const data = JSON.parse((e as any).data);
        setState(s => ({ ...s, error: data.detail || "Search failed", loading: false }));
      } catch {
        // not a real event payload — let onerror below handle connection failures
      }
      cleanup();
    });

    es.onerror = () => {
      cleanup();
      setState(s => (s.result ? s : { ...s, loading: true })); // keep loading UI while we retry via blocking fetch
      fallbackToBlocking(query, history, sessionContext);
    };
  }, [cleanup, fallbackToBlocking]);

  const cancel = useCallback(() => {
    cleanup();
    setState(INITIAL_STATE);
  }, [cleanup]);

  return { ...state, run, cancel };
}
