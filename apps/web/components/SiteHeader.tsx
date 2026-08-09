"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import { useNavLoading } from "@/components/NavLoadingProvider";
import { useAlerts } from "@/components/AlertProvider";
import { Bell, Search, ChevronDown, Menu, X, Bookmark } from "lucide-react";
import { WatchlistDrawer } from "@/components/WatchlistDrawer";
import { useWatchlist } from "@/hooks/useWatchlist";
import { ThemeToggle } from "@/components/ThemeToggle";
import { API_BASE_URL as API } from "@/lib/api";
import { trackNavClick, trackSubmenuClick } from "@/lib/navAnalytics";

interface NavSubItem { label: string; href: string; blurb?: string; }
interface NavItem { label: string; href: string; sub?: NavSubItem[]; }

// Header = the investor journey, left to right: how's the market today,
// what just happened, what does it mean, which companies, trace the
// effect + validate against history, what's the resulting opportunity,
// or skip straight to asking. Each hub with more than one real underlying
// page gets a mega-menu of its former-standalone pages, now tabs of that
// hub (routes are unchanged — see next.config.ts, nothing redirects).
const NAV_PRIMARY: NavItem[] = [
  {
    label: "Markets", href: "/market-intelligence",
    sub: [
      { label: "Market Overview",   href: "/market-intelligence",                      blurb: "Where the market stands right now" },
      { label: "Live Market",       href: "/market-intelligence?tab=live-market",       blurb: "Real-time moves as they happen" },
      { label: "Global Markets",    href: "/market-intelligence?tab=global-markets",    blurb: "US, Asia, Europe overnight context" },
      { label: "Economic Calendar", href: "/calendar",                                  blurb: "Upcoming events that could move markets" },
      { label: "Commodities",       href: "/commodities",                               blurb: "Gold, crude, and the rest" },
      { label: "Sector Intelligence", href: "/sectors",                                 blurb: "Performance by sector" },
    ],
  },
  { label: "Events", href: "/events" },
  {
    label: "Insights", href: "/newsroom",
    sub: [
      { label: "Breaking Intelligence", href: "/newsroom/breaking",     blurb: "What just happened, explained" },
      { label: "Live Feed",             href: "/newsroom",              blurb: "The full AI Newsroom feed" },
      { label: "Daily Brief",           href: "/newsroom/daily-brief",  blurb: "Today's market, in one read" },
      { label: "Market Themes",         href: "/newsroom/themes",       blurb: "Recurring narratives worth tracking" },
      { label: "Library",               href: "/newsroom/library",      blurb: "Every AI article, searchable" },
    ],
  },
  {
    label: "Companies", href: "/companies",
    sub: [
      { label: "All Companies", href: "/companies",     blurb: "Search and filter the full universe" },
      { label: "Best Stocks",   href: "/best-stocks",   blurb: "Ranked by AI Company Intelligence Score" },
      { label: "Compare",       href: "/compare",       blurb: "Side-by-side company comparison" },
      { label: "IPO Hub",       href: "/ipo-hub",       blurb: "Upcoming, ongoing, and listed IPOs" },
      { label: "Sectors",       href: "/sectors",       blurb: "Browse companies by sector" },
    ],
  },
  {
    label: "Ripple Intelligence", href: "/ripple",
    sub: [
      { label: "Ripple Chain",         href: "/ripple",     blurb: "Trace an event's cascading effects" },
      { label: "Historical Patterns",  href: "/historical", blurb: "Has this happened before?" },
      { label: "Explore Full Graph",   href: "/graph",      blurb: "The entire dependency network" },
    ],
  },
  { label: "Opportunity Radar", href: "/opportunity-radar" },
  { label: "AI Search", href: "/ai-search" },
  {
    // First of 5 planned tools — a real Tools Home page plus a sub array,
    // same shape every other hub above already uses, so tool 2 is a
    // one-line addition here, not a nav redesign.
    label: "Tools", href: "/tools",
    sub: [
      { label: "Portfolio Confidence Check", href: "/tools/portfolio-confidence", blurb: "How much real coverage do your holdings actually have?" },
    ],
  },
];

function getISTSession() {
  const istMs = Date.now() + (5 * 60 + 30) * 60_000;
  const ist   = new Date(istMs);
  const h = ist.getUTCHours(), m = ist.getUTCMinutes(), dow = ist.getUTCDay();
  const mins = h * 60 + m;
  const isWd = dow >= 1 && dow <= 5;
  if (!isWd) return { label: "WEEKEND", cls: "bg-violet-600/20 text-violet-400 border-violet-500/30", dot: "bg-violet-400" };
  if (mins < 9 * 60 + 15) return { label: "PRE-MARKET", cls: "bg-sky-600/20 text-sky-400 border-sky-500/30", dot: "bg-sky-400" };
  if (mins <= 15 * 60 + 30) return { label: "LIVE", cls: "bg-emerald-600/20 text-emerald-400 border-emerald-500/30", dot: "bg-emerald-400 animate-pulse" };
  return { label: "CLOSED", cls: "bg-text-primary/[0.09] text-text-secondary border-surface-border/9", dot: "bg-slate-500" };
}

