import type { Metadata } from "next";
import Link from "next/link";
import { NewsroomSidebarNav, NewsroomTabsNav } from "@/components/newsroom/NewsroomSidebarNav";

export const metadata: Metadata = {
  title: "AI Newsroom",
  description:
    "MarketRipple's AI Newsroom — continuously generated market intelligence: daily briefs, breaking analysis, theme and company intelligence, grounded in real data and live sources.",
  alternates: { canonical: "/newsroom" },
};

// Brand: primary #6366F1, secondary #14B8A6. Dark mode: background #0B1020, card #151B2E, text #F8FAFC, muted #94A3B8.
const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6366F1]";
// Glass: a frosted layer with a bright top edge, so it reads as a pane lying over the coloured light behind it.
const GLASS = "border border-white/60 bg-white/50 backdrop-blur-xl shadow-[inset_0_1px_0_rgba(255,255,255,0.8),0_10px_40px_-16px_rgba(99,102,241,0.35)] dark:border-white/10 dark:bg-[#151B2E]/70 dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.1),0_10px_40px_-16px_rgba(0,0,0,0.7)]";
const RULE = "h-px bg-gradient-to-r from-[#6366F1]/70 via-[#14B8A6]/50 to-transparent";

/** The light the glass sits over: a soft primary glow top-left and a secondary glow bottom-right. Decorative. */
function Glow() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute -left-16 -top-10 h-64 w-64 rounded-full bg-[#6366F1]/30 blur-3xl dark:bg-[#6366F1]/35" />
      <div className="absolute -bottom-12 -right-16 h-72 w-72 rounded-full bg-[#14B8A6]/25 blur-3xl dark:bg-[#14B8A6]/22" />
    </div>
  );
}

export default function NewsroomLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-surface-card text-text-primary">
      {/* Mobile masthead + section tabs — deliberately edge-to-edge (background spans the
          full viewport regardless of the root layout's PageContainer padding around this
          whole route), via the standard full-bleed break-out: 100vw width, re-centered
          with a negative margin. */}
      <div className="relative left-1/2 right-1/2 -mx-[50vw] w-screen overflow-hidden border-b border-surface-border/10 dark:bg-[#0B1020] lg:hidden">
        <Glow />
        <div className="relative bg-white/40 px-4 pt-3 backdrop-blur-xl dark:bg-[#151B2E]/60 sm:px-6">
          <Link href="/newsroom" className={`mb-3 block rounded-md ${FOCUS}`}>
            <span className="block text-[15px] font-bold leading-none text-text-primary dark:text-[#F8FAFC]">AI Newsroom</span>
            <span className="mt-1 block text-[10.5px] text-text-muted dark:text-[#94A3B8]">Intelligence Desk</span>
          </Link>
          <NewsroomTabsNav />
        </div>
        <div aria-hidden="true" className={`relative ${RULE}`} />
      </div>

      <div className="flex">
        {/* Sidebar — desktop only; the masthead and tabs above cover small screens */}
        <aside className="relative hidden h-screen w-64 shrink-0 self-start border-r border-surface-border/10 p-3 dark:bg-[#0B1020] lg:sticky lg:top-0 lg:block">
          <Glow />
          <div className={`relative flex h-full flex-col rounded-2xl p-4 ${GLASS}`}>
            <Link href="/newsroom" className={`block rounded-lg px-1 pb-4 ${FOCUS}`}>
              <span className="block text-[17px] font-bold leading-none tracking-tight text-text-primary dark:text-[#F8FAFC]">AI Newsroom</span>
              <span className="mt-1.5 block text-[11px] text-text-muted dark:text-[#94A3B8]">Intelligence Desk</span>
            </Link>
            <div aria-hidden="true" className={`mb-5 ${RULE}`} />

            <NewsroomSidebarNav />

            <div className="mt-auto border-t border-white/50 pt-3 dark:border-white/10">
              <Link
                href="/ai-methodology"
                className={`block rounded-xl px-3 py-2 text-[12.5px] font-medium text-text-secondary transition-colors duration-200 hover:bg-white/45 hover:text-text-primary dark:text-[#94A3B8] dark:hover:bg-white/[0.08] dark:hover:text-[#F8FAFC] ${FOCUS}`}
              >
                How the Newsroom works
              </Link>
              <p className="mt-1 px-3 text-[10.5px] leading-relaxed text-text-muted dark:text-[#94A3B8]">
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
