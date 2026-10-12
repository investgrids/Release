import type { Metadata } from "next";
import Link from "next/link";
import { NewsroomSidebarNav, NewsroomTabsNav } from "@/components/newsroom/NewsroomSidebarNav";

export const metadata: Metadata = {
  title: "AI Newsroom",
  description:
    "MarketRipple's AI Newsroom — continuously generated market intelligence: daily briefs, breaking analysis, theme and company intelligence, grounded in real data and live sources.",
  alternates: { canonical: "/newsroom" },
};

const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-violet";

/** Newsroom seal: a gold crown on a royal-indigo disc with a fine gold ring. Authored SVG, decorative. */
function Seal({ size, id }: { size: number; id: string }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 40 40" className="shrink-0">
      <defs>
        <linearGradient id={`seal-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#f6e5a4" />
          <stop offset="0.55" stopColor="#dcb85a" />
          <stop offset="1" stopColor="#b08a2e" />
        </linearGradient>
      </defs>
      <circle cx="20" cy="20" r="19" fill="#2b2087" />
      <circle cx="20" cy="20" r="17.2" fill="none" stroke={`url(#seal-${id})`} strokeWidth="1.1" />
      <path d="M10.5 26 12 15l5.2 5L20 12l2.8 8 5.2-5 1.5 11z" fill={`url(#seal-${id})`} />
      <rect x="10.5" y="26" width="19" height="3" rx="0.8" fill={`url(#seal-${id})`} />
      <circle cx="12" cy="14" r="1.4" fill={`url(#seal-${id})`} />
      <circle cx="20" cy="11" r="1.6" fill={`url(#seal-${id})`} />
      <circle cx="28" cy="14" r="1.4" fill={`url(#seal-${id})`} />
    </svg>
  );
}

const GOLD_RULE = "h-px bg-gradient-to-r from-[#d4b04e] via-[#d4b04e]/40 to-transparent";

export default function NewsroomLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-surface-card text-text-primary">
      {/* Mobile masthead + section tabs — deliberately edge-to-edge (background spans the
          full viewport regardless of the root layout's PageContainer padding around this
          whole route), via the standard full-bleed break-out: 100vw width, re-centered
          with a negative margin. */}
      <div className="relative left-1/2 right-1/2 -mx-[50vw] w-screen border-b border-surface-border/10 bg-accent-violet/[0.05] lg:hidden">
        <div className="px-4 pt-3 sm:px-6">
          <Link href="/newsroom" className={`mb-3 flex items-center gap-2.5 rounded-md ${FOCUS}`}>
            <Seal size={30} id="m" />
            <span className="leading-none">
              <span className="block text-[15px] font-bold text-text-primary">AI Newsroom</span>
              <span className="mt-0.5 block text-[10.5px] text-text-muted">Intelligence Desk</span>
            </span>
          </Link>
          <NewsroomTabsNav />
        </div>
        <div aria-hidden="true" className={GOLD_RULE} />
      </div>

      <div className="flex">
        {/* Sidebar — desktop only; the masthead and tabs above cover small screens */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-surface-border/10 bg-accent-violet/[0.04] p-4 lg:flex">
          <Link href="/newsroom" className={`block rounded-lg px-1 pb-4 ${FOCUS}`}>
            <span className="flex items-center gap-3">
              <Seal size={40} id="d" />
              <span className="leading-none">
                <span className="block text-[17px] font-bold tracking-tight text-text-primary">AI Newsroom</span>
                <span className="mt-1 block text-[11px] text-text-muted">Intelligence Desk</span>
              </span>
            </span>
          </Link>
          <div aria-hidden="true" className={`mb-5 ${GOLD_RULE}`} />

          <NewsroomSidebarNav />

          <div className="mt-auto border-t border-surface-border/10 pt-3">
            <Link
              href="/ai-methodology"
              className={`block rounded-lg px-3 py-2 text-[12.5px] font-medium text-text-secondary transition-colors duration-200 hover:bg-accent-violet/[0.08] hover:text-text-primary ${FOCUS}`}
            >
              How the Newsroom works
            </Link>
            <p className="mt-1 px-3 text-[10.5px] leading-relaxed text-text-muted">
              Research and education only. Not investment advice.
            </p>
          </div>
        </aside>

        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </main>
  );
}
