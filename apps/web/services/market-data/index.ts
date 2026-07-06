/**
 * Market Data Service — frontend barrel export.
 *
 * Import from here ONLY. Never import from sub-modules directly.
 *
 * HTTP client:
 *   import { marketDataClient } from "@/services/market-data";
 *
 * Live quotes:
 *   import { WebSocketManager } from "@/services/market-data";
 *   const ws = WebSocketManager.getInstance();
 *   const unsub = ws.subscribe(["RELIANCE"], (q) => console.log(q.price_str));
 *
 * Types:
 *   import type { Quote, Company, Candle, IndexQuote } from "@/services/market-data";
 */

export { default as marketDataClient } from "./MarketDataClient";
export { default as WebSocketManager } from "./WebSocketManager";

export type {
  Quote,
  Company,
  Candle,
  ChartPoint,
  IndexQuote,
  SectorPerformance,
  MarketStatus,
  TopMover,
  TopMovers,
  QuotePeriod,
  QuoteInterval,
  WSMessage,
  WSQuoteMessage,
  WSPingMessage,
  WSSubscribeCmd,
  ProviderInfo,
} from "./types";
