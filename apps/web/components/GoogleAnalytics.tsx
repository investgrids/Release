"use client";

/**
 * Real consent gate for GA4 (2026-08 audit) — previously loaded
 * unconditionally in layout.tsx for every visitor, which directly
 * contradicted legal/page.tsx's own Cookie Information section ("we do
 * not use cookies for tracking... essential cookies only"). gtag.js's
 * <Script> tags, and therefore the _ga/_ga_* cookies it sets, now only
 * render once CookieConsentBanner records "granted" — Reject means GA4
 * never loads this session, not just a banner shown alongside it anyway.
 *
 * send_page_view: false — see AnalyticsPageView's own docstring for why
 * (client-side App Router navigation never fires gtag's automatic
 * page_view beyond the first page load).
 */
import Script from "next/script";
import { useEffect, useState } from "react";
import { getConsent, onConsentChange } from "@/lib/cookieConsent";
import { AnalyticsPageView } from "./AnalyticsPageView";

const GA_MEASUREMENT_ID = "G-W76EXES2KE";

export function GoogleAnalytics() {
  const [granted, setGranted] = useState(false);

  useEffect(() => {
    setGranted(getConsent() === "granted");
    return onConsentChange(status => setGranted(status === "granted"));
  }, []);

  if (!granted) return null;

  return (
    <>
      <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`} strategy="afterInteractive" />
      <Script id="ga-gtag" strategy="afterInteractive">
        {`
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${GA_MEASUREMENT_ID}', { send_page_view: false });
        `}
      </Script>
      <AnalyticsPageView />
    </>
  );
}
