// Step 6 browser verification helper. Zero provider calls: the AI Search stream is mocked from saved/deterministic responses.
//   node shot.js <name> <width> [fixtureClass|none] [path] [query]
//   fixtureClass: a key prefix of contract_audit_after.json ("01", "02", ... "13") or "none". Output: screenshots/<name>_<width>.png (full page)
const { chromium } = require("D:/IG/node_modules/playwright");
const fs = require("fs");
const path = require("path");

const [name, widthArg, fixture = "none", route = "/ai-search", query = "How is the market doing"] = process.argv.slice(2);
const width = parseInt(widthArg, 10);
const audit = JSON.parse(fs.readFileSync(path.join(__dirname, "../step5/contract_audit_after.json"), "utf-8"));
const fixtures = Object.fromEntries(Object.entries(audit).map(([k, v]) => [k.slice(0, 2), v]));
const extra = fs.existsSync(path.join(__dirname, "fixtures_extra.json")) ? JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures_extra.json"), "utf-8")) : {};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width, height: width > 800 ? 900 : 844 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.text().startsWith("DBG")) errors.push(m.text()); if (m.type() === "error") errors.push("console: " + m.text().slice(0, 1500)); });
  const result = fixtures[fixture] || extra[fixture];
  if (result) {
    await page.route("**/api/ai/search/stream**", (r) => {
      const body = "event: stage\ndata: " + JSON.stringify({ stage: "intent", label: "Understanding your question" }) + "\n\n" +
        "event: answer\ndata: " + JSON.stringify({ result, cached: false, response_id: result.response_id, latency_ms: 1200, provider: null }) + "\n\n" +
        "event: done\ndata: {}\n\n";
      r.fulfill({ status: 200, contentType: "text/event-stream", headers: { "access-control-allow-origin": "*", "cache-control": "no-cache" }, body });
    });
    await page.route("**/api/ai/search?**", (r) => r.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: JSON.stringify({ query, cached: false, result }) }));
  }
  const url = "http://localhost:3000" + route + (result ? (route.includes("?") ? "&" : "?") + "q=" + encodeURIComponent(query) : "");
  await page.goto(url, { waitUntil: "networkidle", timeout: 90000 });
  await page.waitForTimeout(result ? 2500 : 1200);
  const overflow = await page.evaluate(() => ({ scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth, bg: getComputedStyle(document.body).backgroundColor }));
  const out = path.join(__dirname, "screenshots", `${name}_${width}.png`);
  await page.screenshot({ path: out, fullPage: true });
  console.log(JSON.stringify({ out, overflow, horizontalOverflow: overflow.scrollW > overflow.clientW + 1, errors: errors.slice(0, 12) }));
  await browser.close();
})();
