"use client";

// direct_company_research — build order item 2 (2026-09-22 AI Answer UI
// work). Sourced ENTIRELY from AEV2DirectCompanyAnswer (answerTypes.ts),
// itself built only from assemble_aev2()'s real output plus a
// hand-authored fixture meta flag — never from a plain SearchResult
// field. See answerTypes.ts's own module-boundary comment for why: no
// live HTTP path to this data exists yet (AEV2_BUILD_COMPLETE is False),
// so this component is developed and tested against fixtures mirroring
// exactly what the backend already produces server-side, not wired into
// SearchResults until a dedicated activation commit.
//
// Every prohibited concept (investment_verdict, engine_verdict, rating,
// suitable_for, risk_level, top_picks, scenarios, a self-rated
// confidence) is structurally unreachable here, not just avoided by
// convention — AEV2DirectCompanyAnswer carries no `raw: SearchResult`
// and AEV2Response itself has no field for any of them (see
// aev2/assemble.py's own "Deliberately absent, by design" note).
import { AIAnswerShell } from "../AIAnswerShell";
import type { AEV2DirectCompanyAnswer } from "../answerTypes";
import { buildCitationIndex, buildEvidenceCoverage, CitationMarks, AEV2ConfidenceCard } from "../aev2Shared";
import { formatShortDate } from "../answerTypes";

const HORIZON_PHASE_LABEL: Record<string, string> = {
  immediate: "Immediate",
  medium_term: "Medium term",
  long_term: "Long term",
};

