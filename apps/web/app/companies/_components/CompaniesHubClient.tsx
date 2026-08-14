"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Building2, TrendingUp, GitCompare, Rocket, LayoutGrid, LayoutDashboard } from "lucide-react";
import { HubHero, type HubStat } from "@/components/HubHero";
import { HubTabBar, type HubTab } from "@/components/HubTabBar";
import { useDelayedPending } from "@/hooks/useDelayedPending";

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
  { id: "ipo",           label: "IPO Hub",        icon: <Rocket className="h-3.5 w-3.5" /> },
];

export function CompaniesHubClient({
  activeTab, stats, children,
}: {
  activeTab: string;
  stats: HubStat[];
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  // Tab switches are a real server round-trip (force-dynamic, each tab
  // fetches its own data) with no feedback otherwise — but flashing a
  // spinner for every fast switch would be worse than nothing, so this
  // only shows once a switch has actually been slow (see useDelayedPending).
  const showLoading = useDelayedPending(isPending);
  const navigate = (href: string) => startTransition(() => router.push(href));

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
          navigate(`/companies?tab=all-companies&q=${encodeURIComponent(q)}`);
        }}
      />
      <div className="mb-5">
        <HubTabBar hub="Companies" tabs={TABS} active={activeTab} pending={showLoading} onChange={(id) => navigate(`/companies?tab=${id}`)} />
      </div>
      <div className="relative">
        {showLoading && (
          <div className="absolute inset-0 z-10 flex items-start justify-center bg-bg/60 pt-20 backdrop-blur-[1px]">
            <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-violet-400 border-t-transparent" />
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
