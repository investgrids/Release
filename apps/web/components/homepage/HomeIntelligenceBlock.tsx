"use client";

import { useIntelligence } from "@/hooks/useIntelligence";
import { IntelligenceBlock } from "@/components/intelligence/IntelligenceBlock";

export function HomeIntelligenceBlock() {
  const { data, loading } = useIntelligence("home");

  if (loading) {
    return (
      <div className="space-y-2">
        <div className="h-14 animate-pulse rounded-2xl bg-white/[0.03]" />
      </div>
    );
  }

  if (!data || !data.market_story) return null;

  return (
    <IntelligenceBlock
      data={data}
      label="Market Intelligence"
      compact={false}
    />
  );
}
