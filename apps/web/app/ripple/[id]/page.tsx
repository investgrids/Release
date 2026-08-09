import { API_BASE_URL as API } from "@/lib/api";
import RipplePage, { type RippleData } from "./RipplePageClient";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

/**
 * Server wrapper — newly-discovered Phase 1-class gap (found while wiring
 * RelatedContent's SSR conversion, not in the original SEO audit pass):
 * this route was a 900-line "use client" component with zero server-
 * rendered content, same failure mode as Critical Finding #1. Mirrors the
 * proven pattern from companies/[symbol]/page.tsx exactly.
 */

async function fetchRipple(id: string): Promise<RippleData | null> {
  try {
    const res = await fetch(`${API}/api/ripple/event/${id}`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function fetchRelated(id: string, title: string, sector?: string) {
  try {
    const params = new URLSearchParams({ title, ...(sector ? { sector } : {}) });
    const res = await fetch(`${API}/api/related/ripple/${encodeURIComponent(id)}?${params}`, { next: { revalidate: 600 } });
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

export default async function RippleDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await fetchRipple(id);
  const sector = data?.insights?.impacted_sectors?.[0]?.name;
  const related = data ? await fetchRelated(id, data.event_title, sector) : null;
  // SEO fix: same treatment as /events/[id] — prefer the real, human-
  // readable slug (Ripple pages represent the same Event record Events
  // does, so they share its slug) over the opaque id this URL was reached
  // with. middleware.ts issues a real 301 for old id-based links; this is
  // what makes this page assert the slug as its own canonical identity.
  const url = `${SITE}/ripple/${data?.event_slug || id}`;
  const description = data ? withPeriod(
    data.insights?.summary || `${data.event_title} — ripple-chain market dependency analysis on MarketRipple.`
  ) : "";

  const jsonLd = data ? {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: data.event_title,
    description,
    url,
    publisher: { "@type": "Organization", name: "MarketRipple" },
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: SITE },
        { "@type": "ListItem", position: 2, name: "Ripple Engine", item: `${SITE}/ripple` },
        { "@type": "ListItem", position: 3, name: data.event_title, item: url },
      ],
    },
  } : null;

  return (
    <>
      {jsonLd && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      )}
      {data && (
        <section className="mb-4 border-b border-surface-border/6 pb-4">
          {/* The single real <h1> for this page — the client component's
              own header renders the same title as a <p>, not a second <h1>. */}
          <h1 className="text-[13px] font-semibold uppercase tracking-wide text-text-muted">{data.event_title}</h1>
          <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-text-secondary">{description}</p>
        </section>
      )}
      <RipplePage initialData={data} initialRelated={related} />
    </>
  );
}
