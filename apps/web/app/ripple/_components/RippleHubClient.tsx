"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { GitBranch, Target } from "lucide-react";
import { HubHero, type HubStat } from "@/components/HubHero";
import { HubTabBar, type HubTab } from "@/components/HubTabBar";
import { useDelayedPending } from "@/hooks/useDelayedPending";

// Historical Patterns / Winners / Losers tabs removed (2026-08 audit, per
// explicit request) — that content is already shown in full on the
// dedicated /historical page; duplicating it here as three more tabs was
// the same content twice, not a distinct view.
const TABS: HubTab[] = [
  { id: "chain",  label: "Ripple Chain",      icon: <GitBranch className="h-3.5 w-3.5" /> },
  { id: "thesis", label: "Investment Thesis", icon: <Target className="h-3.5 w-3.5" /> },
];

export function RippleHubClient({
  activeTab, stats, children,
}: {
  activeTab: string;
  stats: HubStat[];
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const showLoading = useDelayedPending(isPending);

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
        <HubTabBar hub="Ripple Intelligence" tabs={TABS} active={activeTab} pending={showLoading}
          onChange={(id) => startTransition(() => router.push(`/ripple?tab=${id}`))} />
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
