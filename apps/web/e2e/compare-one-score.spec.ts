import { test, expect } from "@playwright/test";

/**
 * Compare page — one-score migration, real hydrated-browser verification
 * (2026-09-26). The Compare page used to run its own client-side "AI
 * Score" (a hardcoded formula, no backend call, over a hardcoded
 * 30-company registry) and declared an "AI winner." Replaced with the
 * real, canonical MarketRipple Score projection and a real company-
 * directory search. Component tests (CompareContent.test.tsx) cover the
 * populated and partial-coverage states with fixtures, because the local
 * dev DB currently has ZERO real MarketRipple Score snapshots for ANY
 * company (confirmed live: every Banking symbol returns
 * {"resolved":false}, and GET /api/company-rankings/Banking returns
 * ranked:[] / partial_coverage:[] for the whole sector) — the same
 * standing "local zero-snapshot findings establish nothing about
 * production" gap already tracked elsewhere in this engagement, not
 * something specific to the Compare page. This spec verifies what real
 * local data DOES support: the honest "Unavailable" state on two real
 * companies, real financial data rendering, the real company-directory
 * search, and — most importantly — that no fabricated score/winner
 * element survives real hydration anywhere on the page.
 *
 * Requires two real local servers already running before `npx playwright
 * test` — see one-score-company-page.spec.ts's header for the exact
 * commands.
 */

test.describe("Compare page — one-score migration (real hydrated browser)", () => {
  test("shows real financial data and the honest 'Unavailable' MarketRipple Score state, never a fabricated AI score or declared winner", async ({ page }) => {
    await page.goto("/companies?tab=compare&a=ICICIBANK&b=TCS");

    // Real, sourced financial data for both real companies must render.
    await expect(page.getByText("ICICI Bank", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Tata Consultancy", { exact: false }).first()).toBeVisible({ timeout: 15_000 });

    // The old fabricated summary/banner must never appear.
    await expect(page.getByText("AI Comparison Summary")).not.toBeVisible();
    await expect(page.getByText("Best Future Potential")).not.toBeVisible();
    await expect(page.getByText("AI Recommended Pick")).not.toBeVisible();
    await expect(page.getByText(/leads on risk-adjusted return metrics/)).not.toBeVisible();

    // Real, neutral, single-metric summary in its place.
    await expect(page.getByText("Comparison Summary")).toBeVisible();
    await expect(page.getByText("Highest ROE")).toBeVisible();
    await expect(page.getByText("Lowest Beta")).toBeVisible();

    // Real fiscal-year-end label (2026-09-26, owner instruction) — both
    // real companies' latest annual figures happen to be FY26 (confirmed
    // live via /api/stocks/{symbol}), replacing the old generic "Latest
    // FY" placeholder with each company's own real year.
    await expect(page.getByText("FY26").first()).toBeVisible();

    // Honest period-label disclosure — TTM figures are the data
    // provider's own convention, not independently recomputed here.
    await expect(page.getByText(/trailing-twelve-month calculation/).first()).toBeVisible();

    // Valuation tab: the real MarketRipple Score card, honestly showing
    // "Unavailable" for both real companies (confirmed live: no snapshot
    // exists locally for either symbol) — never the old fabricated ring.
    await page.getByRole("button", { name: "Valuation" }).click();
    await expect(page.getByText("MarketRipple Score", { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Unavailable").first()).toBeVisible();
    await expect(page.getByText("Score Comparison")).not.toBeVisible();
    await expect(page.getByText(/Score derived from ROE, PE/)).not.toBeVisible();

    // AI Analysis tab: same real per-company MarketRipple Score display,
    // and the old winner-declaring banner is gone entirely.
    await page.getByRole("button", { name: "AI Analysis" }).click();
    await expect(page.getByText(/^ICICI Bank/).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("AI Score")).not.toBeVisible();
    await expect(page.getByText("AI Powered")).not.toBeVisible();
    await expect(page.getByText("AI Recommended Pick")).not.toBeVisible();
    await expect(page.getByText(/Scores highest/)).not.toBeVisible();
  });

  test("Add Company search calls the real company directory, not a hardcoded list", async ({ page }) => {
    await page.goto("/companies?tab=compare&a=ICICIBANK&b=TCS");
    await expect(page.getByText("ICICI Bank", { exact: false }).first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /add company/i }).click();
    const searchBox = page.getByPlaceholder("Search company or symbol…");
    await searchBox.fill("Infosys");

    // A company only findable via the real backend directory (not the old
    // hardcoded 30-company list, which this exact test would still have
    // passed against — the real assertion is the network call itself).
    const searchRequest = page.waitForRequest(req => req.url().includes("/api/companies/search") && req.url().includes("Infosys"));
    await searchRequest;
    await expect(page.getByText("Infosys", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
  });
});
