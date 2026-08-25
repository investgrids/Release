"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { safeJsonLd } from "@/lib/text";

export interface Crumb {
  label: string;
  href?: string; // omit on the final/current crumb
}

// The root layout renders one global <Breadcrumbs/> above every page's
// {children} (see layout.tsx) — a page nested underneath has no direct way
// to hand it real, server-fetched title data (a company name, an event
// headline) instead of the humanized-raw-slug fallback. This context is
// that channel: a page calls useBreadcrumbOverride() with its real crumbs
// once its data loads, and the root Breadcrumbs reads it instead of
// re-deriving from the URL. Client-side only (fixes the post-hydration DOM
// real users and JS-executing crawlers see; the very first static HTML
// still briefly shows the humanized fallback, same tradeoff every other
// client-fetched personalization in this app already makes).
const BreadcrumbOverrideContext = createContext<{
  override: Crumb[] | null;
  setOverride: (items: Crumb[] | null) => void;
} | null>(null);

export function BreadcrumbOverrideProvider({ children }: { children: ReactNode }) {
  const [override, setOverride] = useState<Crumb[] | null>(null);
  // Found live (React error #185, "Maximum update depth exceeded" on
  // /events and /events/[id]): value={{ override, setOverride }} without
  // memoization creates a brand-new object on every render of this
  // provider — which is every render triggered by setOverride itself.
  // useBreadcrumbOverride's effect has `ctx` in its dependency array, so a
  // new ctx reference re-fires that effect, which calls setOverride again,
  // which re-renders this provider, which creates a new ctx — infinite
  // loop. Memoizing on `override` (the only thing that should ever change
  // this value) keeps ctx referentially stable across unrelated re-renders.
  const value = useMemo(() => ({ override, setOverride }), [override]);
  return (
    <BreadcrumbOverrideContext.Provider value={value}>
      {children}
    </BreadcrumbOverrideContext.Provider>
  );
}

