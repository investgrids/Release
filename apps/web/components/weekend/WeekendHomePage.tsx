import { fetchWeekendIntelligence } from "@/lib/weekendIntelligence";
import { WeekendUnavailable } from "./WeekendUnavailable";
import { WeekendHero } from "./WeekendHero";
import { WeekendChanges } from "./WeekendChanges";
import { WeekendChangesSincePrior } from "./WeekendChangesSincePrior";
import { WeekendSectors } from "./WeekendSectors";
import { WeekendCompanies } from "./WeekendCompanies";
import { WeekendOpportunities } from "./WeekendOpportunities";
import { WeekendRisks } from "./WeekendRisks";
import { WeekendConfidenceWarnings } from "./WeekendConfidenceWarnings";
import { WeekendHistoricalContext } from "./WeekendHistoricalContext";
import { WeekendEvidenceSummary } from "./WeekendEvidenceSummary";

/**
 * The Weekend Intelligence homepage — brief §2/§4: a single, self-
 * contained variant rendered in place of the normal homepage, not
 * scattered `if weekend` branches through the existing one. One fetch
 * (GET /api/intelligence/weekend/current — the only Weekend
 * Intelligence data source this component or its children are allowed
 * to read), then presentation-only composition — no client-side
 * reranking, recalculation, or invented conclusions (brief §5/§33).
 *
 * Section order follows brief §7's stated priority: outlook+confidence
 * (hero) -> what changed -> sectors -> companies -> opportunities ->
 * risks -> confidence warnings -> historical context -> evidence
 * summary. Any section with no real data to show renders nothing
 * (brief §44: "does any card exist only because data was available?" —
 * every section component below already self-hides on empty input).
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
      <div className="space-y-5 py-6 pb-12">
        <div className="py-4">
          <WeekendUnavailable kind="insufficient_evidence" />
        </div>
        {snapshot.evidence_summary.total > 0 && <WeekendEvidenceSummary summary={snapshot.evidence_summary} />}
      </div>
    );
  }

  return (
    <div className="space-y-5 py-6 pb-12">
      <WeekendHero snapshot={snapshot} />

      <WeekendChanges items={snapshot.new_since_close} count={snapshot.new_since_close_count} />

      <WeekendChangesSincePrior changes={snapshot.changes_since_prior} version={snapshot.version} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <WeekendSectors sectors={snapshot.top_sectors} />
        <WeekendCompanies companies={snapshot.top_companies} />
      </div>

      <WeekendOpportunities opportunities={snapshot.opportunities} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <WeekendRisks risks={snapshot.market_risks} />
        <WeekendConfidenceWarnings warnings={snapshot.confidence_warnings} />
      </div>

      <WeekendHistoricalContext analogues={snapshot.historical_analogues} />

      <WeekendEvidenceSummary summary={snapshot.evidence_summary} />
    </div>
  );
}
