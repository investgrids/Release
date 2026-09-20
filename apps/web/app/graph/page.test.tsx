/**
 * app/graph/page.tsx (2026-09-20 egress fix) -- real production finding:
 * this page used to fetch the ENTIRE intelligence graph (8.34MB) purely
 * to compute a center node, then discard it in ~97% of real cases in
 * favor of a small bounded subgraph. Proves the page now calls only the
 * bounded /api/graph/default-subgraph endpoint and never /api/graph/full.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import GraphPage from "./page";

vi.mock("./GraphCanvas", () => ({ GraphCanvas: () => null }));

function mockFetchWith(responder: (url: string) => { ok: boolean; json: () => Promise<unknown> }) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => responder(url)));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("graph/page.tsx -- bounded fetch only", () => {
  it("calls /api/graph/default-subgraph and never /api/graph/full", async () => {
    const calls: string[] = [];
    mockFetchWith((url) => {
      calls.push(url);
      if (url.includes("/api/graph/full")) {
        throw new Error("TEST FAILURE: /api/graph/full was requested");
      }
      if (url.includes("/api/graph/default-subgraph")) {
        return { ok: true, json: async () => ({ nodes: [{ id: "a" }, { id: "b" }], edges: [], center_id: "a" }) };
      }
      return { ok: false, json: async () => ({}) };
    });

    renderToStaticMarkup(await GraphPage());

    expect(calls.some(u => u.includes("/api/graph/default-subgraph"))).toBe(true);
    expect(calls.some(u => u.includes("/api/graph/full"))).toBe(false);
  });

  it("renders nothing crash-worthy when the endpoint returns an empty graph", async () => {
    mockFetchWith((url) => {
      if (url.includes("/api/graph/default-subgraph")) {
        return { ok: true, json: async () => ({ nodes: [], edges: [], center_id: null }) };
      }
      return { ok: false, json: async () => ({}) };
    });

    // Must not throw.
    renderToStaticMarkup(await GraphPage());
  });

  it("renders nothing crash-worthy when the endpoint request fails", async () => {
    mockFetchWith(() => ({ ok: false, json: async () => ({}) }));

    renderToStaticMarkup(await GraphPage());
  });
});
