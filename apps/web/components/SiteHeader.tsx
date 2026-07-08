"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { useNavLoading } from "@/components/NavLoadingProvider";
import { useAlerts } from "@/components/AlertProvider";
import { Bell, Sun, Moon } from "lucide-react";

const navItems = [
  {
    label: "Market",
    href: "/",
    subtitle: "Live indices, sectors & market overview",
  },
  {
    label: "Events",
    href: "/events",
    subtitle: "Policy decisions, earnings & economic events",
  },
  {
    label: "Company Insights",
    href: "/companies",
    subtitle: "Understand businesses beyond stock prices",
  },
  {
    label: "Market Stories",
    href: "/stories",
    subtitle: "Deep dives into the themes shaping markets",
  },
  {
    label: "Best Opportunities",
    href: "/radar",
    subtitle: "AI-scored sectors and companies worth watching",
  },
  {
    label: "Market Impact",
    href: "/ripple",
    subtitle: "See how events ripple across sectors and companies",
  },
  {
    label: "Ask Market AI",
    href: "/ai-search",
    subtitle: "Get reasoned answers to any investment question",
  },
];

export function SiteHeader() {
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const { start } = useNavLoading();
  const { alerts } = useAlerts();
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [tooltip, setTooltip] = useState<string | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("mr_theme") as "dark" | "light" | null;
      if (saved) setTheme(saved);
    } catch {}
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("mr_theme", theme); } catch {}
  }, [theme]);

  function isActive(href: string) {
    if (!pathname) return false;
    if (href === "/radar") {
      return (
        pathname === "/radar" ||
        pathname.startsWith("/radar/") ||
        pathname === "/opportunity-radar" ||
        pathname.startsWith("/opportunity-radar/")
      );
    }
    return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/90 shadow-[0_25px_80px_rgba(2,7,10,0.35)] dark-header light-header">
      <div className="mx-auto flex h-[68px] max-w-[1600px] items-center gap-4 px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3 shrink-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-[14px] bg-gradient-to-br from-violet-500 to-sky-400 text-white shadow-lg shadow-violet-500/25">
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
              <path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/>
            </svg>
          </div>
          <span className="text-base font-semibold text-white hidden sm:block">MarketRipple</span>
        </Link>

        {/* Search bar */}
        <form action="/ai-search" method="get" className="flex flex-1 max-w-[520px]">
          <div className="flex w-full items-center gap-2 rounded-full border border-white/10 bg-slate-900/80 px-4 py-2 shadow-inner transition focus-within:border-sky-500/30">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 shrink-0 text-slate-500">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              type="text"
              name="q"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask any market question…"
              className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500 min-w-0"
            />
          </div>
        </form>

        {/* Nav links */}
        <nav className="hidden xl:flex items-center gap-0.5 text-sm text-slate-400 ml-2">
          {navItems.map((item) => (
            <div
              key={item.label}
              className="relative"
              onMouseEnter={() => setTooltip(item.label)}
              onMouseLeave={() => setTooltip(null)}
            >
              <Link
                href={item.href as any}
                onClick={() => { if (!isActive(item.href)) start(); }}
                className={`rounded-full px-3 py-1.5 transition text-sm whitespace-nowrap ${
                  isActive(item.href)
                    ? "bg-white/10 text-white font-medium"
                    : "hover:bg-white/5 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
              {/* Tooltip */}
              {tooltip === item.label && (
                <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 z-50 pointer-events-none">
                  <div className="rounded-xl border border-white/10 bg-slate-900/95 px-3 py-2 shadow-xl backdrop-blur-sm whitespace-nowrap">
                    <p className="text-[11px] text-slate-300">{item.subtitle}</p>
                  </div>
                  <div className="absolute -top-1 left-1/2 -translate-x-1/2 h-2 w-2 rotate-45 border-l border-t border-white/10 bg-slate-900/95" />
                </div>
              )}
            </div>
          ))}
        </nav>

        {/* Right actions */}
        <div className="ml-auto flex items-center gap-2 shrink-0">
          {/* Theme toggle */}
          <button
            onClick={() => setTheme(t => t === "dark" ? "light" : "dark")}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-slate-900/80 text-slate-400 transition hover:bg-white/5 hover:text-white"
            title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          <div className="relative hidden xl:inline-flex">
            <button className="h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-slate-900/80 text-slate-400 transition hover:bg-white/5 hover:text-white flex">
              <Bell className="h-4 w-4" />
            </button>
            {alerts.length > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[9px] font-bold text-white animate-pulse">
                {alerts.length}
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
