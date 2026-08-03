import type { Metadata } from "next";
import { COMPANIES, ALL_SECTORS } from "@/lib/companies-data";
import { fetchAPI } from "@/lib/api";
import { CompaniesHubClient } from "./_components/CompaniesHubClient";
import { OverviewTab } from "./_components/OverviewTab";
import { AllCompaniesTab } from "./_components/AllCompaniesTab";
import BestStocksHubPage from "@/app/best-stocks/page";
import SectorsPage from "@/app/sectors/page";
import ComparePage from "@/app/compare/page";
import IPOHubPage from "@/app/ipo-hub/page";

export const metadata: Metadata = {
  title: "Companies — NSE Listed Companies & AI Rankings | MarketRipple",
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
  const articlesTotal = await fetchAPI<{ total: number }>("/api/insights/?limit=1").then(d => d.total).catch(() => null);

  const stats = [
    { label: "Companies",  value: COMPANIES.length.toLocaleString() },
    { label: "Sectors",    value: String(ALL_SECTORS.length) },
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
