import { defineConfig, devices } from "@playwright/test";

// One-score migration hydrated-browser verification (2026-09-26). Real
// dev servers (backend + `next dev`) must already be running — see
// e2e/one-score-company-page.spec.ts's own header comment for the exact
// commands. reuseExistingServer avoids Playwright trying to start its own
// second frontend instance against a different backend URL.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "e2e/.output",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3125",
    screenshot: "off",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
});
