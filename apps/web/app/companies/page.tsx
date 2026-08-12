import type { Metadata } from "next";
import { fetchAPI } from "@/lib/api";
import { CompaniesHubClient } from "./_components/CompaniesHubClient";
import { OverviewTab } from "./_components/OverviewTab";
import { AllCompaniesTab } from "./_components/AllCompaniesTab";
import BestStocksHubPage from "@/app/best-stocks/page";
import SectorsPage from "@/app/sectors/page";
import ComparePage from "@/app/compare/page";
import IPOHubPage from "@/app/ipo-hub/page";

const TITLE = "Companies — NSE Listed Companies & AI Rankings";
// Trimmed from 171 to within the ~160-char guideline (was truncating with
// an ellipsis mid-word in real search-result previews).
const DESCRIPTION =
  "Find India's best companies using AI — search the full NSE universe, AI-ranked Best Stocks, sector breakdowns, and side-by-side comparison, all in one place.";
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // The tab switcher (?tab=) keeps every variant on one canonical URL —
  // without this, /companies?tab=sectors etc. had no signal telling
  // crawlers it's the same page as /companies, not separate content.
  alternates: { canonical: `${SITE_URL}/companies` },
  openGraph: {
    type: "website",
    title: TITLE,
    description: DESCRIPTION,
    url: `${SITE_URL}/companies`,
    siteName: "MarketRipple",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
};
export const dynamic = "force-dynamic";

const VALID_TABS = new Set(["overview", "all-companies", "best-stocks", "sectors", "compare", "ipo-hub"]);

export default async function CompaniesHubPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const rawTab = typeof params.tab === "string" ? params.tab : "overview";
  const tab    = VALID_TABS.has(rawTab) ? rawTab : "overview";

  const q      = typeof params.q      === "string" ? params.q      : "";
  const sector = typeof params.sector === "string" ? params.sector : "";
  const cap    = typeof params.cap    === "string" ? params.cap    : "";
  const sort   = typeof params.sort   === "string" ? params.sort   : "name";
  const page   = typeof params.page   === "string" ? Math.max(1, parseInt(params.page, 10) || 1) : 1;

  // Real numbers only — no "5,000+" placeholder. Article total comes from
  // the same /api/insights/ endpoint the rest of the app already uses.
  // Companies/sectors used to read a static local copy of the universe
  // (lib/companies-data.ts) that had silently drifted to 194 companies vs.
  // the backend's real 512 — now reads the same live source everything
  // else in this hub does.
  const [articlesTotal, companiesTotal, sectorsCount] = await Promise.all([
    fetchAPI<{ total: number }>("/api/insights/?limit=1").then(d => d.total).catch(() => null),
    fetchAPI<{ total: number }>("/api/companies/?page_size=6").then(d => d.total).catch(() => null),
    fetchAPI<{ sectors: string[] }>("/api/companies/sectors").then(d => d.sectors.length).catch(() => null),
  ]);

  const stats = [
    ...(companiesTotal != null ? [{ label: "Companies", value: companiesTotal.toLocaleString() }] : []),
    ...(sectorsCount != null ? [{ label: "Sectors", value: String(sectorsCount) }] : []),
    ...(articlesTotal != null ? [{ label: "AI Articles", value: articlesTotal.toLocaleString() }] : []),
    { label: "Prices",     value: "Live" },
  ];

  let content: React.ReactNode;
  switch (tab) {
    case "all-companies": content = <AllCompaniesTab q={q} sector={sector} cap={cap} sort={sort} page={page} />; break;
    case "best-stocks":   content = <BestStocksHubPage />; break;
    case "sectors":       content = <SectorsPage />; break;
    case "compare":       content = <ComparePage />; break;
    case "ipo-hub":       content = <IPOHubPage />; break;
    default:              content = <OverviewTab />;
  }

  return (
    <CompaniesHubClient activeTab={tab} stats={stats}>
      {content}
    </CompaniesHubClient>
  );
}
