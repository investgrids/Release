import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { API_BASE_URL as API } from "@/lib/api";
import { safeJsonLd } from "@/lib/text";
import RadarDetailPage from "./OpportunityPageClient";
import { isV2Detail, type AnyOpportunityDetail } from "./types";

/**
 * Server wrapper (Phase 1 SEO fix — see the SEO/Growth audit's Critical
 * Finding #1, and the audit's separate note that this route had NO
 * generateMetadata at all, so every one of the 40 opportunity pages
 * inherited the generic site-wide title/description). Fetches the same
 * /api/radar/{id} endpoint the client component already calls.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

async function fetchOpportunity(id: string): Promise<AnyOpportunityDetail | null> {
  try {
    const res = await fetch(`${API}/api/radar/${id}`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// V2-A contract alignment, 2026-08-24 — V1 and V2 keep separate field
// names for the same concepts (title/summary vs. title/why_this_exists),
// so metadata generation needs its own version-aware read instead of
// assuming the V1 shape. Real values only in both branches.
function titleOf(d: AnyOpportunityDetail): string {
  return d.title;
}
function descriptionOf(d: AnyOpportunityDetail): string {
  return isV2Detail(d)
    ? (d.why_this_exists || `${d.title} — AI-tracked opportunity on MarketRipple.`)
    : (d.summary || d.ai_summary?.matters || `${d.title} — AI-powered opportunity analysis on MarketRipple.`);
}
function sectorsOf(d: AnyOpportunityDetail): string[] {
  return isV2Detail(d) ? d.sectors_themes : (d.sectors ?? []);
}

// V2-B, 2026-08-24 — the one real signal a V1 legacy page needs to decide
// whether to self-noindex: has the system actually been promoted to V2 as
// canonical? Long revalidate — this is a deploy-time posture flag, not
// something that changes moment to moment, so there's no reason to refetch
// it on every request the way the opportunity itself is.
async function fetchOpportunityV2Promoted(): Promise<boolean> {
  try {
    const res = await fetch(`${API}/api/radar/meta`, { next: { revalidate: 3600 } });
    if (!res.ok) return false;
    const d = await res.json();
    return d.opportunity_v2_promoted === true;
  } catch {
    return false;
  }
}

// Backend already supports entity_type="opportunity" — this page just
// never called it (confirmed: zero RelatedContent usage anywhere under
// opportunity-radar), a real orphan-page gap despite the plumbing already
// existing. Server-fetched for the same reason companies/research pages
// are: real internal links in the initial HTML, not just after hydration.
async function fetchRelated(id: string, sector?: string) {
  try {
    const params = new URLSearchParams(sector ? { sector } : {});
    const res = await fetch(`${API}/api/related/opportunity/${encodeURIComponent(id)}?${params}`, { next: { revalidate: 600 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function withPeriod(text: string) {
  const t = text.trim();
  return /[.!?]$/.test(t) ? t : `${t}.`;
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/opportunity-radar/${id}`;
  const d = await fetchOpportunity(id);
  if (!d) {
    return { title: "Opportunity — AI Analysis", alternates: { canonical: url } };
  }
  const title = titleOf(d);
  const desc = descriptionOf(d).slice(0, 160);

  // V2-B, 2026-08-24 — "numeric and slug routes cannot both stay
  // independently indexable" (owner instruction). Once V2 is promoted to
  // canonical, V1 legacy pages self-noindex — real, aging content that's
  // no longer the canonical source, not deleted and not redirected (there
  // is no reliable 1:1 V1<->V2 thesis mapping to redirect to — see
  // shadow_report.py's own module docstring: "necessarily a heuristic").
  // V2 pages are never touched by this — they're the canonical surface
  // post-promotion and keep the site's normal index:true default.
  const robots = (!isV2Detail(d) && await fetchOpportunityV2Promoted())
    ? { index: false, follow: true }
    : undefined;

  return {
    title: `${title} — Opportunity Analysis`,
    description: desc,
    ...(robots ? { robots } : {}),
    openGraph: { type: "article", title: `${title} — MarketRipple`, description: desc, url, siteName: "MarketRipple" },
    twitter: { card: "summary_large_image", title, description: desc },
    alternates: { canonical: url },
  };
}

export default async function OpportunityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const detail = await fetchOpportunity(id);
  // 2026-08 fix — this route never called notFound() at all: a deleted/
  // nonexistent id rendered a near-empty page at HTTP 200. Same fix as
  // /events/[id] and /ripple/[id].
  if (!detail) notFound();
  const url = `${SITE}/opportunity-radar/${id}`;
  const title = titleOf(detail);
  const description = withPeriod(descriptionOf(detail));
  const related = await fetchRelated(id, sectorsOf(detail)[0]);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: title,
    description,
    url,
    publisher: { "@type": "Organization", name: "MarketRipple" },
  };

  return (
    <>
      {/* JSON.stringify (not safeJsonLd) previously left "<" unescaped —
          same stored-XSS class already fixed on the article/signal/
          research pages. */}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }} />
      <section className="mb-4 border-b border-surface-border/6 pb-4">
        {/* The single real <h1> for this page — the client component's
            own header renders the same title as a <p>, not a second <h1>. */}
        <h1 className="text-[13px] font-semibold uppercase tracking-wide text-text-muted">{title}</h1>
        <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-text-secondary">{description}</p>
      </section>
      <RadarDetailPage params={params} initialDetail={detail} initialRelated={related} />
    </>
  );
}
