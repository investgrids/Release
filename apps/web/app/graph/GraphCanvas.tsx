"use client";

import dynamic from "next/dynamic";

interface GraphData { nodes: unknown[]; edges: unknown[] }

const IntelligenceGraph = dynamic(
  () => import("@/components/IntelligenceGraph").then((m) => m.IntelligenceGraph),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
          <p className="text-[13px] text-slate-500">Loading graph…</p>
        </div>
      </div>
    ),
  }
);

export function GraphCanvas({ initialGraph }: { initialGraph: GraphData | null }) {
  return <IntelligenceGraph initialGraph={initialGraph as any} />;
}
