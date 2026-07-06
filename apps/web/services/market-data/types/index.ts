/**
 * Standard market data types for the frontend.
 * Mirrors the Python domain models in market_data_service/types/market.py.
 * All components consume these types — never raw API response shapes.
 */

export interface Quote {
  symbol: string;
  name: string;
  exchange: string;
  price: number;
  price_str: string;
  change: number;
  change_str: string;
  change_percent: number;
  change_pct_str: string;
  open: number;
  high: number;
  low: number;
  previous_close: number;
  volume: number;
  positive: boolean;
  last_updated: string;
}

export interface Company {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  market_cap: number;
  pe: number;
  eps: number;
  roe: number;
  book_value: number;
  dividend_yield: number;
  description: string;
}

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartPoint {
  label: string;
  value: number;
}

export interface IndexQuote {
  name: string;
  ticker: string;
  value: string;
  value_raw: number;
  change: string;
  change_str: string;
  pct: string;
  positive: boolean;
  flag: string;
  chart: ChartPoint[];
}

export interface SectorPerformance {
  id: string;
  name: string;
  value: string;
  positive: boolean;
}

export interface MarketStatus {
  is_open: boolean;
  status: "open" | "pre_open" | "pre_market" | "closed" | "weekend";
  time_ist: string;
  date: string;
}

export interface TopMover {
  ticker: string;
  company: string;
  value: string;
  subtitle: string;
  positive: boolean;
}

export interface TopMovers {
  gainers: TopMover[];
  losers: TopMover[];
  active: TopMover[];
}

export type QuotePeriod = "1D" | "1W" | "1M" | "6M" | "1Y" | "3Y" | "5Y";
export type QuoteInterval = "5m" | "60m" | "1d" | "1wk" | "1mo";

// WebSocket message types from server
export interface WSQuoteMessage {
  type: "quote";
  data: Quote;
}
export interface WSPingMessage {
  type: "ping";
}
export type WSMessage = WSQuoteMessage | WSPingMessage;

// WebSocket commands from client
export interface WSSubscribeCmd {
  cmd: "subscribe" | "unsubscribe";
  symbols: string[];
}

export interface ProviderInfo {
  provider: string;
  supports_websocket: boolean;
  ws_clients: number;
}
