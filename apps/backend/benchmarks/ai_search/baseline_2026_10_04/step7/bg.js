const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto(process.argv[2] + "/ai-search", { waitUntil: "domcontentloaded" }); await p.waitForTimeout(2500);
  const chain = await p.evaluate(() => { const out = []; let e = document.querySelector('[data-testid="ai-search-page"]'); while (e) { const c = getComputedStyle(e).backgroundColor; if (c !== "rgba(0, 0, 0, 0)") out.push((e.tagName + "." + (e.className || "").toString().split(" ").slice(0, 3).join(".")).slice(0, 70) + " " + c); e = e.parentElement; } return out; });
  console.log(chain.join("\n")); await b.close();
})();
