const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.route("**/api/ai/search/suggestions", async (r) => { await new Promise((x) => setTimeout(x, 2000)); r.continue(); });
  const seen = [];
  await p.goto(process.argv[2] + "/ai-search", { waitUntil: "domcontentloaded" });
  const t0 = Date.now();
  while (Date.now() - t0 < 6000) {
    seen.push(await p.evaluate(() => (document.querySelector('[data-testid="suggestions-loading"]') ? "placeholder" : document.querySelector('[data-testid="suggestions"] h2') ? document.querySelector('[data-testid="suggestions"] h2').innerText.split("\n")[0].trim() : "none")));
    await p.waitForTimeout(150);
  }
  console.log("sequence:", seen.filter((v, i) => v !== seen[i - 1]).join(" -> ")); await b.close();
})();
