import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

// jsdom has no real IntersectionObserver — any component wrapped in this
// codebase's SectionCard (framer-motion's `whileInView`, e.g. the
// MarketRipple Score card) throws ReferenceError without this. A minimal,
// inert stub is enough: no test here asserts on real viewport-triggered
// animation, only on rendered content.
class MockIntersectionObserver {
  readonly root: Element | null = null;
  readonly rootMargin: string = "";
  readonly thresholds: ReadonlyArray<number> = [];
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords(): IntersectionObserverEntry[] { return []; }
}
// @ts-expect-error — a minimal test-only stub, not a full spec implementation
globalThis.IntersectionObserver = MockIntersectionObserver;
