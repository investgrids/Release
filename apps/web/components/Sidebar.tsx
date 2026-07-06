"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useNavLoading } from "@/components/NavLoadingProvider";
import { Sparkles } from "lucide-react";

function NavLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  const pathname = usePathname();
  const { start } = useNavLoading();
  const active = !!pathname && (href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/"));

  return (
    <Link
      href={href as any}
      onClick={() => { if (!active) start(); }}
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
  const nav = [
    {
      label: "Market Intelligence", href: "/",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
    },
    {
      label: "Events", href: "/events",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
    },
    {
      label: "Companies", href: "/companies",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
    },
    {
      label: "Stories", href: "/stories",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
    },
    {
      label: "Opportunity Radar", href: "/radar",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/></svg>
    },
    {
      label: "Ripple Intelligence", href: "/ripple",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><circle cx="12" cy="12" r="3"/><path d="M12 2a10 10 0 0 1 0 20A10 10 0 0 1 12 2"/><path d="M12 5a7 7 0 0 1 0 14A7 7 0 0 1 12 5" strokeOpacity="0.5"/></svg>
    },
    {
      label: "AI Search", href: "/ai-search",
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0"><path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z"/><path d="M18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z"/></svg>
    },
  ];

  return (
    <aside className="hidden xl:block sticky top-[92px] self-start">
      <div className="sidebar-scroll flex flex-col rounded-[28px] border border-white/10 bg-[#06070A] p-4 shadow-[0_45px_120px_rgba(2,7,10,0.45)] overflow-y-auto max-h-[calc(100vh-116px)]">
        <nav className="space-y-0.5 text-sm flex-1">
          {nav.map((item) => (
            <NavLink key={item.label} href={item.href} icon={item.icon} label={item.label} />
          ))}
        </nav>

        {/* Pro upgrade card */}
        <div className="mt-6 rounded-[20px] border border-violet-500/20 bg-gradient-to-br from-violet-500/10 to-sky-500/5 p-4">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="h-4 w-4 text-violet-400" />
            <p className="text-sm font-semibold text-white">Upgrade to Pro</p>
          </div>
          <p className="text-xs leading-5 text-slate-400">Unlock deeper AI insights, custom reports, advanced filters, and real-time alerts.</p>
          <button className="mt-3 w-full rounded-[14px] bg-gradient-to-r from-violet-600 to-sky-500 px-4 py-2.5 text-xs font-semibold text-white shadow-lg transition hover:opacity-90">
            Upgrade Now
          </button>
        </div>
      </div>
    </aside>
  );
}
