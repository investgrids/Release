import { fetchWeekendHistory, fetchWeekendIntelligence } from "@/lib/weekendIntelligence";
import { WeekendUnavailable } from "./WeekendUnavailable";
import { WeekendPrimaryMetrics } from "./WeekendPrimaryMetrics";
import { WeekendMetadataStrip } from "./WeekendMetadataStrip";
import { WeekendChanges } from "./WeekendChanges";
import { WeekendSectors } from "./WeekendSectors";
import { WeekendCompanies } from "./WeekendCompanies";
import { WeekendOpportunities } from "./WeekendOpportunities";
import { WeekendRisks } from "./WeekendRisks";
import { WeekendConfidenceWarnings } from "./WeekendConfidenceWarnings";
import { WeekendSummary } from "./WeekendSummary";
import { WeekendHistoricalContext } from "./WeekendHistoricalContext";
import { WeekendEvidenceSummary } from "./WeekendEvidenceSummary";
import { Band, BAND } from "@/components/homepage/Band";
import { safeJsonLd } from "@/lib/text";

// Same verbatim FAQ copy as the weekday homepage (app/page.tsx's HOME_FAQS) —
// duplicated here rather than cross-imported, so the weekend page stays its
// own self-contained unit per this component's own module contract (one
// fetch, presentation-only composition). Keep both copies in sync manually
// if /faq changes; see app/page.tsx's own comment for the source of truth.
const WEEKEND_FAQS: { q: string; a: string }[] = [
  {
    q: "What is MarketRipple?",
    a: "MarketRipple is an AI-powered market intelligence platform focused on Indian equity markets. It continuously monitors market-moving events — from government policy announcements and RBI decisions to global macro developments — and uses artificial intelligence to analyse their impact on sectors, companies, and broader market themes.",
  },
  {
    q: "Is MarketRipple free to use?",
    a: "Yes — the current version of MarketRipple is completely free to use. All core features including the Events Engine, AI Search, Market Intelligence dashboard, Opportunity Radar, Stories, Sector Heatmap, Economic Calendar, Ripple Engine, and Company Intelligence pages are available at no cost.",
  },
  {
    q: "Does MarketRipple require login or account creation?",
    a: "No — MarketRipple currently requires no login or account creation. You can access all features immediately without registering.",
  },
  {
    q: "What markets does MarketRipple cover?",
    a: "MarketRipple's primary focus is Indian equity markets — stocks listed on the BSE and NSE. Coverage includes Nifty 50, Sensex, Nifty Bank, Nifty IT, mid-cap and small-cap segments, and sector-level indices, alongside global market context that influences Indian markets.",
  },
];

/**
 * The Weekend Intelligence homepage — brief §2/§4 (Phase 1D) + the
 * 2026-08-15 redesign brief's dashboard architecture. A single, self-
 * contained variant rendered in place of the normal homepage. One fetch
 * (GET /api/intelligence/weekend/current — the only Weekend
 * Intelligence data source this component or its children are allowed
 * to read), then presentation-only composition — no client-side
 * reranking, recalculation, or invented conclusions.
 *
 * Layout (redesign brief §4/§8/§32/§33/§34, re-grouped into the same
 * band language as the weekday homepage on 2026-11-07): hero + 4 primary
 * metric cards -> compact metadata strip -> "Since Market Close" band
 * (what changed / sectors / companies) -> "Risks & Confidence" band
 * (risks / confidence warnings / summary) -> "Opportunities" band ->
 * "Historical Context" band -> FAQ band. The hero (WeekendPrimaryMetrics)
 * is deliberately left OUTSIDE the Band wrapper — it already carries its
 * own real <h1> + eyebrow, and Band always renders its own heading, so
 * wrapping it would create a second <h1> on the page. Only the Band
 * wrapper and each child's own card class changed (mr-card's gradient
 * recipe, picking up the Band's --band-tint); no child component's props,
 * data bindings, or internal logic were touched — none of the owner
 * corrections documented below were revisited. Any section with no real
 * data to show renders nothing — every section component below already
 * self-hides on empty input; this page never renders a hollow card just
 * because a backend array happens to exist.
 *
 * `weekend-enter-stagger` (globals.css) staggers each top-level section's
 * paint-time reveal — pure CSS (opacity/transform only), reduced-motion
 * disables it to the settled end state. Nothing here is gated behind it:
 * every section is already fully present in the server-rendered HTML.
 *
 * "Since Our Last Update" (changes_since_prior) is deliberately NOT
 * rendered here (owner correction, 2026-08-15): it's not part of the
 * approved reference layout and exposed too much version-to-version
 * state-change noise (dozens of "X turned neutral"/"Y newly appeared"
 * rows) between the metadata strip and the primary grid. The backend
 * field and WeekendChangesSincePrior component are both untouched and
 * still real/tested — this is a display-only omission, not a data
 * deletion, so it stays trivially reversible if the product decides to
 * bring it back (e.g. behind an expand control) later. The primary
 * "what changed" story for a user is new_since_close, shown via
 * WeekendChanges below.
 */
