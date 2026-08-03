"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home, Library, Sunrise, Radio, TrendingUp, Building2, CalendarClock,
} from "lucide-react";

// No "Live Sources" entry — that page's whole purpose was linking out to
// third-party wire copy, which the app doesn't do (see /newsroom/sources
// and every other former external-link exit point, all converted to
// plain attribution text).
const NAV = [
  { href: "/newsroom",              label: "Home",        icon: Home },
  { href: "/newsroom/library",      label: "Library",     icon: Library },
  { href: "/newsroom/daily-brief",  label: "Daily Brief",  icon: Sunrise },
  { href: "/newsroom/breaking",     label: "Breaking",    icon: Radio },
  { href: "/newsroom/themes",       label: "Themes",      icon: TrendingUp },
  { href: "/newsroom/companies",    label: "Companies",   icon: Building2 },
  { href: "/newsroom/events",       label: "Events",      icon: CalendarClock },
];

export function NewsroomSidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="space-y-0.5">
      {NAV.map((n) => {
        // "/newsroom" must match exactly (it's a prefix of every other
        // route here); everything else matches on prefix so a detail page
        // like /newsroom/article/[slug] still highlights its section —
        // article pages don't have their own nav entry.
        const active = n.href === "/newsroom" ? pathname === "/newsroom" : pathname.startsWith(n.href);
        const Icon = n.icon;
        return (
          <Link
            key={n.href}
            href={n.href}
            className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition ${
              active ? "bg-text-primary/[0.08] text-text-primary" : "text-text-secondary hover:bg-text-primary/[0.04] hover:text-text-primary"
            }`}
          >
            <Icon className={`h-3.5 w-3.5 shrink-0 ${active ? "text-sky-400" : "text-text-muted"}`} />
            {n.label}
          </Link>
        );
      })}
    </nav>
  );
}
