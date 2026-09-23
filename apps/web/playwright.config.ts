import { defineConfig, devices } from "@playwright/test";

// AEV2 fixture-backed browser QA harness (2026-09-23). Test-only: every
// spec under e2e/ intercepts the frontend's OWN outgoing SSE request
// with page.route() and fulfills it from a real captured backend
// response (apps/web/components/ai/__fixtures__/backend-real/*.json) —
// no public fixture route or endpoint is created anywhere in the app.
// This exists specifically because live provider capacity is exhausted
// locally, blocking real happy-path rendering for five of the six
// implemented modes — real captured contracts are the only way to see
// them render at all right now.
//
// Requires the dev server already running with, at minimum,
// NEXT_PUBLIC_AI_ANSWER_SHELL=1 and NEXT_PUBLIC_AI_SEARCH_V3=1 (see
// .env.local) — webServer below reuses it if already up rather than
// starting a second instance with different env vars.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  // The local dev server this harness talks to is a single Next.js dev
  // process (not scaled) — too many concurrent workers hitting it at
  // once caused sporadic timeouts unrelated to the app itself. Capped
  // rather than run fully parallel.
  workers: 3,
  retries: 1,
  reporter: [["list"]],
  outputDir: "e2e/.output",
  use: {
    baseURL: "http://localhost:3000",
    screenshot: "off",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    // Pixel 5 (Chromium-based) rather than an iOS preset — this harness
    // only needs a real mobile VIEWPORT, not WebKit engine coverage,
    // and staying on one browser engine avoids installing a second one.
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
