"use client";

import { useRouter } from "next/navigation";
import { GitBranch, History, TrendingUp, TrendingDown, Target } from "lucide-react";
import { HubHero, type HubStat } from "@/components/HubHero";
import { HubTabBar, type HubTab } from "@/components/HubTabBar";

// Kept as 5 dedicated tabs, not collapsed into sections — this is the
// product's own stated flagship differentiator, and the reasoning flow
// (ripple effect → has this happened before → winners → losers →
// investment thesis) reads as a connected argument this way.
const TABS: HubTab[] = [
  { id: "chain",      label: "Ripple Chain",         icon: <GitBranch className="h-3.5 w-3.5" /> },
  { id: "historical", label: "Historical Patterns",  icon: <History className="h-3.5 w-3.5" /> },
  { id: "winners",    label: "Historical Winners",   icon: <TrendingUp className="h-3.5 w-3.5" /> },
  { id: "losers",     label: "Historical Losers",    icon: <TrendingDown className="h-3.5 w-3.5" /> },
  { id: "thesis",     label: "Investment Thesis",    icon: <Target className="h-3.5 w-3.5" /> },
];

export function RippleHubClient({
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
        hub="Ripple Intelligence"
        eyebrow="Market Dependency Graph"
        title="See how one event creates opportunities"
        pitch="Trace an event's cascading effects, validate the chain against real historical precedent, and arrive at an investment thesis — not just data, an argument."
        stats={stats}
      />
      <div className="mb-5">
        <HubTabBar hub="Ripple Intelligence" tabs={TABS} active={activeTab} onChange={(id) => router.push(`/ripple?tab=${id}`)} />
      </div>
      {children}
    </div>
  );
}
