import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

/**
 * Batch G, 2026-09-20 -- the sitemap must list the real, now-genuinely-
 * indexable /newsroom/themes hub, but never a per-slug
 * /newsroom/themes/{slug} entry (those are pure redirects to their real
 * /opportunity-radar/{id} canonical -- a sitemap listing a redirecting URL
 * is a confirmed Search Console "Page with redirect" warning, the exact
 * problem this route's own code comments already document). Source-pattern
 * gate rather than executing the route handler, since buildEntries() makes
 * a real network-fetch fan-out this unit test shouldn't need to mock.
 */
const ROUTE_FILE = path.resolve(__dirname, "route.ts");

describe("sitemap excludes legacy theme-detail URLs but includes the real hub", () => {
  const src = fs.readFileSync(ROUTE_FILE, "utf-8");

  it("includes /newsroom/themes as a real static entry", () => {
    expect(src).toMatch(/\$\{base\}\/newsroom\/themes`/);
  });

  it("never constructs a per-slug /newsroom/themes/{slug} sitemap URL", () => {
    expect(src).not.toMatch(/newsroom\/themes\/\$\{/);
  });
});
