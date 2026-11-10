import { afterEach, describe, expect, it, vi } from "vitest";
import { GET as sitemapGET } from "./route";
import { GET as newsSitemapGET } from "../news-sitemap.xml/route";

// Workstream C (2026-11-10): an article the backend marks search_indexable=false
// renders noindex, so listing it in either sitemap would be a contradictory signal.

const recent = new Date().toISOString();
const ITEMS = [
  { slug: "kept-article", article_type: "policy_intelligence", published_at: recent, search_indexable: true },
  { slug: "noindexed-article", article_type: "policy_intelligence", published_at: recent, search_indexable: false },
  { slug: "legacy-no-field", article_type: "policy_intelligence", published_at: recent },
];

function stubFetch() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const body = String(url).includes("/api/insights/?limit=100") ? { items: ITEMS } : {};
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe("sitemaps exclude search_indexable=false articles", () => {
  it("sitemap.xml", async () => {
    stubFetch();
    const xml = await (await sitemapGET()).text();
    expect(xml).toContain("/newsroom/article/kept-article");
    expect(xml).toContain("/newsroom/article/legacy-no-field");
    expect(xml).not.toContain("noindexed-article");
  });

  it("news-sitemap.xml", async () => {
    stubFetch();
    const xml = await (await newsSitemapGET()).text();
    expect(xml).toContain("/newsroom/article/kept-article");
    expect(xml).toContain("/newsroom/article/legacy-no-field");
    expect(xml).not.toContain("noindexed-article");
  });
});
