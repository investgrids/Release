import type { Page } from "@playwright/test";

// Builds the exact SSE envelope shape app/api/ai_search.py's real
// /api/ai/search/stream route sends for its "answer" event (see that
// route's own `envelope = {"result": payload, "cached": ..., ...}` —
// mirrored here verbatim, not guessed) — the frontend's useAISearchStream
// hook reads `data.result` off this envelope, exactly as a real answer
// event would deliver it.
function sseAnswerBody(result: object, overrides: { cached?: boolean; response_id?: string; latency_ms?: number; provider?: string } = {}): string {
  const envelope = {
    result,
    cached: overrides.cached ?? false,
    response_id: overrides.response_id ?? (result as { response_id?: string }).response_id ?? "e2e-mock-response",
    latency_ms: overrides.latency_ms ?? 1200,
    provider: overrides.provider ?? "e2e-mock",
  };
  return `event: answer\ndata: ${JSON.stringify(envelope)}\n\nevent: done\ndata: {}\n\n`;
}

// Intercepts BOTH real outgoing requests this frontend can make for a
// query — GET /api/ai/search/stream (EventSource, the primary path) and
// the blocking POST /api/ai/search/v3 fallback useAISearchStream's own
// `es.onerror` switches to (see that hook's own docstring). Mocking only
// the SSE route is not enough in practice: Playwright's route.fulfill()
// delivers one complete, finite HTTP response, and a real browser
// EventSource treats the connection then closing as a dropped
// connection and can race its own auto-reconnect/onerror handling
// against this app's "done"-event handler calling es.close() — when
// that race is lost, the hook falls back to the blocking POST, which
// would otherwise hit the REAL (capacity-exhausted, slow) local
// backend instead of this fixture. Mocking both makes the test
// correct regardless of which path a given browser run actually takes
// — neither request ever reaches the real dev backend at all, and no
// route/endpoint anywhere in the app itself serves fixture data; this
// interception lives only inside the Playwright test process.
export async function mockSearchStream(page: Page, result: object): Promise<void> {
  await page.route("**/api/ai/search/stream**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sseAnswerBody(result),
    });
  });
  await page.route("**/api/ai/search/v3", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        result,
        cached: false,
        response_id: (result as { response_id?: string }).response_id ?? "e2e-mock-response",
        latency_ms: 1200,
        provider: "e2e-mock",
      }),
    });
  });
}

// Sets the SAME localStorage key app/layout.tsx's own inline theme
// script reads (`localStorage.getItem('mr-theme')`) — this app drives
// dark mode via a `data-theme="dark"` attribute set from that key, NOT
// the `prefers-color-scheme` media query, so Playwright's own
// `colorScheme` context option would silently do nothing here. Must run
// via addInitScript (before any page script executes), not after goto.
export async function setTheme(page: Page, theme: "light" | "dark"): Promise<void> {
  await page.addInitScript((t) => {
    try {
      localStorage.setItem("mr-theme", t);
    } catch {
      // ignore — matches the app's own try/catch around this exact call
    }
  }, theme);
}