// Call with the real crumb trail once a page's own data has loaded (or
// `null` while it's still loading/unavailable, to fall back to the
// auto-derived one rather than show nothing). Clears itself on unmount so
// navigating to a different page never leaks a stale override forward.
export function useBreadcrumbOverride(items: Crumb[] | null) {
  const ctx = useContext(BreadcrumbOverrideContext);
  const key = items ? JSON.stringify(items) : null;
  useEffect(() => {
    if (!ctx) return;
    ctx.setOverride(items);
    return () => ctx.setOverride(null);
    // `ctx` deliberately NOT a dependency, even after memoizing the
    // provider's value (previous fix, still needed on its own merits) —
    // items is a fresh array literal on every caller render, so
    // setOverride(items) always receives a new reference regardless of
    // content, which changes `override` state, which changes `ctx` (even
    // memoized, `override` genuinely changed), which — if `ctx` were a
    // dependency here — re-fires this effect with the SAME content,
    // calling setOverride again with yet another new reference: an
    // infinite loop (confirmed live, React error #185 on every /events
    // and /events/[id] page load). Re-firing only needs to be gated on
    // `key`, the actual content fingerprint — ctx.setOverride itself is
    // already a stable function reference from useState, safe to call
    // without being a listed dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}

// Drop-in for a SERVER page/component that already has the real title at
// render time (it doesn't need useEffect's client-only timing at all) but
// can't call a hook itself without becoming a client component. Renders
// nothing — just registers the override via the client boundary this
// component itself crosses.
export function BreadcrumbSetter({ items }: { items: Crumb[] }) {
  useBreadcrumbOverride(items);
  return null;
}

// Static segment → display label for every route this maps into a hub/tab.
// Dynamic segments ([slug], [id], [symbol], [sector], [term]) have no entry
// here on purpose — pages with a real human-readable title for that segment
// (a company name, an article headline) should pass `items` explicitly
// instead of relying on the humanized-slug fallback below.
const SEGMENT_LABEL: Record<string, string> = {
  "market-intelligence": "Markets",
  markets: "Markets",
  commodities: "Commodities",
  calendar: "Economic Calendar",
  sectors: "Sectors",
  events: "Events",
  newsroom: "Insights",
  themes: "Market Themes",
  "daily-brief": "Daily Brief",
  breaking: "Breaking Intelligence",
  library: "Library",
  companies: "Companies",
  "best-stocks": "Best Stocks",
  compare: "Compare",
  "ipo-hub": "IPO Hub",
  ripple: "Ripple Intelligence",
  historical: "Historical Patterns",
  "opportunity-radar": "Opportunity Radar",
  "ai-search": "AI Search",
  learn: "Knowledge Library",
  glossary: "Glossary",
  guides: "Learning Center",
  articles: "Articles",
  research: "Research",
  article: "Article",
};

function humanize(segment: string): string {
  return segment
    .replace(/-/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
}

// Segments that are real, meaningful crumb LABELS but not real, standalone
// PAGES — pure URL namespacing for a dynamic route (e.g. "article" in
// /newsroom/article/[slug]; the article's own real page is the full path
// with the slug, not /newsroom/article on its own). Every other non-final
// segment gets a real link because it corresponds to a real hub/index page
// (e.g. "newsroom" -> /newsroom, a real page). Confirmed live: /newsroom/
// article 404s — a crawler flagged the resulting link as "non-descriptive
// anchor text", but the deeper issue is the href itself points nowhere.
const NON_LINKABLE_SEGMENTS = new Set(["article", "intel"]);

function autoCrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: Crumb[] = [];
  let hrefSoFar = "";
  segments.forEach((seg, i) => {
    hrefSoFar += `/${seg}`;
    const isLast = i === segments.length - 1;
    const label = SEGMENT_LABEL[seg] ?? humanize(decodeURIComponent(seg));
    const linkable = !isLast && !NON_LINKABLE_SEGMENTS.has(seg);
    crumbs.push({ label, href: linkable ? hrefSoFar : undefined });
  });
  return crumbs;
}

export function Breadcrumbs({ items, siteUrl }: { items?: Crumb[]; siteUrl?: string }) {
  const pathname = usePathname();
  // Hooks must run unconditionally, before the early-return below.
  const overrideCtx = useContext(BreadcrumbOverrideContext);
  if (!pathname || pathname === "/") return null;

  const crumbs = items ?? overrideCtx?.override ?? autoCrumbs(pathname);
  if (crumbs.length === 0) return null;

  // NEXT_PUBLIC_ vars are inlined at build time — identical on server and
  // client, unlike window.location.origin (which differs from the SSR
  // fallback in dev, causing a hydration mismatch on the JSON-LD string).
  const base = siteUrl ?? process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: base },
      ...crumbs.map((c, i) => ({
        "@type": "ListItem",
        position: i + 2,
        name: c.label,
        ...(c.href ? { item: `${base}${c.href}` } : {}),
      })),
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        // SEO P1-P2, 2026-08-24 — was JSON.stringify with a comment claiming
        // "static JSON, no user-supplied HTML", which is wrong for the
        // override path: `items`/the context override can carry a real
        // company name or article headline (external, not static). This
        // component runs on every page via the root layout, so it's the
        // highest-leverage single fix for the same escaping gap already
        // closed on article/signal/research/opportunity-radar pages.
        // eslint-disable-next-line react/no-danger -- escaped via safeJsonLd below
        dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }}
      />
      <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1.5 text-[12.5px] text-text-muted overflow-x-auto whitespace-nowrap">
        <Link href="/" className="flex items-center gap-1 hover:text-text-secondary transition shrink-0">
          <Home className="h-3 w-3" />
        </Link>
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center gap-1.5 shrink-0">
            <ChevronRight className="h-3 w-3 text-text-muted/60" />
            {c.href ? (
              <Link href={c.href as any} className="hover:text-text-secondary transition">{c.label}</Link>
            ) : (
              <span className="text-text-secondary font-medium">{c.label}</span>
            )}
          </span>
        ))}
      </nav>
    </>
  );
}
