import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";
import { RippleHubClient } from "./_components/RippleHubClient";
import { RippleChainTab } from "./_components/RippleChainTab";
import { HistoricalWinnersTab } from "./_components/HistoricalWinnersTab";
import { HistoricalLosersTab } from "./_components/HistoricalLosersTab";
import { InvestmentThesisTab } from "./_components/InvestmentThesisTab";
import HistoricalHubPage from "@/app/historical/page";

export const metadata: Metadata = {
  title: "Ripple Intelligence — Market Dependency Graph",
  description: "See how one event creates opportunities — trace cascading effects across sectors and companies, validate against real historical precedent, and arrive at an investment thesis.",
};
export const dynamic = "force-dynamic";

const VALID_TABS = new Set(["chain", "historical", "winners", "losers", "thesis"]);

async function getRealCounts() {
  const [rippleRes, historicalRes] = await Promise.all([
    fetch(`${API}/api/ripple/featured?limit=50`, { next: { revalidate: 900 } }).catch(() => null),
    fetch(`${API}/api/historical/all?limit=200`, { next: { revalidate: 3600 } }).catch(() => null),
  ]);
  const rippleCount     = rippleRes && rippleRes.ok ? (await rippleRes.json()).length ?? 0 : null;
  const historicalCount = historicalRes && historicalRes.ok ? ((await historicalRes.json()).events ?? []).length : null;
  return { rippleCount, historicalCount };
}

export default async function RippleHubPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const rawTab = typeof params.tab === "string" ? params.tab : "chain";
  const tab    = VALID_TABS.has(rawTab) ? rawTab : "chain";

  const { rippleCount, historicalCount } = await getRealCounts();
  const stats = [
    ...(rippleCount != null ? [{ label: "Traced Events", value: String(rippleCount) }] : []),
    ...(historicalCount != null ? [{ label: "Historical Patterns", value: String(historicalCount) }] : []),
    { label: "Coverage", value: "Live" },
  ];

  let content: React.ReactNode;
  switch (tab) {
    case "historical": content = <HistoricalHubPage />; break;
    case "winners":     content = <HistoricalWinnersTab />; break;
    case "losers":      content = <HistoricalLosersTab />; break;
    case "thesis":      content = <InvestmentThesisTab />; break;
    default:            content = <RippleChainTab />;
  }

  return (
    <RippleHubClient activeTab={tab} stats={stats}>
      {content}
    </RippleHubClient>
  );
}
