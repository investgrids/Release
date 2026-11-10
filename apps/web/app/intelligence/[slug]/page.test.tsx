import { afterEach, describe, expect, it, vi } from "vitest";
import { generateMetadata } from "./page";

// /intelligence/{slug} serves the same article as /newsroom/article/{slug}, so it must
// never be indexed and must point Google at the real URL.

function stubArticle(body: Record<string, unknown> | null) {
  vi.stubGlobal("fetch", vi.fn(async () =>
    body ? new Response(JSON.stringify(body), { status: 200 }) : new Response("", { status: 404 }),
  ));
}

afterEach(() => vi.unstubAllGlobals());

const params = (slug: string) => ({ params: Promise.resolve({ slug }) });

describe("/intelligence/[slug] metadata", () => {
  it("is noindex,follow with canonical to the newsroom article", async () => {
    stubArticle({ slug: "some-article", headline: "Headline" });
    const m = await generateMetadata(params("some-article"));
    expect(m.robots).toEqual({ index: false, follow: true });
    expect(m.alternates?.canonical).toBe("/newsroom/article/some-article");
  });

  it("prefers the article's own canonical_url (e.g. live_signal articles)", async () => {
    stubArticle({ slug: "sig", headline: "H", canonical_url: "https://www.marketripple.in/intelligence/signal/sig" });
    const m = await generateMetadata(params("sig"));
    expect(m.alternates?.canonical).toBe("https://www.marketripple.in/intelligence/signal/sig");
  });

  it("canonicalizes an id-based URL to the article's slug", async () => {
    stubArticle({ id: "uuid-123", slug: "real-slug", headline: "H" });
    const m = await generateMetadata(params("uuid-123"));
    expect(m.alternates?.canonical).toBe("/newsroom/article/real-slug");
  });

  it("is still noindex when the article is missing", async () => {
    stubArticle(null);
    const m = await generateMetadata(params("missing"));
    expect(m.robots).toEqual({ index: false, follow: true });
  });
});
