"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home, Library, Sunrise, Radio, TrendingUp, Building2, CalendarClock,
  type LucideIcon,
} from "lucide-react";

// No "Live Sources" entry — that page's whole purpose was linking out to
// third-party wire copy, which the app doesn't do (see /newsroom/sources
// and every other former external-link exit point, all converted to
// plain attribution text).
type NavItem = { href: string; label: string; icon: LucideIcon };
type NavGroup = { title: string; items: NavItem[] };

export const NEWSROOM_NAV: NavGroup[] = [
  {
    title: "Today",
    items: [
      { href: "/newsroom",             label: "Home",        icon: Home },
      { href: "/newsroom/daily-brief", label: "Daily Brief", icon: Sunrise },
      { href: "/newsroom/breaking",    label: "Breaking",    icon: Radio },
    ],
  },
  {
    title: "Intelligence",
    items: [
      { href: "/newsroom/themes",    label: "Themes",    icon: TrendingUp },
      { href: "/newsroom/companies", label: "Companies", icon: Building2 },
      { href: "/newsroom/events",    label: "Events",    icon: CalendarClock },
    ],
  },
  {
    title: "Archive",
    items: [{ href: "/newsroom/library", label: "Library", icon: Library }],
  },
];

// "/newsroom" must match exactly (it's a prefix of every other route here);
// everything else matches on prefix so a detail page like
// /newsroom/article/[slug] still highlights its section — article pages
// don't have their own nav entry.
export function isNewsroomNavActive(pathname: string, href: string): boolean {
  return href === "/newsroom" ? pathname === "/newsroom" : pathname.startsWith(href);
}

const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#d4b86a]";

/** Desktop rail: grouped, with a gold marker on the current page. */
export function NewsroomSidebarNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="AI Newsroom" className="space-y-6">
      {NEWSROOM_NAV.map((group) => (
        <div key={group.title}>
          <p className="mb-2 px-3 font-[family-name:var(--font-newsroom-serif)] text-[13px] italic tracking-wide text-[#a9b3cf]">
            {group.title}
          </p>
          <ul className="space-y-0.5">
            {group.items.map((n) => {
              const active = isNewsroomNavActive(pathname, n.href);
              const Icon = n.icon;
              return (
                <li key={n.href}>
                  <Link
                    href={n.href}
                    aria-current={active ? "page" : undefined}
                    className={`group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-[13.5px] font-medium transition-[background-color,color,transform] duration-200 ease-out motion-safe:hover:translate-x-0.5 ${FOCUS} ${
                      active
                        ? "bg-white/[0.08] text-[#f6f2e6] shadow-[inset_0_0_0_1px_rgba(212,184,106,0.28)]"
                        : "text-[#c3cbe2] hover:bg-white/[0.05] hover:text-[#f6f2e6]"
                    }`}
                  >
                    <Icon
                      aria-hidden="true"
                      strokeWidth={1.75}
                      className={`h-4 w-4 shrink-0 transition-colors duration-200 ${active ? "text-[#d4b86a]" : "text-[#8d98b8] group-hover:text-[#d4b86a]"}`}
                    />
                    <span className="flex-1">{n.label}</span>
                    {active && (
                      <svg aria-hidden="true" viewBox="0 0 8 8" className="h-1.5 w-1.5 shrink-0 text-[#d4b86a]">
                        <path d="M4 0 8 4 4 8 0 4z" fill="currentColor" />
                      </svg>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/** Small-screen tabs: the sidebar is desktop-only, so this is the only way to move around the newsroom on a phone. */
export function NewsroomTabsNav() {
  const pathname = usePathname();
  const items = NEWSROOM_NAV.flatMap((g) => g.items);

  return (
    <nav aria-label="AI Newsroom sections" className="scrollbar-hide -mx-4 overflow-x-auto px-4 sm:-mx-6 sm:px-6">
      <ul className="flex min-w-max gap-1 pb-2.5">
        {items.map((n) => {
          const active = isNewsroomNavActive(pathname, n.href);
          const Icon = n.icon;
          return (
            <li key={n.href}>
              <Link
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-2 text-[12.5px] font-medium transition-colors duration-200 ${FOCUS} ${
                  active
                    ? "bg-white/[0.1] text-[#f6f2e6] shadow-[inset_0_0_0_1px_rgba(212,184,106,0.35)]"
                    : "text-[#c3cbe2] hover:bg-white/[0.06] hover:text-[#f6f2e6]"
                }`}
              >
                <Icon aria-hidden="true" strokeWidth={1.75} className={`h-3.5 w-3.5 ${active ? "text-[#d4b86a]" : "text-[#8d98b8]"}`} />
                {n.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
