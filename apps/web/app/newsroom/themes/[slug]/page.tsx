import { notFound, permanentRedirect } from "next/navigation";
import { API_BASE_URL as API } from "@/lib/api";

// Batch G rewrite (2026-09-20) — this route no longer renders any theme
// detail content. Genuine Theme Intelligence lives at its own real
// canonical URL (/newsroom/article/{slug}, see the sibling index page's
// header comment); this legacy path's slugs are ALL provably V1
// Opportunity slugs (verified: zero overlap with real theme_intelligence
// article slugs, which are RSS-hash-shaped and never resembled these
// title-derived ones). Every resolvable slug permanently redirects (308)
// to its real, already-canonical /opportunity-radar/{id} — the exact same
// numeric id this page used to fetch full V1 detail from and then
// re-render as a duplicate. An unresolvable slug is a real 404, never a
// silent fallback and never a guess (the old findMatchingThemeArticle()
// title/sector fuzzy-match this route used to do for a *different*
// purpose is removed entirely along with it).
interface OpportunityListItem { id: number; slug: string }

async function resolveIdBySlug(slug: string): Promise<number | null> {
  try {
    const res = await fetch(`${API}/api/radar/?page=1&page_size=100`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    const list: { items: OpportunityListItem[] } = await res.json();
    return list.items.find((o) => o.slug === slug)?.id ?? null;
  } catch {
    return null;
  }
}

export default async function LegacyThemeRedirect({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const id = await resolveIdBySlug(slug);
  if (id === null) notFound();
  permanentRedirect(`/opportunity-radar/${id}`);
}
