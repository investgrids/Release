import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

/**
 * Route-tree safety gate for `loading.tsx` — 2026-08 regression test.
 *
 * Real, confirmed production bug (commit b55061e, same session): a
 * `loading.tsx` anywhere in a route's ANCESTOR chain wraps that whole
 * segment's subtree in a React Suspense boundary. Next.js streams the
 * Suspense fallback and commits HTTP 200 before an awaited `notFound()`
 * inside that boundary can resolve — a real, Google-Search-Console-flagged
 * soft-404 across virtually every dynamic detail route on the site, which
 * is exactly why `loading.tsx` was deliberately REMOVED from 5 routes
 * (root, news, events, ripple, sectors) rather than kept.
 *
 * This test makes that constraint durable: for every real `loading.tsx`
 * under app/, walk its full filesystem subtree (which is exactly the set
 * of routes Next.js's Suspense boundary actually wraps, regardless of
 * route-group parens — those only affect the URL, not this wrapping) and
 * fail if ANY `page.tsx` in that subtree calls `notFound()`. A page that
 * itself doesn't call notFound() is still unsafe if a descendant does —
 * that's the exact shape of the original bug (a parent-level loading.tsx
 * wrapping a notFound()-calling child).
 */

const APP_DIR = path.resolve(__dirname);

function findFiles(dir: string, filename: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...findFiles(full, filename));
    } else if (entry.name === filename) {
      out.push(full);
    }
  }
  return out;
}

function callsNotFound(pageFile: string): boolean {
  const src = fs.readFileSync(pageFile, "utf-8");
  return /\bnotFound\s*\(/.test(src);
}

describe("loading.tsx route-tree safety (soft-404 regression gate)", () => {
  const loadingFiles = findFiles(APP_DIR, "loading.tsx");

  it("found at least the routes known to have loading.tsx today (sanity check the walker works)", () => {
    expect(loadingFiles.length).toBeGreaterThan(0);
  });

  it.each(loadingFiles.map((f) => [path.relative(APP_DIR, f), f]))(
    "%s wraps no notFound()-calling page anywhere in its subtree",
    (_label, loadingFile) => {
      const subtreeRoot = path.dirname(loadingFile);
      const pagesInSubtree = findFiles(subtreeRoot, "page.tsx");
      const offenders = pagesInSubtree.filter(callsNotFound);
      expect(
        offenders.map((f) => path.relative(APP_DIR, f)),
        `${path.relative(APP_DIR, loadingFile)} wraps a Suspense boundary around ` +
          `${offenders.length} page(s) that call notFound() — this recreates the exact ` +
          `soft-404 bug fixed in b55061e. Remove this loading.tsx or move the notFound() ` +
          `check to a point that isn't wrapped by it.`,
      ).toEqual([]);
    },
  );

  it("no loading.tsx exists at the app root (explicit design rule — root/global loading.tsx is never safe, since it would wrap the entire site's route tree)", () => {
    const rootLoading = path.join(APP_DIR, "loading.tsx");
    expect(fs.existsSync(rootLoading)).toBe(false);
  });
});
