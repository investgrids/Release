const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const out = "D:/IG-ai-v2-release/apps/backend/benchmarks/ai_search/baseline_2026_10_04/step7/screenshots/";
  await p.goto("http://localhost:3101/ai-search", { waitUntil: "domcontentloaded" }); await p.waitForSelector('[data-testid="suggestions"]', { timeout: 30000 }); await p.waitForTimeout(800);
  await p.screenshot({ path: out + "look_landing.png", clip: { x: 0, y: 60, width: 1440, height: 760 } });
  await p.goto("http://localhost:3101/ai-search?q=" + encodeURIComponent("Compare HDFC Bank and ICICI Bank"), { waitUntil: "domcontentloaded" }); await p.waitForSelector("[data-kind]", { timeout: 30000 }); await p.waitForTimeout(1000);
  await p.screenshot({ path: out + "look_answer.png", clip: { x: 0, y: 120, width: 1440, height: 1100 } });
  await b.close();
})();
