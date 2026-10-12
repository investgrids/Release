import type { Metadata } from "next";
import Link from "next/link";
import { Cormorant_Garamond } from "next/font/google";
import { NewsroomSidebarNav, NewsroomTabsNav } from "@/components/newsroom/NewsroomSidebarNav";

export const metadata: Metadata = {
  title: "AI Newsroom",
  description:
    "MarketRipple's AI Newsroom — continuously generated market intelligence: daily briefs, breaking analysis, theme and company intelligence, grounded in real data and live sources.",
  alternates: { canonical: "/newsroom" },
};

// Display serif for the masthead and group titles only; body and data stay in the app's sans.
const serif = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-newsroom-serif",
  display: "swap",
});

/** Newsroom crest: a thin gold double ring around a serif M. Authored SVG, decorative. */
function Crest({ size }: { size: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 40 40" className="shrink-0">
      <circle cx="20" cy="20" r="18.5" fill="none" stroke="#d4b86a" strokeWidth="1.25" />
      <circle cx="20" cy="20" r="15" fill="none" stroke="#d4b86a" strokeOpacity="0.45" strokeWidth="0.75" />
      <text x="20" y="26.2" textAnchor="middle" fontSize="19" fontWeight="600" fill="#f6f2e6"
        style={{ fontFamily: "var(--font-newsroom-serif), Georgia, serif" }}>M</text>
    </svg>
  );
}

const INK = "bg-[#0a1229] bg-[radial-gradient(110%_55%_at_0%_0%,rgba(99,102,241,0.22),transparent_62%)]";
const GOLD_FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#d4b86a]";

export default function NewsroomLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className={`${serif.variable} min-h-screen bg-surface-card text-text-primary`}>
      {/* Mobile masthead + section tabs — deliberately edge-to-edge (background spans the
          full viewport regardless of the root layout's PageContainer padding around this
          whole route), via the standard full-bleed break-out: 100vw width, re-centered
          with a negative margin. */}
      <div className={`relative left-1/2 right-1/2 -mx-[50vw] w-screen border-b border-[#d4b86a]/25 ${INK} lg:hidden`}>
        <div className="px-4 pb-1 pt-3.5 sm:px-6">
          <Link href="/newsroom" className={`mb-3 flex items-center gap-2.5 ${GOLD_FOCUS}`}>
            <Crest size={30} />
            <span className="font-[family-name:var(--font-newsroom-serif)] text-[20px] font-semibold leading-none tracking-wide text-[#f6f2e6]">
              The AI Newsroom
            </span>
          </Link>
          <NewsroomTabsNav />
        </div>
      </div>

      <div className="flex">
        {/* Sidebar — desktop only; the masthead and tabs above cover small screens */}
        <aside className={`sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-[#d4b86a]/25 ${INK} px-4 py-6 lg:flex`}>
          <Link href="/newsroom" className={`mb-8 block rounded-md px-1 ${GOLD_FOCUS}`}>
            <span className="flex items-center gap-3">
              <Crest size={42} />
              <span className="font-[family-name:var(--font-newsroom-serif)] text-[24px] font-semibold leading-[1.05] tracking-wide text-[#f6f2e6]">
                The AI<br />Newsroom
              </span>
            </span>
            <span className="mt-3 block h-px w-full bg-gradient-to-r from-[#d4b86a]/60 via-[#d4b86a]/20 to-transparent" />
            <span className="mt-2 block text-[10px] font-medium uppercase tracking-[0.13em] text-[#8d98b8]">
              MarketRipple Intelligence Desk
            </span>
          </Link>

          <NewsroomSidebarNav />

          <div className="mt-auto border-t border-white/10 pt-4">
            <Link
              href="/ai-methodology"
              className={`block rounded-md px-3 py-2 text-[12.5px] font-medium text-[#c3cbe2] transition-colors duration-200 hover:bg-white/[0.05] hover:text-[#f6f2e6] ${GOLD_FOCUS}`}
            >
              How the Newsroom works
            </Link>
            <p className="mt-2 px-3 text-[10.5px] leading-relaxed text-[#8d98b8]">
              Research and education only. Not investment advice.
            </p>
          </div>
        </aside>

        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </main>
  );
}
