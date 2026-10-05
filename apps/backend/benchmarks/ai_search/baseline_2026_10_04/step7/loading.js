const { chromium } = require("playwright");
const fs = require("fs"), path = require("path");
const audit = JSON.parse(fs.readFileSync(path.join(__dirname, "../step5/contract_audit_after.json"), "utf-8"));
const result = Object.entries(audit).find(([k]) => k.startsWith("01"))[1];
const BASE = process.argv[2];
(async () => {
  const b = await chromium.launch();
  for (const [name, width] of [["desktop", 1440], ["mobile", 390]]) {
    const p = await (await b.newContext({ viewport: { width, height: 844 } })).newPage();
    const errs = []; p.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 120)); });
    // stream path: real-looking stage events arrive over time, the answer comes last. Plain path: the POST is simply held.
    await p.route("**/api/ai/search/stream**", async (r) => {
      const stages = [["intent", "Understanding your question", 600], ["entities", "Finding the companies and sectors involved", 900], ["evidence", "Gathering evidence", 1200]];
      let body = ""; for (const [s, l] of stages) body += `event: stage\ndata: ${JSON.stringify({ stage: s, label: l })}\n\n`;
      await new Promise((x) => setTimeout(x, 2500));
      r.fulfill({ status: 200, contentType: "text/event-stream", headers: { "access-control-allow-origin": "*" }, body: body + `event: answer\ndata: ${JSON.stringify({ result, cached: false })}\n\nevent: done\ndata: {}\n\n` });
    });
    await p.route(/\/api\/ai\/search$/, async (r) => { if (r.request().method() !== "POST") return r.continue(); await new Promise((x) => setTimeout(x, 17000)); r.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: JSON.stringify({ cached: false, result }) }); });
    await p.goto(BASE + "/ai-search?q=" + encodeURIComponent("What is happening with Wipro?"), { waitUntil: "domcontentloaded" });
    await p.waitForSelector('[data-testid="ai-search-working"]', { timeout: 20000 });
    await p.waitForTimeout(1800);
    await p.screenshot({ path: path.join(__dirname, "screenshots", `researching_${name}.png`), clip: { x: 0, y: 60, width, height: 520 } });
    const t = await p.evaluate(() => ({ stages: !!document.querySelector('[data-testid="working-stages"]'), elapsed: document.querySelector('[data-testid="working-elapsed"]')?.textContent, over: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, cardRight: Math.round(document.querySelector("[data-testid=ai-search-working]").getBoundingClientRect().right) }));
    console.log(name, JSON.stringify(t), "errors:", errs.length);
  }
  await b.close();
})();
