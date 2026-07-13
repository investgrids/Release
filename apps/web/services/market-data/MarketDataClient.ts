/**
 * MarketDataClient — typed HTTP client for the Market Data Service API.
 *
 * All components call this client — never fetch /api/data/* directly.
 * This is the TypeScript boundary that mirrors MarketDataService on the backend.
 *
 * Usage:
 *   import { marketDataClient } from "@/services/market-data";
 *
 *   const quote = await marketDataClient.getQuote("RELIANCE");
 *   const candles = await marketDataClient.getHistory("TCS", "6M");
 */

import type {
  Quote,
  Company,
  Candle,
  ChartPoint,
  IndexQuote,
  SectorPerformance,
  MarketStatus,
  TopMovers,
  ProviderInfo,
  QuotePeriod,
} from "./types";
import { clientCache, TTL_QUOTE, TTL_INDICES, TTL_HISTORY, TTL_COMPANY, TTL_MOVERS, TTL_SECTORS, TTL_STATUS } from "./cache/memory";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DATA_BASE = `${API_BASE}/api/data`;

// ── Fetch helper ────────────────────────────────────────────────────────────

async function _get<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${DATA_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Market data error ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ── MarketDataClient ────────────────────────────────────────────────────────

class MarketDataClient {
  // ── Provider info ─────────────────────────────────────────────────────────

  async getProviderInfo(): Promise<ProviderInfo> {
    return _get<ProviderInfo>("/provider");
  }

  // ── Market status ─────────────────────────────────────────────────────────

  async getMarketStatus(): Promise<MarketStatus> {
    const cached = clientCache.getIfFresh<MarketStatus>("status", TTL_STATUS);
    if (cached) return cached;
    const result = await _get<MarketStatus>("/status");
    clientCache.set("status", result);
    return result;
  }

  // ── Single quote ──────────────────────────────────────────────────────────

  async getQuote(symbol: string): Promise<Quote> {
    const key = `quote:${symbol.toUpperCase()}`;
    const cached = clientCache.getIfFresh<Quote>(key, TTL_QUOTE);
    if (cached) return cached;
    const result = await _get<Quote>(`/quote/${symbol.toUpperCase()}`);
    clientCache.set(key, result);
    return result;
  }

  // ── Batch quotes ──────────────────────────────────────────────────────────

  async getQuotes(symbols: string[]): Promise<Quote[]> {
    if (!symbols.length) return [];

    const cached: Quote[]  = [];
    const missing: string[] = [];

    for (const sym of symbols) {
      const key = `quote:${sym.toUpperCase()}`;
      const hit = clientCache.getIfFresh<Quote>(key, TTL_QUOTE);
      if (hit) cached.push(hit);
      else missing.push(sym);
    }

    if (missing.length) {
      const { quotes } = await _get<{ count: number; quotes: Quote[] }>(
        `/quotes?symbols=${encodeURIComponent(missing.join(","))}`
      );
      for (const q of quotes) {
        clientCache.set(`quote:${q.symbol}`, q);
        cached.push(q);
      }
    }

    return cached;
  }

  // ── Company ───────────────────────────────────────────────────────────────

  async getCompany(symbol: string): Promise<Company> {
    const key = `company:${symbol.toUpperCase()}`;
    const cached = clientCache.getIfFresh<Company>(key, TTL_COMPANY);
    if (cached) return cached;
    const result = await _get<Company>(`/company/${symbol.toUpperCase()}`);
    clientCache.set(key, result);
    return result;
  }

  // ── Historical candles ────────────────────────────────────────────────────

  async getHistory(
    symbol: string,
    period: QuotePeriod = "6M"
  ): Promise<{ candles: Candle[]; chart: ChartPoint[] }> {
    const key = `history:${symbol.toUpperCase()}:${period}`;
    const cached = clientCache.getIfFresh<{ candles: Candle[]; chart: ChartPoint[] }>(key, TTL_HISTORY);
    if (cached) return cached;
    const result = await _get<{ symbol: string; period: string; count: number; candles: Candle[]; chart: ChartPoint[] }>(
      `/history/${symbol.toUpperCase()}?period=${period}`
    );
    const data = { candles: result.candles, chart: result.chart };
    clientCache.set(key, data);
    return data;
  }

  // ── Indices ───────────────────────────────────────────────────────────────

  async getIndices(): Promise<IndexQuote[]> {
    const cached = clientCache.getIfFresh<IndexQuote[]>("indices", TTL_INDICES);
    if (cached) return cached;
    const { indices } = await _get<{ count: number; indices: IndexQuote[] }>("/indices");
    clientCache.set("indices", indices);
    return indices;
  }

  // ── Top movers ────────────────────────────────────────────────────────────

  async getMovers(): Promise<TopMovers> {
    const cached = clientCache.getIfFresh<TopMovers>("movers", TTL_MOVERS);
    if (cached) return cached;
    const result = await _get<TopMovers>("/movers");
    clientCache.set("movers", result);
    return result;
  }

  // ── Sector performance ────────────────────────────────────────────────────

  async getSectors(): Promise<SectorPerformance[]> {
    const cached = clientCache.getIfFresh<SectorPerformance[]>("sectors", TTL_SECTORS);
    if (cached) return cached;
    const { sectors } = await _get<{ count: number; sectors: SectorPerformance[] }>("/sectors");
    clientCache.set("sectors", sectors);
    return sectors;
  }

  // ── Fyers auth ────────────────────────────────────────────────────────────

  async getFyersAuthUrl(): Promise<{ auth_url: string; instructions: string }> {
    return _get("/auth/fyers");
  }

  async exchangeFyersAuthCode(authCode: string): Promise<{ status: string; provider: string; message: string }> {
    const res = await fetch(`${DATA_BASE}/auth/fyers/callback?auth_code=${encodeURIComponent(authCode)}`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(`Auth exchange failed: ${res.status}`);
    return res.json();
  }
}

// ── Singleton ─────────────────────────────────────────────────────────────────
export const marketDataClient = new MarketDataClient();
export default marketDataClient;
