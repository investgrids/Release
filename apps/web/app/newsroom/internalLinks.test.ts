import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

/**
 * Batch G, 2026-09-20 -- /newsroom/themes/{slug} is now a pure 308 redirect
 * layer (see themes/[slug]/page.tsx), never a rendered destination. Any
 * internal link still pointing there sends real traffic through a needless
 * redirect hop. This is a source-pattern regression gate (same convention
 * as loadingSafety.test.ts) rather than a full render test, since
 * app/newsroom/page.tsx pulls in a large real data-fetch surface (hero,
 * companies, news, mie, indices, stats) that a unit test shouldn't need to
 * mock in full just to check a single href's shape.
 */
const NEWSROOM_PAGE = path.resolve(__dirname, "page.tsx");
const HOMEPAGE = path.resolve(__dirname, "..", "page.tsx");

describe("internal links never pass through the legacy /newsroom/themes/{slug} redirect", () => {
  it("app/newsroom/page.tsx's 'Themes to Watch' table links directly to /opportunity-radar/{id}", () => {
    const src = fs.readFileSync(NEWSROOM_PAGE, "utf-8");
    expect(src).not.toMatch(/newsroom\/themes\/\$\{/);
    expect(src).toMatch(/opportunity-radar\/\$\{t\.id\}/);
  });

  it("the homepage does not link to the legacy per-slug theme-detail path either", () => {
    const src = fs.readFileSync(HOMEPAGE, "utf-8");
    // Excludes comment lines -- a historical "// was /newsroom/themes/${...}"
    // note documenting an earlier fix is not a live link and shouldn't fail
    // this gate; only an actual unfixed usage should.
    const liveLines = src.split("\n").filter((l) => !l.trim().startsWith("//"));
    expect(liveLines.join("\n")).not.toMatch(/newsroom\/themes\/\$\{/);
  });
});
