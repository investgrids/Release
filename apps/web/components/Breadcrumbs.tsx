"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";

export interface Crumb {
  label: string;
  href?: string; // omit on the final/current crumb
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

function autoCrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: Crumb[] = [];
  let hrefSoFar = "";
  segments.forEach((seg, i) => {
    hrefSoFar += `/${seg}`;
    const isLast = i === segments.length - 1;
    const label = SEGMENT_LABEL[seg] ?? humanize(decodeURIComponent(seg));
    crumbs.push({ label, href: isLast ? undefined : hrefSoFar });
  });
  return crumbs;
}

export function Breadcrumbs({ items, siteUrl }: { items?: Crumb[]; siteUrl?: string }) {
  const pathname = usePathname();
  if (!pathname || pathname === "/") return null;

  const crumbs = items ?? autoCrumbs(pathname);
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
        // eslint-disable-next-line react/no-danger -- static JSON, no user-supplied HTML
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
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
