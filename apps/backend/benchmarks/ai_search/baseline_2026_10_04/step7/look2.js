const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto("http://localhost:3101/ai-search?q=" + encodeURIComponent("Compare HDFC Bank and ICICI Bank"), { waitUntil: "domcontentloaded" }); await p.waitForSelector('[data-testid="comparison"]', { timeout: 30000 }); await p.waitForTimeout(800);
  const el = await p.$('[data-testid="comparison"]');
  await el.screenshot({ path: "D:/IG-ai-v2-release/apps/backend/benchmarks/ai_search/baseline_2026_10_04/step7/screenshots/look_table.png" });
  const rows = await p.$$eval('[data-testid="comparison-table"] tbody tr th', (t) => t.map((x) => x.textContent));
  console.log("rows:", rows.join(" | "));
  await b.close();
})();
