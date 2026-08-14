"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

// Centered overlay spinner during route navigation (2026-08 audit, explicit
// request — replaces the previous top progress bar, which the user reported
// as effectively invisible: nextjs-toploader is a thin top-of-viewport bar
// that renders behind anything with a higher stacking context, e.g. the
// sticky header/menu it's meant to accompany). No extra dependency: listens
// for clicks on internal links (how Next's own <Link> navigates) to show the
// overlay the instant a nav is initiated, and clears it once the route
// actually changes (pathname/search params updating is the real signal the
// new page has taken over — not a fixed animation duration).
export function NavigationProgress() {
  // Not useSearchParams() too — that hook requires its own Suspense
  // boundary in the App Router, which would mean wrapping every page (this
  // renders once in the root layout). Pathname changes already cover the
  // overwhelming majority of real navigations (any menu/link click); a
  // same-path search-param-only change is rare enough, and self-corrects
  // via the safety timeout below, that it isn't worth that cost.
  const pathname = usePathname();
  const [loading, setLoading] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Route actually changed — the incoming page has taken over, hide.
  useEffect(() => {
    setLoading(false);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
  }, [pathname]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const link = (e.target as HTMLElement)?.closest("a");
      if (!link) return;
      const href = link.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
      if (link.target && link.target !== "_self") return;
      let url: URL;
      try { url = new URL(href, window.location.href); } catch { return; }
      if (url.origin !== window.location.origin) return;
      // Same destination as the current page — no navigation will fire, so
      // no route-change effect will ever come along to clear the overlay.
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
      setLoading(true);
      // Safety net only — normal clears happen via the pathname effect
      // above the moment the real navigation lands.
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setLoading(false), 8000);
    }
    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("click", onClick);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  if (!loading) return null;
  return (
    <div className="fixed inset-0 z-[1600] flex items-center justify-center bg-bg/40 backdrop-blur-[1px]" role="status" aria-live="polite" aria-label="Loading page">
      <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-violet-400 border-t-transparent shadow-[0_0_16px_rgba(139,92,246,0.35)]" />
    </div>
  );
}
