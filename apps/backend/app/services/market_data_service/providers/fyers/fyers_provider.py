"""
FyersProvider — implements MarketDataProvider using Fyers API v3.

Priority:
  1. Live quotes and candles come from Fyers REST API
  2. Company fundamentals fall back to yfinance (Fyers lacks this data)
  3. Live tick streaming via FyersWebSocketManager
  4. All responses normalized to standard domain models via transformers

This provider is active only when FYERS_CLIENT_ID and a valid access_token
are configured. The MarketDataService handles provider selection automatically.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Optional, AsyncIterator

from ...interfaces import MarketDataProvider
from ...types import Quote, Company, Candle, IndexQuote, SectorPerformance, MarketStatus, TopMover
from ...transformers import quote as qt, candle as ct
from ..yfinance.yfinance_provider import YFinanceProvider
from .fyers_auth import FyersAuthManager
from .fyers_rest import FyersRestClient
from .fyers_websocket import FyersWebSocketManager

log = logging.getLogger(__name__)

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="fyers-")


class FyersProvider(MarketDataProvider):
    """
    Primary market data provider using Fyers API v3.
    Falls back to YFinanceProvider for features Fyers doesn't cover (fundamentals).
    """

    def __init__(
        self,
        client_id:    str,
        access_token: str,
        secret_key:   str = "",
        # No hardcoded default — every call site passes this explicitly,
        # sourced from settings.fyers_redirect_uri (the single source of
        # truth for this URL). A provider-level default here was just
        # another copy of the same literal to keep in sync.
        redirect_uri: str = "",
    ) -> None:
        self._client_id    = client_id
        self._access_token = access_token

        self._auth = FyersAuthManager(
            client_id    = client_id,
            secret_key   = secret_key,
            redirect_uri = redirect_uri,
        )
        self._auth.set_token_direct(access_token)

        self._rest = FyersRestClient(client_id=client_id, access_token=access_token)
        self._ws   = FyersWebSocketManager(client_id=client_id, access_token=access_token)

        # Fallback for features not available in Fyers
        self._yf   = YFinanceProvider()

        # Live quote queues keyed by subscriber id
        self._live_queues: dict[int, asyncio.Queue] = {}
        self._ws.add_callback(self._on_tick)

    @property
    def name(self) -> str:
        return "Fyers"

    @property
    def supports_websocket(self) -> bool:
        return True

    # ── Quote ─────────────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> Optional[Quote]:
        def _fetch():
            raw_map = self._rest.get_quotes([symbol])
            raw = raw_map.get(symbol.upper())
            if raw:
                return qt.from_fyers_quote(raw)
            return None

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _fetch)

        # Fallback to yfinance if Fyers returns nothing
        if result is None:
            log.debug("fyers_provider.quote_fallback symbol=%s", symbol)
            result = await self._yf.get_quote(symbol)

        return result

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        def _fetch():
            raw_map = self._rest.get_quotes(symbols)
            quotes  = []
            for sym in symbols:
                raw = raw_map.get(sym.upper())
                if raw:
                    q = qt.from_fyers_quote(raw)
                    if q:
                        quotes.append(q)
            return quotes

        loop = asyncio.get_event_loop()
        fyers_quotes = await loop.run_in_executor(_executor, _fetch)

        # Find any symbols that Fyers missed and fill from yfinance
        fetched_syms = {q.symbol for q in fyers_quotes}
        missing = [s for s in symbols if s.upper() not in fetched_syms]
        if missing:
            yf_quotes = await self._yf.get_quotes(missing)
            fyers_quotes.extend(yf_quotes)

        return fyers_quotes

    # ── Company profile — Fyers has no fundamentals; delegate to yfinance ─────

    async def get_company(self, symbol: str) -> Optional[Company]:
        return await self._yf.get_company(symbol)

    # ── Historical candles ────────────────────────────────────────────────────

    async def get_historical_candles(self, symbol: str, period: str = "6M", interval: str = "1d") -> list[Candle]:
        def _fetch():
            raw_candles = self._rest.get_history(symbol, period)
            return [c for raw in raw_candles if (c := ct.from_fyers_candle(raw))]

        loop = asyncio.get_event_loop()
        candles = await loop.run_in_executor(_executor, _fetch)

        if not candles:
            log.debug("fyers_provider.history_fallback symbol=%s", symbol)
            candles = await self._yf.get_historical_candles(symbol, period, interval)

        return candles

    # ── Indices — delegate to yfinance (Fyers index coverage is partial) ──────

    async def get_indices(self) -> list[IndexQuote]:
        return await self._yf.get_indices()

    # ── Top movers — delegate to yfinance ─────────────────────────────────────

    async def get_top_movers(self) -> dict[str, list[TopMover]]:
        return await self._yf.get_top_movers()

    # ── Market status (pure IST clock — no network) ───────────────────────────

    async def get_market_status(self) -> MarketStatus:
        return await self._yf.get_market_status()

    # ── Sector performance — delegate to yfinance ─────────────────────────────

    async def get_sector_performance(self) -> list[SectorPerformance]:
        return await self._yf.get_sector_performance()

    # ── WebSocket live quotes ─────────────────────────────────────────────────

    async def subscribe_quotes(self, symbols: list[str]) -> AsyncIterator[Quote]:
        queue: asyncio.Queue[Quote] = asyncio.Queue(maxsize=500)
        qid   = id(queue)
        self._live_queues[qid] = queue

        self._ws.subscribe(symbols)

        try:
            while True:
                quote = await asyncio.wait_for(queue.get(), timeout=60.0)
                yield quote
        except asyncio.TimeoutError:
            pass
        finally:
            del self._live_queues[qid]

    async def unsubscribe(self, symbols: list[str]) -> None:
        self._ws.unsubscribe(symbols)

    async def disconnect(self) -> None:
        self._ws.disconnect()
        _executor.shutdown(wait=False)

    # ── Internal tick handler ─────────────────────────────────────────────────

    def _on_tick(self, raw: dict) -> None:
        """Called by FyersWebSocketManager on each incoming tick."""
        try:
            # Fyers WebSocket tick format: {"type": "SymbolUpdate", "symbol": "NSE:RELIANCE-EQ", ...}
            quote = qt.from_fyers_quote(raw)
            if not quote:
                return
            for queue in list(self._live_queues.values()):
                try:
                    queue.put_nowait(quote)
                except asyncio.QueueFull:
                    pass
        except Exception as exc:
            log.warning("fyers_provider.tick_error error=%s", str(exc))
