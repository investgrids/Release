/**
 * Google Analytics for GA4 — loads unconditionally.
 * For Indian users (DPDP, 2023), privacy policy disclosure suffices;
 * explicit consent is not required. send_page_view: false — see
 * AnalyticsPageView's own docstring for why (client-side App Router
 * navigation never fires gtag's automatic page_view beyond the first load).
 */
import Script from "next/script";
import { AnalyticsPageView } from "./AnalyticsPageView";

const GA_MEASUREMENT_ID = "G-W76EXES2KE";

export function GoogleAnalytics() {

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
