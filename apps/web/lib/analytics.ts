/**
 * GA4 custom event tracking (SEO Phase 4, §4.3 — analytics instrumentation).
 * GA4's own gtag.js is already wired up in app/layout.tsx. page_view does
 * NOT fire automatically beyond the first page a visitor lands on — this
 * app's navigation is almost entirely client-side App Router routing,
 * which gtag's own config-triggered pageview never sees (confirmed live
 * via Playwright, 2026-08 audit); see components/AnalyticsPageView.tsx
 * for the actual page_view source. This file adds a thin, safe wrapper
 * for the handful of real interaction events worth tracking beyond that,
 * per the SEO/Growth audit's own §10 recommendation list. Deliberately
 * NOT a large invented event taxonomy — a few genuinely valuable events
 * wired into pages this same SEO pass already touched, not a guess at a
 * full analytics plan that's really a product decision.
 *
 * No-ops safely in dev (gtag.js only loads in production, see layout.tsx)
 * and if ad blockers strip window.gtag — tracking must never throw or
 * affect the actual page.
 */
"use client";

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

export function trackEvent(name: string, params?: Record<string, string | number | boolean>) {
  try {
    if (typeof window !== "undefined" && typeof window.gtag === "function") {
      window.gtag("event", name, params);
    }
  } catch {
    // Analytics must never break the page it's measuring.
  }
}
