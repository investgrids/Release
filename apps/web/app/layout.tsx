import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

import { SiteHeader }        from "@/components/SiteHeader";
import { Footer }             from "@/components/Footer";
import { NavigationProgress } from "@/components/NavigationProgress";
import { NavLoadingProvider } from "@/components/NavLoadingProvider";
import { AlertProvider }      from "@/components/AlertProvider";
import { BreakingNewsAlert }  from "@/components/BreakingNewsAlert";

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

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://marketripple.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default:  "MarketRipple — AI-Powered Market Intelligence for India",
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
    title:       "MarketRipple — AI-Powered Market Intelligence for India",
    description: "Understand Indian market events, ripple effects, and investment opportunities with AI-powered analysis.",
    url:         SITE_URL,
    locale:      "en_IN",
  },
  twitter: {
    card:        "summary_large_image",
    site:        "@marketripple",
    creator:     "@marketripple",
    title:       "MarketRipple — AI-Powered Market Intelligence for India",
    description: "Understand Indian market events, ripple effects, and investment opportunities with AI-powered analysis.",
  },
  alternates: { canonical: SITE_URL },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: browser extensions (dark-mode tools, password
    // managers) often inject attributes on <html> between SSR and hydration,
    // causing a harmless but noisy hydration mismatch warning.
    <html lang="en-IN" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-[#020617] text-slate-100 font-[family-name:var(--font-inter)]">
        <script
          type="application/ld+json"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: static JSON-LD
          dangerouslySetInnerHTML={{ __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Organization",
            name: "MarketRipple",
            url: SITE_URL,
            description: "AI-powered market intelligence platform for Indian equity markets.",
            sameAs: [],
          }) }}
        />
        <NavigationProgress />
        <AlertProvider>
          <NavLoadingProvider>
            <SiteHeader />
            <main className="min-h-[calc(100vh-72px)]">
              {children}
            </main>
            <BreakingNewsAlert />
          </NavLoadingProvider>
        </AlertProvider>
        <Footer />
      </body>
    </html>
  );
}
