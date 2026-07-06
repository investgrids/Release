"""
MarketDataProvider — abstract base class every data provider must implement.

No page, router, or AI module may import a concrete provider directly.
All consumers must go through MarketDataService which uses this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator

from ..types import Quote, Company, Candle, IndexQuote, SectorPerformance, MarketStatus, TopMover


class MarketDataProvider(ABC):
    """
    Contract that all market data providers must satisfy.
    Implementations: FyersProvider, YFinanceProvider.
    Adding a new provider requires only implementing this class —
    zero changes to any other part of the application.
    """

    # ── Single quote ─────────────────────────────────────────────────────────

    @abstractmethod
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        """Return live quote for one NSE symbol (e.g. 'RELIANCE', 'HDFCBANK')."""

    # ── Batch quotes ─────────────────────────────────────────────────────────

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        """Return live quotes for multiple symbols in one round-trip where possible."""

    # ── Company profile ───────────────────────────────────────────────────────

    @abstractmethod
    async def get_company(self, symbol: str) -> Optional[Company]:
        """Return fundamental company profile (sector, PE, EPS, ROE …)."""

    # ── Historical candles ────────────────────────────────────────────────────

    @abstractmethod
    async def get_historical_candles(
        self,
        symbol: str,
        period: str = "6M",       # 1D | 1W | 1M | 6M | 1Y | 3Y | 5Y
        interval: str = "1d",     # 5m | 60m | 1d | 1wk | 1mo
    ) -> list[Candle]:
        """Return OHLCV candles for charting."""

    # ── Market indices ────────────────────────────────────────────────────────

    @abstractmethod
    async def get_indices(self) -> list[IndexQuote]:
        """Return quotes for all tracked Indian + global indices."""

    # ── Top movers ────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_top_movers(self) -> dict[str, list[TopMover]]:
        """Return {'gainers': [...], 'losers': [...], 'active': [...]}."""

    # ── Market status ─────────────────────────────────────────────────────────

    @abstractmethod
    async def get_market_status(self) -> MarketStatus:
        """Return current NSE market status — no network call required."""

    # ── Sector performance ────────────────────────────────────────────────────

    @abstractmethod
    async def get_sector_performance(self) -> list[SectorPerformance]:
        """Return 1-day % change for each tracked sector."""

    # ── Live quote stream (WebSocket) ─────────────────────────────────────────

    @abstractmethod
    async def subscribe_quotes(
        self, symbols: list[str]
    ) -> AsyncIterator[Quote]:
        """
        Async generator that yields Quote objects as live ticks arrive.
        The caller is responsible for breaking out of the iteration.
        Only providers with WebSocket support need to implement this fully;
        others may raise NotImplementedError.
        """

    @abstractmethod
    async def unsubscribe(self, symbols: list[str]) -> None:
        """Remove symbol subscriptions from the live stream."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Cleanly close any open connections."""

    # ── Provider metadata ─────────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name, e.g. 'Fyers' or 'YFinance'."""

    @property
    def supports_websocket(self) -> bool:
        """True if this provider has a live WebSocket feed."""
        return False
