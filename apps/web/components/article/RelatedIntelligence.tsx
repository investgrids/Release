import Link from "next/link";
import { Layers, Building2, MessageCircleQuestion, ArrowLeft } from "lucide-react";

// Consolidated internal-linking surface for the article page (AI Newsroom
// redesign, Decision 2 — 2026-08-10). Before this, the article page had
// THREE separate, independently-computed link sources (related_companies/
// related_themes, related_articles campaign siblings, and this new
// internal_link_candidates SEO layer) with no coordination between them —
// the same company or sector could legitimately appear twice with two
// different hrefs. This component is the one place all of them render,
// deduped by href so nothing repeats and the more specific canonical page
// always wins over a generic one.

export interface CampaignSibling { slug: string; headline: string; angle: string; angle_entity?: string | null; article_type: string }
export interface RelatedCompany { symbol: string; name: string; link: string }
export interface RelatedTheme { theme: string; link: string }
export interface LinkCandidate { label: string; href: string; type: string }

const ANGLE_LABEL: Record<string, (entity?: string | null) => string> = {
  per_company: (e) => e ?? "Company",
  sector_rollup: (e) => `${e} Sector`,
  theme: (e) => `${e} Theme`,
};

export function RelatedIntelligence({
  campaignSiblings, relatedCompanies, relatedThemes, linkCandidates,
}: {
  campaignSiblings: CampaignSibling[];
  relatedCompanies: RelatedCompany[];
  relatedThemes: RelatedTheme[];
  linkCandidates: LinkCandidate[];
}) {
  const questionSiblings = campaignSiblings.filter(r => r.angle === "question");
  const otherSiblings = campaignSiblings.filter(r => r.angle !== "question");

  // Every href rendered anywhere in this component gets tracked here so a
  // later group never repeats a link an earlier group already showed —
  // campaign siblings and Q&A are inherently unique (own article slugs),
  // so dedup only matters for the entity-link groups below them.
  const seenHrefs = new Set<string>([...otherSiblings, ...questionSiblings].map(s => `/newsroom/article/${s.slug}`));

  const companies = relatedCompanies.filter(c => {
    if (seenHrefs.has(c.link)) return false;
    seenHrefs.add(c.link);
    return true;
  });
  const themes = relatedThemes.filter(t => {
    if (seenHrefs.has(t.link)) return false;
    seenHrefs.add(t.link);
    return true;
  });
  // Supplementary SEO-layer candidates (historical/compare-tool links,
  // sectors not already covered by relatedThemes) — only the ones not
  // already shown by a more specific group above.
  const extra = linkCandidates.filter(c => {
    if (seenHrefs.has(c.href)) return false;
    seenHrefs.add(c.href);
    return true;
  });

  const hasAnything = otherSiblings.length > 0 || questionSiblings.length > 0 || companies.length > 0 || themes.length > 0 || extra.length > 0;
  if (!hasAnything) return null;

  return (
    <div className="space-y-5">
      {otherSiblings.length > 0 && (
        <div>
          <div className="mb-2.5 flex items-center justify-between">
            <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
              <Layers className="h-3.5 w-3.5 text-accent-violet" /> Related Campaign
            </p>
            <span className="text-[10px] text-text-muted">{otherSiblings.length + 1} articles</span>
          </div>
          <div className="space-y-2">
            {otherSiblings.map((r, i) => (
              <Link key={i} href={`/newsroom/article/${r.slug}`}
                className="flex items-center justify-between rounded-xl border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3 hover:border-surface-border/20 transition">
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-text-muted">
                    {(ANGLE_LABEL[r.angle] ?? (() => r.article_type))(r.angle_entity)}
                  </span>
                  <p className="text-[12px] font-medium text-text-secondary">{r.headline}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {questionSiblings.length > 0 && (
        <div>
          <p className="mb-2.5 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
            <MessageCircleQuestion className="h-3.5 w-3.5 text-pink-500" /> People Also Asked
          </p>
          <div className="space-y-2">
            {questionSiblings.map((r, i) => (
              <Link key={i} href={`/newsroom/article/${r.slug}`}
                className="flex items-center justify-between rounded-xl border border-pink-200 dark:border-pink-500/15 bg-pink-50 dark:bg-pink-500/[0.03] px-4 py-3 hover:border-pink-300 dark:hover:border-pink-500/30 transition">
                <p className="text-[13px] font-medium text-text-primary">{r.headline}</p>
                <ArrowLeft className="h-3.5 w-3.5 shrink-0 rotate-180 text-pink-500" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {(companies.length > 0 || themes.length > 0 || extra.length > 0) && (
        <div>
          <p className="mb-2.5 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-text-muted">
            <Building2 className="h-3.5 w-3.5" /> Related Companies &amp; Themes
          </p>
          <div className="flex flex-wrap gap-2">
            {companies.map((c, i) => (
              <Link key={`co-${i}`} href={c.link}
                className="rounded-full border border-sky-200 dark:border-sky-500/20 bg-sky-50 dark:bg-sky-500/[0.06] px-3 py-1.5 text-[11px] font-medium text-sky-700 dark:text-sky-300 hover:text-sky-900 dark:hover:text-sky-200 transition">
                {c.name}
              </Link>
            ))}
            {themes.map((t, i) => (
              <Link key={`th-${i}`} href={t.link}
                className="rounded-full border border-violet-200 dark:border-violet-500/20 bg-violet-50 dark:bg-violet-500/[0.06] px-3 py-1.5 text-[11px] font-medium text-violet-700 dark:text-violet-300 hover:text-violet-900 dark:hover:text-violet-200 transition">
                {t.theme}
              </Link>
            ))}
            {extra.map((c, i) => (
              <Link key={`ex-${i}`} href={c.href}
                className="rounded-full border border-surface-border/15 bg-text-primary/[0.02] px-3 py-1.5 text-[11px] font-medium text-text-secondary hover:text-text-primary transition">
                {c.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
