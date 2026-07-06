import type { Metadata } from "next";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const res = await fetch(`${API}/api/events/${id}`, {
      next: { revalidate: 3600 },
    });
    if (res.ok) {
      const event = await res.json();
      return {
        title: `${event.title} | InvestGrids`,
        description: event.summary?.slice(0, 160) ?? "Market event analysis from InvestGrids.",
      };
    }
  } catch {}
  return {
    title: "Market Event | InvestGrids",
    description: "Event-driven market intelligence from InvestGrids.",
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
