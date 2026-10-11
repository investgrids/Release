const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const page = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const bad = [], good = []; let broken = 0;
  page.on("response", (r) => { if (r.request().resourceType() === "image") (r.status() >= 400 ? bad : good).push(r.status() + " " + r.url().slice(0, 100)); });
  for (const route of ["/", "/insights", "/newsroom", "/events"]) {
    await page.goto("https://www.marketripple.in" + route, { waitUntil: "networkidle", timeout: 90000 }).catch(() => {});
    await page.waitForTimeout(1500);
    const n = await page.evaluate(() => Array.from(document.images).filter((i) => i.complete && i.naturalWidth === 0 && i.src && !i.src.startsWith("data:")).length);
    broken += n;
    console.log(route.padEnd(11), "images in the DOM that are broken:", n);
  }
  console.log("image requests: ", good.length, "ok,", bad.length, "failed;", "broken <img> total:", broken);
  bad.slice(0, 4).forEach((x) => console.log("  failed:", x));
  // an older article page
  const r = await (await fetch("https://api.marketripple.in/api/insights/?limit=40")).json();
  const items = r.items || [];
  console.log("articles in the latest 40: with hero image:", items.filter((a) => a.hero_image_url).length, "| without (gradient fallback):", items.filter((a) => !a.hero_image_url).length);
  await b.close();
})();
