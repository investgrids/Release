"use client";

import dynamic from "next/dynamic";
import { useEffect } from "react";

interface GraphData { nodes: unknown[]; edges: unknown[] }

const IntelligenceGraph = dynamic(
  () => import("@/components/IntelligenceGraph").then(m => m.IntelligenceGraph),
  {
    ssr: false,
    loading: () => (
      <div style={{
        height: "calc(100vh - 68px)", background: "#050a18",
        display: "flex", alignItems: "center", justifyContent: "center",
        flexDirection: "column", gap: 20,
      }}>
        <svg width="48" height="48" viewBox="0 0 48 48">
          <circle cx="24" cy="24" r="20" fill="none" stroke="rgba(139,92,246,.15)" strokeWidth="2"/>
          <circle cx="24" cy="24" r="12" fill="none" stroke="rgba(139,92,246,.3)" strokeWidth="1.5"/>
          <circle cx="24" cy="24" r="4" fill="rgba(139,92,246,.8)"/>
          <circle cx="24" cy="4" r="2.5" fill="#a78bfa" opacity="0.9"
            style={{ transformOrigin: "24px 24px", animation: "spin .9s linear infinite" }}/>
        </svg>
        <p style={{ fontSize: 13, color: "#475569", fontWeight: 600, margin: 0 }}>
          Loading Intelligence Map…
        </p>
        <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
      </div>
    ),
  }
);

export function GraphCanvas({ initialGraph }: { initialGraph: GraphData | null }) {
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  return <IntelligenceGraph initialGraph={initialGraph as any} />;
}
