import type { Metadata } from "next";
import { fetchAPI } from "@/lib/api";
import { CompaniesHubClient } from "./_components/CompaniesHubClient";
import { OverviewTab } from "./_components/OverviewTab";
import { AllCompaniesTab } from "./_components/AllCompaniesTab";
import { BestStocksContent } from "@/app/best-stocks/BestStocksContent";
import { SectorsContent } from "@/app/sectors/SectorsContent";
import { CompareContent } from "@/app/compare/CompareContent";
import { IPOHubContent } from "@/app/ipo-hub/IPOHubContent";

export const metadata: Metadata = {
  title: "Companies — NSE Listed Companies & AI Rankings",
  description:
    "Find India's best companies using AI — search the full NSE universe, AI-ranked Best Stocks, sector breakdowns, side-by-side comparison, and IPO tracking, all in one place.",
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
    case "best-stocks":   content = <BestStocksContent headingLevel="h2" />; break;
    case "sectors":       content = <SectorsContent headingLevel="h2" />; break;
    case "compare":       content = <CompareContent headingLevel="h2" />; break;
    case "ipo-hub":       content = <IPOHubContent headingLevel="h2" />; break;
    default:              content = <OverviewTab />;
  }

  return (
    <CompaniesHubClient activeTab={tab} stats={stats}>
      {content}
    </CompaniesHubClient>
  );
}
