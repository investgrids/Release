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

const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#f3dc92]";
const SERIF = "font-[family-name:var(--font-newsroom-serif)]";
// Gold foil: the plaque behind the current page. Text on it is the deep royal blue (contrast above 9:1).
const FOIL = "bg-[linear-gradient(135deg,#f8e9ae_0%,#e0bc62_48%,#b88a30_100%)] text-[#150e52] shadow-[0_6px_18px_-6px_rgba(0,0,0,0.55),inset_0_1px_0_rgba(255,255,255,0.55)]";

/** Desktop rail: grouped under ornamental headings, the current page set on a gold-foil plaque. */
export function NewsroomSidebarNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="AI Newsroom" className="space-y-7">
      {NEWSROOM_NAV.map((group) => (
        <div key={group.title}>
          <div className="mb-3 flex items-center gap-2.5 px-1" aria-hidden="true">
            <span className="h-px flex-1 bg-gradient-to-r from-transparent to-[#e0bc62]/55" />
            <span className={`${SERIF} text-[13px] font-semibold uppercase tracking-[0.28em] text-[#ecd48a]`}>{group.title}</span>
            <span className="h-px flex-1 bg-gradient-to-l from-transparent to-[#e0bc62]/55" />
          </div>
          <h2 className="sr-only">{group.title}</h2>
          <ul className="space-y-1">
            {group.items.map((n) => {
              const active = isNewsroomNavActive(pathname, n.href);
              const Icon = n.icon;
              return (
                <li key={n.href}>
                  <Link
                    href={n.href}
                    aria-current={active ? "page" : undefined}
                    className={`group relative flex items-center gap-3.5 rounded-lg px-3.5 py-2.5 transition-[background-color,color,box-shadow,transform] duration-200 ease-out ${FOCUS} ${
                      active
                        ? FOIL
                        : "text-[#e9e3ff] hover:bg-[#e0bc62]/[0.12] hover:text-[#fff6d8] hover:shadow-[inset_0_0_0_1px_rgba(224,188,98,0.4)] motion-safe:hover:translate-x-0.5"
                    }`}
                  >
                    <Icon
                      aria-hidden="true"
                      strokeWidth={1.6}
                      className={`h-[18px] w-[18px] shrink-0 transition-colors duration-200 ${active ? "text-[#150e52]" : "text-[#e0bc62]"}`}
                    />
                    <span className={`${SERIF} flex-1 text-[19px] font-semibold leading-none tracking-wide`}>{n.label}</span>
                    {active && (
                      <svg aria-hidden="true" viewBox="0 0 10 10" className="h-2 w-2 shrink-0 text-[#150e52]">
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
                className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-4 py-2 transition-colors duration-200 ${FOCUS} ${
                  active ? FOIL : "text-[#e9e3ff] shadow-[inset_0_0_0_1px_rgba(224,188,98,0.35)] hover:bg-[#e0bc62]/[0.14]"
                }`}
              >
                <Icon aria-hidden="true" strokeWidth={1.6} className={`h-3.5 w-3.5 ${active ? "text-[#150e52]" : "text-[#e0bc62]"}`} />
                <span className={`${SERIF} text-[16px] font-semibold leading-none tracking-wide`}>{n.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
