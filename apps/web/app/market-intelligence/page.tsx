import { Suspense } from "react";
import { MarketClient } from "./MarketClient";
import { FloatingAISearch } from "@/components/FloatingAISearch";
import { API_BASE_URL as API } from "@/lib/api";


async function safe<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  try { return await fn(); } catch { return fallback; }
}

export const dynamic  = "force-dynamic";
export const revalidate = 0;

export default async function MarketIntelligencePage() {
  // overview is intentionally excluded — it's the slow endpoint (yfinance × 24 tickers).
  // It fetches client-side after the page renders so the page is never blocked by it.
  const [session, events, news, opportunities, calendar, insights, movers] =
    await Promise.all([
      safe(() => fetch(`${API}/api/market/session`,          { cache: "no-store" }).then(r => r.ok ? r.json() : null), null),
      safe(() => fetch(`${API}/api/market/events?limit=10`,  { cache: "no-store" }).then(r => r.ok ? r.json() : null), null),
      safe(() => fetch(`${API}/api/market/news?limit=8`,     { cache: "no-store" }).then(r => r.ok ? r.json() : null), null),
      safe(() => fetch(`${API}/api/market/opportunities`,    { cache: "no-store" }).then(r => r.ok ? r.json() : null), null),
      safe(() => fetch(`${API}/api/market/calendar`,         { cache: "no-store" }).then(r => r.ok ? r.json() : null), null),
      safe(() => fetch(`${API}/api/market/insights`,         { cache: "no-store" }).then(r => r.ok ? r.json() : null), null),
      safe(() => fetch(`${API}/api/market/top-movers`,       { cache: "no-store" }).then(r => r.ok ? r.json() : null), null),
    ]);

  return (
    <>
      <Suspense fallback={null}>
        <MarketClient
          initialSession={session}
          initialOverview={null}
          initialEvents={events?.events ?? []}
          initialNews={news?.news ?? []}
          initialOpportunities={opportunities?.opportunities ?? []}
          initialCalendar={calendar?.events ?? []}
          initialInsights={insights}
          initialMovers={movers}
        />
      </Suspense>
      <FloatingAISearch className="bottom-4"/>
    </>
  );
}
