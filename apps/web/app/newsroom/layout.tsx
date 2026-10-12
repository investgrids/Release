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
          <Link href="/newsroom" className={`mb-3 block rounded-md ${FOCUS}`}>
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
            <span className="block">
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
