import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

// revalidatePath requires Next's request-scoped static-generation store,
// which only exists inside a real server request — not in this unit-test
// environment. Mocked here so the happy-path tests can verify the route's
// own status/response contract without needing a full Next.js runtime;
// the actual revalidatePath call is exercised for real in production via
// the live post-deploy verification, not by this test file.
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));

const { POST } = await import("./route");

/**
 * app/api/revalidate/route.ts security hardening (2026-09-20) — real
 * production finding: reverting an Opportunity V2 canary left its page
 * publicly serving stale (already-rejected) content past its own
 * revalidate window, and this endpoint (built to fix that) had no
 * security review of its own before being wired up with a real secret.
 * Covers: missing/incorrect secret, header (not body) auth, kind
 * allowlisting, and slug validation that structurally prevents path
 * traversal — the route never treats client input as a path, only as an
 * interpolation value validated against a strict slug pattern first.
 */
const ORIGINAL_SECRET = process.env.REVALIDATE_SECRET;
const TEST_SECRET = "test-secret-value-at-least-32-bytes-long";

function makeRequest(body: unknown, headers: Record<string, string> = {}): NextRequest {
  return new NextRequest("https://example.test/api/revalidate", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "content-type": "application/json", ...headers },
  });
}

describe("POST /api/revalidate", () => {
  beforeEach(() => {
    process.env.REVALIDATE_SECRET = TEST_SECRET;
  });
  afterEach(() => {
    process.env.REVALIDATE_SECRET = ORIGINAL_SECRET;
  });

  it("returns 503 when no secret is configured at all", async () => {
    delete process.env.REVALIDATE_SECRET;
    const res = await POST(makeRequest({ kind: "opportunity_v2", slug: "real-slug" }, { "x-revalidate-secret": "anything" }));
    expect(res.status).toBe(503);
  });

  it("rejects a request with no secret header", async () => {
    const res = await POST(makeRequest({ kind: "opportunity_v2", slug: "real-slug" }));
    expect(res.status).toBe(401);
  });

  it("rejects an incorrect secret", async () => {
    const res = await POST(makeRequest({ kind: "opportunity_v2", slug: "real-slug" }, { "x-revalidate-secret": "wrong-value" }));
    expect(res.status).toBe(401);
  });

  it("ignores a secret placed in the body instead of the header", async () => {
    const res = await POST(makeRequest({ kind: "opportunity_v2", slug: "real-slug", secret: TEST_SECRET }));
    expect(res.status).toBe(401);
  });

  it("rejects an unapproved kind", async () => {
    const res = await POST(makeRequest({ kind: "newsroom_theme", slug: "real-slug" }, { "x-revalidate-secret": TEST_SECRET }));
    expect(res.status).toBe(400);
  });

  it("rejects a slug containing a path-traversal attempt", async () => {
    const res = await POST(makeRequest({ kind: "opportunity_v2", slug: "../../etc/passwd" }, { "x-revalidate-secret": TEST_SECRET }));
    expect(res.status).toBe(400);
  });

  it("rejects a slug containing an embedded slash", async () => {
    const res = await POST(makeRequest({ kind: "opportunity_v2", slug: "a/b" }, { "x-revalidate-secret": TEST_SECRET }));
    expect(res.status).toBe(400);
  });

  it("rejects a slug that is actually a full arbitrary path", async () => {
    const res = await POST(makeRequest({ kind: "article", slug: "http://evil.example/x" }, { "x-revalidate-secret": TEST_SECRET }));
    expect(res.status).toBe(400);
  });

  it("accepts a valid opportunity_v2 request with the correct header secret", async () => {
    const res = await POST(makeRequest(
      { kind: "opportunity_v2", slug: "adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b" },
      { "x-revalidate-secret": TEST_SECRET },
    ));
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toMatchObject({ revalidated: true, kind: "opportunity_v2" });
  });

  it("accepts a valid article request with the correct header secret", async () => {
    const res = await POST(makeRequest(
      { kind: "article", slug: "some-real-article-slug" },
      { "x-revalidate-secret": TEST_SECRET },
    ));
    expect(res.status).toBe(200);
  });
});
