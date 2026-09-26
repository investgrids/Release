import { test, expect } from "@playwright/test";

/**
 * One-score migration — real, hydrated-browser verification (2026-09-26).
 * Component tests (MarketRippleScoreCard.test.tsx, CompanyScoreContributors.test.tsx)
 * prove the rendering logic in isolation; this proves it survives real
 * client hydration against the real backend, which a plain `curl` of the
 * SSR HTML cannot show (the score card fetches client-side via useEffect).
 *
 * Requires two real local servers already running before `npx playwright test`:
 *   backend:  cd apps/backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8123
 *   frontend: cd apps/web && NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8123 npx next dev -p 3125
 * (or set PLAYWRIGHT_BASE_URL / point the backend URL elsewhere as needed).
 *
 * Uses ICICIBANK against the real local dev DB: has real, rich
 * company-scores evidence (50 contributing signals) but no MarketRipple
 * Score snapshot/CompanyEntity resolution yet ({"resolved":false} from
 * /api/companies/ICICIBANK/marketripple-score, confirmed live) — the
 * exact real-world state that exercises both changes made this session.
 */

test.describe("Company page — one-score migration (real hydrated browser)", () => {
  test("Overview tab: MarketRipple Score card shows Unavailable, never the old Current Intelligence fallback", async ({ page }) => {
    await page.goto("/companies/ICICIBANK");

    // The real MarketRipple Score header tile and Overview card both fetch
    // client-side — wait for hydration to actually resolve the real state.
    await expect(page.getByText("Unavailable").first()).toBeVisible({ timeout: 15_000 });

    // The old fallback component no longer exists in this file at all —
    // its title/text must never appear anywhere on the page.
    await expect(page.getByText("Current Intelligence", { exact: true })).not.toBeVisible();
    await expect(page.getByText(/Insufficient evidence for a current-intelligence view/)).not.toBeVisible();
  });

  test("Intelligence tab: shows 'Recent Intelligence Evidence' with real dated evidence, never the old score/rating/verdict", async ({ page }) => {
    await page.goto("/companies/ICICIBANK?tab=intelligence");

    const heading = page.getByText("Recent Intelligence Evidence");
    await expect(heading).toBeVisible({ timeout: 15_000 });

    // Real, dated, sourced evidence must still render (what this section
    // exists to show).
    await expect(page.getByText(/contributing signal/)).toBeVisible();
    await expect(page.getByText(/From published analysis|From opportunity tracking/).first()).toBeVisible();

    // The removed elements must never appear, on the real rendered page —
    // not the old section title, not the headline number's own label, not
    // the AI-powered badge, not the risk/trend colour pills, not the
    // evidence-quality rating label.
    await expect(page.getByText("AI Company Score")).not.toBeVisible();
    await expect(page.getByText("AI Powered")).not.toBeVisible();
    await expect(page.getByText("Evidence quality")).not.toBeVisible();
    await expect(page.getByText(/^(Low|Medium|High) Risk$/)).not.toBeVisible();
    await expect(page.getByText(/^Trending (Up|Down)$/)).not.toBeVisible();
  });
});
