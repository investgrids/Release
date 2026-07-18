import type { Metadata } from "next";
import Link from "next/link";
import { BookOpen, Library, Compass, GraduationCap } from "lucide-react";

export const metadata: Metadata = {
  title: {
    default: "Learn — MarketRipple Knowledge Library",
    template: "%s | MarketRipple Learn",
  },
  description:
    "MarketRipple's Knowledge Library — a glossary of Indian market terms, product guides, and investor education articles. Understand markets, not just watch them.",
};

const NAV = [
  { href: "/learn",          label: "Overview", icon: Compass },
  { href: "/learn/glossary", label: "Glossary",  icon: Library },
  { href: "/learn/guides",   label: "Guides",    icon: BookOpen },
  { href: "/learn/articles", label: "Articles",  icon: GraduationCap },
];

export default function LearnLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-5xl px-5 py-8 md:px-8">
      <nav aria-label="Knowledge Library" className="mb-8 flex gap-1 overflow-x-auto rounded-xl border border-white/[0.07] bg-[#080c14] p-1 scrollbar-hide">
        {NAV.map(item => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href as any}
              className="flex min-w-[110px] flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[12px] font-semibold text-slate-400 transition hover:bg-white/[0.04] hover:text-white"
            >
              <Icon className="h-3.5 w-3.5" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
