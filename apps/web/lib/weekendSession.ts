/**
 * The single predicate deciding whether app/page.tsx renders the
 * Weekend Intelligence homepage or the normal weekday homepage (brief
 * §3/§4/§38). Reuses `/api/market/session`'s own real `session` value
 * (already fetched by page.tsx's existing `getSession()` for
 * TickerStrip/MarketSnapshotCard — see app/page.tsx's ROOT PAGE comment
 * for why this endpoint was chosen over /api/mie/state's equivalent
 * field) — this file does not compute a session itself, it only
 * interprets the value the backend already computed.
 *
 * Backend's real session values (apps/backend/app/api/market.py
 * market_session(), verified 2026-08): "weekend" | "pre_market" |
 * "pre_open" | "open" | "after_market". Only "weekend" routes to the
 * Weekend homepage — every other value (including both pre-market
 * sub-states and after-market) renders the normal homepage unchanged.
 */
export function isWeekendSession(session: { session?: string | null } | null | undefined): boolean {
  return session?.session === "weekend";
}
