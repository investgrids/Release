"use client";

import { useRouter } from "next/navigation";
import { Building2, TrendingUp, GitCompare, Rocket, LayoutGrid, LayoutDashboard } from "lucide-react";
import { HubHero, type HubStat } from "@/components/HubHero";
import { HubTabBar, type HubTab } from "@/components/HubTabBar";

// Tabs are server-driven via ?tab= (not local useState) — "All Companies"
// needs real URL-shareable filters (?sector=&cap=&sort=&q=&page=), so the
// whole hub stays server-rendered per tab rather than mixing a client tab
// switch with server-only tab content. HubTabBar itself doesn't care which
// pattern a hub uses — this one just navigates on change.
const TABS: HubTab[] = [
  { id: "overview",      label: "Overview",       icon: <LayoutDashboard className="h-3.5 w-3.5" /> },
  { id: "all-companies", label: "All Companies",  icon: <Building2 className="h-3.5 w-3.5" /> },
  { id: "best-stocks",   label: "Best Stocks",    icon: <TrendingUp className="h-3.5 w-3.5" /> },
  { id: "sectors",       label: "Sectors",        icon: <LayoutGrid className="h-3.5 w-3.5" /> },
  { id: "compare",       label: "Company Compare",icon: <GitCompare className="h-3.5 w-3.5" /> },
  { id: "ipo-hub",       label: "IPO Hub",        icon: <Rocket className="h-3.5 w-3.5" /> },
];

export function CompaniesHubClient({
  activeTab, stats, children,
}: {
  activeTab: string;
  stats: HubStat[];
  children: React.ReactNode;
}) {
  const router = useRouter();

  return (
    <div className="pb-16">
      <HubHero
        hub="Companies"
        eyebrow="Company Research"
        title="Find India's best companies using AI"
        pitch="Discover the best investment opportunities with AI-powered company intelligence — ranked, compared, and explained."
        stats={stats}
        searchPlaceholder="Search companies, tickers, sectors…"
        onSearch={(q) => {
          if (!q.trim()) return;
          router.push(`/companies?tab=all-companies&q=${encodeURIComponent(q)}`);
        }}
      />
      <div className="mb-5">
        <HubTabBar hub="Companies" tabs={TABS} active={activeTab} onChange={(id) => router.push(`/companies?tab=${id}`)} />
      </div>
      {children}
    </div>
  );
}
