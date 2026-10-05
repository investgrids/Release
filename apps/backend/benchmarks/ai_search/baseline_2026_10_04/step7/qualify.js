// Step 7 browser qualification. Zero provider calls: answers are fulfilled from the saved Step 5 contract fixtures through page.route().
//   BASE=http://localhost:3100 node qualify.js [outDir]
// Checks per state (desktop 1440 and mobile 390): renders the expected presentation, no confidence UI, no fake defaults, no verdict card, white page background, no AI-Search horizontal overflow, no console/page errors.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE || "http://localhost:3100";
const out = process.argv[2] || path.join(__dirname, "screenshots");
fs.mkdirSync(out, { recursive: true });
const audit = JSON.parse(fs.readFileSync(path.join(__dirname, "../step5/contract_audit_after.json"), "utf-8"));
const fx = (p) => Object.entries(audit).find(([k]) => k.startsWith(p))[1];

const STATES = [
  { name: "research", f: "01", testid: "answer-research" },
  { name: "partial", f: "02", testid: "answer-research", partial: true },
  { name: "education", f: "11", testid: "answer-education" },
  { name: "product", f: "12", testid: "answer-product" },
  { name: "insufficient", f: "04", testid: "answer-unavailable" },
  { name: "temp_retrieval", f: "05", testid: "answer-temporary" },
  { name: "temp_capacity", f: "07", testid: "answer-temporary" },
  { name: "gateb", f: "10", testid: "answer-unavailable" },
];
const FORBIDDEN = [/\bconfidence\b/i, /6-12 months/i, /opportunity score/i, /risk level/i, /\bMedium\s*\/\s*60\b/i, /Not Applicable/];

