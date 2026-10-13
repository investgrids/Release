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

// Brand: primary #6366F1, secondary #14B8A6.
const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6366F1]";
// The current page: a tinted glass pill (primary into secondary) with a bright top edge and a soft primary glow.
const ACTIVE = "text-text-primary dark:text-[#F8FAFC] border border-[#6366F1]/45 bg-gradient-to-br from-[#6366F1]/30 to-[#14B8A6]/20 backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.55),0_8px_20px_-10px_rgba(99,102,241,0.75)]";
const INACTIVE = "border border-transparent text-text-secondary hover:border-white/50 hover:bg-white/40 hover:text-text-primary hover:backdrop-blur-md dark:text-[#94A3B8] dark:hover:border-white/10 dark:hover:bg-white/[0.08] dark:hover:text-[#F8FAFC]";
const TEAL = "text-[#14B8A6]";

/** Desktop rail. Sits on the frosted panel in layout.tsx; primary and secondary only mark the current page and hover. */
export function NewsroomSidebarNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="AI Newsroom" className="space-y-5">
      {NEWSROOM_NAV.map((group) => (
        <div key={group.title}>
          <h2 className="mb-1.5 px-3 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-text-muted dark:text-[#94A3B8]">{group.title}</h2>
          <ul className="space-y-0.5">
            {group.items.map((n) => {
              const active = isNewsroomNavActive(pathname, n.href);
              const Icon = n.icon;
              return (
                <li key={n.href}>
                  <Link
                    href={n.href}
                    aria-current={active ? "page" : undefined}
                    className={`group flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13.5px] font-medium transition-[background-color,border-color,color,box-shadow] duration-200 ${FOCUS} ${
                      active ? ACTIVE : INACTIVE
                    }`}
                  >
                    <Icon
                      aria-hidden="true"
                      strokeWidth={1.75}
                      className={`h-4 w-4 shrink-0 transition-colors duration-200 ${active ? TEAL : "text-text-muted group-hover:text-[#6366F1]"}`}
                    />
                    <span className="flex-1">{n.label}</span>
                    {active && (
                      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#14B8A6] shadow-[0_0_8px_2px_rgba(20,184,166,0.55)]" />
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
      <ul className="flex min-w-max gap-1.5 pb-3">
        {items.map((n) => {
          const active = isNewsroomNavActive(pathname, n.href);
          const Icon = n.icon;
          return (
            <li key={n.href}>
              <Link
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-[background-color,border-color,color] duration-200 ${FOCUS} ${
                  active ? ACTIVE : "border border-white/50 bg-white/35 text-text-secondary backdrop-blur-md hover:bg-white/55 hover:text-text-primary dark:border-white/10 dark:bg-white/[0.06] dark:text-[#94A3B8] dark:hover:text-[#F8FAFC]"
                }`}
              >
                <Icon aria-hidden="true" strokeWidth={1.75} className={`h-3.5 w-3.5 ${active ? TEAL : "text-text-muted"}`} />
                {n.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
