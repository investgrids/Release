"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function Icon({ path, viewBox = "0 0 24 24" }: { path: string; viewBox?: string }) {
  return (
    <svg viewBox={viewBox} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4 shrink-0">
      <path d={path} />
    </svg>
  );
}

const primaryNav = [
  {
    label: "Dashboard", href: "/",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
  },
  {
    label: "Events", href: "/events",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
  },
  {
    label: "Stories", href: "/stories",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
  },
  {
    label: "News", href: "/news",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><path d="M19 20H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h10l6 6v8a2 2 0 0 1-2 2z"/><path d="M17 20v-8H7v8M7 4v4h10"/></svg>
  },
  {
    label: "Opportunity Radar", href: "/radar",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/></svg>
  },
  {
    label: "Event Explorer", href: "/stocks",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
  },
  {
    label: "Compare Companies", href: "/compare",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>
  },
  {
    label: "Economic Calendar", href: "/calendar",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
  }
];

const marketOverview = [
  {
    label: "Market Indices", href: "/market-indices",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>
  },
  {
    label: "Sectors", href: "/sectors",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
  },
  {
    label: "Heatmap", href: "/heatmap",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><rect x="3" y="3" width="4" height="4"/><rect x="10" y="3" width="4" height="4"/><rect x="17" y="3" width="4" height="4"/><rect x="3" y="10" width="4" height="4"/><rect x="10" y="10" width="4" height="4"/><rect x="17" y="10" width="4" height="4"/><rect x="3" y="17" width="4" height="4"/><rect x="10" y="17" width="4" height="4"/><rect x="17" y="17" width="4" height="4"/></svg>
  },
  {
    label: "Market Breadth", href: "/market-breadth",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
  }
];

const intelligenceNav = [
  {
    label: "AI Market Wrap", href: "/ai-wrap",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
  },
  {
    label: "Top Themes", href: "/themes",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
  },
  {
    label: "Government Policies", href: "/policies",
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
  }
];

function NavLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
  return (
    <Link
      href={href as any}
      className={`flex items-center gap-3 rounded-[16px] px-3 py-2.5 text-sm transition ${
        active
          ? "bg-indigo-600/20 text-white font-medium ring-1 ring-indigo-500/30"
          : "text-slate-400 hover:bg-white/5 hover:text-white"
      }`}
    >
      <span className={active ? "text-indigo-400" : "text-slate-500"}>{icon}</span>
      {label}
    </Link>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden xl:block sticky top-[92px] self-start max-h-[calc(100vh-92px)]">
      <div className="flex h-full flex-col rounded-[28px] border border-white/10 bg-[#06070A]/70 p-4 shadow-[0_45px_120px_rgba(2,7,10,0.45)] backdrop-blur-2xl overflow-y-auto">
        <div className="space-y-1 text-sm flex-1">
          <nav className="space-y-0.5">
            {primaryNav.map((item) => (
              <NavLink key={item.label} href={item.href} icon={item.icon} label={item.label} />
            ))}
          </nav>

          <div className="pt-4">
            <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-600">Market Overview</p>
            <nav className="space-y-0.5">
              {marketOverview.map((item) => (
                <NavLink key={item.label} href={item.href} icon={item.icon} label={item.label} />
              ))}
            </nav>
          </div>

          <div className="pt-4">
            <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-600">Intelligence</p>
            <nav className="space-y-0.5">
              {intelligenceNav.map((item) => (
                <NavLink key={item.label} href={item.href} icon={item.icon} label={item.label} />
              ))}
            </nav>
          </div>
        </div>

        {/* Pro upgrade card */}
        <div className="mt-4 rounded-[20px] border border-violet-500/20 bg-gradient-to-br from-violet-500/10 to-sky-500/5 p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-violet-400 text-base">💎</span>
            <p className="text-sm font-semibold text-white">EventIQ Pro</p>
          </div>
          <p className="text-xs leading-5 text-slate-400">Unlock advanced intelligence &amp; export</p>
          <button className="mt-3 w-full rounded-[14px] bg-gradient-to-r from-violet-600 to-sky-500 px-4 py-2.5 text-xs font-semibold text-white shadow-lg transition hover:opacity-90">
            Upgrade Now
          </button>
        </div>
      </div>
    </aside>
  );
}
