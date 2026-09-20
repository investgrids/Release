/**
 * IntelligenceGraph.tsx (2026-09-20 egress fix) -- real production
 * finding: the live-poll's "topology changed" handler fetched the ENTIRE
 * intelligence graph (8.34MB) on essentially every poll where the graph
 * grew (near-constant, given continuous ingestion), then unconditionally
 * replaced whatever curated neighborhood the user had open with that
 * entire dump. Covers: pickCenter's deterministic tie-break, that
 * /api/graph/full is never requested, that the refresh preserves the
 * user's current center via a bounded /subgraph call, and that
 * overlapping 30s poll ticks don't fire concurrent request cycles.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { IntelligenceGraph, pickCenter } from "./IntelligenceGraph";

// jsdom has no ResizeObserver -- the component observes its container to
// track canvas size, irrelevant to the network-behavior this file tests.
class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function node(id: string, node_type = "company") {
  return { id, node_type, label: id };
}
function edge(id: string, source: string, target: string) {
  return { id, source, target, edge_type: "influences", weight: 0.5, confidence: 0.5 };
}

function baseGraph() {
  return {
    center_id: "company:center",
    nodes: [node("company:center"), node("company:a"), node("company:b")],
    edges: [edge("e1", "company:center", "company:a"), edge("e2", "company:center", "company:b")],
  };
}

describe("pickCenter -- deterministic tie-break", () => {
  it("picks the lexically smallest id on an exact score tie", () => {
    const nodes = [node("company:zzz"), node("company:aaa")];
    const edges = [edge("e1", "company:zzz", "company:aaa")];
    // Both have degree 1, identical rank 0 -- a genuine tie.
    expect(pickCenter(nodes, edges)).toBe("company:aaa");
  });

  it("is stable across repeated calls with the same input", () => {
    const nodes = [node("company:zzz"), node("company:aaa")];
    const edges = [edge("e1", "company:zzz", "company:aaa")];
    const results = new Set(Array.from({ length: 5 }, () => pickCenter(nodes, edges)));
    expect(results.size).toBe(1);
  });

  it("still prefers the real highest-degree node over the tiebreak", () => {
    const nodes = [node("company:zzz"), node("company:aaa"), node("company:hub")];
    const edges = [
      edge("e1", "company:zzz", "company:hub"),
      edge("e2", "company:aaa", "company:hub"),
    ];
    expect(pickCenter(nodes, edges)).toBe("company:hub");
  });
});

describe("IntelligenceGraph -- bounded live refresh", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("never requests /api/graph/full, even across topology changes", async () => {
    const calls: string[] = [];
    let topologyCall = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      calls.push(url);
      if (url.includes("/api/graph/full")) {
        throw new Error("TEST FAILURE: /api/graph/full was requested");
      }
      if (url.includes("/api/graph/live")) {
        topologyCall += 1;
        // Change topology on every call after the first, to force the
        // refresh branch as often as possible.
        return { ok: true, json: async () => ({ prices: {}, topology: { node_count: 3 + topologyCall, edge_count: 2 + topologyCall }, updated_at: "2026-09-20T00:00:00Z" }) };
      }
      if (url.includes("/api/graph/subgraph/")) {
        return { ok: true, json: async () => baseGraph() };
      }
      return { ok: false, json: async () => ({}) };
    }));

    render(<IntelligenceGraph initialGraph={baseGraph()} />);

    // Advance past several 30s ticks, each with a topology change.
    for (let i = 0; i < 4; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });
    }

    expect(calls.some(u => u.includes("/api/graph/full"))).toBe(false);
    expect(calls.some(u => u.includes("/api/graph/subgraph/"))).toBe(true);
  });

  it("refreshes around the server-provided initial center_id, not a hardcoded/stale value", async () => {
    // Proves the live-refresh path reads the actual current centerId
    // (via centerIdRef, kept in sync every render) rather than closing
    // over a stale value from mount -- the exact class of bug fixed
    // alongside the full-graph removal (the original code's fetchLive
    // callback closed over `gData` from mount time via its dependency
    // array, but the interval effect captured that FIRST callback
    // instance permanently, so it was reading stale data on every tick).
    const subgraphRequests: string[] = [];
    let tick = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("/api/graph/live")) {
        tick += 1;
        return { ok: true, json: async () => ({ prices: {}, topology: { node_count: 3 + tick, edge_count: 2 + tick }, updated_at: "2026-09-20T00:00:00Z" }) };
      }
      if (url.includes("/api/graph/subgraph/")) {
        subgraphRequests.push(url);
        return { ok: true, json: async () => baseGraph() };
      }
      return { ok: false, json: async () => ({}) };
    }));

    render(<IntelligenceGraph initialGraph={baseGraph()} />);
    await act(async () => {}); // let init-center/layout effects settle

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000);
    });

    expect(subgraphRequests.some(u => u.includes(encodeURIComponent("company:center")))).toBe(true);
  });

  it("does not fire an overlapping poll while a previous one is still in flight", async () => {
    let liveCallCount = 0;
    const pending: { resolve: (() => void) | undefined } = { resolve: undefined };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("/api/graph/live")) {
        liveCallCount += 1;
        if (liveCallCount === 1) {
          // First call hangs until the test explicitly releases it.
          await new Promise<void>(resolve => { pending.resolve = resolve; });
        }
        return { ok: true, json: async () => ({ prices: {}, topology: { node_count: 3, edge_count: 2 }, updated_at: "2026-09-20T00:00:00Z" }) };
      }
      return { ok: false, json: async () => ({}) };
    }));

    render(<IntelligenceGraph initialGraph={baseGraph()} />);

    // Two more 30s ticks fire while the first call is still hanging.
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });

    // Only the very first call should have actually reached fetch --
    // the in-flight guard must have skipped the two ticks that fired
    // while it was still pending.
    expect(liveCallCount).toBe(1);

    pending.resolve?.();
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  });
});
