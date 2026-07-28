import { API_BASE_URL as API } from "@/lib/api";
import EventExplorerPage, { type EventDetail } from "./EventPageClient";

/**
 * Server wrapper (Phase 1 SEO fix — see the SEO/Growth audit's Critical
 * Finding #1). Fetches the same /api/events/{id} endpoint the client
 * component already calls, purely so crawlers and the first paint see a
 * real, indexable <h1> + summary instead of nothing. Mirrors the same
 * pattern used for companies/[symbol]/page.tsx.
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

export default async function EventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const detail = await fetchEvent(id);
  const ev = detail?.event;

  return (
    <>
      {ev && (
        <section className="mb-4 border-b border-white/[0.06] pb-4">
          {/* The single real <h1> for this page — EventExplorerPage's own
              header renders the same title as a <p>, not a second <h1>. */}
          <h1 className="text-[13px] font-semibold uppercase tracking-wide text-slate-500">{ev.title}</h1>
          <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-slate-400">
            {withPeriod(
              detail?.summary?.why_it_matters || detail?.summary?.text || ev.description || `${ev.title} — real-time market intelligence and ripple-chain impact analysis on MarketRipple.`
            )}
          </p>
        </section>
      )}
      <EventExplorerPage initialDetail={detail} />
    </>
  );
}
