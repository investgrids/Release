import type { Metadata } from "next";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const res = await fetch(`${API}/api/radar/${id}`, {
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const item = await res.json();
      return {
        title: `${item.title} | Opportunity Radar | InvestGrids`,
        description: item.summary?.slice(0, 160) ?? "Opportunity analysis from InvestGrids Radar.",
      };
    }
  } catch {}
  return {
    title: "Opportunity Analysis | InvestGrids Radar",
    description: "AI-powered investment opportunity analysis from InvestGrids.",
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
