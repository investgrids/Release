"""
MarketDataService — the single entry point for all market data in the application.

What it does:
  1. Selects the active provider (Fyers when configured, YFinance otherwise)
  2. Applies a two-level TTL cache (memory first, Redis on miss)
  3. Handles retries and graceful degradation transparently
  4. Exposes one clean async API — callers never know which provider is active

Usage:
    from app.services.market_data_service import market_data_service

    quote = await market_data_service.get_quote("RELIANCE")
    candles = await market_data_service.get_historical_candles("TCS", period="6M")

Adding a new provider:
    1. Implement MarketDataProvider ABC
    2. Add detection logic in _build_provider()
    3. The rest of the application is unchanged.
"""
from __future__ import annotations

import logging
from typing import Optional

from .interfaces import MarketDataProvider
from .types import Quote, Company, Candle, IndexQuote, SectorPerformance, MarketStatus, TopMover
from .cache.memory_cache import (
    MemoryCache,
    TTL_QUOTE, TTL_INDICES, TTL_HISTORY, TTL_COMPANY,
    TTL_SECTOR, TTL_MOVERS, TTL_MARKET_OVERVIEW,
)

log = logging.getLogger(__name__)


def _build_provider() -> MarketDataProvider:
    """
    Select the best available provider at startup.

    Decision order:
      1. Fyers — FYERS_CLIENT_ID + token from env var OR Redis cache
      2. YFinance — always available, no credentials needed

    If TOTP credentials are also set (FYERS_LOGIN_ID / FYERS_PIN / FYERS_TOTP_KEY),
    the async upgrade_to_fyers() is called from the app lifespan to auto-auth
    and swap the provider without a restart.
    """
    try:
        from app.core.config import settings

        client_id    = getattr(settings, "fyers_client_id",    "")
        access_token = getattr(settings, "fyers_access_token", "")
        secret_key   = getattr(settings, "fyers_secret_key",   "")
        redirect_uri = getattr(settings, "fyers_redirect_uri", "https://127.0.0.1:8000/api/data/auth/callback")

        if client_id:
            # If no token in env, try Redis (token stored there after TOTP auth / OAuth)
            if not access_token:
                try:
                    from .providers.fyers import FyersAuthManager
                    _mgr = FyersAuthManager(client_id, secret_key, redirect_uri)
                    access_token = _mgr.get_token() or ""
                    if access_token:
                        log.info("market_data.fyers_token_from_redis")
                except Exception:
                    pass

            if access_token:
                try:
                    from .providers.fyers import FyersProvider
                    provider = FyersProvider(
                        client_id    = client_id,
                        access_token = access_token,
                        secret_key   = secret_key,
                        redirect_uri = redirect_uri,
                    )
                    log.info("market_data.provider=Fyers")
                    return provider
                except Exception as exc:
                    log.warning("market_data.fyers_init_failed error=%s", str(exc))
    except Exception:
        pass

    from .providers.yfinance import YFinanceProvider
    log.info("market_data.provider=YFinance (Fyers credentials not set or token missing)")
    return YFinanceProvider()


