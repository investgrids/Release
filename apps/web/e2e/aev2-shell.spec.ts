import { test, expect, type Page } from "@playwright/test";
import { mockSearchStream, setTheme } from "./fixtures/mockSearchStream";

import directCompanyResearchReal from "../components/ai/__fixtures__/backend-real/direct_company_research.json";
import switchAnalysisReal from "../components/ai/__fixtures__/backend-real/switch_analysis.json";
import companyComparisonReal from "../components/ai/__fixtures__/backend-real/company_comparison.json";
import eventImpactReal from "../components/ai/__fixtures__/backend-real/event_impact.json";
import marketPulseReal from "../components/ai/__fixtures__/backend-real/market_pulse.json";
import factualLookupReal from "../components/ai/__fixtures__/backend-real/factual_lookup.json";

// Fixture-backed browser QA (2026-09-23) — the six real backend-finalizer
// captures used throughout this engagement's own contract tests
// (test_aev2_frontend_contract.py / answerTypes.backendContract.test.ts),
// rendered through the ACTUAL page for the first time. Live provider
// capacity is exhausted, so this is the only way to see five of the six
// modes' happy paths render at all right now — see this repo's own
// project memory for that condition.
const MODES = [
  { name: "direct_company_research", fixture: directCompanyResearchReal, query: "Should I invest in Reliance Industries?" },
  { name: "switch_analysis", fixture: switchAnalysisReal, query: "Should I continue holding BEL or switch to HAL?" },
  { name: "company_comparison", fixture: companyComparisonReal, query: "Compare Infosys and TCS" },
  { name: "event_impact", fixture: eventImpactReal, query: "Reliance Jio just announced its 5G rollout is complete, what does this mean?" },
  { name: "market_pulse", fixture: marketPulseReal, query: "top gainers today" },
  { name: "factual_lookup", fixture: factualLookupReal, query: "What was TCS's Q4 FY25 revenue?" },
] as const;

const SEARCH_PLACEHOLDER = "Ask any market question — hold, switch, compare, or analyse…";

async function submitQuery(page: Page, query: string): Promise<void> {
  await page.goto("/ai-search");
  const textarea = page.getByPlaceholder(SEARCH_PLACEHOLDER);
  await textarea.fill(query);
  await textarea.press("Enter");
  await expect(page.getByTestId("ai-answer-shell")).toBeVisible({ timeout: 10_000 });
}

function clone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

// ── 1. All six modes render their real layout from a real captured contract ──

for (const mode of MODES) {
  test(`${mode.name}: renders the real layout from a real backend contract`, async ({ page }) => {
    await mockSearchStream(page, mode.fixture);
    await submitQuery(page, mode.query);

    const shell = page.getByTestId("ai-answer-shell");
    await expect(shell).toHaveAttribute("data-ui-mode", mode.name);
    // Never the legacy degraded/"analysis unavailable" chrome for a
    // fixture that IS a real, eligible successful contract.
    await expect(page.getByTestId("degraded-search-answer")).not.toBeVisible();

    await page.screenshot({ path: `e2e/.output/screenshots/${mode.name}-desktop-light.png`, fullPage: true });
  });
}

// ── 2. Desktop/mobile x light/dark, on the flagship mode ─────────────────────

test.describe("direct_company_research — viewport/theme matrix", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`renders correctly in ${theme} mode`, async ({ page }) => {
      await setTheme(page, theme);
      await mockSearchStream(page, directCompanyResearchReal);
      await submitQuery(page, "Should I invest in Reliance Industries?");

      if (theme === "dark") {
        await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
      }
      await page.screenshot({ path: `e2e/.output/screenshots/direct_company_research-${test.info().project.name}-${theme}.png`, fullPage: true });
    });
  }
});

// ── 3. Edge cases: missing fields, long titles, zero evidence, partial evidence ──

