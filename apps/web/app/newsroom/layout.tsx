import type { Metadata } from "next";
import Link from "next/link";
import { Radio } from "lucide-react";
import { NewsroomSidebarNav } from "@/components/newsroom/NewsroomSidebarNav";

export const metadata: Metadata = {
  title: "AI Newsroom",
  description:
    "MarketRipple's AI Newsroom — continuously generated market intelligence: daily briefs, breaking analysis, theme and company intelligence, grounded in real data and live sources.",
  alternates: { canonical: "/newsroom" },
};

export default function NewsroomLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-surface-card text-text-primary">
      <div className="border-b border-surface-border/7 bg-black/20 lg:hidden">
        <div className="px-4 py-3 sm:px-6">
          <Link href="/newsroom" className="flex items-center gap-2">
            <Radio className="h-3.5 w-3.5 text-sky-400" />
            <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-text-secondary">
              AI Newsroom
            </span>
          </Link>
        </div>
      </div>

      <div className="mx-auto flex max-w-[1600px]">
        {/* Sidebar — desktop only; the mobile header above covers small screens */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-surface-border/7 bg-black/10 p-4 lg:flex">
          <Link href="/newsroom" className="mb-6 flex items-center gap-2 px-1">
            <Radio className="h-4 w-4 text-sky-400" />
            <span className="text-[12px] font-bold uppercase tracking-[0.18em] text-text-secondary">
              AI Newsroom
            </span>
          </Link>
          <NewsroomSidebarNav />
        </aside>

        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </main>
  );
}
