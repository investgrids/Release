"use client";

/**
 * Manual GA4 page_view emitter (2026-08 audit — confirmed live via
 * Playwright that client-side <Link> navigation never fired a page_view;
 * gtag's automatic page_view only fires once, on whichever page the
 * script itself first loads on, and this app's navigation is almost
 * entirely client-side App Router routing after that). layout.tsx's
 * `gtag('config', ...)` call disables its own automatic page_view
 * (send_page_view: false) so this component is the SINGLE source of
 * every page_view, first load included — no double-count guard needed,
 * since nothing else emits one.
 *
 * useSearchParams() requires a Suspense boundary in the App Router —
 * isolated to this leaf component, not the root layout, so it can't
 * affect SSR/hydration of anything else on the page.
 */

import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

function AnalyticsPageViewInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.gtag !== "function") return;
    const query = searchParams?.toString();
    const page_path = query ? `${pathname}?${query}` : pathname;
    window.gtag("event", "page_view", {
      page_location: window.location.href,
      page_path,
      page_title: document.title,
    });
    // pathname + the search params' own string value (not the
    // searchParams object identity, which is a new object every render)
    // — this must only re-fire on a real navigation, not every render.
  }, [pathname, searchParams?.toString()]);

  return null;
}

export function AnalyticsPageView() {
  return (
    <Suspense fallback={null}>
      <AnalyticsPageViewInner />
    </Suspense>
  );
}
