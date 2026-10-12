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

// Display serif for the masthead, group headings and navigation labels; body and data stay in the app's sans.
const serif = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-newsroom-serif",
  display: "swap",
});

const SERIF = "font-[family-name:var(--font-newsroom-serif)]";
const GOLD_FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#f3dc92]";

// Imperial royal blue-violet, lit from the upper left, over a fine diamond lattice (guilloché), all drawn here: no image assets.
const LATTICE = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='28' viewBox='0 0 28 28'%3E%3Cpath d='M14 0 28 14 14 28 0 14z' fill='none' stroke='%23e0bc62' stroke-opacity='0.09' stroke-width='1'/%3E%3C/svg%3E\")";
const ROYAL_BG = `bg-[#120b49] bg-[radial-gradient(120%_60%_at_0%_0%,rgba(124,92,255,0.5),transparent_62%),radial-gradient(90%_50%_at_100%_100%,rgba(60,32,150,0.55),transparent_60%),linear-gradient(180deg,#1b1163_0%,#0e0838_100%)]`;

/** Crown-and-shield crest in gold foil. `id` keeps the gradient ids unique when the crest is on screen twice. */
function Crest({ width, id }: { width: number; id: string }) {
  const h = Math.round(width * 1.18);
  return (
    <svg aria-hidden="true" width={width} height={h} viewBox="0 0 52 61" className="shrink-0 drop-shadow-[0_2px_6px_rgba(0,0,0,0.5)]">
      <defs>
        <linearGradient id={`foil-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fbefb9" />
          <stop offset="0.5" stopColor="#e0bc62" />
          <stop offset="1" stopColor="#a87a28" />
        </linearGradient>
      </defs>
      {/* crown */}
      <path d="M8 21 11 8l7 7 8-11 8 11 7-7 3 13z" fill={`url(#foil-${id})`} />
      <rect x="8" y="21" width="36" height="4.5" rx="1" fill={`url(#foil-${id})`} />
      <circle cx="11" cy="7" r="2.1" fill={`url(#foil-${id})`} />
      <circle cx="26" cy="3.2" r="2.4" fill={`url(#foil-${id})`} />
      <circle cx="41" cy="7" r="2.1" fill={`url(#foil-${id})`} />
      {/* shield */}
      <path d="M9 29h34v13c0 9-8 15-17 18C17 57 9 51 9 42z" fill="#150e52" stroke={`url(#foil-${id})`} strokeWidth="1.8" />
      <path d="M13.5 32.5h25v9.5c0 6.6-6 11.2-12.5 13.6C19.5 53.2 13.5 48.6 13.5 42z" fill="none" stroke="#e0bc62" strokeOpacity="0.5" strokeWidth="0.8" />
      <text x="26" y="48" textAnchor="middle" fontSize="20" fontWeight="700" fill={`url(#foil-${id})`}
        style={{ fontFamily: "var(--font-newsroom-serif), Georgia, serif" }}>M</text>
    </svg>
  );
}

/** Divider: gold hairlines meeting at a small diamond. */
function Flourish({ className = "" }: { className?: string }) {
  return (
    <div aria-hidden="true" className={`flex items-center gap-2 ${className}`}>
      <span className="h-px flex-1 bg-gradient-to-r from-transparent via-[#e0bc62]/70 to-[#e0bc62]" />
      <svg viewBox="0 0 10 10" className="h-2 w-2 text-[#f3dc92]"><path d="M5 0 10 5 5 10 0 5z" fill="currentColor" /></svg>
      <span className="h-px flex-1 bg-gradient-to-l from-transparent via-[#e0bc62]/70 to-[#e0bc62]" />
    </div>
  );
}

export default function NewsroomLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className={`${serif.variable} min-h-screen bg-surface-card text-text-primary`}>
      {/* Mobile masthead + section tabs — deliberately edge-to-edge (background spans the
          full viewport regardless of the root layout's PageContainer padding around this
          whole route), via the standard full-bleed break-out: 100vw width, re-centered
          with a negative margin. */}
      <div
        className={`relative left-1/2 right-1/2 -mx-[50vw] w-screen border-y-2 border-[#e0bc62]/70 ${ROYAL_BG} shadow-[0_8px_24px_-12px_rgba(18,11,73,0.6)] lg:hidden`}
      >
        <div className="relative px-4 pb-0.5 pt-3.5 sm:px-6">
          <Link href="/newsroom" className={`mb-3 flex items-center gap-3 ${GOLD_FOCUS}`}>
            <Crest width={30} id="m" />
            <span className="leading-none">
              <span className={`${SERIF} block text-[24px] font-semibold tracking-wide text-[#fff3cf]`}>The AI Newsroom</span>
              <span className="mt-1 block text-[9.5px] font-medium uppercase tracking-[0.22em] text-[#c9bff0]">MarketRipple Intelligence Desk</span>
            </span>
          </Link>
          <NewsroomTabsNav />
        </div>
      </div>

      <div className="flex">
        {/* Sidebar — desktop only; the masthead and tabs above cover small screens */}
        <aside
          className={`relative sticky top-0 hidden h-screen w-72 shrink-0 flex-col overflow-hidden ${ROYAL_BG} px-5 py-7 shadow-[inset_-1px_0_0_rgba(224,188,98,0.9),inset_-5px_0_0_rgba(18,11,73,1),inset_-6px_0_0_rgba(224,188,98,0.45)] lg:flex`}
        >
          <div aria-hidden="true" className="pointer-events-none absolute inset-0" style={{ backgroundImage: LATTICE }} />

          <div className="relative flex h-full flex-col">
            <Link href="/newsroom" className={`block rounded-lg ${GOLD_FOCUS}`}>
              <span className="flex flex-col items-center text-center">
                <Crest width={58} id="d" />
                <span className={`${SERIF} mt-3 block text-[31px] font-semibold leading-[1.02] tracking-wide text-[#fff3cf]`}>
                  The AI Newsroom
                </span>
                <span className="mt-2 block text-[10px] font-medium uppercase tracking-[0.24em] text-[#c9bff0]">
                  MarketRipple Intelligence Desk
                </span>
              </span>
            </Link>

            <Flourish className="my-6" />

            <NewsroomSidebarNav />

            <div className="mt-auto pt-5">
              <Flourish className="mb-4" />
              <Link
                href="/ai-methodology"
                className={`block rounded-lg px-3 py-2 text-center ${SERIF} text-[17px] font-semibold tracking-wide text-[#ecd48a] transition-colors duration-200 hover:bg-[#e0bc62]/[0.12] hover:text-[#fff3cf] ${GOLD_FOCUS}`}
              >
                How the Newsroom works
              </Link>
              <p className="mt-1.5 text-center text-[10.5px] leading-relaxed text-[#b9b0e6]">
                Research and education only. Not investment advice.
              </p>
            </div>
          </div>
        </aside>

        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </main>
  );
}