export function DirectCompanyResearchLayout({
  answer, onNewSearch, onRefine,
}: {
  answer: AEV2DirectCompanyAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}) {
  const { aev2, resolvedCompany } = answer;
  const { rows: evidenceRows, refIndex } = buildCitationIndex(
    [
      { label: "Summary", refs: aev2.direct_conclusion.evidence_refs },
      { label: "What happened", refs: aev2.what_happened.evidence_refs },
      { label: "Analysis", refs: aev2.why_it_matters.evidence_refs },
    ],
    aev2.evidence,
  );
  const evidenceCoverage = buildEvidenceCoverage(aev2.evidence);

  const priced = [...aev2.companies_affected.currently_higher, ...aev2.companies_affected.currently_lower]
    .find(c => c.symbol.toUpperCase() === resolvedCompany.symbol.toUpperCase());
  const isHigher = aev2.companies_affected.currently_higher.some(
    c => c.symbol.toUpperCase() === resolvedCompany.symbol.toUpperCase(),
  );

  const showWhyItMatters = !aev2.why_it_matters.is_fallback && !!aev2.why_it_matters.text;
  const horizonPhases = aev2.time_horizon.timeline_phases;
  const hasHorizonSection = !!aev2.time_horizon.primary_horizon || horizonPhases.length > 0;
  const risks = aev2.risks_and_invalidation.risks;
  const invalidatesIf = aev2.risks_and_invalidation.invalidates_if;
  const watchFor = aev2.risks_and_invalidation.watch_for;
  const hasRisksSection = risks.length > 0 || invalidatesIf.length > 0 || watchFor.length > 0;

  return (
    <AIAnswerShell
      query={answer.query}
      uiMode="direct_company_research"
      sourceCount={evidenceRows.length}
      evidenceRows={evidenceRows}
      evidenceCoverage={evidenceCoverage}
      showConfidence={false}
      sidebarSnapshot={<AEV2ConfidenceCard confidence={aev2.confidence} />}
      onNewSearch={onNewSearch}
      onRefine={onRefine}
    >
      {/* 1. Evidence-based research summary — never labeled Buy/Sell/
          Hold/Verdict/Recommendation; every factual sentence here is
          exactly assemble_aev2's own citation-validated text. */}
      <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Evidence-based research summary</p>
      <p className="text-[15px] leading-7 font-semibold text-text-primary">
        {aev2.direct_conclusion.text}
        <CitationMarks refs={aev2.direct_conclusion.evidence_refs} refIndex={refIndex} />
      </p>

      {/* 2. What happened — company-attributable developments only, via
          the same citation-validated field. */}
      {aev2.what_happened.summary && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">What happened</p>
          <p className="text-[13px] leading-6 text-text-secondary">
            {aev2.what_happened.summary}
            <CitationMarks refs={aev2.what_happened.evidence_refs} refIndex={refIndex} />
          </p>
        </div>
      )}

      {/* 3. Why it matters — clearly labeled as analysis, suppressed
          entirely on a validation fallback (is_fallback) rather than
          shown with a caveat. */}
      {showWhyItMatters && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Analysis — why it matters</p>
          <p className="text-[13px] leading-6 text-text-secondary">
            {aev2.why_it_matters.text}
            <CitationMarks refs={aev2.why_it_matters.evidence_refs} refIndex={refIndex} />
          </p>
        </div>
      )}

      {/* 4. Company impact / Price reaction — omitted honestly (not a
          placeholder) whenever this company's price fetch failed
          (build_price_movement_groups put it in omitted_unattributed).
          Never phrased as "benefit"/"exposure"/causal proof — a plain
          fact about where the price sits right now. */}
      {priced && (
        <div className="mt-5 rounded-[14px] border border-surface-border/8 bg-text-primary/[0.02] px-4 py-3">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Price reaction</p>
          <p className="text-[13px] text-text-secondary">
            <span className="font-semibold text-text-primary">{resolvedCompany.name}</span> ({resolvedCompany.symbol}) is
            currently trading {isHigher ? "higher" : "lower"} at {priced.price} ({priced.change}).
          </p>
          <p className="mt-1 text-[10px] text-text-muted">
            Fetched {formatShortDate(priced.fetched_at) ?? priced.fetched_at} · Source: Yahoo Finance
          </p>
        </div>
      )}

      {/* 5. Factors supporting the thesis — omitted entirely. AEV2's
          schema has no field for this today (no CoreAnswer source, per
          aev2/assemble.py's own docstring) — there is nothing here to
          render honestly, so nothing renders, rather than reusing
          why_it_matters or risks to manufacture a "supporting factors"
          list the backend never produced. */}

      {/* 6. Risks and invalidation — analysis, not facts; citations only
          where a factual premise exists (none of these 3 list fields
          carry their own evidence_refs in this schema — they inherit
          the same claim_refs already shown above, so no separate
          citation marks are added here to avoid implying a per-risk
          citation this data doesn't actually have). */}
      {hasRisksSection && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Risks and invalidation</p>
          {risks.length > 0 && (
            <ul className="list-disc pl-4 space-y-1">
              {risks.map((r, i) => (
                <li key={i} className="text-[13px] leading-6 text-text-secondary">{r}</li>
              ))}
            </ul>
          )}
          {invalidatesIf.length > 0 && (
            <div className="mt-2">
              <p className="text-[11px] font-semibold text-text-secondary">This view would be invalidated if:</p>
              <ul className="list-disc pl-4 space-y-1">
                {invalidatesIf.map((r, i) => (
                  <li key={i} className="text-[13px] leading-6 text-text-secondary">{r}</li>
                ))}
              </ul>
            </div>
          )}
          {watchFor.length > 0 && (
            <div className="mt-2">
              <p className="text-[11px] font-semibold text-text-secondary">Watch for:</p>
              <ul className="list-disc pl-4 space-y-1">
                {watchFor.map((r, i) => (
                  <li key={i} className="text-[13px] leading-6 text-text-secondary">{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 7. Time horizon — deterministic primary_horizon only; hidden
          (never "Not specified") when the backend has none. */}
      {hasHorizonSection && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Time horizon</p>
          {aev2.time_horizon.primary_horizon && (
            <p className="text-[13px] font-medium text-text-primary">{aev2.time_horizon.primary_horizon}</p>
          )}
          {horizonPhases.length > 0 && (
            <ul className="mt-1.5 space-y-1">
              {horizonPhases.map(p => (
                <li key={p.phase} className="text-[12.5px] text-text-secondary">
                  <span className="font-medium text-text-primary">{HORIZON_PHASE_LABEL[p.phase] ?? p.phase}: </span>
                  {p.text}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </AIAnswerShell>
  );
}
