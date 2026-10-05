// Step 7 streamed-result stress: the integrated build with the stream transport on (NEXT_PUBLIC_AI_SEARCH_V3=1). Counts "Maximum update depth exceeded" over repeated fixture loads. Zero provider calls (stream is mocked).
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path");
const BASE = process.env.BASE || "http://localhost:3101";
const audit = JSON.parse(fs.readFileSync(path.join(__dirname, "../step5/contract_audit_after.json"), "utf-8"));
const fx = (p) => Object.entries(audit).find(([k]) => k.startsWith(p))[1];
const PLAN = [["01", 60], ["02", 25], ["10", 25], ["11", 15]];
(async () => {
  const browser = await chromium.launch();
  let loads = 0, depth = 0, otherErrors = 0;
  for (const [f, n] of PLAN) {
    const result = fx(f);
    for (let i = 0; i < n; i++) {
      const ctx = await browser.newContext({ viewport: { width: i % 2 ? 390 : 1440, height: 900 } });
      const page = await ctx.newPage();
      let d = 0, o = 0, streamed = 0;
      page.on("console", (m) => { if (m.type() === "error") { if (/Maximum update depth/.test(m.text())) d++; else if (!/ERR_FAILED/.test(m.text())) o++; } });
      page.on("pageerror", () => o++);
      await page.route("**/api/ai/search/stream**", (r) => { streamed++; r.fulfill({ status: 200, contentType: "text/event-stream", headers: { "access-control-allow-origin": "*" }, body: "event: stage\ndata: " + JSON.stringify({ stage: "intent", label: "Understanding your question" }) + "\n\nevent: answer\ndata: " + JSON.stringify({ result, cached: false, response_id: result.response_id }) + "\n\nevent: done\ndata: {}\n\n" }); });
      await page.goto(BASE + "/ai-search?q=" + encodeURIComponent(result.query), { waitUntil: "domcontentloaded" });
      await page.waitForSelector("[data-kind]", { timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(1500);
      loads++; depth += d; otherErrors += o;
      if (i === 0 && f === "01") console.log("stream transport used:", streamed > 0);
      await ctx.close();
    }
  }
  await browser.close();
  console.log(JSON.stringify({ loads, maxUpdateDepthErrors: depth, otherConsoleErrors: otherErrors }));
})();
