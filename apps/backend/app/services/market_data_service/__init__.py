"""
Market Data Service — public surface.

Import from here only:
    from app.services.market_data_service import market_data_service
    from app.services.market_data_service import ws_hub

Never import provider classes or transformers from application code.
"""
from .market_data_service import MarketDataService, market_data_service
from .websocket_manager import ServerWSHub, ws_hub, handle_quote_ws
from .interfaces import MarketDataProvider
from .types import Quote, Company, Candle, IndexQuote, SectorPerformance, MarketStatus, TopMover

__all__ = [
    "MarketDataService",
    "market_data_service",
    "ServerWSHub",
    "ws_hub",
    "handle_quote_ws",
    "MarketDataProvider",
    "Quote", "Company", "Candle", "IndexQuote",
    "SectorPerformance", "MarketStatus", "TopMover",
]