async function run(width, state, opts = {}) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width, height: width > 800 ? 900 : 844 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message.slice(0, 160)));
  page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text().slice(0, 160)); });
  if (opts.suggestionsDown) await page.route("**/api/ai/search/suggestions", (r) => r.abort());
  let result = null;
  if (state) {
    result = fx(state.f);
    await page.route(/\/api\/ai\/search$/, async (r) => {
      if (r.request().method() !== "POST") return r.continue();
      if (opts.delay) await new Promise((x) => setTimeout(x, opts.delay));
      r.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: JSON.stringify({ query: result.query, cached: false, result }) });
    });
    await page.route("**/api/ai/search/stream**", (r) => {
      const body = "event: answer\ndata: " + JSON.stringify({ result, cached: false, response_id: result.response_id }) + "\n\nevent: done\ndata: {}\n\n";
      r.fulfill({ status: 200, contentType: "text/event-stream", headers: { "access-control-allow-origin": "*" }, body });
    });
  }
  const url = BASE + "/ai-search" + (state ? "?q=" + encodeURIComponent(result.query) : "");
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
  const tag = (state ? state.name : opts.tag || "landing") + "_" + width;
  if (opts.delay) { await page.waitForSelector('[data-testid="ai-search-working"]', { timeout: 15000 }).catch(() => {}); await page.screenshot({ path: path.join(out, tag + ".png"), fullPage: true }); }
  if (state) await page.waitForSelector(`[data-testid="${state.testid}"]`, { timeout: 30000 }).catch(() => {});
  else await page.waitForSelector('[data-testid="suggestions"]', { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1200);
  const info = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="ai-search-page"]');
    const main = el ? el.innerText : "";
    const r = el ? el.getBoundingClientRect() : null;
    return {
      main,
      bg: getComputedStyle(document.body).backgroundColor,
      pageScrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
      contentRight: r ? Math.round(r.right) : null,
      suggestions: Array.from(document.querySelectorAll('[data-testid="suggestions"] button')).map((b) => b.innerText.replace(/\s+/g, " ")),
      suggestionsHeading: (document.querySelector('[data-testid="suggestions"] h2') || {}).innerText || null,
      verdict: !!document.querySelector('[data-testid="verdict"]'),
      kind: (document.querySelector("[data-kind]") || {}).getAttribute ? document.querySelector("[data-kind]").getAttribute("data-kind") : null,
      title: (document.querySelector('[data-testid="notice-title"]') || {}).innerText || null,
    };
  });
  const checks = {};
  checks.rendered = state ? !!(await page.$(`[data-testid="${state.testid}"]`)) : info.suggestions.length > 0;
  if (state) {
    // The product guide documents the score and legitimately says "Coverage is not confidence"; every other forbidden pattern still applies to it.
    const forbidden = state.name === "product" ? FORBIDDEN.filter((re) => !/confidence/.test(re.source)) : FORBIDDEN;
    checks.noForbiddenText = forbidden.every((re) => !re.test(info.main));
    if (state.name === "product") checks.noConfidenceGaugeOrPercent = !/\d+\s*%\s*confiden|confidence\s*[:=]?\s*\d/i.test(info.main);
    if (state.name === "education" || state.name === "product") checks.noFailureOrVerdictLanguage = !/couldn't|not enough|evidence strength/i.test(info.main);
    checks.verdictAbsent = !info.verdict;
    if (state.partial) checks.partialNotice = !!(await page.$('[data-testid="partial-notice"]'));
    if (state.name.startsWith("temp")) checks.retryShown = !!(await page.$('[data-testid="retry"]'));
    if (state.name === "insufficient") checks.noRetry = !(await page.$('[data-testid="retry"]'));
    if (state.name === "research") {
      const toggle = await page.$('[data-testid="evidence-toggle"]');
      checks.evidenceDisclosure = toggle ? true : "n/a (<=6 items)";
      if (toggle) { const before = (await page.$$('[data-testid="evidence-list"] tbody tr')).length; await toggle.click(); checks.evidenceExpands = (await page.$$('[data-testid="evidence-list"] tbody tr')).length > before; }
      checks.evidenceTablePresent = !!(await page.$('[data-testid="evidence-list"] table'));
      const fu = await page.$('[data-testid="follow-ups"] button');
      checks.followUpsPresent = !!fu;
    }
  } else {
    checks.suggestionsCount = info.suggestions.length;
    checks.suggestionsHeading = info.suggestionsHeading;
  }
  checks.whiteBackground = info.bg === "rgb(255, 255, 255)";
  checks.noAiSearchHorizontalOverflow = width > 800 ? true : info.pageScrollW <= info.clientW + 1;
  checks.noContentOverflow = info.contentRight === null ? true : info.contentRight <= info.clientW + 1;
  checks.noConsoleErrors = opts.suggestionsDown ? errors.every((e) => /ERR_FAILED/.test(e)) : errors.length === 0; // the one tolerated line is the request this check aborts on purpose
  await page.screenshot({ path: path.join(out, tag + (opts.delay ? "_done" : "") + ".png"), fullPage: true });
  await browser.close();
  return { tag, checks, kind: info.kind, bg: info.bg, scrollW: info.pageScrollW, clientW: info.clientW, errors: errors.slice(0, 3), sample: state ? undefined : info.suggestions.slice(0, 3) };
}

(async () => {
  const results = [];
  for (const width of [1440, 390]) {
    results.push(await run(width, null));
    for (const s of STATES) results.push(await run(width, s));
  }
  results.push(await run(1440, null, { suggestionsDown: true, tag: "suggestions_down" }));
  results.push(await run(390, STATES[0], { delay: 2500 }));
  let fail = 0;
  for (const r of results) {
    const bad = Object.entries(r.checks).filter(([, v]) => v === false);
    fail += bad.length;
    console.log((bad.length ? "FAIL " : "ok   ") + r.tag.padEnd(26), bad.map(([k]) => k).join(","), r.errors.length ? JSON.stringify(r.errors) : "");
  }
  fs.writeFileSync(path.join(out, "qualification.json"), JSON.stringify(results, null, 1));
  console.log("total failed checks:", fail);
})();
