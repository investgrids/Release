// Live-site check for www.marketripple.in after the backend cutover. Real browser, real production. Makes ordinary page loads only; it never submits an AI question (no provider quota is used).
//   node live_check.js [outDir]
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path");
const SITE = "https://www.marketripple.in";
const NEW_API = "api.marketripple.in", OLD_API = "backend-production-78042.up.railway.app";
const out = process.argv[2] || path.join(__dirname, "screenshots", "live");
fs.mkdirSync(out, { recursive: true });

const PAGES = [
  ["home", "/"], ["events", "/events"], ["companies", "/companies"], ["ai_search", "/ai-search"], ["sectors", "/sectors"], ["market", "/market-intelligence"],
];

async function visit(browser, name, route, width) {
  const ctx = await browser.newContext({ viewport: { width, height: width > 800 ? 900 : 844 } });
  const page = await ctx.newPage();
  const consoleErrors = [], failed = [], apiHosts = new Set(), statuses = {};
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 140)); });
  page.on("pageerror", (e) => consoleErrors.push("pageerror: " + e.message.slice(0, 140)));
  page.on("response", (r) => {
    const u = new URL(r.url());
    if (u.host === NEW_API || u.host === OLD_API) { apiHosts.add(u.host); statuses[r.status()] = (statuses[r.status()] || 0) + 1; if (r.status() >= 400) failed.push(r.status() + " " + u.pathname.slice(0, 60)); }
  });
  const resp = await page.goto(SITE + route, { waitUntil: "networkidle", timeout: 90000 }).catch((e) => ({ status: () => "ERR " + e.message.slice(0, 60) }));
  await page.waitForTimeout(2500);
  const info = await page.evaluate(() => ({
    title: document.title, h1: (document.querySelector("h1") || {}).innerText || null, textLen: document.body.innerText.length,
    emptyStates: (document.body.innerText.match(/no data|unavailable|failed to load|something went wrong|try again later/gi) || []).length,
    scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
    suggestions: Array.from(document.querySelectorAll('[data-testid="suggestions"] button')).map((b) => b.innerText.replace(/\s+/g, " ").slice(0, 60)).slice(0, 3),
    suggestionsHeading: (document.querySelector('[data-testid="suggestions"] h2') || {}).innerText || null,
  }));
  await page.screenshot({ path: path.join(out, `${name}_${width}.png`), fullPage: false });
  await ctx.close();
  return { name, width, http: resp.status(), ...info, apiHosts: [...apiHosts], apiStatuses: statuses, apiFailures: failed.slice(0, 4), consoleErrors: consoleErrors.slice(0, 3) };
}

(async () => {
  const browser = await chromium.launch();
  const rows = [];
  for (const [n, r] of PAGES) rows.push(await visit(browser, n, r, 1440));
  for (const [n, r] of [PAGES[0], PAGES[3], PAGES[2]]) rows.push(await visit(browser, n, r, 390));
  await browser.close();
  let bad = 0;
  for (const r of rows) {
    const usingNew = r.apiHosts.includes(NEW_API) && !r.apiHosts.includes(OLD_API);
    const problems = [];
    if (r.http !== 200) problems.push("HTTP " + r.http);
    if (!usingNew && r.apiHosts.length) problems.push("still calling " + r.apiHosts.join(","));
    if (r.apiFailures.length) problems.push("api failures: " + r.apiFailures.join("; "));
    if (r.consoleErrors.length) problems.push("console: " + r.consoleErrors[0]);
    if (r.width < 800 && r.scrollW > r.clientW + 1 && r.name !== "home") problems.push("horizontal overflow");
    if (problems.length) bad++;
    console.log((problems.length ? "ISSUE " : "ok    ") + `${r.name}@${r.width}`.padEnd(18) + ` api:${r.apiHosts.join("|") || "-"} ${JSON.stringify(r.apiStatuses)} ` + problems.join(" | "));
  }
  const ai = rows.find((r) => r.name === "ai_search" && r.width === 1440);
  console.log("AI Search landing:", ai.suggestionsHeading, "|", (ai.suggestions || []).join(" || "));
  fs.writeFileSync(path.join(out, "live_check.json"), JSON.stringify(rows, null, 1));
  console.log(bad ? `${bad} page(s) with issues` : "ALL PAGES CLEAN");
})();
