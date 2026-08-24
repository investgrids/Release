import type { Metadata } from "next";
import Link from "next/link";
import { TrendingUp } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

// SEO P1-P2, 2026-08-24 — same duplicate-content finding the P0 fix
// already applied to /newsroom/themes/[slug] (each card here links to
// those exact pages), just not previously checked at the hub level: this
// page re-lists the identical /api/radar/ data /opportunity-radar
// already lists, self-canonicalized to itself rather than pointing at
// the real hub. noindex,follow + canonical -> the real destination,
// matching the Indexability Contract's DUPLICATE/PREVIEW rule.
const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";
export const metadata: Metadata = {
  title: "Theme Intelligence | AI Newsroom",
  description: "Real, computed opportunity scores paired with AI analysis — neither the number nor the narrative alone tells the full story.",
  robots: { index: false, follow: true },
  alternates: { canonical: `${SITE}/opportunity-radar` },
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
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          <TrendingUp className="h-3 w-3 text-emerald-400" /> AI Newsroom
        </p>
        <h1 className="mt-2 text-[26px] font-black leading-tight text-text-primary md:text-[30px]">
          Theme Intelligence
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-text-secondary">
          Real, computed opportunity scores paired with AI analysis — neither the number nor
          the narrative alone tells the full story.
        </p>
      </div>

      {themes.length === 0 ? (
        <p className="rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-8 text-center text-[13px] text-text-muted">
          No scored themes available right now.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {themes.map((t) => (
            <Link
              key={t.id}
              href={`/newsroom/themes/${t.slug}`}
              className="block rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-4 transition hover:border-surface-border/20 hover:bg-text-primary/[0.05]"
            >
              <div className="flex items-baseline justify-between">
                <span className="text-[26px] font-black text-emerald-400">{Math.round(t.opportunity_score)}</span>
                <span className="text-[10px] uppercase tracking-wider text-text-muted">{t.risk_level} risk</span>
              </div>
              <p className="mt-1 line-clamp-2 text-[13.5px] font-semibold text-text-primary">{cleanText(t.title)}</p>
              <div className="mt-2 flex items-center justify-between">
                {t.sectors.length > 0 && (
                  <p className="text-[11px] text-text-muted">{t.sectors.slice(0, 2).join(" · ")}</p>
                )}
                <span className="text-[10.5px] text-text-muted">{t.company_count} companies</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