export function SiteHeader() {
  const pathname    = usePathname();
  const router       = useRouter();
  const { start }   = useNavLoading();
  const [session, setSession]   = useState(getISTSession);
  const [nifty, setNifty]       = useState<{ value: string; change: string; positive: boolean } | null>(null);
  const [mobileOpen, setMobile]       = useState(false);
  const [mobileExpanded, setMobileExpanded] = useState<string | null>(null);
  const [searchOpen, setSearch]       = useState(false);
  const [watchlistOpen, setWatchlist] = useState(false);
  const { count: watchlistCount }     = useWatchlist();
  const [query, setQuery]       = useState("");
  const { alerts, dismiss }     = useAlerts();

  // Every header dropdown (hub mega menus + notifications) shares one piece
  // of state instead of independent booleans, so opening one always closes
  // any other — previously each toggle was independent, which let the
  // notifications panel stay open while a mega menu (or vice versa) opened
  // on top of it, visually overlapping. "openMenu" is either a hub label,
  // "notifications", or null.
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpenMenu(null);
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
    const base = href.split("?")[0];
    return base === "/" ? pathname === "/" : pathname === base || pathname.startsWith(base + "/");
  }

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-surface-border/8 bg-bg/95 backdrop-blur-xl">
        <div className="mx-auto flex h-[68px] max-w-[1600px] items-center gap-3 px-6" ref={menuRef}>

          {/* Logo — mark is a transparent gradient glyph, theme-agnostic.
              The wordmark bakes in a fixed "market" text color per file (a
              flat image can't read a CSS var), so light/dark variants swap
              via the pure-CSS theme-light-only/theme-dark-only classes
              (globals.css) rather than a JS theme check. */}
          <Link href="/" className="flex shrink-0 items-center mr-4">
            <Image
              src="/marketripple-mark.png"
              alt="MarketRipple"
              width={480}
              height={480}
              className="h-8 w-auto sm:hidden"
              priority
            />
            {/* The responsive (mobile/desktop) and theme (light/dark)
                visibility toggles are two independent concerns handled at
                two DOM levels on purpose — combining "hidden sm:block" and
                "theme-light/dark-only" on the same element let a Tailwind
                media-query utility and a plain CSS rule fight over the same
                `display` property with no reliable winner. */}
            <span className="hidden sm:block">
              <Image
                src="/marketripple-logo.png"
                alt="MarketRipple"
                width={2583}
                height={780}
                className="theme-light-only h-8 w-auto"
                priority
              />
              <Image
                src="/marketripple-logo-dark.png"
                alt="MarketRipple"
                width={2583}
                height={780}
                className="theme-dark-only h-8 w-auto"
                priority
              />
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden lg:flex items-center gap-0.5">
            {NAV_PRIMARY.map(item => {
              const hasSub = !!item.sub?.length;
              const menuOpen = openMenu === item.label;
              const activeHere = isActive(item.href) || (item.sub?.some(s => isActive(s.href)) ?? false);

              if (!hasSub) {
                return (
                  <Link
                    key={item.href}
                    href={item.href as any}
                    onClick={() => { trackNavClick(item.label); if (!isActive(item.href)) start(); }}
                    className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-all whitespace-nowrap ${
                      activeHere ? "bg-text-primary/10 text-text-primary" : "text-text-secondary hover:bg-text-primary/5 hover:text-text-primary"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              }

              return (
                <div key={item.label} className="relative">
                  <button
                    onClick={() => { trackNavClick(item.label); setOpenMenu(o => o === item.label ? null : item.label); }}
                    className={`flex items-center gap-1 rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-all whitespace-nowrap ${
                      menuOpen || activeHere ? "bg-text-primary/10 text-text-primary" : "text-text-secondary hover:bg-text-primary/5 hover:text-text-primary"
                    }`}
                  >
                    {item.label} <ChevronDown className={`h-3.5 w-3.5 transition-transform ${menuOpen ? "rotate-180" : ""}`} />
                  </button>
                  {menuOpen && (
                    <div className="absolute left-0 top-full mt-2 w-80 rounded-2xl border border-surface-border/10 bg-surface-card shadow-2xl p-2 z-50">
                      <Link
                        href={item.href as any}
                        onClick={() => { setOpenMenu(null); trackSubmenuClick(item.label, item.label); if (!isActive(item.href)) start(); }}
                        className="mb-1 flex items-center justify-between rounded-xl px-3 py-2 text-[12px] font-bold uppercase tracking-wide text-accent-violet hover:bg-violet-500/[0.06] transition"
                      >
                        {item.label} Home →
                      </Link>
                      {item.sub!.map(s => (
                        <Link
                          key={s.href}
                          href={s.href as any}
                          onClick={() => { setOpenMenu(null); trackSubmenuClick(item.label, s.label); if (!isActive(s.href)) start(); }}
                          className={`block w-full rounded-xl px-3 py-2.5 transition-all ${
                            isActive(s.href) ? "bg-text-primary/10" : "hover:bg-text-primary/[0.06]"
                          }`}
                        >
                          <span className="block text-[13px] font-semibold text-text-primary">{s.label}</span>
                          {s.blurb && <span className="block text-[11px] text-text-muted">{s.blurb}</span>}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>

          {/* Right side */}
          <div className="ml-auto flex items-center gap-2 shrink-0">
            {/* Nifty value */}
            {nifty && (
              <div className="hidden lg:flex items-center gap-2 rounded-xl border border-surface-border/6 bg-text-primary/[0.03] px-3 py-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">NIFTY</span>
                <span className="text-[13px] font-bold tabular-nums text-text-primary">{nifty.value}</span>
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
              onClick={() => { setOpenMenu(null); setSearch(s => !s); }}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-surface-border/8 bg-text-primary/[0.03] text-text-secondary transition hover:bg-text-primary/[0.07] hover:text-text-primary"
            >
              <Search className="h-4 w-4" />
            </button>

            {/* Watchlist */}
            <div className="relative">
              <button
                onClick={() => { setOpenMenu(null); setWatchlist(o => !o); }}
                className={`flex h-9 w-9 items-center justify-center rounded-full border transition ${
                  watchlistOpen
                    ? "border-violet-500/40 bg-violet-500/15 text-violet-400"
                    : "border-surface-border/8 bg-text-primary/[0.03] text-text-secondary hover:bg-text-primary/[0.07] hover:text-text-primary"
                }`}
                title="Watchlist"
              >
                <Bookmark className="h-4 w-4" fill={watchlistCount > 0 ? "currentColor" : "none"} />
              </button>
              {watchlistCount > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-violet-500 text-[8px] font-black text-text-primary">
                  {watchlistCount > 9 ? "9+" : watchlistCount}
                </span>
              )}
            </div>

            {/* Notifications */}
            <div className="relative">
              <button
                onClick={() => setOpenMenu(o => o === "notifications" ? null : "notifications")}
                aria-label="Notifications"
                className="flex h-9 w-9 items-center justify-center rounded-full border border-surface-border/8 bg-text-primary/[0.03] text-text-secondary transition hover:bg-text-primary/[0.07] hover:text-text-primary"
              >
                <Bell className="h-4 w-4" />
              </button>
              {alerts.length > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[8px] font-black text-text-primary">
                  {alerts.length > 9 ? "9+" : alerts.length}
                </span>
              )}
              {openMenu === "notifications" && (
                <div className="absolute right-0 top-full mt-2 w-80 max-w-[90vw] rounded-2xl border border-surface-border/10 bg-surface-card/98 backdrop-blur-xl shadow-2xl z-50 overflow-hidden">
                  <div className="flex items-center justify-between border-b border-surface-border/6 px-4 py-3">
                    <span className="text-[12px] font-bold text-text-primary">Notifications</span>
                    {alerts.length > 0 && (
                      <span className="text-[10px] font-semibold text-text-muted">{alerts.length} active</span>
                    )}
                  </div>
                  {alerts.length === 0 ? (
                    <p className="px-4 py-6 text-center text-[12px] text-text-muted">No active alerts right now.</p>
                  ) : (
                    <div className="max-h-96 overflow-y-auto">
                      {alerts.slice(0, 8).map(a => (
                        <div key={a.id} className="flex items-start gap-2.5 border-b border-surface-border/4 px-4 py-3 last:border-0 hover:bg-text-primary/[0.03]">
                          <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${a.urgency === "critical" ? "bg-rose-500" : "bg-amber-500"}`} />
                          <div className="min-w-0 flex-1">
                            <p className="text-[12px] font-semibold leading-snug text-text-primary line-clamp-2">{a.headline}</p>
                            <p className="mt-0.5 text-[10px] text-text-muted line-clamp-1">{a.summary}</p>
                          </div>
                          <button
                            onClick={() => dismiss(a.id)}
                            aria-label="Dismiss"
                            className="shrink-0 rounded-full p-1 text-text-muted hover:bg-text-primary/[0.06] hover:text-text-secondary transition"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <Link
                    href="/market-intelligence"
                    onClick={() => setOpenMenu(null)}
                    className="block border-t border-surface-border/6 px-4 py-2.5 text-center text-[11px] font-semibold text-violet-400 hover:text-violet-600 dark:text-violet-300 transition"
                  >
                    View Markets →
                  </Link>
                </div>
              )}
            </div>

            {/* Theme toggle */}
            <ThemeToggle />

            {/* Mobile menu toggle */}
            <button
              onClick={() => setMobile(o => !o)}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-surface-border/8 bg-text-primary/[0.03] text-text-secondary lg:hidden"
            >
              {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Search bar dropdown */}
        {searchOpen && (
          <div className="border-t border-surface-border/6 bg-bg/95 px-6 py-3">
            <form
              action="/search"
              method="get"
              onSubmit={(e) => {
                // Client-side navigate instead of letting the browser run
                // the native GET submit: setSearch(false) below unmounts
                // this form (it's behind {searchOpen && ...}) synchronously,
                // which was racing the in-flight native navigation and
                // canceling it before the destination page ever loaded.
                //
                // Real site search (/search — matches our own articles,
                // companies, sectors, themes), not the AI Q&A tool: that's
                // still reachable from /search's "no results" state via
                // "Ask MarketRipple AI instead" for open-ended questions.
                e.preventDefault();
                const q = query.trim();
                if (!q) return;
                setSearch(false);
                router.push(`/search?q=${encodeURIComponent(q)}`);
              }}
            >
              <div className="mx-auto flex max-w-2xl items-center gap-3 rounded-2xl border border-surface-border/10 bg-text-primary/[0.04] px-4 py-2.5 focus-within:border-violet-500/40">
                <Search className="h-4 w-4 shrink-0 text-text-muted" />
                <input
                  autoFocus
                  type="text"
                  name="q"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Search companies, sectors, themes, articles…"
                  className="flex-1 bg-transparent text-[14px] text-text-primary outline-none placeholder:text-text-muted"
                />
                <kbd className="hidden rounded-md border border-surface-border/8 bg-text-primary/[0.04] px-1.5 py-0.5 text-[10px] text-text-muted sm:block">⌘K</kbd>
              </div>
            </form>
          </div>
        )}
      </header>

      {/* Watchlist drawer */}
      <WatchlistDrawer open={watchlistOpen} onClose={() => setWatchlist(false)} />

      {/* Mobile nav drawer — accordion: tap a hub to expand its sub-items,
          instead of the old flat list with no grouping. */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobile(false)} />
          <nav className="absolute left-0 top-[68px] w-72 bg-surface-card border-r border-surface-border/8 h-[calc(100vh-68px)] p-4 flex flex-col gap-1 overflow-y-auto">
            {NAV_PRIMARY.map(item => {
              const hasSub = !!item.sub?.length;
              const expanded = mobileExpanded === item.label;
              return (
                <div key={item.label}>
                  <div className="flex items-center">
                    <Link
                      href={item.href as any}
                      onClick={() => { setMobile(false); trackNavClick(item.label); if (!isActive(item.href)) start(); }}
                      className={`flex-1 rounded-xl px-4 py-3 text-[14px] font-medium transition ${
                        isActive(item.href) ? "bg-text-primary/10 text-text-primary" : "text-text-secondary hover:bg-text-primary/5 hover:text-text-primary"
                      }`}
                    >
                      {item.label}
                    </Link>
                    {hasSub && (
                      <button
                        onClick={() => setMobileExpanded(e => e === item.label ? null : item.label)}
                        aria-label={`Toggle ${item.label} submenu`}
                        className="shrink-0 rounded-xl p-3 text-text-muted"
                      >
                        <ChevronDown className={`h-4 w-4 transition-transform ${expanded ? "rotate-180" : ""}`} />
                      </button>
                    )}
                  </div>
                  {hasSub && expanded && (
                    <div className="ml-3 flex flex-col gap-0.5 border-l border-surface-border/8 pl-3">
                      {item.sub!.map(s => (
                        <Link
                          key={s.href}
                          href={s.href as any}
                          onClick={() => { setMobile(false); trackSubmenuClick(item.label, s.label); if (!isActive(s.href)) start(); }}
                          className={`rounded-lg px-3 py-2 text-[13px] transition ${
                            isActive(s.href) ? "bg-text-primary/10 text-text-primary" : "text-text-secondary hover:bg-text-primary/5"
                          }`}
                        >
                          {s.label}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>
        </div>
      )}
    </>
  );
}
