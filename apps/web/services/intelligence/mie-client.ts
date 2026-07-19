/**
 * MIE Client — typed HTTP client for the Market Intelligence Engine.
 *
 * Architecture note: the backend organizes itself as a Market Intelligence
 * Platform (MIP) — this Intelligence Engine ("the Brain", /api/mie/*) sits
 * alongside the Scoring Engine, Ripple Engine, Story Engine, Opportunity
 * Engine, Theme Engine, AI Search Context, Publishing Engine, Live Feed
 * Engine, and Alert Engine. Those other engines are consumed *through* the
 * Intelligence Engine's aggregated state (MarketIntelligenceState) — this
 * client is the frontend's single door into that state, not a door into
 * any one engine individually.
 *
 * No page should call /api/intelligence/*, /api/story/*, /api/theme/*, or
 * similar intelligence-shaped endpoints directly. Everything goes through
 * this client — see components/MarketIntelligenceProvider.tsx and
 * hooks/useMarketIntelligence.ts for how pages actually consume it.
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

// Request de-duplication: if two callers ask for the same key while a fetch
// is already in flight, the second caller awaits the same promise instead
// of firing a second network request.
const _inFlight = new Map<string, Promise<unknown>>();

function _cacheGet<T>(key: string): T | null {
  const entry = _cache.get(key);
  if (!entry || Date.now() > entry.expiresAt) return null;
  return entry.data as T;
}

function _cacheSet<T>(key: string, data: T, ttlMs: number): void {
  _cache.set(key, { data, expiresAt: Date.now() + ttlMs });
}

async function _dedupedFetch<T>(key: string, ttlMs: number, fetcher: () => Promise<T>, forceRefresh = false): Promise<T> {
  if (!forceRefresh) {
    const hit = _cacheGet<T>(key);
    if (hit !== null) return hit;
    const pending = _inFlight.get(key);
    if (pending) return pending as Promise<T>;
  }

  const promise = fetcher()
    .then(data => {
      _cacheSet(key, data, ttlMs);
      _inFlight.delete(key);
      return data;
    })
    .catch(err => {
      _inFlight.delete(key);
      throw err;
    });

  _inFlight.set(key, promise);
  return promise;
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

// ── TTLs — match the platform's cache rules ────────────────────────────────────

const TTL_STATE   = 60_000;   // 60 s
const TTL_CONTEXT = 30_000;   // 30 s per symbol
const TTL_FEED     = 30_000;  // 30 s — initial seed only; live updates come via SSE
const TTL_STATUS   = 10_000;  // 10 s

// ── MIE Client ────────────────────────────────────────────────────────────────

export const mieClient = {
  /**
   * Full intelligence state — story + themes + events + signals + the
   * newsroom-style summary fields (biggest_opportunity, biggest_risk,
   * companies_to_watch, market_drivers, tomorrow_watch, market_health, ...).
   * This is the primary call. Almost every page only needs this.
   */
  async getState(forceRefresh = false): Promise<MarketIntelligenceState> {
    return _dedupedFetch("mie:state", TTL_STATE, () => _fetch<MarketIntelligenceState>("/state"), forceRefresh);
  },

  /** Alias kept for the exact method name the platform spec asked for. */
  async getMIEState(forceRefresh = false): Promise<MarketIntelligenceState> {
    return this.getState(forceRefresh);
  },

  /**
   * Force the backend to recompute the state and cache it, then clear the
   * client-side cache entry so the next getState() call fetches fresh data.
   */
  async forceRefresh() {
    _cache.delete("mie:state");
    const result = await _fetch<{ refreshed: boolean; generated_at: string; market_session: string }>(
      "/state/refresh",
      { method: "POST" }
    );
    return result;
  },

  /**
   * Intelligence context for a specific NSE symbol — /api/mie/company/{symbol}.
   */
  async getCompanyContext(symbol: string, forceRefresh = false): Promise<SymbolIntelligenceContext> {
    const key = `mie:company:${symbol.toUpperCase()}`;
    return _dedupedFetch(key, TTL_CONTEXT, () => _fetch<SymbolIntelligenceContext>(`/company/${encodeURIComponent(symbol)}`), forceRefresh);
  },

  /** Older name, same endpoint family — kept so existing call sites don't break mid-migration. */
  async getSymbolContext(symbol: string): Promise<SymbolIntelligenceContext> {
    return this.getCompanyContext(symbol);
  },

  /**
   * Real-time intelligence feed — used only as the *initial seed* before the
   * SSE stream (via MarketIntelligenceProvider) takes over with live updates.
   */
  async getLiveFeed(opts: { limit?: number; minUrgency?: number; hours?: number } = {}): Promise<MIEFeed> {
    const { limit = 20, minUrgency = 4, hours = 8 } = opts;
    const key = `mie:feed:${limit}:${minUrgency}:${hours}`;
    const params = new URLSearchParams({
      limit:       String(limit),
      min_urgency: String(minUrgency),
      hours:       String(hours),
    });
    return _dedupedFetch(key, TTL_FEED, () => _fetch<MIEFeed>(`/feed?${params}`));
  },

  /**
   * Engine health — last refresh time, cache status, version, events processed.
   */
  async getStatus(): Promise<MIEStatus> {
    return _dedupedFetch("mie:status", TTL_STATUS, () => _fetch<MIEStatus>("/status"));
  },

  /** Invalidate all cached MIE data (call after user triggers a manual refresh). */
  invalidateAll(): void {
    for (const key of _cache.keys()) {
      if (key.startsWith("mie:")) _cache.delete(key);
    }
  },
};
