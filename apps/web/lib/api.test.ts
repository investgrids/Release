// Cost follow-up: server-side API fetches are cached for a short time instead of hitting the backend on every render.
import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchAPI, DEFAULT_REVALIDATE_S } from "./api";

const ok = () => vi.fn(async (_url: string, _init?: RequestInit) => ({ ok: true, status: 200, json: async () => ({ a: 1 }) }));
afterEach(() => { vi.unstubAllGlobals(); });

describe("fetchAPI caching", () => {
  it("uses the Next data cache with a short default lifetime instead of no-store", async () => {
    const f = ok(); vi.stubGlobal("fetch", f);
    await fetchAPI("/api/insights/?limit=1");
    const init = f.mock.calls[0][1] as RequestInit & { next?: { revalidate: number } };
    expect(init.next?.revalidate).toBe(DEFAULT_REVALIDATE_S);
    expect(DEFAULT_REVALIDATE_S).toBeGreaterThan(0);
    expect(init.cache).toBeUndefined();
  });
  it("honours a per-call lifetime", async () => {
    const f = ok(); vi.stubGlobal("fetch", f);
    await fetchAPI("/api/data/quotes?symbols=TCS", { revalidate: 30 });
    expect((f.mock.calls[0][1] as { next: { revalidate: number } }).next.revalidate).toBe(30);
  });
  it("revalidate: 0 opts out and fetches fresh every time", async () => {
    const f = ok(); vi.stubGlobal("fetch", f);
    await fetchAPI("/api/x", { revalidate: 0 });
    expect((f.mock.calls[0][1] as RequestInit).cache).toBe("no-store");
  });
  it("still throws on a non-OK response (errors are never cached as data)", async () => {
    vi.stubGlobal("fetch", vi.fn(async (_url: string, _init?: RequestInit) => ({ ok: false, status: 503, json: async () => ({}) })));
    await expect(fetchAPI("/api/x")).rejects.toThrow(/503/);
  });
});
