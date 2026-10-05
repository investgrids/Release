const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const errs = []; p.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 100)); });
  for (const [n, q] of [["wipro", "What is happening with Wipro?"], ["compare", "Compare HDFC Bank and ICICI Bank"]]) {
    await p.goto("http://localhost:3101/ai-search?q=" + encodeURIComponent(q), { waitUntil: "domcontentloaded" });
    await p.waitForSelector("[data-kind]", { timeout: 30000 }); await p.waitForTimeout(1200);
    await p.screenshot({ path: `D:/IG-ai-v2-release/apps/backend/benchmarks/ai_search/baseline_2026_10_04/step7/screenshots/preview_${n}.png`, fullPage: true });
    console.log(n, await p.evaluate(() => document.querySelector("[data-kind]").getAttribute("data-kind")));
  }
  console.log("console errors:", errs.length); await b.close();
})();
