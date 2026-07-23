import type { Metadata } from "next";
import Link from "next/link";
import { Radio } from "lucide-react";

export const metadata: Metadata = {
  title: "AI Newsroom",
  description:
    "MarketRipple's AI Newsroom — continuously generated market intelligence: daily briefs, breaking analysis, theme and company intelligence, grounded in real data and live sources.",
  alternates: { canonical: "/newsroom" },
};

// "Live Sources" (/newsroom/sources) intentionally unlisted for now — the
// page and its data still exist, just not promoted in nav. Not a deletion.
const NAV = [
  { href: "/newsroom",              label: "Home" },
  { href: "/newsroom/library",      label: "Library" },
  { href: "/newsroom/daily-brief",  label: "Daily Brief" },
  { href: "/newsroom/breaking",     label: "Breaking" },
  { href: "/newsroom/themes",       label: "Themes" },
  { href: "/newsroom/companies",    label: "Companies" },
  { href: "/newsroom/events",       label: "Events" },
];

export default function NewsroomLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[#040810] text-white">
      <div className="border-b border-white/[0.07] bg-black/20">
        <div className="mx-auto max-w-6xl px-4 py-3 sm:px-6">
          <Link href="/newsroom" className="flex items-center gap-2">
            <Radio className="h-3.5 w-3.5 text-sky-400" />
            <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">
              AI Newsroom
            </span>
          </Link>
          <nav className="mt-2 flex flex-wrap gap-x-5 gap-y-1.5">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="text-[12.5px] font-medium text-slate-400 transition hover:text-white"
              >
                {n.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
      {children}
    </main>
  );
}