export async function WeekendHomePage() {
  const response = await fetchWeekendIntelligence();

  if (!response) {
    return (
      <div className="py-10">
        <WeekendUnavailable kind="error" />
      </div>
    );
  }

  if (!response.available) {
    return (
      <div className="py-10">
        <WeekendUnavailable kind="no_snapshot" />
      </div>
    );
  }

  const snapshot = response;

  if (snapshot.status === "insufficient_evidence") {
    return (
      <div className="space-y-4 py-6 pb-12">
        <div className="py-4">
          <WeekendUnavailable kind="insufficient_evidence" />
        </div>
        {snapshot.evidence_summary.total > 0 && <WeekendEvidenceSummary summary={snapshot.evidence_summary} />}
      </div>
    );
  }

  // Real "vs previous checkpoint" confidence delta for the Confidence
  // card — a second, cheap read of already-persisted version metadata
  // (brief §8's own description of this endpoint), never a computed/
  // estimated number. Additive only: any failure here must never break
  // the page, so a null history response just omits the delta line.
  const history = await fetchWeekendHistory(snapshot.target_trading_date);
  const versions = history?.versions ?? [];
  const currentIdx = versions.findIndex((v) => v.is_current);
  const previous = currentIdx >= 0 ? versions[currentIdx + 1] : undefined;

  return (
    <div className="weekend-enter-stagger space-y-12 pb-16 pt-6 md:space-y-16">
      {/* Hero — unwrapped (see module docstring): carries its own real <h1>. */}
      <WeekendPrimaryMetrics
        snapshot={snapshot}
        previousConfidence={previous?.production_confidence ?? null}
        previousCheckpointLabel={previous?.checkpoint_label ?? null}
      />

      <WeekendMetadataStrip snapshot={snapshot} />

      <Band id="weekend-changes" index="01" eyebrow="Since Market Close" title="What changed and what to watch"
        tint={BAND.amber}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-[1.35fr_0.82fr_0.9fr]">
          <div className="md:col-span-2 lg:col-span-1">
            <WeekendChanges items={snapshot.new_since_close} count={snapshot.new_since_close_count} />
          </div>
          <WeekendSectors sectors={snapshot.top_sectors} />
          <WeekendCompanies companies={snapshot.top_companies} />
        </div>
      </Band>

      <Band id="weekend-risks" index="02" eyebrow="Risks & Confidence" title="Risks and how confident this read is"
        tint={BAND.rose}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-[1fr_1fr_1.15fr]">
          <WeekendRisks risks={snapshot.market_risks} />
          <WeekendConfidenceWarnings warnings={snapshot.confidence_warnings} />
          <div className="md:col-span-2 lg:col-span-1">
            <WeekendSummary snapshot={snapshot} />
          </div>
        </div>
      </Band>

      <Band id="weekend-opportunities" index="03" eyebrow="Opportunities" title="Weekend opportunity signals"
        tint={BAND.emerald}>
        <WeekendOpportunities opportunities={snapshot.opportunities} />
      </Band>

      <Band id="weekend-history" index="04" eyebrow="Historical Context" title="Similar past weekends"
        tint={BAND.cyan}>
        <WeekendHistoricalContext analogues={snapshot.historical_analogues} />
      </Band>

      {/* FAQ (AEO/GEO, 2026-11-07) — same treatment and verbatim /faq copy as
          the weekday homepage; see WEEKEND_FAQS above. */}
      <Band id="faq" index="05" eyebrow="Frequently Asked" title="About MarketRipple"
        href="/faq" hrefLabel="All FAQs" tint={BAND.violet}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {WEEKEND_FAQS.map((f) => (
            <div key={f.q} className="mr-card rounded-2xl border bg-surface-card p-5">
              <h3 className="font-display text-[15px] font-bold text-text-primary">{f.q}</h3>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-text-secondary">{f.a}</p>
            </div>
          ))}
        </div>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: safeJsonLd({
              "@context": "https://schema.org",
              "@type": "FAQPage",
              mainEntity: WEEKEND_FAQS.map((f) => ({
                "@type": "Question",
                name: f.q,
                acceptedAnswer: { "@type": "Answer", text: f.a },
              })),
            }),
          }}
        />
      </Band>
    </div>
  );
}
