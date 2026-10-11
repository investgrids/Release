// Live AI Search check on www.marketripple.in using only deterministic questions (education / product information): zero AI provider calls.
// Also looks for broken images (article hero images lived on the old volume).
const { chromium } = require("playwright");
const path = require("path");
const OUT = path.join(__dirname, "screenshots", "live");
const SITE = "https://www.marketripple.in";
(async () => {
  const browser = await chromium.launch();
  for (const [name, q, testid, width] of [
    ["education", "What is a P/E ratio and how should I read it?", "answer-education", 1440],
    ["product", "How does the MarketRipple Score work?", "answer-product", 1440],
    ["education_mobile", "What is a P/E ratio and how should I read it?", "answer-education", 390],
  ]) {
    const page = await (await browser.newContext({ viewport: { width, height: width > 800 ? 900 : 844 } })).newPage();
    const errs = [], apiCalls = [];
    page.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 120)); });
    page.on("response", (r) => { const u = new URL(r.url()); if (u.host === "api.marketripple.in" && /ai\/search/.test(u.pathname) && !/suggestions/.test(u.pathname)) apiCalls.push(r.status() + " " + u.pathname); });
    await page.goto(SITE + "/ai-search?q=" + encodeURIComponent(q), { waitUntil: "domcontentloaded", timeout: 90000 });
    const ok = await page.waitForSelector(`[data-testid="${testid}"]`, { timeout: 60000 }).then(() => true).catch(() => false);
    await page.waitForTimeout(1500);
    const info = await page.evaluate(() => ({ h1: (document.querySelector("h1") || {}).innerText, text: document.body.innerText, bg: getComputedStyle(document.body).backgroundColor, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
    await page.screenshot({ path: path.join(OUT, `ai_${name}.png`), fullPage: true });
    const forbidden = /confidence|6-12 months|opportunity score|Not Applicable/i.test(info.text.replace(/Coverage is not confidence/gi, ""));
    console.log(`${ok ? "ok   " : "FAIL "} ${name}@${width}: presentation=${ok} | search calls=${JSON.stringify(apiCalls)} | forbidden text=${forbidden} | white bg=${info.bg === "rgb(255, 255, 255)"} | overflow=${width < 800 ? info.sw > info.cw + 1 : "n/a"} | console errors=${errs.length}`);
    if (!ok) console.log("   page text sample:", info.text.slice(0, 200).replace(/\s+/g, " "));
  }
  // images: visit the newsroom and an article, report any image request that fails
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const bad = [], good = [];
  page.on("response", (r) => { if (r.request().resourceType() === "image") (r.status() >= 400 ? bad : good).push(r.status() + " " + r.url().slice(0, 90)); });
  for (const route of ["/newsroom", "/events"]) {
    await page.goto(SITE + route, { waitUntil: "networkidle", timeout: 90000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
  console.log(`images on /newsroom and /events: ${good.length} loaded, ${bad.length} failed`);
  bad.slice(0, 5).forEach((b) => console.log("   failed image:", b));
  await browser.close();
})();
