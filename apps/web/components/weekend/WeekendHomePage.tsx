import { fetchWeekendIntelligence } from "@/lib/weekendIntelligence";
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

/**
 * The Weekend Intelligence homepage — brief §2/§4 (Phase 1D) + the
 * 2026-08-15 redesign brief's dashboard architecture. A single, self-
 * contained variant rendered in place of the normal homepage. One fetch
 * (GET /api/intelligence/weekend/current — the only Weekend
 * Intelligence data source this component or its children are allowed
 * to read), then presentation-only composition — no client-side
 * reranking, recalculation, or invented conclusions.
 *
 * Layout (redesign brief §4/§8/§32/§33/§34): hero + 4 primary metric
 * cards -> compact metadata strip -> 3-column main grid (what changed /
 * sectors / companies) -> 3-column secondary grid (risks / confidence
 * warnings / summary) -> opportunities (full width, secondary) ->
 * historical analogues (secondary) -> evidence footer. Any section with
 * no real data to show renders nothing — every section component below
 * already self-hides on empty input; this page never renders a hollow
 * card just because a backend array happens to exist.
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

  return (
    <div className="space-y-4 pb-10 pt-6">
      <WeekendPrimaryMetrics snapshot={snapshot} />

      <WeekendMetadataStrip snapshot={snapshot} />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-[1.35fr_0.82fr_0.9fr]">
        <div className="md:col-span-2 lg:col-span-1">
          <WeekendChanges items={snapshot.new_since_close} count={snapshot.new_since_close_count} />
        </div>
        <WeekendSectors sectors={snapshot.top_sectors} />
        <WeekendCompanies companies={snapshot.top_companies} />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-[1fr_1fr_1.15fr]">
        <WeekendRisks risks={snapshot.market_risks} />
        <WeekendConfidenceWarnings warnings={snapshot.confidence_warnings} />
        <div className="md:col-span-2 lg:col-span-1">
          <WeekendSummary snapshot={snapshot} />
        </div>
      </div>

      <WeekendOpportunities opportunities={snapshot.opportunities} />

      <WeekendHistoricalContext analogues={snapshot.historical_analogues} />

      <WeekendEvidenceSummary summary={snapshot.evidence_summary} />
    </div>
  );
}
