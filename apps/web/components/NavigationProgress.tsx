"use client";

import { useEffect, useRef, useState } from "react";

// Centered overlay spinner during route navigation (2026-08 audit; kept —
// the previous top-of-viewport bar was already tried and rejected as
// invisible behind the sticky header).
//
// 2026-08-23 rewrite, revision 5 — four earlier "start"/"done" signals were
// tried and disproved with real testing (temporarily adding an artificial
// multi-second delay to a route with no loading.tsx, then instrumenting
// with console timestamps + fresh-context Playwright runs correlated
// against real network timing):
//   1. usePathname()/navigatesuccess as "done" — both fire within ~15ms of
//      the click, the moment Next.js commits the URL to history, nowhere
//      near when real content lands. Settling on this cancelled the reveal
//      timer on every navigation, fast or slow, so the overlay never showed.
//   2. MutationObserver quiet-period on the content region as "done" — the
//      DOM during the gap isn't empty, it's a frozen, stable leftover
//      (confirmed: childCount/text length held constant for 3+ seconds,
//      then jumped once real content landed) — indistinguishable from
//      genuinely-done by mutation timing alone.
//   3. The Navigation API's `navigate` event as "start" — confirmed to fire
//      ~70ms AFTER Next.js has already dispatched the real RSC fetch, so
//      state set by that event always missed the fetch.
//   4. Wrapping window.fetch from a React effect — confirmed (via
//      page.addInitScript() vs. a normal effect, same page, same click) to
//      install too late: Next's client router has already dispatched its
//      fetch before any post-hydration React effect gets a chance to patch
//      window.fetch, so the wrap silently caught nothing, every time.
//
// What actually works: a plain, synchronous inline <script> in <head>
// (app/layout.tsx, same pattern already used there for the dark-mode FOUC
// script) wraps window.fetch as early as the page can possibly run JS —
// before Next's own bundles initialize — and dispatches DOM CustomEvents
// for a real, same-origin RSC navigation fetch (identified by the `_rsc`
// query param Next.js's router adds) starting and finishing. This
// component just listens. A fresh-context Playwright run confirmed the
// dispatched events line up with real wall-clock server latency (measured
// 3.1s via curl, then 3.1s again via the wrapped fetch in the browser).
// `_rsc` is a Next.js implementation detail, not a public API — if a
// future Next.js version renames it, the inline script simply never
// matches anything and the overlay never shows, which is only ever a
// silent no-op, never a stuck-visible state.
const REVEAL_MS = 2000;
const SAFETY_MS = 8000;

export function NavigationProgress() {
  const [visible, setVisible] = useState(false);
  const revealTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const safetyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Bumped on every settle so a reveal/safety timer belonging to an
  // already-finished (or superseded by a rapid second navigation) fetch
  // can't act late.
  const generation = useRef(0);

  useEffect(() => {
    function clearTimers() {
      if (revealTimer.current) { clearTimeout(revealTimer.current); revealTimer.current = null; }
      if (safetyTimer.current) { clearTimeout(safetyTimer.current); safetyTimer.current = null; }
    }

    // The inline script's own generation counter (event.detail) — not
    // React state — is the source of truth for "which fetch is this," so a
    // late `done` from a navigation already superseded by a newer click
    // can't incorrectly settle the current one.
    function settle(gen: number) {
      if (gen !== generation.current) return;
      clearTimers();
      setVisible(false);
    }

    function onStart(e: Event) {
      const gen = (e as CustomEvent<number>).detail;
      generation.current = gen;
      clearTimers();
      revealTimer.current = setTimeout(() => {
        if (gen === generation.current) setVisible(true);
      }, REVEAL_MS);
      safetyTimer.current = setTimeout(() => settle(gen), SAFETY_MS);
    }

    function onDone(e: Event) {
      settle((e as CustomEvent<number>).detail);
    }

    window.addEventListener("mr:navfetchstart", onStart);
    window.addEventListener("mr:navfetchdone", onDone);
    return () => {
      window.removeEventListener("mr:navfetchstart", onStart);
      window.removeEventListener("mr:navfetchdone", onDone);
      clearTimers();
    };
  }, []);

  if (!visible) return null;
  return (
    <div className="fixed inset-0 z-[1600] flex items-center justify-center bg-bg/40 backdrop-blur-[1px]" role="status" aria-live="polite" aria-label="Loading page">
      <div className="h-10 w-10 animate-spin motion-reduce:animate-none rounded-full border-[3px] border-violet-400 border-t-transparent shadow-[0_0_16px_rgba(139,92,246,0.35)]" />
    </div>
  );
}
