import type { Metadata } from "next";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

// Batch G rewrite (2026-09-20) — this hub previously re-listed the exact
// same /api/radar/ (V1 Opportunity) data /opportunity-radar already lists,
// self-canonicalized to itself despite pointing at duplicated content. A
// real, separate content type exists (IntelligenceArticle rows with
// article_type="theme_intelligence" -- genuine editorial Theme
// Intelligence: what's developing, why it matters, related companies/
// events, supporting evidence), already served at its own real canonical
// URL (/newsroom/article/{slug} via GET /api/insights/{slug}). This page
// now lists only that real content and links directly there -- no
// intermediate redirect, no V1 Opportunity metadata or schema, no
// duplicated article bodies. Genuinely indexable now: this is the real,
// non-duplicate home for this content, so it self-canonicalizes for real
// (see the Indexability Contract's real-primary-URL rule) rather than
// deferring to /opportunity-radar as before.
const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";
export const metadata: Metadata = {
  title: "Theme Intelligence | AI Newsroom",
  description: "What's developing across the market, why it matters, and the companies and events behind it — real published analysis, not a scored opportunity list.",
  robots: { index: true, follow: true },
  alternates: { canonical: `${SITE}/newsroom/themes` },
};

interface ThemeArticleCard {
  slug: string;
  headline: string;
  key_takeaway: string | null;
  executive_summary: string | null;
  sectors_affected: { name: string }[] | null;
  companies_affected: { symbol: string | null; name: string }[] | null;
  published_at: string | null;
}

async function getThemeArticles(): Promise<ThemeArticleCard[]> {
  try {
    const res = await fetch(`${API}/api/insights/?article_type=theme_intelligence&sort_by=newest&limit=40`, { next: { revalidate: 300 } });
    if (!res.ok) return [];
    const d = await res.json();
    return d.items ?? [];
  } catch {
    return [];
  }
}

export default async function ThemesIndexPage() {
  const articles = await getThemeArticles();

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          <Sparkles className="h-3 w-3 text-violet-400" /> AI Newsroom
        </p>
        <h1 className="mt-2 text-[26px] font-black leading-tight text-text-primary md:text-[30px]">
          Theme Intelligence
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-text-secondary">
          What&apos;s developing across the market, why it matters, and the companies and events
          behind it.
        </p>
      </div>

      {articles.length === 0 ? (
        <p className="rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-8 text-center text-[13px] text-text-muted">
          No theme intelligence published right now.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {articles.map((a) => {
            const sectors = (a.sectors_affected ?? []).map((s) => s.name).filter(Boolean);
            const companyCount = (a.companies_affected ?? []).length;
            const summary = a.key_takeaway ?? a.executive_summary;
            return (
              <Link
                key={a.slug}
                href={`/newsroom/article/${a.slug}`}
                className="block rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-4 transition hover:border-surface-border/20 hover:bg-text-primary/[0.05]"
              >
                <p className="line-clamp-2 text-[13.5px] font-semibold text-text-primary">{cleanText(a.headline)}</p>
                {summary && (
                  <p className="mt-1.5 line-clamp-2 text-[12px] leading-5 text-text-secondary">{cleanText(summary)}</p>
                )}
                <div className="mt-2 flex items-center justify-between">
                  {sectors.length > 0 && (
                    <p className="text-[11px] text-text-muted">{sectors.slice(0, 2).join(" · ")}</p>
                  )}
                  {companyCount > 0 && (
                    <span className="text-[10.5px] text-text-muted">{companyCount} companies</span>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
