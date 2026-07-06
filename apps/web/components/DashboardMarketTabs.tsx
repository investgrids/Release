"use client";

import { useState } from "react";
import Link from "next/link";
import { PreMarketTab }  from "@/components/market/tabs/PreMarketTab";
import { LiveMarketTab } from "@/components/market/tabs/LiveMarketTab";
import { AfterMarketTab } from "@/components/market/tabs/AfterMarketTab";

type TabId = "pre-market" | "live" | "after-market";

const TABS: { id: TabId; label: string; marketHours: string }[] = [
  { id: "pre-market",   label: "Pre-Market",  marketHours: "Before 9:15 AM"     },
  { id: "live",         label: "Live Market", marketHours: "9:15 AM – 3:30 PM"  },
  { id: "after-market", label: "After Market",marketHours: "After 3:30 PM"      },
];

function getDefaultTab(): TabId {
  const ist  = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const mins = ist.getHours() * 60 + ist.getMinutes();
  if (mins < 9 * 60 + 15)   return "pre-market";
  if (mins <= 15 * 60 + 30) return "live";
  return "after-market";
}

export function DashboardMarketTabs() {
  const [activeTab, setActiveTab] = useState<TabId>(getDefaultTab);

  return (
    <div className="rounded-[28px] border border-white/[0.06] bg-white/[0.02] p-5">

      {/* ── Header: tab strip (left) + View Full link (right) ──────────────── */}
      <div className="mb-5 flex items-start justify-between gap-4">

        <div className="flex flex-col gap-1.5">
          {/* Tab strip */}
          <div className="inline-flex gap-1 rounded-full border border-white/10 bg-slate-900/50 p-1">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={[
                  "rounded-full px-3 py-1.5 text-[12px] transition",
                  activeTab === tab.id
                    ? "border border-indigo-500/30 bg-indigo-600/20 font-medium text-white"
                    : "border border-transparent text-slate-400 hover:text-white",
                ].join(" ")}
              >
                {tab.label}
              </button>
            ))}
          </div>
          {/* Subtext */}
          <p className="text-[10px] text-slate-600">NSE Opens 9:15 AM IST</p>
        </div>

        <Link
          href={`/market-intelligence?tab=${activeTab}`}
          className="shrink-0 text-[11px] font-medium text-sky-400 transition hover:text-sky-300"
        >
          View Full →
        </Link>
      </div>

      {/* ── Tab content ──────────────────────────────────────────────────────── */}
      {activeTab === "pre-market"   && <PreMarketTab />}
      {activeTab === "live"         && <LiveMarketTab />}
      {activeTab === "after-market" && <AfterMarketTab />}

    </div>
  );
}
