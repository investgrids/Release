/**
 * MIE Client — typed HTTP client for the Market Intelligence Engine.
 *
 * The MIE is the single source of truth for all intelligence in the app.
 * Every page should call this client instead of making isolated API calls
 * to /api/stories, /api/themes, or /api/events.
 *
 * Usage:
 *   import { mieClient } from "@/services/intelligence/mie-client";
 *
 *   const state = await mieClient.getState();
 *   const ctx   = await mieClient.getSymbolContext("RELIANCE");
 */

import type {
  MarketIntelligenceState,
  SymbolIntelligenceContext,
  MIEFeed,
  MIEStatus,
} from "@/types/intelligence";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const MIE_BASE = `${API_BASE}/api/mie`;

// ── Simple in-memory cache (client-side only) ─────────────────────────────────

interface CacheEntry<T> {
  data:      T;
  expiresAt: number;
}

const _cache = new Map<string, CacheEntry<unknown>>();

function _cacheGet<T>(key: string): T | null {
  const entry = _cache.get(key);
  if (!entry || Date.now() > entry.expiresAt) return null;
  return entry.data as T;
}

function _cacheSet<T>(key: string, data: T, ttlMs: number): void {
  _cache.set(key, { data, expiresAt: Date.now() + ttlMs });
}

// ── Fetch helper ───────────────────────────────────────────────────────────────

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${MIE_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    throw new Error(`MIE ${path} → ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ── TTLs ───────────────────────────────────────────────────────────────────────

const TTL_STATE   = 60_000;   // 60 s — backend refreshes every 5 min; front-end re-fetches every minute
const TTL_CONTEXT = 60_000;   // 60 s per symbol
const TTL_FEED    = 30_000;   // 30 s — feed is the live pulse
const TTL_STATUS  = 10_000;   // 10 s

// ── MIE Client ────────────────────────────────────────────────────────────────

export const mieClient = {
  /**
   * Full intelligence state — story + themes + events + signals.
   * This is the primary call. Most pages only need this.
   */
  async getState(forceRefresh = false): Promise<MarketIntelligenceState> {
    const key = "mie:state";
    if (!forceRefresh) {
      const hit = _cacheGet<MarketIntelligenceState>(key);
      if (hit) return hit;
    }
    const data = await _fetch<MarketIntelligenceState>("/state");
    _cacheSet(key, data, TTL_STATE);
    return data;
  },

  /**
   * Force the backend to recompute the state and cache it.
   * Use after a bulk ingest or manual trigger.
   */
  async forceRefresh() {
    _cache.delete("mie:state");
    return _fetch<{ refreshed: boolean; generated_at: string; market_session: string }>(
      "/state/refresh",
      { method: "POST" }
    );
  },

  /**
   * Intelligence context for a specific NSE symbol.
   * Filters the global state to events and themes relevant to this symbol.
   */
  async getSymbolContext(symbol: string): Promise<SymbolIntelligenceContext> {
    const key = `mie:ctx:${symbol.toUpperCase()}`;
    const hit = _cacheGet<SymbolIntelligenceContext>(key);
    if (hit) return hit;
    const data = await _fetch<SymbolIntelligenceContext>(`/context/${encodeURIComponent(symbol)}`);
    _cacheSet(key, data, TTL_CONTEXT);
    return data;
  },

  /**
   * Real-time intelligence feed — triaged events ranked by urgency.
   * High urgency (≥7) = breaking alert; medium (4-6) = informational.
   */
  async getFeed(opts: { limit?: number; minUrgency?: number; hours?: number } = {}): Promise<MIEFeed> {
    const { limit = 20, minUrgency = 4, hours = 8 } = opts;
    const key = `mie:feed:${limit}:${minUrgency}:${hours}`;
    const hit = _cacheGet<MIEFeed>(key);
    if (hit) return hit;
    const params = new URLSearchParams({
      limit:       String(limit),
      min_urgency: String(minUrgency),
      hours:       String(hours),
    });
    const data = await _fetch<MIEFeed>(`/feed?${params}`);
    _cacheSet(key, data, TTL_FEED);
    return data;
  },

  /**
   * Engine health — last refresh time, cache status, session.
   */
  async getStatus(): Promise<MIEStatus> {
    const key = "mie:status";
    const hit = _cacheGet<MIEStatus>(key);
    if (hit) return hit;
    const data = await _fetch<MIEStatus>("/status");
    _cacheSet(key, data, TTL_STATUS);
    return data;
  },

  /** Invalidate all cached MIE data (call after user triggers a refresh). */
  invalidateAll(): void {
    for (const key of _cache.keys()) {
      if (key.startsWith("mie:")) _cache.delete(key);
    }
  },
};

// ── React hooks (client components only) ──────────────────────────────────────

/**
 * Convenience: fetch the MIE state for use in a React useEffect.
 *
 * Example:
 *   useEffect(() => {
 *     fetchMIEState().then(setState).catch(console.error);
 *   }, []);
 */
export async function fetchMIEState(): Promise<MarketIntelligenceState | null> {
  try {
    return await mieClient.getState();
  } catch {
    return null;
  }
}

export async function fetchSymbolContext(symbol: string): Promise<SymbolIntelligenceContext | null> {
  try {
    return await mieClient.getSymbolContext(symbol);
  } catch {
    return null;
  }
}
