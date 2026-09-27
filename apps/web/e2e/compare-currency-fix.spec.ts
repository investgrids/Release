import { test, expect } from "@playwright/test";

/**
 * Currency/unit correctness fix — real hydrated-browser verification
 * (2026-09-27). Confirmed live before this fix: GET /api/stocks/INFY
 * unconditionally divided revenue/profit by 1e7 assuming INR, even though
 * yfinance's own financialCurrency for INFY is "USD" (real annual revenue
 * $20.158B) — a genuine currency mismatch, not merely a magnitude error.
 * Fixed at the source (market_data.py::get_stock_detail): revenue/profit
 * now scale and label correctly for the real confirmed currency (USD ->
 * $ Million for INFY, INR -> ₹ Crore for most other NSE companies), and
 * withhold the figure entirely when the currency is genuinely unconfirmed
 * rather than defaulting to INR.
 *
 * Requires two real local servers already running before `npx playwright
 * test` — see one-score-company-page.spec.ts's header for the exact
 * commands.
 */

test.describe("Compare page — currency/unit correctness (real hydrated browser)", () => {
  test("INFY's real revenue renders as $ Million, TCS's as ₹ Crore, side by side — never mislabeled", async ({ page }) => {
    await page.goto("/companies?tab=compare&a=INFY&b=TCS");

    await expect(page.getByText("Infosys", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Tata Consultancy", { exact: false }).first()).toBeVisible({ timeout: 15_000 });

    // Real confirmed-live figures (curled directly before writing this
    // test): INFY FY26 revenue = 20,158 ($ Million); TCS FY26 revenue =
    // 267,021 (₹ Crore). Both must render, correctly scaled for their own
    // real currency, in the same comparison table.
    await expect(page.getByText("20,158").first()).toBeVisible();
    await expect(page.getByText("2,67,021").first()).toBeVisible();

    // The real currency/unit labels themselves must be visible and
    // distinct per company — never one page-wide "₹ Crore" assumption.
    await expect(page.getByText(/\$ Million/).first()).toBeVisible();
    await expect(page.getByText(/₹ Crore/).first()).toBeVisible();

    // The old bug's exact wrong output must never appear: INFY's real
    // revenue divided by the INR/Crore divisor instead of the correct
    // USD/Million one would show "2,016", not "20,158".
    await expect(page.getByText("2,016", { exact: true })).not.toBeVisible();
  });
});
