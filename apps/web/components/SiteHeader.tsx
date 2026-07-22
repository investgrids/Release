"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import { useNavLoading } from "@/components/NavLoadingProvider";
import { useAlerts } from "@/components/AlertProvider";
import { Bell, Search, ChevronDown, Menu, X, Bookmark } from "lucide-react";
import { WatchlistDrawer } from "@/components/WatchlistDrawer";
import { useWatchlist } from "@/hooks/useWatchlist";
import { API_BASE_URL as API } from "@/lib/api";

// Primary nav — always visible on desktop
const NAV_PRIMARY = [
  { label: "Home",        href: "/" },
  { label: "AI Newsroom", href: "/newsroom" },
  { label: "Intelligence",href: "/market-intelligence" },
  { label: "Events",      href: "/events" },
  { label: "Companies",   href: "/companies" },
  { label: "AI Search",   href: "/ai-search" },
];

// Secondary nav — shown in "More" dropdown and mobile drawer
// "Publishing" removed: it pointed at the internal ops/monitoring dashboard
// (validation stats, retry queue — not reader content), which next to the
// new public "AI Newsroom" primary nav item read as two destinations for
// the same thing. The ops dashboard itself is untouched, just no longer
// linked from public nav — reachable directly by URL for staff.
const NAV_MORE = [
  { label: "Market Overview",   href: "/markets" },
  { label: "Policy & Calendar", href: "/calendar" },
  { label: "Themes",            href: "/newsroom/themes" },
  { label: "Graph",             href: "/graph" },
  { label: "Learn",             href: "/learn" },
];

const NAV_ALL = [...NAV_PRIMARY, ...NAV_MORE];

function getISTSession() {
  const istMs = Date.now() + (5 * 60 + 30) * 60_000;
  const ist   = new Date(istMs);
  const h = ist.getUTCHours(), m = ist.getUTCMinutes(), dow = ist.getUTCDay();
  const mins = h * 60 + m;
  const isWd = dow >= 1 && dow <= 5;
  if (!isWd) return { label: "WEEKEND", cls: "bg-violet-600/20 text-violet-400 border-violet-500/30", dot: "bg-violet-400" };
  if (mins < 9 * 60 + 15) return { label: "PRE-MARKET", cls: "bg-sky-600/20 text-sky-400 border-sky-500/30", dot: "bg-sky-400" };
  if (mins <= 15 * 60 + 30) return { label: "LIVE", cls: "bg-emerald-600/20 text-emerald-400 border-emerald-500/30", dot: "bg-emerald-400 animate-pulse" };
  return { label: "CLOSED", cls: "bg-slate-700/40 text-slate-400 border-slate-600/40", dot: "bg-slate-500" };
}

