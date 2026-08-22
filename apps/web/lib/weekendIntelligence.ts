import { API_BASE_URL as API } from "@/lib/api";
import type { WeekendHistoryResponse, WeekendIntelligenceResponse } from "@/types/weekendIntelligence";

/**
 * Fetches GET /api/intelligence/weekend/current — the ONLY Weekend
 * Intelligence data source the frontend is allowed to read (brief §5:
 * "the backend owns intelligence, the frontend owns presentation").
 * This never triggers backend synthesis — it's a cheap read over an
 * already-persisted snapshot.
 *
 * Mirrors app/page.tsx's own `live()` helper (7s abort timeout,
 * no-store, null on any failure) rather than lib/api.ts's throwing
 * fetchAPI — the weekend homepage needs the same "never crash the page
 * on a backend hiccup" resilience the rest of the homepage already has,
 * so the caller can render an honest "temporarily unavailable" state
 * instead of a Next.js error boundary.
 */
export async function fetchWeekendIntelligence(
  ms = 7000,
): Promise<WeekendIntelligenceResponse | null> {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), ms);
  try {
    const r = await fetch(`${API}/api/intelligence/weekend/current`, {
      cache: "no-store",
      signal: ac.signal,
    });
    clearTimeout(t);
    if (!r.ok) return null;
    return (await r.json()) as WeekendIntelligenceResponse;
  } catch {
    clearTimeout(t);
    return null;
  }
}

/**
 * Fetches GET /api/intelligence/weekend/history — version metadata only
 * (newest first, real production_confidence per checkpoint), used solely
 * to show a real "vs previous checkpoint" confidence delta on the
 * homepage's Confidence card. Same resilience contract as
 * fetchWeekendIntelligence above: null on any failure, never throws —
 * the delta is additive context, its absence must never break the page.
 */
export async function fetchWeekendHistory(
  targetTradingDate: string,
  ms = 5000,
): Promise<WeekendHistoryResponse | null> {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), ms);
  try {
    const r = await fetch(`${API}/api/intelligence/weekend/history?target_trading_date=${encodeURIComponent(targetTradingDate)}`, {
      cache: "no-store",
      signal: ac.signal,
    });
    clearTimeout(t);
    if (!r.ok) return null;
    return (await r.json()) as WeekendHistoryResponse;
  } catch {
    clearTimeout(t);
    return null;
  }
}
