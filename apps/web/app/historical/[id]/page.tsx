import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText, safeJsonLd, truncateForQuery } from "@/lib/text";
import { NextSteps } from "@/components/NextSteps";
import { HistoricalDetailContent, type HistoricalDetail } from "./HistoricalDetailContent";

/**
 * Historical Memory detail page — SEO audit's "no page, engine exists"
 * finding: historical_memory_service.py + /api/historical/ already stores
 * 56 real, richly-detailed market-pattern events (Union Budgets, RBI rate
 * cycles, market corrections, global shocks — dated back to 2008), consumed
 * only by the HistoricalMemory.tsx sidebar widget until now. These pages
 * have long organic life since a pattern (not a single day's news) stays
 * relevant long after the event itself fades from search.
 *
 * The `pattern` field (compute_category_pattern in the backend service)
 * aggregates every stored event sharing this one's category — winners/
 * losers consistency, sector consistency, timeline, confidence — all real
 * cross-event math, not per-event data reused to look bigger than it is.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

async function fetchEvent(id: string): Promise<HistoricalDetail | null> {
  try {
    const res = await fetch(`${API}/api/historical/${id}`, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    const raw = await res.json();
    return {
      ...raw,
      event_title: cleanText(raw.event_title),
      what_happened: raw.what_happened ? cleanText(raw.what_happened) : raw.what_happened,
      key_lesson: raw.key_lesson ? cleanText(raw.key_lesson) : raw.key_lesson,
      historical_winners: (raw.historical_winners ?? []).map((w: HistoricalDetail["historical_winners"][number]) => ({ ...w, reason: cleanText(w.reason) })),
      historical_losers: (raw.historical_losers ?? []).map((w: HistoricalDetail["historical_losers"][number]) => ({ ...w, reason: cleanText(w.reason) })),
    };
  } catch {
    return null;
  }
}

function pct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`;
}

// Data has near-duplicate category casings ("Monetary Policy" / "monetary
// policy") — normalized for display without touching the stored value,
// since that's a data-entry inconsistency, not something worth a migration
// for a read-only display label.
function normalizeCategory(c: string): string {
  return c.replace(/_/g, " ").trim().split(" ").map(w => w[0]?.toUpperCase() + w.slice(1)).join(" ");
}

// Thin, auto-captured events (no real Nifty reaction or scoring data yet —
// see sitemap.ts's same filter) still render honestly rather than 404ing,
// since a widget or direct link might reach one, but they shouldn't be
// indexed as a "full analysis" page — same thin-content reasoning as the
// sitemap exclusion, applied here too since crawlers can reach a page
// through links even when it's absent from the sitemap.
function isSubstantive(d: HistoricalDetail): boolean {
  return d.nifty_1w != null || d.opportunity_score != null || d.historical_winners.length > 0;
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/historical/${id}`;
  const d = await fetchEvent(id);
  if (!d) return { title: "Historical Pattern Not Found", alternates: { canonical: url } };
  const title = `${d.event_title} — What Happened & What It Means Now`;
  const description = (d.key_lesson || d.what_happened || `${d.event_title}: real historical market data on how Nifty and key sectors reacted.`).slice(0, 160);
  return {
    title,
    description,
    ...(isSubstantive(d) ? {} : { robots: { index: false, follow: true } }),
    openGraph: { type: "article", title, description, url, siteName: "MarketRipple" },
    twitter: { card: "summary_large_image", title, description },
    alternates: { canonical: url },
  };
}

export default async function HistoricalDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const d = await fetchEvent(id);
  if (!d) notFound();

  const url = `${SITE}/historical/${id}`;
  const category = normalizeCategory(d.category);
  const p = d.pattern;
  const multi = p.category_occurrences > 1;

  // Real, honestly-derived FAQs from fields already on the page and the
  // real cross-event pattern aggregate — not a second LLM call, not
  // invented. Only included when the underlying data actually supports
  // the answer.
  const faqs: { q: string; a: string }[] = [];
  if (d.what_happened) faqs.push({ q: `What happened during ${d.event_title}?`, a: d.what_happened });
  if (d.historical_winners.length) {
    const names = d.historical_winners.slice(0, 3).map(w => w.name || w.symbol).join(", ");
    faqs.push({ q: `Which stocks benefited most from ${d.event_title}?`, a: `Historically, ${names} were among the strongest performers in the aftermath, based on real 1-week/1-month return data.` });
  }
  if (d.nifty_1w != null) {
    faqs.push({ q: `How did the Nifty 50 react to ${d.event_title}?`, a: `The Nifty 50 moved ${pct(d.nifty_1w)} in the following week and ${pct(d.nifty_1m)} over the following month.` });
  }
  if (d.key_lesson) faqs.push({ q: `What's the investing lesson from ${d.event_title}?`, a: d.key_lesson });
  if (multi && p.win_rate_pct != null) {
    faqs.push({ q: `How reliable is this historical pattern?`, a: `This pattern has occurred ${p.category_occurrences} times in our verified database, with the Nifty 50 moving higher in ${p.win_rate_pct}% of those occurrences. Our Historical Confidence score for it is ${p.historical_confidence.score}/100, based on sample size, consistency, and data quality.` });
  }
  if (multi && p.best_sectors[0]) {
    const top3 = [...p.best_sectors].sort((a, b) => b.avg_reaction - a.avg_reaction).slice(0, 3).map(s => s.sector).join(", ");
    faqs.push({ q: `Which sectors are most consistently affected?`, a: `Across all ${p.category_occurrences} occurrences, ${top3} showed the strongest and most consistent reactions — led by ${p.best_sectors[0].sector} at ${pct(p.best_sectors[0].avg_reaction)} on average.` });
  }
  if (multi && p.holding_period) {
    faqs.push({ q: `What's the ideal holding period based on history?`, a: `Historically, the strongest and most consistent move has come over a ${p.holding_period.label.toLowerCase()} window, averaging ${pct(p.holding_period.avg_return)} with a ${p.holding_period.positive_rate}% positive rate.` });
  }
  if (multi && p.consistency.nifty_direction) {
    faqs.push({ q: `Does this pattern always play out the same way?`, a: `No — history shows a tendency, not a certainty. The Nifty 50 moved ${p.consistency.nifty_direction.value} in ${p.consistency.nifty_direction.pct}% of the ${p.consistency.nifty_direction.of} recorded occurrences, meaning it moved the other way the rest of the time.` });
  }

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": faqs.length ? ["Article", "FAQPage"] : "Article",
    headline: d.event_title,
    description: d.key_lesson || d.what_happened || d.event_title,
    datePublished: d.event_date,
    dateModified: d.event_date,
    author: { "@type": "Organization", name: "MarketRipple AI Intelligence Engine" },
    publisher: { "@type": "Organization", name: "MarketRipple" },
    mainEntityOfPage: url,
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: SITE },
        { "@type": "ListItem", position: 2, name: "Historical Patterns", item: `${SITE}/historical` },
        { "@type": "ListItem", position: 3, name: d.event_title, item: url },
      ],
    },
    ...(faqs.length ? {
      mainEntity: faqs.map(f => ({
        "@type": "Question", name: f.q,
        acceptedAnswer: { "@type": "Answer", text: f.a },
      })),
    } : {}),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }} />
      <HistoricalDetailContent d={d} faqs={faqs} category={category} />
      <div className="mx-auto max-w-[1100px] pb-16">
        <NextSteps config={{
          takeaway: d.key_lesson || `${cleanText(d.event_title)} is real historical precedent — see who actually won and lost, then check if a similar setup is forming today.`,
          primary: {
            label: "See Historical Winners & Losers",
            why:   "Because knowing which companies actually gained or lost last time is the whole point of a historical pattern — not just that the market moved.",
            href:  "/ripple?tab=winners",
          },
          groups: [
            ...(d.companies.length > 0 ? [{
              label: "Explore Further",
              actions: d.companies.slice(0, 3).map(sym => ({
                label: `Research ${sym}`,
                why:   `Because ${sym} was directly involved in this historical pattern — its current setup is worth comparing.`,
                href:  `/companies/${sym}`,
              })),
            }] : []),
            {
              label: "Continue Research",
              actions: [
                {
                  label: "Trace a similar event's ripple effects",
                  why:   "Because a historical pattern is only useful if you connect it to what's happening right now.",
                  href:  "/ripple",
                },
                {
                  label: `Ask AI: does this pattern apply today?`,
                  why:   "Because market conditions change — an AI read on today's setup vs. this historical one adds context a static page can't.",
                  href:  `/ai-search?q=${encodeURIComponent(`Does the historical pattern from "${truncateForQuery(d.event_title)}" apply to current market conditions?`)}`,
                },
              ],
            },
          ],
          path: [d.category, "Historical Validation", "Investment Decision"].filter(Boolean),
        }} />
      </div>
    </>
  );
}
