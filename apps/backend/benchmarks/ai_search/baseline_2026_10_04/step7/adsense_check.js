const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext()).newPage();
  const csp = [], req = [];
  p.on("console", (m) => { if (/Content Security Policy|violates the following/i.test(m.text())) csp.push(m.text().slice(0, 160)); });
  p.on("response", (r) => { if (/googlesyndication|adtrafficquality|googleadservices/.test(r.url())) req.push(r.status() + " " + r.url().slice(0, 90)); });
  await p.goto("http://localhost:3101/ai-search", { waitUntil: "load" }); await p.waitForTimeout(5000);
  console.log("adsbygoogle global defined:", await p.evaluate(() => typeof window.adsbygoogle !== "undefined"));
  console.log("CSP violations:", csp.length, csp.slice(0, 2));
  console.log("google ad requests:", req.slice(0, 4));
  await b.close();
})();
