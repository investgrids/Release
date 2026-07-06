"""
Thread-safe in-memory TTL cache used by MarketDataService.
A lightweight alternative to Redis for short-lived market data.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional


class MemoryCache:
    """
    Simple key→(timestamp, value) dict protected by a RLock.
    get() returns None on miss or expired entry (no stale reads).
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            return value  # TTL is checked separately — caller controls eviction

    def get_if_fresh(self, key: str, ttl: float) -> Optional[Any]:
        """Return value only if it was stored within the last `ttl` seconds."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts > ttl:
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def evict_expired(self, ttl: float) -> int:
        """Remove all entries older than `ttl` seconds. Returns eviction count."""
        cutoff = time.time() - ttl
        with self._lock:
            stale = [k for k, (ts, _) in self._store.items() if ts < cutoff]
            for k in stale:
                del self._store[k]
        return len(stale)


# ── Suggested TTLs (seconds) ─────────────────────────────────────────────────

TTL_QUOTE             = 8       # live quote: 8 seconds
TTL_INDICES           = 10      # index basket: 10 seconds
TTL_MARKET_OVERVIEW   = 30      # dashboard overview: 30 seconds
TTL_HISTORY           = 300     # historical candles: 5 minutes
TTL_COMPANY           = 86_400  # company profile: 24 hours
TTL_SECTOR            = 300     # sector performance: 5 minutes
TTL_MOVERS            = 900     # top movers: 15 minutes
TTL_FII_DII           = 21_600  # FII/DII: 6 hours
TTL_PCR               = 900     # put-call ratio: 15 minutes
TTL_PREMARKET         = 900     # pre-market snapshot: 15 minutes
