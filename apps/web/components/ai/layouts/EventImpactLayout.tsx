"use client";

// event_impact — narrow contract (2026-09-22, approved after the
// policy_macro_impact and event_impact read-only audits). Sourced
// ENTIRELY from AEV2EventImpactAnswer (answerTypes.ts), itself built
// only from assemble_aev2()'s real event_impact field — never a plain
// SearchResult field. See answerTypes.ts's own module-boundary comment:
// no live HTTP path to this data exists yet, so this component is
// developed and tested against fixtures mirroring exactly what
// aev2/event_impact.py already produces server-side.
//
// Deliberately excludes every concept the approved narrow contract
// dropped: no transmission chain, no beneficiary/loser framing (only
// "Connected company"), no monitoring checklist, no Ripple graph, no
// Intelligence Graph propagation, no generic bull/bear case, no
// forecast language. Every one of these is structurally unreachable —
// AEV2EventImpactAnswer carries no `raw: SearchResult` and
// AEV2EventImpact itself has no field for any of them.
import { AIAnswerShell } from "../AIAnswerShell";
import type { AEV2EventImpactAnswer } from "../answerTypes";
import { formatShortDate } from "../answerTypes";
import { buildCitationIndex, buildEvidenceCoverage, CitationMarks, AEV2ConfidenceCard } from "../aev2Shared";

const WINDOW_LABEL: Record<string, string> = {
  next_session: "Next session",
  five_sessions: "5 sessions later",
};

export function EventImpactLayout({
  answer, onNewSearch, onRefine,
}: {
  answer: AEV2EventImpactAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}) {
  const { aev2, eventImpact: ei } = answer;
  const { rows: evidenceRows, refIndex } = buildCitationIndex(
    [{ label: "Summary", refs: ei.direct_conclusion.evidence_refs }],
    aev2.evidence,
  );
  const evidenceCoverage = buildEvidenceCoverage(aev2.evidence);

  return (
    <AIAnswerShell
      query={answer.query}
      uiMode="event_impact"
      sourceCount={evidenceRows.length}
      evidenceRows={evidenceRows}
      evidenceCoverage={evidenceCoverage}
      showConfidence={false}
      sidebarSnapshot={<AEV2ConfidenceCard confidence={aev2.confidence} />}
      onNewSearch={onNewSearch}
      onRefine={onRefine}
    >
      {/* 1. Evidence-based event summary — never labeled Buy/Sell/Hold/
          Verdict/Recommendation. */}
      <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Evidence-based event summary</p>
      <p className="text-[15px] leading-7 font-semibold text-text-primary">
        {ei.direct_conclusion.text}
        <CitationMarks refs={ei.direct_conclusion.evidence_refs} refIndex={refIndex} />
      </p>

      {/* 2. What happened — Event.title / Event.summary, both source-
          derived text, never Event.ai_summary and never a Development's
          own prompt text. */}
      <div className="mt-5">
        <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">What happened</p>
        <p className="text-[13px] font-semibold text-text-primary">{ei.event.title}</p>
        <p className="mt-1 text-[13px] leading-6 text-text-secondary">{ei.event.summary}</p>
        <p className="mt-1.5 text-[10px] text-text-muted">
          {formatShortDate(ei.event.published_at) ?? ei.event.published_at} · Source: {ei.event.source_name}
        </p>
        {ei.event.original_source_url ? (
          <a
            href={ei.event.original_source_url}
            className="mt-1 inline-block text-[11px] text-violet-500 hover:underline"
            rel="noopener noreferrer"
          >
            View original source
          </a>
        ) : (
          <p className="mt-1 text-[11px] text-text-muted">
            Original source link unavailable.{" "}
            <a href={ei.event.internal_url} className="text-violet-500 hover:underline">
              View the structured MarketRipple Event record.
            </a>
          </p>
        )}
      </div>

      {/* 3. Companies connected — neutral relationship language only,
          never "beneficiary"/"loser"/"affected company". */}
      {ei.linked_companies.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Companies connected</p>
          <ul className="space-y-1">
            {ei.linked_companies.map(c => (
              <li key={c.symbol} className="text-[13px] text-text-secondary">
                <span className="font-medium text-text-primary">{c.name}</span>{" "}
                <span className="text-text-muted">({c.symbol})</span> — Connected company
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 4. Sectors connected — optional, omitted entirely when empty
          rather than shown as a blank section. */}
      {ei.linked_sectors.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Sectors connected</p>
          <p className="text-[13px] text-text-secondary">
            {ei.linked_sectors.map(s => s.name).join(", ")}
          </p>
        </div>
      )}

      {/* 5. Observed price reactions — optional; always states an
          OBSERVED association over a named window, never a causal
          claim. Omitted entirely (not a placeholder) when empty — the
          real, current state of every response today, since the
          canonical pipeline carries no clean price observation yet
          (see aev2/event_impact.py's own docstring). */}
      {ei.observed_reactions.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Observed price reactions</p>
          <ul className="space-y-1.5">
            {ei.observed_reactions.map((r, i) => (
              <li key={i} className="text-[13px] text-text-secondary">
                <span className="font-medium text-text-primary">{r.company.name}</span> ({r.company.symbol}):{" "}
                {r.percent_change >= 0 ? "+" : ""}{r.percent_change}% observed {WINDOW_LABEL[r.window] ?? r.window}{" "}
                ({formatShortDate(r.start_date) ?? r.start_date} → {formatShortDate(r.end_date) ?? r.end_date})
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-[10px] text-text-muted">
            An observed association, not a causal claim — other factors may also have moved the price over this window.
          </p>
        </div>
      )}
    </AIAnswerShell>
  );
}