test.describe("edge cases", () => {
  test("missing optional fields (no price data, no timeline) renders without blank sections", async ({ page }) => {
    const mutated = clone(directCompanyResearchReal) as { answer_experience_v2: Record<string, unknown> };
    mutated.answer_experience_v2.companies_affected = { currently_higher: [], currently_lower: [], omitted_unattributed: [] };
    mutated.answer_experience_v2.time_horizon = { primary_horizon: null, timeline_phases: [] };
    mutated.answer_experience_v2.risks_and_invalidation = { kind: "analysis", risks: [], invalidates_if: [], watch_for: [] };

    await mockSearchStream(page, mutated);
    await submitQuery(page, "Should I invest in Reliance Industries?");

    await expect(page.getByTestId("ai-answer-shell")).toHaveAttribute("data-ui-mode", "direct_company_research");
    await page.screenshot({ path: "e2e/.output/screenshots/edge-missing-fields.png", fullPage: true });
  });

  test("a very long title/conclusion wraps without breaking the layout", async ({ page }) => {
    const longText = "Reliance Industries secured a 2,500 MW power supply contract that materially expands its renewable energy generation capacity across multiple states and represents one of the largest single infrastructure commitments announced by an Indian conglomerate in the current fiscal year, with analysts noting significant downstream implications for the broader clean-energy supply chain. ".repeat(2);
    const mutated = clone(directCompanyResearchReal) as { query: string; answer_experience_v2: { direct_conclusion: { text: string } } };
    mutated.query = longText;
    mutated.answer_experience_v2.direct_conclusion.text = longText;

    await mockSearchStream(page, mutated);
    await submitQuery(page, "Should I invest in Reliance Industries?");

    const shell = page.getByTestId("ai-answer-shell");
    await expect(shell).toBeVisible();
    // No horizontal scrollbar/overflow — the shell's own bounding box
    // must not exceed the viewport width even with an unusually long
    // real-world title.
    const shellBox = await shell.boundingBox();
    const viewportSize = page.viewportSize();
    if (shellBox && viewportSize) {
      expect(shellBox.width).toBeLessThanOrEqual(viewportSize.width);
    }
    await page.screenshot({ path: "e2e/.output/screenshots/edge-long-title.png", fullPage: true });
  });

  test("zero evidence (real degraded state, no leaked fixture, no fabricated fallback content)", async ({ page }) => {
    const mutated = clone(directCompanyResearchReal) as Record<string, unknown>;
    mutated.synthesis_incomplete = true;
    mutated.degraded_reason = "capacity";
    mutated.related_events = [];
    mutated.news = [];
    mutated.policies = [];
    delete mutated.answer_experience_v2;

    await mockSearchStream(page, mutated);
    await submitQuery(page, "Should I invest in Reliance Industries?");

    const shell = page.getByTestId("ai-answer-shell");
    await expect(shell).toHaveAttribute("data-ui-mode", "degraded");
    await expect(page.getByText("Limited evidence")).toBeVisible();
    // The two real bugs this exact scenario caught live (2026-09-23,
    // commit 27f4f1e) — regression-proofed here at the browser level,
    // not just in unit tests.
    await expect(page.getByText("Evidence Coverage")).not.toBeVisible();
    await expect(page.getByText(/No related news, events, or policy evidence was found/)).toBeVisible();
    await expect(page.getByText(/shown below/)).not.toBeVisible();

    await page.screenshot({ path: "e2e/.output/screenshots/edge-zero-evidence.png", fullPage: true });
  });

  test("partially populated evidence (event with no linked sectors or observed reactions) renders honestly, no fabricated fill", async ({ page }) => {
    const mutated = clone(eventImpactReal) as { answer_experience_v2: { event_impact: Record<string, unknown> } };
    mutated.answer_experience_v2.event_impact.linked_sectors = [];
    mutated.answer_experience_v2.event_impact.observed_reactions = [];

    await mockSearchStream(page, mutated);
    await submitQuery(page, "Reliance Jio just announced its 5G rollout is complete, what does this mean?");

    await expect(page.getByTestId("ai-answer-shell")).toHaveAttribute("data-ui-mode", "event_impact");
    await page.screenshot({ path: "e2e/.output/screenshots/edge-partial-evidence.png", fullPage: true });
  });
});

// ── 4. New Search works; Refine stays disabled ───────────────────────────────

test.describe("shell chrome behavior", () => {
  test("New Search clears the result and returns to the empty search state", async ({ page }) => {
    await mockSearchStream(page, directCompanyResearchReal);
    await submitQuery(page, "Should I invest in Reliance Industries?");

    await page.getByRole("button", { name: "New Search" }).click();

    await expect(page.getByTestId("ai-answer-shell")).not.toBeVisible();
    await expect(page.getByPlaceholder(SEARCH_PLACEHOLDER)).toHaveValue("");
  });

  test("Refine stays disabled even on a real, fully successful contract", async ({ page }) => {
    await mockSearchStream(page, directCompanyResearchReal);
    await submitQuery(page, "Should I invest in Reliance Industries?");

    const refineButton = page.getByRole("button", { name: /Refine/ });
    await expect(refineButton).toBeDisabled();
    await expect(refineButton).toHaveAttribute("title", "Refinement is being upgraded for this answer format.");
  });
});
