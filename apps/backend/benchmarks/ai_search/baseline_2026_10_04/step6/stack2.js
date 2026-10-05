const { chromium } = require("D:/IG/node_modules/playwright");
const fs = require("fs"), path = require("path");
const audit = JSON.parse(fs.readFileSync(path.join(__dirname, "../step5/contract_audit_after.json"), "utf-8"));
const result = Object.entries(audit).find(([k]) => k.startsWith("01"))[1];
(async () => {
  const b = await chromium.launch(); const logs=[]; const page = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  page.on("console", m => { if (m.text().startsWith("DBG")) logs.push(m.text()); });
  await page.addInitScript(() => { const o = console.error; window.__st = []; console.error = function (...a) { if (String(a[0]).includes("Maximum update depth") && window.__st.length < 1) window.__st.push(new Error().stack); o.apply(console, a); }; });
  await page.route("**/api/ai/search/stream**", (r) => r.fulfill({ status: 200, contentType: "text/event-stream", headers: { "access-control-allow-origin": "*" }, body: "event: answer\ndata: " + JSON.stringify({ result, cached: false, response_id: result.response_id }) + "\n\nevent: done\ndata: {}\n\n" }));
  for (let i = 0; i < 50; i++) {
    await page.goto("http://localhost:3000/ai-search?q=" + encodeURIComponent(result.query), { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    const st = await page.evaluate(() => window.__st); const c={}; logs.forEach(l=>c[l]=(c[l]||0)+1); console.log(i, JSON.stringify(Object.entries(c).slice(0,10)), st.length); logs.length=0;
    if (st.length) { console.log(st[0].split("\n").slice(0, 14).join("\n")); break; }
  }
  await b.close();
})();
