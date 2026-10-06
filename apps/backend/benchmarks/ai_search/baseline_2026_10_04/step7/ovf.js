const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await p.route(/\/api\/ai\/search$/, async (r) => { if (r.request().method() !== "POST") return r.continue(); await new Promise((x) => setTimeout(x, 6000)); r.abort(); });
  await p.route("**/api/ai/search/stream**", async (r) => { await new Promise((x) => setTimeout(x, 6000)); r.abort(); });
  await p.goto(process.argv[2] + "/ai-search?q=" + encodeURIComponent("What is happening with Wipro?"), { waitUntil: "domcontentloaded" });
  await p.waitForSelector('[data-testid="ai-search-working"]'); await p.waitForTimeout(500);
  console.log(JSON.stringify(await p.evaluate(() => {
    const cw = document.documentElement.clientWidth; const bad = [];
    document.querySelectorAll("body *").forEach((e) => { const r = e.getBoundingClientRect(); if (r.right > cw + 1 && r.width > 0) bad.push((e.tagName + "." + String(e.className).split(" ").slice(0, 3).join(".")).slice(0, 80) + " right=" + Math.round(r.right)); });
    const card = document.querySelector('[data-testid="ai-search-working"]').getBoundingClientRect();
    return { scrollW: document.documentElement.scrollWidth, cw, cardRight: Math.round(card.right), offenders: bad.slice(0, 6) };
  })));
  await b.close();
})();
