import Link from "next/link";
import Image from "next/image";

const COMPANY_LINKS = [
  { label: "About MarketRipple",       href: "/about" },
  { label: "Why MarketRipple",         href: "/why-marketripple" },
  { label: "How MarketRipple Works",   href: "/how-it-works" },
  { label: "How MarketRipple Thinks",  href: "/how-marketripple-thinks" },
  { label: "AI & Methodology",    href: "/ai-methodology" },
  { label: "Data Sources",        href: "/data-sources" },
  { label: "FAQ",                 href: "/faq" },
  { label: "What's New",          href: "/whats-new" },
  { label: "Contact Us",          href: "/contact" },
  { label: "Privacy Policy",      href: "/legal#privacy" },
  { label: "Terms of Service",    href: "/legal#terms" },
  { label: "Disclaimer",          href: "/legal#disclaimer" },
];

// "Market Intelligence" used to link to "/" (a bug — it's the homepage,
// not the dashboard); fixed to the real Markets hub. "Stories" removed —
// it's folded into Insights (AI Newsroom) as of the nav refactor, no
// longer a separate product, so no separate footer link for it either.
const PRODUCT_LINKS = [
  { label: "Markets",             href: "/market-intelligence" },
  { label: "Events",              href: "/events" },
  { label: "Companies",           href: "/companies" },
  { label: "Opportunity Radar",   href: "/opportunity-radar" },
  { label: "Best Stocks",         href: "/best-stocks" },
  { label: "Ripple Intelligence", href: "/ripple" },
  { label: "AI Search",           href: "/ai-search" },
  { label: "Historical Patterns", href: "/historical" },
  { label: "Commodities",         href: "/commodities" },
  { label: "Tools",                href: "/tools" },
];

// New group, moved out of primary header nav — real, existing pages (all
// confirmed live under app/learn/), good for SEO long-tail search terms.
const RESOURCES_LINKS = [
  { label: "Knowledge Library", href: "/learn" },
  { label: "Glossary",          href: "/learn/glossary" },
  { label: "Learning Center",   href: "/learn/guides" },
];

export function Footer() {
  return (
    <footer
      className="border-t border-surface-border/6 bg-surface-header mt-4"
      aria-label="Site footer"
    >
      <div className="mx-auto max-w-[1600px] px-6 py-10">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-5">

          {/* Brand */}
          <div className="col-span-full lg:col-span-1">
            <Link href="/" className="mb-4 inline-block" aria-label="MarketRipple home">
              <Image
                src="/marketripple-logo.png"
                alt="MarketRipple"
                width={2583}
                height={780}
                className="theme-light-only h-8 w-auto"
              />
              <Image
                src="/marketripple-logo-dark.png"
                alt="MarketRipple"
                width={2583}
                height={780}
                className="theme-dark-only h-8 w-auto"
              />
            </Link>
            <p className="text-[12px] text-text-secondary leading-5 max-w-[220px]">
              AI-powered market intelligence. Understand not just what happened — but why, who's affected, and what comes next.
            </p>
            <p className="mt-4 text-[10px] text-text-muted leading-4">
              For research and educational purposes only. Not investment advice.
            </p>
          </div>

          {/* Product */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted mb-3">
              Product
            </p>
            <ul className="space-y-2" role="list">
              {PRODUCT_LINKS.map(link => (
                <li key={link.href}>
                  <Link
                    href={link.href as any}
                    className="text-[12px] text-text-secondary hover:text-text-primary transition"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted mb-3">
              Resources
            </p>
            <ul className="space-y-2" role="list">
              {RESOURCES_LINKS.map(link => (
                <li key={link.href}>
                  <Link
                    href={link.href as any}
                    className="text-[12px] text-text-secondary hover:text-text-primary transition"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Company — split into two columns on wider screens */}
          <div className="col-span-full sm:col-span-2 lg:col-span-2">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted mb-3">
              Company
            </p>
            <ul className="grid grid-cols-2 gap-x-6 gap-y-2" role="list">
              {COMPANY_LINKS.map(link => (
                <li key={link.href}>
                  <Link
                    href={link.href as any}
                    className="text-[12px] text-text-secondary hover:text-text-primary transition"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-8 flex flex-col gap-3 border-t border-surface-border/6 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-[11px] text-text-muted">
            © {new Date().getFullYear()} MarketRipple. All rights reserved.
          </p>
          <p className="text-[11px] text-text-muted max-w-md text-left sm:text-right">
            MarketRipple provides market intelligence for research and educational purposes.
            It is not a registered investment advisor. Users remain responsible for all investment decisions.
          </p>
        </div>
      </div>
    </footer>
  );
}
