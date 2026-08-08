import { API_BASE_URL as API } from "@/lib/api";
import EventExplorerPage, { type EventDetail } from "./EventPageClient";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

/**
 * Server wrapper (Phase 1 SEO fix — see the SEO/Growth audit's Critical
 * Finding #1). Fetches the same /api/events/{id} endpoint the client
 * component already calls, purely so crawlers and the first paint see a
 * real, indexable <h1> + summary instead of nothing. Mirrors the same
 * pattern used for companies/[symbol]/page.tsx.
 *
 * Structured data is NewsArticle, not schema.org Event (SEO Phase 2,
 * §2.3's original recommendation) — deliberate deviation. schema.org
 * Event/Google's Event rich-result eligibility both assume a real-world
 * attendable event (location, startDate as the thing that HAPPENS at a
 * place) — these pages are market/corporate events ("RBI raised the repo
 * rate"), which NewsArticle honestly describes and Event would misuse.
 */

async function fetchEvent(id: string): Promise<EventDetail | null> {
  try {
    const res = await fetch(`${API}/api/events/${id}`, { next: { revalidate: 300 } });
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

// SEO Phase 2, §2.4 — server-fetches the same /api/related endpoint
// RelatedContent otherwise fetches client-side (see the identical helper
// in companies/[symbol]/page.tsx for the full reasoning).
async function fetchRelated(id: string, title: string, sector?: string) {
  try {
    const params = new URLSearchParams({ title, ...(sector ? { sector } : {}) });
    const res = await fetch(`${API}/api/related/event/${encodeURIComponent(id)}?${params}`, { next: { revalidate: 600 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export default async function EventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const detail = await fetchEvent(id);
  const ev = detail?.event;
  const related = ev ? await fetchRelated(id, ev.title, detail?.affectedSectors?.[0]?.sector) : null;
  // Same SEO fix as layout.tsx's generateMetadata — prefer the real,
  // human-readable slug over the opaque id for the URL this page asserts
  // as its own identity (JSON-LD url + breadcrumb item).
  const url = `${SITE}/events/${ev?.slug || id}`;
  const description = ev ? withPeriod(
    detail?.summary?.why_it_matters || detail?.summary?.text || ev.description || `${ev.title} — real-time market intelligence and ripple-chain impact analysis on MarketRipple.`
  ) : "";

  const jsonLd = ev ? {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: ev.title,
    description,
    datePublished: ev.event_date,
    url,
    publisher: { "@type": "Organization", name: "MarketRipple" },
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: SITE },
        { "@type": "ListItem", position: 2, name: "Events", item: `${SITE}/events` },
        { "@type": "ListItem", position: 3, name: ev.title, item: url },
      ],
    },
  } : null;

  return (
    <>
      {jsonLd && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      )}
      {ev && (
        <section className="mb-4 border-b border-surface-border/6 pb-4">
          {/* The single real <h1> for this page — EventExplorerPage's own
              header renders the same title as a <p>, not a second <h1>. */}
          <h1 className="text-[13px] font-semibold uppercase tracking-wide text-text-muted">{ev.title}</h1>
          <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-text-secondary">{description}</p>
        </section>
      )}
      <EventExplorerPage initialDetail={detail} initialRelated={related} />
    </>
  );
}
