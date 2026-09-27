import { test, expect } from "@playwright/test";

/**
 * Company page — currency/unit correctness fix, real hydrated-browser
 * verification (2026-09-27). Second real consumer of the same
 * get_stock_detail() bug fixed for the Compare page: FinancialHighlights
 * (Financials tab) hardcoded "₹ in Crore"/" Cr" for every company,
 * regardless of the company's real reporting currency. Confirmed live:
 * INFY reports financialCurrency="USD" (real FY26 revenue $20.158B /
 * 20,158 $ Million), not INR.
 */

test.describe("Company page — currency/unit correctness (real hydrated browser)", () => {
  test("INFY's Financial Highlights table shows $ Million, never a wrongly-scaled ₹ Crore number", async ({ page }) => {
    await page.goto("/companies/INFY?tab=financials");

    await expect(page.getByText("Financial Highlights")).toBeVisible({ timeout: 15_000 });

    // Real confirmed-live INFY figure (curled directly): FY26 revenue =
    // 20,158, correctly labeled "$ Million" — never "2,016" (the old
    // bug's INR/Crore-divisor result) and never a bare "₹ in Crore"
    // header applied to a real USD statement.
    await expect(page.getByText("20,158")).toBeVisible();
    await expect(page.getByText("$ Million")).toBeVisible();
    await expect(page.getByText("2,016", { exact: true })).not.toBeVisible();
  });

  test("TCS's Financial Highlights table still shows the real ₹ Crore label for a real INR reporter", async ({ page }) => {
    await page.goto("/companies/TCS?tab=financials");

    await expect(page.getByText("Financial Highlights")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("267021", { exact: false }).or(page.getByText("2,67,021"))).toBeVisible();
    await expect(page.getByText("₹ Crore")).toBeVisible();
  });
});