export function SiteHeader() {
  const pathname    = usePathname();
  const { start }   = useNavLoading();
  const [session, setSession]   = useState(getISTSession);
  const [nifty, setNifty]       = useState<{ value: string; change: string; positive: boolean } | null>(null);
  const [mobileOpen, setMobile]       = useState(false);
  const [searchOpen, setSearch]       = useState(false);
  const [moreOpen, setMore]           = useState(false);
  const [watchlistOpen, setWatchlist] = useState(false);
  const { count: watchlistCount }     = useWatchlist();
  const [query, setQuery]       = useState("");
  const [notifOpen, setNotif]   = useState(false);
  const moreRef                 = useRef<HTMLDivElement>(null);
  const notifRef                = useRef<HTMLDivElement>(null);
  const { alerts, dismiss }     = useAlerts();

  // Close "More" dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMore(false);
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotif(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Refresh session badge every 30 s
  useEffect(() => {
    const id = setInterval(() => setSession(getISTSession()), 30_000);
    return () => clearInterval(id);
  }, []);

  // Fetch Nifty value once on mount (lightweight, non-blocking)
  useEffect(() => {
    fetch(`${API}/api/indices/`)
      .then(r => r.ok ? r.json() : null)
      .then((data: any[] | null) => {
        const idx = data?.find((i: any) => /nifty 50/i.test(i.title ?? i.name ?? ""));
        if (idx) setNifty({ value: idx.value, change: idx.change, positive: idx.positive !== false });
      })
      .catch(() => {});
  }, []);

  function isActive(href: string) {
    if (!pathname) return false;
    return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-white/[0.08] bg-[#020617]/95 backdrop-blur-xl">
        <div className="mx-auto flex h-[68px] max-w-[1600px] items-center gap-3 px-6">

          {/* Logo */}
          <Link href="/" className="flex shrink-0 items-center gap-2.5 mr-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-gradient-to-br from-violet-500 to-sky-500 shadow-lg shadow-violet-500/20">
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4 text-white">
                <path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/>
              </svg>
            </div>
            <span className="hidden text-[15px] font-bold text-white sm:block">MarketRipple</span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden lg:flex items-center gap-0.5">
            {NAV_PRIMARY.map(item => (
              <Link
                key={item.href}
                href={item.href as any}
                onClick={() => { if (!isActive(item.href)) start(); }}
                className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-all whitespace-nowrap ${
                  isActive(item.href)
                    ? "bg-white/10 text-white"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                }`}
              >
                {item.label}
              </Link>
            ))}

            {/* More dropdown */}
            <div className="relative" ref={moreRef}>
              <button
                onClick={() => setMore(o => !o)}
                className={`flex items-center gap-1 rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-all whitespace-nowrap ${
                  moreOpen || NAV_MORE.some(i => isActive(i.href))
                    ? "bg-white/10 text-white"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                }`}
              >
                More <ChevronDown className={`h-3.5 w-3.5 transition-transform ${moreOpen ? "rotate-180" : ""}`} />
              </button>
              {moreOpen && (
                <div className="absolute left-0 top-full mt-2 w-48 rounded-2xl border border-white/[0.10] bg-[#0a0f1e] shadow-2xl p-2 z-50">
                  {NAV_MORE.map(item => (
                    <Link
                      key={item.href}
                      href={item.href as any}
                      onClick={() => { setMore(false); if (!isActive(item.href)) start(); }}
                      className={`flex w-full items-center rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all ${
                        isActive(item.href)
                          ? "bg-white/10 text-white"
                          : "text-slate-400 hover:bg-white/[0.06] hover:text-slate-200"
                      }`}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </nav>

          {/* Right side */}
          <div className="ml-auto flex items-center gap-2 shrink-0">
            {/* Nifty value */}
            {nifty && (
              <div className="hidden lg:flex items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">NIFTY</span>
                <span className="text-[13px] font-bold tabular-nums text-white">{nifty.value}</span>
                <span className={`text-[11px] font-semibold tabular-nums ${nifty.positive ? "text-emerald-400" : "text-rose-400"}`}>{nifty.change}</span>
              </div>
            )}

            {/* Session badge */}
            <div className={`hidden sm:flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-bold ${session.cls}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${session.dot}`} />
              {session.label}
            </div>

            {/* Search */}
            <button
              onClick={() => setSearch(s => !s)}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.03] text-slate-400 transition hover:bg-white/[0.07] hover:text-white"
            >
              <Search className="h-4 w-4" />
            </button>

            {/* Watchlist */}
            <div className="relative">
              <button
                onClick={() => setWatchlist(o => !o)}
                className={`flex h-9 w-9 items-center justify-center rounded-full border transition ${
                  watchlistOpen
                    ? "border-violet-500/40 bg-violet-500/15 text-violet-400"
                    : "border-white/[0.08] bg-white/[0.03] text-slate-400 hover:bg-white/[0.07] hover:text-white"
                }`}
                title="Watchlist"
              >
                <Bookmark className="h-4 w-4" fill={watchlistCount > 0 ? "currentColor" : "none"} />
              </button>
              {watchlistCount > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-violet-500 text-[8px] font-black text-white">
                  {watchlistCount > 9 ? "9+" : watchlistCount}
                </span>
              )}
            </div>

            {/* Notifications */}
            <div className="relative" ref={notifRef}>
              <button
                onClick={() => setNotif(o => !o)}
                aria-label="Notifications"
                className="flex h-9 w-9 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.03] text-slate-400 transition hover:bg-white/[0.07] hover:text-white"
              >
                <Bell className="h-4 w-4" />
              </button>
              {alerts.length > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[8px] font-black text-white">
                  {alerts.length > 9 ? "9+" : alerts.length}
                </span>
              )}
              {notifOpen && (
                <div className="absolute right-0 top-full mt-2 w-80 rounded-2xl border border-white/[0.10] bg-[#0a0f1e]/98 backdrop-blur-xl shadow-2xl z-50 overflow-hidden">
                  <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
                    <span className="text-[12px] font-bold text-white">Notifications</span>
                    {alerts.length > 0 && (
                      <span className="text-[10px] font-semibold text-slate-500">{alerts.length} active</span>
                    )}
                  </div>
                  {alerts.length === 0 ? (
                    <p className="px-4 py-6 text-center text-[12px] text-slate-500">No active alerts right now.</p>
                  ) : (
                    <div className="max-h-96 overflow-y-auto">
                      {alerts.slice(0, 8).map(a => (
                        <div key={a.id} className="flex items-start gap-2.5 border-b border-white/[0.04] px-4 py-3 last:border-0 hover:bg-white/[0.03]">
                          <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${a.urgency === "critical" ? "bg-rose-500" : "bg-amber-500"}`} />
                          <div className="min-w-0 flex-1">
                            <p className="text-[12px] font-semibold leading-snug text-slate-200 line-clamp-2">{a.headline}</p>
                            <p className="mt-0.5 text-[10px] text-slate-500 line-clamp-1">{a.summary}</p>
                          </div>
                          <button
                            onClick={() => dismiss(a.id)}
                            aria-label="Dismiss"
                            className="shrink-0 rounded-full p-1 text-slate-600 hover:bg-white/[0.06] hover:text-slate-300 transition"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <Link
                    href="/market-intelligence"
                    onClick={() => setNotif(false)}
                    className="block border-t border-white/[0.06] px-4 py-2.5 text-center text-[11px] font-semibold text-violet-400 hover:text-violet-300 transition"
                  >
                    View Market Intelligence →
                  </Link>
                </div>
              )}
            </div>

            {/* Mobile menu toggle */}
            <button
              onClick={() => setMobile(o => !o)}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.03] text-slate-400 lg:hidden"
            >
              {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Search bar dropdown */}
        {searchOpen && (
          <div className="border-t border-white/[0.06] bg-[#020617]/95 px-6 py-3">
            <form action="/ai-search" method="get" onSubmit={() => setSearch(false)}>
              <div className="mx-auto flex max-w-2xl items-center gap-3 rounded-2xl border border-white/[0.1] bg-white/[0.04] px-4 py-2.5 focus-within:border-violet-500/40">
                <Search className="h-4 w-4 shrink-0 text-slate-500" />
                <input
                  autoFocus
                  type="text"
                  name="q"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Ask any market question…"
                  className="flex-1 bg-transparent text-[14px] text-white outline-none placeholder:text-slate-500"
                />
                <kbd className="hidden rounded-md border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-slate-600 sm:block">⌘K</kbd>
              </div>
            </form>
          </div>
        )}
      </header>

      {/* Watchlist drawer */}
      <WatchlistDrawer open={watchlistOpen} onClose={() => setWatchlist(false)} />

      {/* Mobile nav drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobile(false)} />
          <nav className="absolute left-0 top-[68px] w-64 bg-[#0a0f1e] border-r border-white/[0.08] h-[calc(100vh-68px)] p-4 flex flex-col gap-1 overflow-y-auto">
            {NAV_ALL.map(item => (
              <Link
                key={item.href}
                href={item.href as any}
                onClick={() => { setMobile(false); if (!isActive(item.href)) start(); }}
                className={`rounded-xl px-4 py-3 text-[14px] font-medium transition ${
                  isActive(item.href)
                    ? "bg-white/10 text-white"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </>
  );
}
