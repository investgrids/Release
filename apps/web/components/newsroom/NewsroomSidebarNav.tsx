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

const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-violet";
// The current page: royal indigo with a gold icon. White on #2b2087 is above 12:1.
const ACTIVE = "bg-[#2b2087] text-white shadow-[0_6px_16px_-8px_rgba(43,32,135,0.8)]";
const GOLD = "text-[#e8c766]";

/** Desktop rail. Uses the site's own surface, border and type tokens; royal indigo and gold only mark the current page. */
export function NewsroomSidebarNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="AI Newsroom" className="space-y-5">
      {NEWSROOM_NAV.map((group) => (
        <div key={group.title}>
          <h2 className="mb-1.5 px-3 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-text-muted">{group.title}</h2>
          <ul className="space-y-0.5">
            {group.items.map((n) => {
              const active = isNewsroomNavActive(pathname, n.href);
              const Icon = n.icon;
              return (
                <li key={n.href}>
                  <Link
                    href={n.href}
                    aria-current={active ? "page" : undefined}
                    className={`group flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] font-medium transition-colors duration-200 ${FOCUS} ${
                      active ? ACTIVE : "text-text-secondary hover:bg-accent-violet/[0.08] hover:text-text-primary"
                    }`}
                  >
                    <Icon
                      aria-hidden="true"
                      strokeWidth={1.75}
                      className={`h-4 w-4 shrink-0 transition-colors duration-200 ${active ? GOLD : "text-text-muted group-hover:text-accent-violet"}`}
                    />
                    <span className="flex-1">{n.label}</span>
                    {active && (
                      <svg aria-hidden="true" viewBox="0 0 10 10" className={`h-1.5 w-1.5 shrink-0 ${GOLD}`}>
                        <path d="M5 0 10 5 5 10 0 5z" fill="currentColor" />
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
      <ul className="flex min-w-max gap-1.5 pb-3">
        {items.map((n) => {
          const active = isNewsroomNavActive(pathname, n.href);
          const Icon = n.icon;
          return (
            <li key={n.href}>
              <Link
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-colors duration-200 ${FOCUS} ${
                  active ? ACTIVE : "border border-surface-border/10 text-text-secondary hover:bg-accent-violet/[0.08] hover:text-text-primary"
                }`}
              >
                <Icon aria-hidden="true" strokeWidth={1.75} className={`h-3.5 w-3.5 ${active ? GOLD : "text-text-muted"}`} />
                {n.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
