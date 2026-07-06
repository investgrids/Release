import type { Metadata } from "next";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const res = await fetch(`${API}/api/news/${id}`, {
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const article = await res.json();
      return {
        title: `${article.headline} | InvestGrids`,
        description: article.summary?.slice(0, 160) ?? "Market news from InvestGrids.",
      };
    }
  } catch {}
  return {
    title: "Market News | InvestGrids",
    description: "Real-time Indian market news and financial intelligence.",
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
