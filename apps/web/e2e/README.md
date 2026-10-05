# Fixture-backed browser QA (AEV2 shell)

Real browser rendering of all six implemented AI Answer modes, using
**real captured backend contracts** — the same JSON files in
`apps/web/components/ai/__fixtures__/backend-real/*.json` that
`answerTypes.backendContract.test.ts` already proves the frontend gate
functions accept (see that directory's own README for how they're
generated). This exists because local free-tier LLM provider capacity
is exhausted, blocking real happy-path browser QA for five of the six
modes — captured contracts are the only way to see them render at all
right now.

## Test-only, by design

Every spec intercepts the frontend's own outgoing request with
Playwright's `page.route()` and fulfills it from a fixture, entirely
inside the browser context the test controls. **No route or endpoint
anywhere in the app itself serves fixture data** — the real dev
backend never sees these requests at all. Nothing here should ever be
adapted into a public "preview" or "demo" route.

## Running it

Requires the dev server already running with, at minimum:

```
NEXT_PUBLIC_AI_ANSWER_SHELL=1
NEXT_PUBLIC_AI_SEARCH_V3=1
```

(see `.env.local` — both stay off in production; this harness only
ever talks to a local dev server you started yourself).

```
npm run test:e2e                    # all specs, both projects
npx playwright test --project=desktop
npx playwright show-report          # after a run, if you want the HTML report
```

Screenshots land in `e2e/.output/screenshots/` (gitignored).

## What's covered

- All six modes render their real layout from a real captured contract
  (`data-ui-mode` matches, never the legacy degraded chrome).
- Desktop + mobile viewport, light + dark theme, on the flagship mode
  (`direct_company_research`) — dark mode is set via
  `localStorage.setItem('mr-theme', 'dark')` in `fixtures/mockSearchStream.ts`'s
  `setTheme()`, matching this app's REAL theming mechanism
  (`app/layout.tsx`'s own inline script), not the `prefers-color-scheme`
  media query Playwright's `colorScheme` context option would drive.
- Edge cases: missing optional fields, a very long title/conclusion
  (checked for layout overflow, not just presence), zero evidence (the
  real bug class found live in this engagement — commit `27f4f1e`),
  and partially populated evidence.
- Shell chrome: "New Search" actually clears state (not the historical
  no-op — see `AISearchClient.tsx`'s `resetToEmptySearch`); "Refine"
  stays disabled even on a fully successful, real contract.

## A real gotcha this harness hit

Mocking only `GET /api/ai/search/stream` (the primary EventSource path)
is not enough. Playwright's `route.fulfill()` delivers one complete,
finite HTTP response; a real browser `EventSource` can treat the
connection then closing as a dropped connection and race its own
auto-reconnect/`onerror` handling against this app's own `"done"`-event
handler calling `es.close()`. When that race is lost, `useAISearchStream`
falls back to the blocking `POST /api/ai/search/v3` — which, unmocked,
hit the real (capacity-exhausted, slow) local backend instead of the
fixture, causing sporadic 30s test timeouts. `mockSearchStream()` mocks
both routes with the same fixture for exactly this reason.
