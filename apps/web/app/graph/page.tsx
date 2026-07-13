import { Metadata } from "next";
import { GraphCanvas } from "./GraphCanvas";

export const metadata: Metadata = {
  title: "Intelligence Graph · MarketRipple",
  description: "Live dependency map of Indian market entities, sectors, and causal relationships",
};

export const dynamic = "force-dynamic";
export const revalidate = 0;

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchGraphData() {
  try {
    const res = await fetch(`${API}/api/graph/full`, {
      cache: "no-store",
      next: { revalidate: 0 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function GraphPage() {
  const graphData = await fetchGraphData();
  return <GraphCanvas initialGraph={graphData} />;
}
