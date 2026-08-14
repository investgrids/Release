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
  // Used for JSON-LD only (2026-08 audit, per explicit request) — no
  // visible "Quick Answer" or description paragraph up here anymore. That
  // content was the same real text as the Overview tab's own What
  // Happened / Why It Matters cards, just phrased slightly differently
  // three separate times before a reader got past the page header.
  // Search engines still get the full text via JSON-LD either way.
  const description = ev ? withPeriod(
    detail?.summary?.why_it_matters || detail?.summary?.text || ev.description || `${ev.title} — real-time market intelligence and ripple-chain impact analysis on MarketRipple.`
  ) : "";

  // Phase 12 (2026-08 audit) — machine-readable "Event Facts", using
  // schema.org's own additionalProperty/PropertyValue mechanism (the
  // correct, non-misused way to attach extra structured facts to an
  // existing type — not a second competing schema block). Every entry
  // here is a real value already present in `detail`; fields with no
  // real value (e.g. importance when no macro release or coverage
  // priority exists) are simply omitted, never filled with a placeholder.
  const factProperties = ev ? [
    { "@type": "PropertyValue", name: "eventDate", value: ev.event_date || "" },
    { "@type": "PropertyValue", name: "source", value: ev.source || "" },
    { "@type": "PropertyValue", name: "category", value: ev.event_type || "" },
    ...(detail?.macroRelease?.importance ? [{ "@type": "PropertyValue", name: "importance", value: detail.macroRelease.importance }] : []),
    ...(detail?.affectedSectors?.length ? [{ "@type": "PropertyValue", name: "affectedSectors", value: detail.affectedSectors.map(s => s.sector).join(", ") }] : []),
    ...(detail?.companies?.length ? [{ "@type": "PropertyValue", name: "affectedCompanies", value: detail.companies.map(c => c.symbol).join(", ") }] : []),
  ].filter(p => p.value) : [];

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
    additionalProperty: factProperties,
  } : null;

  return (
    <>
      {jsonLd && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      )}
      {ev && (
        <section className="mb-4 border-b border-surface-border/6 pb-4">
          {/* The single real <h1> for this page — EventExplorerPage's own
              header renders the same title as a <p>, not a second <h1>.
              Deliberately NOT verbatim-identical to that card's title
              (2026-08 audit, user-reported: the exact same sentence
              appearing twice read as a plain duplicate). Same fix already
              applied on the company page (see companies/[symbol]/page.tsx)
              — a real, visible h1 stays, but its text is a distinct
              SEO-flavored framing of the same real event, not a repeat. */}
          <h1 className="text-[13px] font-semibold uppercase tracking-wide text-text-muted">{ev.title} — Market Impact &amp; AI Analysis</h1>
          {/* No Quick Answer, no description paragraph here (2026-08 audit,
              per explicit request — three overlapping renderings of the
              same real text before a reader reached any actual content
              was the duplicate). The Event Explorer card below shows the
              title once; the Overview tab's What Happened / Why It
              Matters cards are the single real place for the descriptive
              text. `description` above still feeds JSON-LD only. */}
        </section>
      )}
      <EventExplorerPage initialDetail={detail} initialRelated={related} />
    </>
  );
}
