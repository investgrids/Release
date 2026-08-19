import type { Metadata } from "next";
import { Inter, Geist } from "next/font/google";
import Script from "next/script";
import "./globals.css";

import { SiteHeader }        from "@/components/SiteHeader";
import { Footer }             from "@/components/Footer";
import { NavigationProgress } from "@/components/NavigationProgress";
import { NavLoadingProvider } from "@/components/NavLoadingProvider";
import { AlertProvider }      from "@/components/AlertProvider";
import { MarketIntelligenceProvider } from "@/components/MarketIntelligenceProvider";
import { BreakingNewsAlert }  from "@/components/BreakingNewsAlert";
import { ReturningUserFeedbackModal } from "@/components/feedback/ReturningUserFeedbackModal";
import { Breadcrumbs, BreadcrumbOverrideProvider } from "@/components/Breadcrumbs";
import { PageContainer } from "@/components/PageContainer";
import { AnalyticsPageView } from "@/components/AnalyticsPageView";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});


// next/font downloads Inter at build time, self-hosts it, and injects an
// optimised <link rel="preload"> — no external roundtrip, no FOUT.
const inter = Inter({
  subsets: ["latin"],
  // Only load weights we actually use — cuts ~40 kB from the font bundle.
  weight: ["400", "500", "600", "700", "800", "900"],
  display: "swap",
  variable: "--font-inter",
  preload: true,
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default:  "MarketRipple — AI-Powered Market Intelligence",
    template: "%s | MarketRipple",
  },
  description:
    "Understand Indian market events, ripple effects, and investment opportunities with AI-powered analysis. MarketRipple traces how events ripple through sectors, companies, and portfolios.",
  keywords: ["Indian stock market", "market intelligence", "investment analysis", "Nifty", "BSE", "NSE", "AI finance", "ripple effect", "market events"],
  authors: [{ name: "MarketRipple" }],
  creator: "MarketRipple",
  publisher: "MarketRipple",
  robots: { index: true, follow: true, googleBot: { index: true, follow: true } },
  openGraph: {
    type:        "website",
    siteName:    "MarketRipple",
    title:       "MarketRipple — AI-Powered Market Intelligence",
    description: "Understand Indian market events, ripple effects, and investment opportunities with AI-powered analysis.",
    url:         SITE_URL,
    locale:      "en_IN",
  },
  twitter: {
    card:        "summary_large_image",
    site:        "@marketripple",
    creator:     "@marketripple",
    title:       "MarketRipple — AI-Powered Market Intelligence",
    description: "Understand Indian market events, ripple effects, and investment opportunities with AI-powered analysis.",
  },
  // SEO fix: this used to be `alternates: { canonical: SITE_URL }` — a
  // blanket default that every page without its OWN canonical silently
  // inherited, incorrectly telling search engines the homepage was the
  // canonical version of /companies, /faq, /ripple, /about, and more
  // (confirmed live via curl on all of them, flagged by an SEO crawl as
  // "non-canonical URL" on 21 pages — the real number affected is likely
  // higher, every page site-wide that has no metadata export of its own).
  // Removed rather than made dynamic: a root layout's static `metadata`
  // export has no access to the actual requested path, so there's no
  // correct single value to put here — the homepage now sets its own
  // (app/page.tsx), and no canonical tag is strictly better than a wrong
  // one for every other page until each gets its own (tracked separately).
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: browser extensions (dark-mode tools, password
    // managers) often inject attributes on <html> between SSR and hydration,
    // causing a harmless but noisy hydration mismatch warning.
    <html lang="en-IN" className={cn("font-sans", geist.variable)} suppressHydrationWarning>
      <head>
        {/* Theme FOUC prevention — must run before first paint, so it's a
            plain blocking inline script, not next/script (which defers).
            Light is the default (bare :root, no attribute needed in
            globals.css); this only ever needs to ADD data-theme="dark"
            when that's the visitor's stored choice. Wrapped in try/catch
            since localStorage can throw in some privacy-mode browsers. */}
        <script
          // biome-ignore lint/security/noDangerouslySetInnerHtml: static script, no interpolated data
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('mr-theme');if(t==='dark'){document.documentElement.setAttribute('data-theme','dark');}}catch(e){}})();`,
          }}
        />
      </head>
      <body className="min-h-screen bg-bg text-text-primary font-[family-name:var(--font-inter)]">
        {/* Google Analytics — prod only, so local `next dev` traffic never
            pollutes real analytics. next/script afterInteractive loads it
            off the critical rendering path instead of blocking like a raw
            <script> tag. NODE_ENV is set by the Next.js build itself
            ("development" under `next dev`, "production" for the real
            Vercel build) — not a value anyone here configures by hand.

            send_page_view: false (2026-08 audit) — confirmed live that
            this app's near-entirely-client-side App Router navigation
            never fired a page_view beyond the very first page a visitor
            landed on; gtag's own automatic page_view only fires once, at
            initial script execution. AnalyticsPageView is now the single
            source of every page_view (first load included), so the
            config call's own automatic one is turned off here to avoid
            double-counting the first page. NOTE: GA4's Data Stream ->
            Enhanced Measurement -> "Page changes based on browser
            history events" toggle can ALSO independently emit page_views
            for the same navigations and must stay OFF in the GA4 admin
            UI for this same reason — that's a property-level setting,
            not something this codebase controls. */}
        {process.env.NODE_ENV === "production" && (
          <>
            <Script src="https://www.googletagmanager.com/gtag/js?id=G-W76EXES2KE" strategy="afterInteractive" />
            <Script id="ga-gtag" strategy="afterInteractive">
              {`
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', 'G-W76EXES2KE', { send_page_view: false });
              `}
            </Script>
            <AnalyticsPageView />
          </>
        )}
        <script
          type="application/ld+json"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: static JSON-LD
          dangerouslySetInnerHTML={{ __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Organization",
            name: "MarketRipple",
            url: SITE_URL,
            description: "AI-powered market intelligence platform for Indian equity markets.",
            email: "support@marketripple.in",
            contactPoint: {
              "@type": "ContactPoint",
              email: "support@marketripple.in",
              contactType: "customer support",
              areaServed: "IN",
              availableLanguage: ["English"],
            },
            // Only the handle already self-declared elsewhere in this file's
            // own twitter.site/twitter.creator metadata — not adding
            // unverified profile URLs for platforms the site doesn't
            // actually declare a presence on.
            sameAs: ["https://x.com/marketripple"],
          }) }}
        />
        {/* WebSite + SearchAction (SEO Phase 2, §2.3) — enables Google's
            sitelinks searchbox. Points at the real /search route, which
            already handles a plain ?q= query param. */}
        <script
          type="application/ld+json"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: static JSON-LD
          dangerouslySetInnerHTML={{ __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebSite",
            name: "MarketRipple",
            url: SITE_URL,
            potentialAction: {
              "@type": "SearchAction",
              target: { "@type": "EntryPoint", urlTemplate: `${SITE_URL}/search?q={search_term_string}` },
              "query-input": "required name=search_term_string",
            },
          }) }}
        />
        <NavigationProgress />
        <AlertProvider>
          <MarketIntelligenceProvider>
            <NavLoadingProvider>
              <SiteHeader />
              <main className="min-h-[calc(100vh-72px)]">
                {/* Auto-generated from the URL on every page (skips "/" —
                    see Breadcrumbs.tsx). A page with a real human-readable
                    title for a dynamic segment (a company name, an event
                    headline) calls useBreadcrumbOverride() with it once its
                    data loads, via the shared BreadcrumbOverrideProvider
                    below — replaces the humanized-raw-slug fallback without
                    that page needing to render its own second <Breadcrumbs>. */}
                <BreadcrumbOverrideProvider>
                  <PageContainer className="pt-4">
                    <Breadcrumbs />
                  </PageContainer>
                  <PageContainer>{children}</PageContainer>
                </BreadcrumbOverrideProvider>
              </main>
              <BreakingNewsAlert />
              <ReturningUserFeedbackModal />
            </NavLoadingProvider>
          </MarketIntelligenceProvider>
        </AlertProvider>
        <Footer />
      </body>
    </html>
  );
}
