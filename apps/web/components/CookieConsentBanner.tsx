"use client";

/**
 * Real cookie consent banner (2026-08 audit) — Accept actually grants
 * GoogleAnalytics permission to load gtag.js; Reject means it never does
 * this session. See lib/cookieConsent.ts for the shared state and
 * legal/page.tsx's Cookie Information section for the full disclosure
 * this banner links to.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { Cookie } from "lucide-react";
import { getConsent, setConsent } from "@/lib/cookieConsent";

export function CookieConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Show banner if user has explicitly rejected OR never made a choice.
    // Once they Accept or Reject, banner won't nag them again.
    // GA loads by default but respects Reject choice.
    const consent = getConsent();
    setVisible(consent === null || consent === "denied");
  }, []);

  if (!visible) return null;

  function accept() {
    setConsent("granted");
    setVisible(false);
  }
  function reject() {
    setConsent("denied");
    setVisible(false);
  }

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Cookie consent"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-surface-border/10 bg-surface-card/95 backdrop-blur px-4 py-4 shadow-[0_-4px_20px_-8px_rgb(var(--text-primary)/0.15)] sm:px-6"
    >
      <div className="mx-auto flex max-w-6xl flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10">
            <Cookie className="h-4 w-4 text-emerald-500" aria-hidden="true" />
          </div>
          <p className="text-[12.5px] leading-relaxed text-text-secondary">
            We use Google Analytics (first-party cookies) to understand how visitors use MarketRipple —
            page views and navigation, never advertising or cross-site tracking. Nothing loads until you
            choose.{" "}
            <Link href="/legal#cookies" className="font-medium text-sky-600 underline-offset-2 hover:underline dark:text-sky-400">
              Learn more
            </Link>
          </p>
        </div>
        <div className="flex w-full shrink-0 items-center gap-2 sm:w-auto">
          <button
            onClick={reject}
            className="flex-1 rounded-lg border border-surface-border/15 bg-text-primary/[0.03] px-4 py-2 text-[12.5px] font-semibold text-text-secondary transition hover:border-surface-border/25 hover:text-text-primary sm:flex-none"
          >
            Reject
          </button>
          <button
            onClick={accept}
            className="flex-1 rounded-lg bg-emerald-600 px-4 py-2 text-[12.5px] font-semibold text-white transition hover:bg-emerald-500 sm:flex-none"
          >
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
