import type { Metadata } from "next";
import Link from "next/link";
import { TrendingUp } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

export const metadata: Metadata = {
  title: "Theme Intelligence | AI Newsroom",
  description: "Real, computed opportunity scores paired with AI analysis — neither the number nor the narrative alone tells the full story.",
  alternates: { canonical: "/newsroom/themes" },
};

interface OpportunityCard {
  id: number;
  slug: string;
  title: string;
  summary: string;
  opportunity_score: number;
  confidence: number;
  trend: string;
  risk_level: string;
  sectors: string[];
  company_count: number;
}

async function getThemes(): Promise<OpportunityCard[]> {
  try {
    const res = await fetch(`${API}/api/radar/?page=1&page_size=40`, { next: { revalidate: 300 } });
    if (!res.ok) return [];
    const d = await res.json();
    return d.items ?? [];
  } catch {
    return [];
  }
}

export default async function ThemesIndexPage() {
  const themes = await getThemes();

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <TrendingUp className="h-3 w-3 text-emerald-400" /> AI Newsroom
        </p>
        <h1 className="mt-2 text-[26px] font-black leading-tight text-white md:text-[30px]">
          Theme Intelligence
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-slate-400">
          Real, computed opportunity scores paired with AI analysis — neither the number nor
          the narrative alone tells the full story.
        </p>
      </div>

      {themes.length === 0 ? (
        <p className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-8 text-center text-[13px] text-slate-500">
          No scored themes available right now.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {themes.map((t) => (
            <Link
              key={t.id}
              href={`/newsroom/themes/${t.slug}`}
              className="block rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition hover:border-white/20 hover:bg-white/[0.05]"
            >
              <div className="flex items-baseline justify-between">
                <span className="text-[26px] font-black text-emerald-400">{Math.round(t.opportunity_score)}</span>
                <span className="text-[10px] uppercase tracking-wider text-slate-500">{t.risk_level} risk</span>
              </div>
              <p className="mt-1 line-clamp-2 text-[13.5px] font-semibold text-white">{cleanText(t.title)}</p>
              <div className="mt-2 flex items-center justify-between">
                {t.sectors.length > 0 && (
                  <p className="text-[11px] text-slate-500">{t.sectors.slice(0, 2).join(" · ")}</p>
                )}
                <span className="text-[10.5px] text-slate-600">{t.company_count} companies</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