class MarketDataService:
    """
    Application-level facade over the active MarketDataProvider.
    Adds caching, rate-limit awareness, and graceful degradation.
    """

    def __init__(self) -> None:
        self._provider: MarketDataProvider = _build_provider()
        self._cache    = MemoryCache()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def supports_websocket(self) -> bool:
        return self._provider.supports_websocket

    # ── Quote ─────────────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> Optional[Quote]:
        key = f"quote:{symbol.upper()}"
        cached = self._cache.get_if_fresh(key, TTL_QUOTE)
        if cached is not None:
            return cached
        result = await self._provider.get_quote(symbol)
        if result:
            self._cache.set(key, result)
        return result

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        """Batch quote fetch — cache individual quotes, batch-fetch misses."""
        cached, missing = [], []
        for sym in symbols:
            key = f"quote:{sym.upper()}"
            hit = self._cache.get_if_fresh(key, TTL_QUOTE)
            if hit:
                cached.append(hit)
            else:
                missing.append(sym)

        if missing:
            fresh = await self._provider.get_quotes(missing)
            for q in fresh:
                self._cache.set(f"quote:{q.symbol}", q)
            cached.extend(fresh)

        return cached

    # ── Company ───────────────────────────────────────────────────────────────

    async def get_company(self, symbol: str) -> Optional[Company]:
        key = f"company:{symbol.upper()}"
        cached = self._cache.get_if_fresh(key, TTL_COMPANY)
        if cached is not None:
            return cached
        result = await self._provider.get_company(symbol)
        if result:
            self._cache.set(key, result)
        return result

    # ── Historical candles ────────────────────────────────────────────────────

    async def get_historical_candles(
        self, symbol: str, period: str = "6M", interval: str = "1d"
    ) -> list[Candle]:
        key = f"candles:{symbol.upper()}:{period}"
        cached = self._cache.get_if_fresh(key, TTL_HISTORY)
        if cached is not None:
            return cached
        result = await self._provider.get_historical_candles(symbol, period, interval)
        if result:
            self._cache.set(key, result)
        return result

    # ── Indices ───────────────────────────────────────────────────────────────

    async def get_indices(self) -> list[IndexQuote]:
        key = "indices:all"
        cached = self._cache.get_if_fresh(key, TTL_INDICES)
        if cached is not None:
            return cached
        result = await self._provider.get_indices()
        if result:
            self._cache.set(key, result)
        return result

    # ── Top movers ────────────────────────────────────────────────────────────

    async def get_top_movers(self) -> dict[str, list[TopMover]]:
        key = "movers:all"
        cached = self._cache.get_if_fresh(key, TTL_MOVERS)
        if cached is not None:
            return cached
        result = await self._provider.get_top_movers()
        if result:
            self._cache.set(key, result)
        return result

    # ── Market status ─────────────────────────────────────────────────────────

    async def get_market_status(self) -> MarketStatus:
        # Market status is computed from clock — no caching needed
        return await self._provider.get_market_status()

    # ── Sector performance ────────────────────────────────────────────────────

    async def get_sector_performance(self) -> list[SectorPerformance]:
        key = "sectors:all"
        cached = self._cache.get_if_fresh(key, TTL_SECTOR)
        if cached is not None:
            return cached
        result = await self._provider.get_sector_performance()
        if result:
            self._cache.set(key, result)
        return result

    # ── WebSocket streaming ───────────────────────────────────────────────────

    def subscribe_quotes(self, symbols: list[str]):
        """Delegate to provider.subscribe_quotes() — async generator."""
        return self._provider.subscribe_quotes(symbols)

    async def unsubscribe(self, symbols: list[str]) -> None:
        await self._provider.unsubscribe(symbols)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def shutdown(self) -> None:
        await self._provider.disconnect()
        self._cache.clear()

    def swap_provider(self, new_provider: MarketDataProvider) -> None:
        """Hot-swap provider at runtime (e.g. after Fyers token refresh)."""
        old = self._provider
        self._provider = new_provider
        log.info("market_data.provider_swapped from=%s to=%s", old.name, new_provider.name)


# ── Singleton (imported by the rest of the application) ───────────────────────
market_data_service = MarketDataService()


# ── App-level Fyers initialisation / refresh ──────────────────────────────────

async def upgrade_to_fyers() -> bool:
    """
    Attempt TOTP-based automated Fyers login and swap the active provider.

    Called at startup (from app lifespan) and daily at 5:30 AM IST (from scheduler).
    Returns True if the provider was successfully swapped to Fyers.

    No-op (returns False silently) if TOTP credentials are not configured.
    """
    import asyncio
    import concurrent.futures

    try:
        from app.core.config import settings
        client_id    = getattr(settings, "fyers_client_id",    "")
        secret_key   = getattr(settings, "fyers_secret_key",   "")
        redirect_uri = getattr(settings, "fyers_redirect_uri", "")
        login_id     = getattr(settings, "fyers_login_id",     "")
        pin          = getattr(settings, "fyers_pin",          "")
        totp_key     = getattr(settings, "fyers_totp_key",     "")

        if not (client_id and secret_key and login_id and pin and totp_key):
            log.debug("market_data.fyers_upgrade_skipped reason=missing_totp_credentials")
            return False

        from .providers.fyers import FyersAuthManager, FyersProvider

        auth_mgr = FyersAuthManager(client_id, secret_key, redirect_uri)

        # Run blocking HTTP calls in a thread so the event loop stays free
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            token = await loop.run_in_executor(
                ex, auth_mgr.auto_authenticate, login_id, pin, totp_key
            )

        if not token:
            log.error("market_data.fyers_upgrade_failed reason=no_token")
            return False

        new_provider = FyersProvider(
            client_id    = client_id,
            access_token = token,
            secret_key   = secret_key,
            redirect_uri = redirect_uri,
        )
        market_data_service.swap_provider(new_provider)
        log.info("market_data.upgraded_to_fyers")
        return True

    except Exception as exc:
        log.error("market_data.fyers_upgrade_error error=%s", str(exc))
        return False
