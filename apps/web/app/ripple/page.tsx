import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";
import { RippleHubClient } from "./_components/RippleHubClient";
import { RippleChainTab } from "./_components/RippleChainTab";
import { InvestmentThesisTab } from "./_components/InvestmentThesisTab";

export const metadata: Metadata = {
  title: "Ripple Intelligence — Market Dependency Graph",
  description: "See how one event creates opportunities — trace cascading effects across sectors and companies, validated against real historical precedent.",
};
export const dynamic = "force-dynamic";

// historical/winners/losers removed (2026-08 audit, per explicit request)
// — same content already shown in full on the dedicated /historical page.
const VALID_TABS = new Set(["chain", "thesis"]);

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
    case "thesis": content = <InvestmentThesisTab />; break;
    default:       content = <RippleChainTab />;
  }

  return (
    <RippleHubClient activeTab={tab} stats={stats}>
      {content}
    </RippleHubClient>
  );
}
