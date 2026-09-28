"use client";

// Single reusable tab bar for hub pages (Markets, Companies, Ripple
// Intelligence, Opportunity Radar) — extracted from the pattern that was
// independently hand-rolled 3 times already (MarketClient.tsx,
// compare/page.tsx, ipo-hub/page.tsx). Presentational only: the hub page
// owns the active-tab state and tab content, this just renders the bar and
// reports clicks.

import { trackTabSwitch } from "@/lib/navAnalytics";

export interface HubTab {
  id: string;
  label: string;
  icon?: React.ReactNode;
}

export function HubTabBar({
  hub, tabs, active, onChange,
}: {
  hub: string;
  tabs: HubTab[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label={`${hub} sections`}
      className="flex flex-wrap gap-1 rounded-xl border border-surface-border/8 bg-text-primary/[0.02] p-1"
    >
      {tabs.map(tab => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => {
              if (!isActive) trackTabSwitch(hub, tab.id);
              onChange(tab.id);
            }}
            className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[12.5px] font-semibold transition whitespace-nowrap ${
              isActive
                ? "bg-accent-violet text-white shadow-sm"
                : "text-text-secondary hover:bg-text-primary/[0.04] hover:text-text-primary"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
