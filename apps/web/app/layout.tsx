import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

import { SiteHeader }        from "@/components/SiteHeader";
import { Sidebar }            from "@/components/Sidebar";
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

export const metadata: Metadata = {
  title: "MarketRipple — AI-Powered Market Intelligence",
  description:
    "Understand market events, ripple effects, and investment opportunities with AI-powered analysis. MarketRipple connects events to companies to stories.",
  openGraph: {
    type:        "website",
    siteName:    "MarketRipple",
    title:       "MarketRipple — AI-Powered Market Intelligence",
    description: "Understand market events, ripple effects, and investment opportunities with AI-powered analysis.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: browser extensions (dark-mode tools, password
    // managers) often inject attributes on <html> between SSR and hydration,
    // causing a harmless but noisy hydration mismatch warning.
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-slate-950 text-slate-100 font-[family-name:var(--font-inter)]">
        <NavigationProgress />
        <AlertProvider>
          <NavLoadingProvider>
            <SiteHeader />
            <div className="mx-auto grid max-w-[1600px] gap-6 px-6 py-6 xl:grid-cols-[240px_1fr_260px]">
              <Sidebar />
              {children}
            </div>
            <BreakingNewsAlert />
          </NavLoadingProvider>
        </AlertProvider>
        <Footer />
      </body>
    </html>
  );
}
