/**
 * Client-side in-memory TTL cache.
 * Prevents redundant fetch calls when multiple components
 * request the same data within a short window.
 */

interface CacheEntry<T> {
  ts: number;
  value: T;
}

class MemoryCache {
  private store = new Map<string, CacheEntry<unknown>>();

  getIfFresh<T>(key: string, ttlMs: number): T | null {
    const entry = this.store.get(key) as CacheEntry<T> | undefined;
    if (!entry) return null;
    if (Date.now() - entry.ts > ttlMs) return null;
    return entry.value;
  }

  set<T>(key: string, value: T): void {
    this.store.set(key, { ts: Date.now(), value });
  }

  delete(key: string): void {
    this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }
}

export const clientCache = new MemoryCache();

// TTL constants (milliseconds)
export const TTL_QUOTE           = 8_000;
export const TTL_INDICES         = 10_000;
export const TTL_HISTORY         = 5 * 60_000;
export const TTL_COMPANY         = 24 * 60 * 60_000;
export const TTL_MOVERS          = 15 * 60_000;
export const TTL_SECTORS         = 5 * 60_000;
export const TTL_STATUS          = 30_000;
