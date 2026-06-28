"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

const navItems = [
  { label: "Dashboard", href: "/"        },
  { label: "Events",    href: "/events"  },
  { label: "Stories",   href: "/stories" },
  { label: "News",      href: "/news"    },
  { label: "Radar",     href: "/radar"   },
  { label: "Explorer",  href: "/stocks"  },
  { label: "Compare",   href: "/compare" },
  { label: "Calendar",  href: "/calendar"},
];

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState("");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    router.push("/search");
  }

  function isActive(href: string) {
    return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/90 backdrop-blur-xl shadow-[0_25px_80px_rgba(2,7,10,0.35)]">
      <div className="mx-auto flex h-[68px] max-w-[1600px] items-center gap-4 px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3 shrink-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-[14px] bg-gradient-to-br from-violet-500 to-sky-400 text-white text-base font-bold shadow-lg shadow-violet-500/25">
            ✦
          </div>
          <span className="text-base font-semibold text-white hidden sm:block">EventIQ</span>
        </Link>

        {/* Search bar */}
        <form onSubmit={handleSearch} className="flex flex-1 max-w-[520px]">
          <div className="flex w-full items-center gap-2 rounded-full border border-white/10 bg-slate-900/80 px-4 py-2 shadow-inner backdrop-blur-xl transition focus-within:border-sky-500/30">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0 text-slate-500">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search events, stocks, sectors…"
              className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500 min-w-0"
            />
            <kbd className="hidden sm:inline-flex items-center gap-1 rounded-md border border-white/10 bg-slate-800/80 px-1.5 py-0.5 text-[10px] text-slate-400">
              <span>⌘</span><span>K</span>
            </kbd>
          </div>
        </form>

        {/* Nav links */}
        <nav className="hidden xl:flex items-center gap-0.5 text-sm text-slate-400 ml-2">
          {navItems.map((item) => (
            <Link
              key={item.label}
              href={item.href as any}
              className={`rounded-full px-3 py-1.5 transition text-sm ${
                isActive(item.href)
                  ? "bg-white/10 text-white font-medium"
                  : "hover:bg-white/5 hover:text-white"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        {/* Right actions */}
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <button className="hidden xl:inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-slate-900/80 text-slate-400 transition hover:bg-white/5 hover:text-white text-sm">
            🔔
          </button>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 to-violet-500 text-xs font-semibold text-white shadow-lg shadow-sky-500/20">
            ML
          </div>
        </div>
      </div>
    </header>
  );
}
